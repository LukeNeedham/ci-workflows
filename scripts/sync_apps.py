#!/usr/bin/env python3
"""Syncs the shared files of this repo into every app listed in apps.json, as one standing PR per app.

What is synced (see docs/sync.md):
  - the Claude skill, mirrored to .claude/skills/lukeneedham-conventions/
  - the callers in .github/workflows/, rendered from examples/ with the app's own settings
  - a managed block in the app's CLAUDE.md
It also reports (never writes) apps whose readme.yml, the data of their generated README.md, is missing or invalid.
Requires PyYAML.

For each app it clones the default branch, makes the changes on the branch `sync/ci-workflows`, and
force-pushes that branch and opens a PR for it, or updates the PR that is already open.

Needs PyYAML and the environment variable SYNC_TOKEN: a personal access token that may write contents, pull
requests and workflows on the apps. Only the standard library is used.

    python3 scripts/sync_apps.py                   sync every app
    python3 scripts/sync_apps.py --apps AppHub     only these (by name or repo)
    python3 scripts/sync_apps.py --dry-run         clone and show the changes, push nothing
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_readme
import yaml

TOOLS = Path(__file__).resolve().parent.parent
SKILL = "lukeneedham-conventions"
BRANCH = "sync/ci-workflows"
DEFAULT_CALLERS = ["trigger_on_pull_request.yml", "build_main.yml", "delete_prereleases.yml"]
DEFAULT_APK_PATH = "app/build/outputs/apk/debug/app-debug.apk"

# The settings of a caller that belong to the app. Everything else in a caller is shared.
INPUT_KEYS = ["apk-path", "gradle-task", "java-version", "java-distribution", "timezone", "comment-header"]

BLOCK_BEGIN = "<!-- ci-workflows:begin (managed by LukeNeedham/ci-workflows, do not edit) -->"
BLOCK_END = "<!-- ci-workflows:end -->"
BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
# The line this block replaces, from when Claude was asked to copy the skill by hand
OLD_BULLET_RE = re.compile(r"^- Before starting work, check that .*?docs/skill\.md`\.\n", re.S | re.M)


# ---------------------------------------------------------------------------------------------------
# What to put in an app. Pure functions on files, so they can be tested without a network.
# ---------------------------------------------------------------------------------------------------

def read_inputs(text):
    """The uncommented `key: value` settings in the `with:` block of a caller, and its `branches:` list."""
    inputs = {}
    branches = []
    in_with = False
    in_branches = False
    for line in text.splitlines():
        if re.match(r"^\s*with:\s*$", line):
            in_with = True
        elif re.match(r"^\s*branches:\s*$", line):
            in_branches = True
        elif in_branches:
            item = re.match(r"^\s+-\s+(\S+)", line)
            if item:
                branches.append(item.group(1))
            else:
                in_branches = False
        if in_with:
            match = re.match(r"^\s+([a-z-]+):\s*(.*?)\s*(\s#.*)?$", line)
            if match and match.group(1) in INPUT_KEYS:
                inputs[match.group(1)] = match.group(2)
    return inputs, branches


def render_caller(template, inputs, branches):
    """[template] with the app's [inputs] and [branches] in place of the template's own."""
    out = []
    in_with = False
    in_branches = False
    first_branch = True
    for line in template.splitlines():
        if re.match(r"^\s*with:\s*$", line):
            in_with = True
        if branches and re.match(r"^\s*branches:\s*$", line):
            in_branches, first_branch = True, True
        elif in_branches:
            item = re.match(r"^(\s+)-\s+\S+(.*)$", line)
            if item:
                if first_branch:
                    # The template's comment stays with the first branch
                    out.extend(f"{item.group(1)}- {name}{item.group(2) if i == 0 else ''}" for i, name in enumerate(branches))
                    first_branch = False
                continue
            in_branches = False
        if in_with:
            for key, value in inputs.items():
                match = re.match(rf"^(\s*)(#\s*)?{re.escape(key)}:\s*([^#\n]*?)(\s+#.*)?$", line)
                if match:
                    if match.group(3).strip() != value:
                        line = f"{match.group(1)}{key}: {value}{match.group(4) or ''}"
                    break
        out.append(line)
    return "\n".join(out) + "\n"


def sync_skill(app_dir, tools=TOOLS):
    """Mirrors the skill into the app. Returns the paths that changed."""
    source = tools / "skills" / SKILL
    dest = app_dir / ".claude" / "skills" / SKILL
    changed = []
    wanted = {p.relative_to(source) for p in source.rglob("*") if p.is_file()}
    if dest.exists():
        for existing in sorted(p for p in dest.rglob("*") if p.is_file()):
            if existing.relative_to(dest) not in wanted:
                existing.unlink()
                changed.append(str(existing.relative_to(app_dir)))
    for relative in sorted(wanted):
        target = dest / relative
        content = (source / relative).read_bytes()
        if not target.exists() or target.read_bytes() != content:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            changed.append(str(target.relative_to(app_dir)))
    return changed


def sync_callers(app, app_dir, tools=TOOLS):
    """Renders the app's callers from examples/, keeping the app's own settings. Returns changed paths."""
    names = app.get("callers", DEFAULT_CALLERS)
    workflows = app_dir / ".github" / "workflows"
    existing = {}
    branches = []
    for name in DEFAULT_CALLERS + [n for n in names if n not in DEFAULT_CALLERS]:
        path = workflows / name
        if path.is_file():
            found, found_branches = read_inputs(path.read_text())
            for key, value in found.items():
                existing.setdefault(key, value)
            branches = branches or found_branches
    inputs = {**existing, **{k: str(v) for k, v in app.get("inputs", {}).items()}}
    inputs.setdefault("comment-header", app["repo"].split("/")[1].lower() + "-app-link")
    changed = []
    for name in names:
        template = (tools / "examples" / name).read_text()
        rendered = render_caller(template, inputs, app.get("branches") or branches)
        target = workflows / name
        if not target.exists() or target.read_text() != rendered:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered)
            changed.append(str(target.relative_to(app_dir)))
    return changed


def claude_block(app):
    parts = []
    if app.get("skill", True):
        parts.append(f"`.claude/skills/{SKILL}`")
    if app.get("callers", DEFAULT_CALLERS):
        parts.append("the callers `" + "`, `".join(app.get("callers", DEFAULT_CALLERS)) + "` in `.github/workflows/`")
    what = " and ".join(parts)
    return (
        f"{BLOCK_BEGIN}\n"
        f"- {what[0].upper() + what[1:]} are kept in sync from `LukeNeedham/ci-workflows` by CI, which\n"
        f"  keeps one PR titled \"Sync from ci-workflows\" open when they differ. Do not edit them here and do\n"
        f"  not copy them by hand: change them in ci-workflows (settings of a caller, such as `apk-path`, are\n"
        f"  the exception and stay as they are).\n"
        f"- **Always give the user the AppHub link when work on this app completes.** As soon as a PR is open,\n"
        f"  paste `https://www.lukeneedham.com/apphub/pr/<repo name>/<PR number>` into the chat (CI posts the\n"
        f"  same link as a PR comment). Do not wait for the build and do not paste the APK link instead.\n"
        f"- **`README.md` is generated by CI from `readme.yml`**, in the standard layout of `docs/readme.md` in\n"
        f"  `LukeNeedham/ci-workflows`. Never edit `README.md`: edit `readme.yml` (write it by hand; skeleton in\n"
        f"  `docs/readme-template.yml`), and keep it accurate when the app changes. If `readme.yml` is missing,\n"
        f"  write it once from the template. The PR build commits the regenerated `README.md` to the PR branch.\n"
        f"- **Every page is an `XPage` (gets the ViewModel, no preview) plus a stateless `XPageContent` with an\n"
        f"  `XPageContentPreview`.** CI renders the README screenshots from those previews into `docs/screenshots/`\n"
        f"  (`docs/screenshots.md` in `LukeNeedham/ci-workflows`); never take or edit them by hand.\n"
        f"{BLOCK_END}\n"
    )


def sync_claude_md(app, app_dir):
    """Puts the managed block into the app's CLAUDE.md, replacing the old copy-it-by-hand line. Returns changed paths."""
    path = app_dir / "CLAUDE.md"
    block = claude_block(app)
    text = path.read_text() if path.is_file() else "# Instructions for Claude\n\n"
    if BLOCK_RE.search(text):
        new = BLOCK_RE.sub(lambda _: block, text, count=1)
    elif OLD_BULLET_RE.search(text):
        new = OLD_BULLET_RE.sub(lambda _: block, text, count=1)
    else:
        new = text.rstrip("\n") + "\n\n" + block if text.strip() else block
    if new == text and path.is_file():
        return []
    path.write_text(new)
    return ["CLAUDE.md"]


