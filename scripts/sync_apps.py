#!/usr/bin/env python3
"""Syncs the shared files of this repo into every app listed in apps.json, as one standing PR per app.

What is synced (see docs/sync.md):
  - the Claude skill, mirrored to .claude/skills/lukeneedham-conventions/
  - the callers in .github/workflows/, copied byte for byte from examples/ (all of them, to every app; they
    hold no settings, see docs/app-config.md)
  - a managed block in the app's CLAUDE.md

For each app it clones the default branch, makes the changes on the branch `sync/ci-workflows`, and
force-pushes that branch and opens a PR for it, or updates the PR that is already open.

Needs the environment variable SYNC_TOKEN: a personal access token that may write contents, pull
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

TOOLS = Path(__file__).resolve().parent.parent
SKILL = "lukeneedham-conventions"
BRANCH = "sync/ci-workflows"
# Every app gets every caller. The release one fails with a clear message if the app is not set up for releases
CALLERS = ["trigger_on_pull_request.yml", "build_main.yml", "delete_prereleases.yml", "release.yml"]

BLOCK_BEGIN = "<!-- ci-workflows:begin (managed by LukeNeedham/ci-workflows, do not edit) -->"
BLOCK_END = "<!-- ci-workflows:end -->"
BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
# The line this block replaces, from when Claude was asked to copy the skill by hand
OLD_BULLET_RE = re.compile(r"^- Before starting work, check that .*?docs/skill\.md`\.\n", re.S | re.M)


# ---------------------------------------------------------------------------------------------------
# What to put in an app. Pure functions on files, so they can be tested without a network.
# ---------------------------------------------------------------------------------------------------

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


def sync_callers(app_dir, tools=TOOLS):
    """Copies the callers from examples/, byte for byte. Returns changed paths."""
    workflows = app_dir / ".github" / "workflows"
    changed = []
    for name in CALLERS:
        content = (tools / "examples" / name).read_bytes()
        target = workflows / name
        if not target.exists() or target.read_bytes() != content:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            changed.append(str(target.relative_to(app_dir)))
    return changed


def claude_block():
    callers = "`, `".join(CALLERS)
    return (
        f"{BLOCK_BEGIN}\n"
        f"- `.claude/skills/{SKILL}` and the callers `{callers}` in `.github/workflows/` are kept in sync from\n"
        f"  `LukeNeedham/ci-workflows` by CI, which keeps one PR titled \"Sync from ci-workflows\" open when they\n"
        f"  differ. Do not edit them here and do not copy them by hand: change them in ci-workflows. The callers\n"
        f"  hold no settings: every app is built the same way (see `docs/app-config.md` there).\n"
        f"- **Always give the user the AppHub link when work on this app completes.** As soon as a PR is open,\n"
        f"  paste `https://www.lukeneedham.com/apphub/pr/<repo name>/<PR number>` into the chat (CI posts the\n"
        f"  same link as a PR comment). Do not wait for the build and do not paste the APK link instead.\n"
        f"{BLOCK_END}\n"
    )


def sync_claude_md(app_dir):
    """Puts the managed block into the app's CLAUDE.md, replacing the old copy-it-by-hand line. Returns changed paths."""
    path = app_dir / "CLAUDE.md"
    block = claude_block()
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


def sync_app(app_dir, tools=TOOLS):
    """Applies everything to the checkout [app_dir]. Returns the paths that changed."""
    return sync_skill(app_dir, tools) + sync_callers(app_dir, tools) + sync_claude_md(app_dir)


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
        "The callers hold no settings: every app is built the same way (`docs/app-config.md` in ci-workflows). This PR is "
        f"opened and updated by ci-workflows' `sync_apps.yml`; it stays one PR (`{BRANCH}`) until it is merged.\n"
    )


def sync_remote(app, token, dry_run, work):
    """Syncs one app on GitHub. Returns a one-line result."""
    repo = app["repo"]
    base = os.environ.get("SYNC_GIT_BASE", "https://github.com")
    checkout = Path(work) / repo.replace("/", "_")
    git(work, "clone", "--quiet", "--depth", "1", f"{base}/{repo}.git", str(checkout), token=token)
    git(checkout, "checkout", "--quiet", "-B", BRANCH)
    changed = sync_app(checkout)
    if not changed:
        return f"{repo}: up to date"
    if dry_run:
        git(checkout, "add", "-A")
        return f"{repo}: would change {len(changed)} files\n" + git(checkout, "diff", "--cached", "--stat")
    git(checkout, "add", "-A")
    git(checkout, "commit", "--quiet", "-m", "Sync from ci-workflows")
    git(checkout, "push", "--quiet", "--force", "origin", BRANCH, token=token)
    default = api(token, "GET", f"/repos/{repo}")["default_branch"]
    owner = repo.split("/")[0]
    open_prs = api(token, "GET", f"/repos/{repo}/pulls?state=open&head={owner}:{BRANCH}")
    if open_prs:
        api(token, "PATCH", f"/repos/{repo}/pulls/{open_prs[0]['number']}", {"body": pr_body(changed)})
        return f"{repo}: updated {open_prs[0]['html_url']}"
    created = api(token, "POST", f"/repos/{repo}/pulls", {
        "title": "Sync from ci-workflows",
        "head": BRANCH,
        "base": default,
        "body": pr_body(changed),
    })
    return f"{repo}: opened {created['html_url']}"


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