def sync_app(app, app_dir, tools=TOOLS):
    """Applies everything to the checkout [app_dir]. Returns the paths that changed."""
    changed = []
    if app.get("skill", True):
        changed += sync_skill(app_dir, tools)
    if app.get("callers", DEFAULT_CALLERS):
        changed += sync_callers(app, app_dir, tools)
    if app.get("skill", True) or app.get("callers", DEFAULT_CALLERS):
        changed += sync_claude_md(app, app_dir)
    return changed


# ---------------------------------------------------------------------------------------------------
# Git and GitHub
# ---------------------------------------------------------------------------------------------------

def git(directory, *args, token=None, check=True):
    command = ["git"]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]
    command += ["-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]
    result = subprocess.run(command + list(args), cwd=directory, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip().replace(token or chr(0), '***')}")
    return result.stdout


def api(token, method, path, body=None):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} returned {e.code}: {e.read().decode()[:300]}") from None


def pr_body(changed):
    files = "\n".join(f"- `{path}`" for path in sorted(changed))
    return (
        "Keeps this repo in line with [`LukeNeedham/ci-workflows`](https://github.com/LukeNeedham/ci-workflows): "
        "the Claude skill, the workflow callers and the managed block in `CLAUDE.md`.\n\n"
        f"Changed:\n{files}\n\n"
        "Settings of a caller (`apk-path`, `comment-header` and so on) are kept as they are here. This PR is "
        f"opened and updated by ci-workflows' `sync_apps.yml`; it stays one PR (`{BRANCH}`) until it is merged.\n"
    )


def readme_note(app_dir):
    """A one-line report on the app's readme.yml. Only reports: readme.yml is handwritten and CI renders README.md."""
    try:
        data = generate_readme.load(app_dir)
    except yaml.YAMLError:
        return "readme.yml is not valid YAML"
    if data is None:
        return "readme.yml is missing"
    found = generate_readme.problems(data, generate_readme.screenshot_files(app_dir))
    return "readme.yml is invalid: " + "; ".join(found) if found else ""


def sync_remote(app, token, dry_run, work):
    """Syncs one app on GitHub. Returns a one-line result."""
    repo = app["repo"]
    base = os.environ.get("SYNC_GIT_BASE", "https://github.com")
    checkout = Path(work) / repo.replace("/", "_")
    git(work, "clone", "--quiet", "--depth", "1", f"{base}/{repo}.git", str(checkout), token=token)
    git(checkout, "checkout", "--quiet", "-B", BRANCH)
    changed = sync_app(app, checkout)
    note = readme_note(checkout)
    note = f" ({note})" if note else ""
    if not changed:
        return f"{repo}: up to date{note}"
    if dry_run:
        git(checkout, "add", "-A")
        return f"{repo}: would change {len(changed)} files{note}\n" + git(checkout, "diff", "--cached", "--stat")
    git(checkout, "add", "-A")
    git(checkout, "commit", "--quiet", "-m", "Sync from ci-workflows")
    git(checkout, "push", "--quiet", "--force", "origin", BRANCH, token=token)
    default = api(token, "GET", f"/repos/{repo}")["default_branch"]
    owner = repo.split("/")[0]
    open_prs = api(token, "GET", f"/repos/{repo}/pulls?state=open&head={owner}:{BRANCH}")
    if open_prs:
        api(token, "PATCH", f"/repos/{repo}/pulls/{open_prs[0]['number']}", {"body": pr_body(changed)})
        return f"{repo}: updated {open_prs[0]['html_url']}{note}"
    created = api(token, "POST", f"/repos/{repo}/pulls", {
        "title": "Sync from ci-workflows",
        "head": BRANCH,
        "base": default,
        "body": pr_body(changed),
    })
    return f"{repo}: opened {created['html_url']}{note}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apps", help="comma-separated names or repos to sync (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, push nothing")
    args = parser.parse_args()

    token = os.environ.get("SYNC_TOKEN")
    if not token and not args.dry_run:
        sys.exit("SYNC_TOKEN is not set. See docs/sync.md for the token it needs.")
    apps = json.loads((TOOLS / "apps.json").read_text())
    if args.apps:
        wanted = {a.strip().lower() for a in args.apps.split(",")}
        apps = [a for a in apps if a["name"].lower() in wanted or a["repo"].lower() in wanted]
        if not apps:
            sys.exit(f"No app in apps.json matches {args.apps}")

    failures = 0
    lines = []
    work = tempfile.mkdtemp(prefix="sync_apps_")
    try:
        for app in apps:
            try:
                lines.append(sync_remote(app, token, args.dry_run, work))
            except Exception as e:  # one broken app must not stop the others
                failures += 1
                lines.append(f"{app['repo']}: FAILED {e}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Sync from ci-workflows\n\n" + "\n".join(f"- {l.splitlines()[0]}" for l in lines) + "\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
