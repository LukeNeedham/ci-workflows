#!/usr/bin/env python3
"""Syncs the shared files of this repo into every app listed in apps.json, as one standing PR per app.

What is synced (see docs/sync.md):
  - the Claude skills of the app's stack, each mirrored to .claude/skills/<name>/
  - the callers of the app's stack in .github/workflows/, copied byte for byte from callers/ (they hold no
    settings, see docs/app-config.md)
  - a managed block in the app's CLAUDE.md
Which of these an app gets depends on its `stack` in apps.json, which every entry must have (STACKS).
It also reports (never writes) apps whose readme.yml, the data of their generated README.md, is missing or invalid.
Requires PyYAML.

For each app it clones the default branch, makes the changes on the branch `sync/ci-workflows`, and
force-pushes that branch and opens a PR for it, or updates the PR that is already open.

Needs PyYAML, PyNaCl (for the secret below) and the environment variable SYNC_TOKEN: a personal access token that may write contents, pull
requests and workflows on the apps.

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
from automerge import TITLE_TAG
from check_screenshot_package import setup_problems

TOOLS = Path(__file__).resolve().parent.parent
BRANCH = "sync/ci-workflows"
# The tag makes the PR merge itself in the app, once its checks have passed (automerge.py)
PR_TITLE = f"{TITLE_TAG} Sync from ci-workflows"

# The Actions secret of every app that holds the token which pushes the files CI generates
COMMIT_TOKEN_SECRET = "GENERATED_COMMIT_TOKEN"
# Every kmp app gets every caller. The release one fails with a clear message if the app is not set up for releases
CALLERS = ["trigger_on_pull_request.yml", "build_main.yml", "delete_prereleases.yml", "release.yml"]
NEXT_JS_CALLERS = ["web_pr.yml"]

# The stacks an app in apps.json can be built with, and what each one gets from the sync. There is no default: every
# entry of apps.json names its stack (docs/sync.md). `callers` is the folder of callers/ the stack's callers are in.
STACKS = {
    # Kotlin Multiplatform: an Android app that also builds for iOS and the web. The skill it reads first is
    # lukeneedham-conventions; the others are optional (networking-setup)
    "kmp": {"skills": ["lukeneedham-conventions", "networking-setup"], "callers": "", "caller_files": CALLERS},
    # A Next.js website: no Android app, no APK, no Gradle (docs/next-js-app.md)
    "next-js": {"skills": ["next-js-conventions"], "callers": "next-js", "caller_files": NEXT_JS_CALLERS},
}

BLOCK_BEGIN = "<!-- ci-workflows:begin (managed by LukeNeedham/ci-workflows, do not edit) -->"
BLOCK_END = "<!-- ci-workflows:end -->"
BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
# The instruction this block replaces, from when Claude was asked to copy the skill by hand: a bullet or a
# paragraph of its own, with the blank line after it
OLD_BULLET_RE = re.compile(r"^(?:- )?Before starting work, check that .*?docs/skill\.md`\.\n\n?", re.S | re.M)


# ---------------------------------------------------------------------------------------------------
# What to put in an app. Pure functions on files, so they can be tested without a network.
# ---------------------------------------------------------------------------------------------------

def stack_of(app):
    """The stack of the apps.json entry [app], which must name one: there is no default."""
    stack = app.get("stack")
    if stack not in STACKS:
        valid = ", ".join(f'"{s}"' for s in STACKS)
        raise ValueError(f'{app.get("repo", app)} has no valid "stack" in apps.json: it is {stack!r}, and it must be one of {valid}')
    return stack


def skill_names(stack, tools=TOOLS):
    """The skills the apps of [stack] get: the folders of skills/ that the stack lists and that have a SKILL.md."""
    wanted = STACKS[stack]["skills"]
    found = sorted(p.name for p in (tools / "skills").iterdir() if (p / "SKILL.md").is_file())
    missing = sorted(set(wanted) - set(found))
    if missing:
        raise ValueError(f"The stack {stack} lists skills that do not exist in skills/: {', '.join(missing)}")
    return sorted(wanted)


def callers_dir(stack, tools=TOOLS):
    return tools / "callers" / STACKS[stack]["callers"]


def sync_skills(app_dir, stack, tools=TOOLS):
    """Mirrors the skills of [stack] into the app. Returns the paths that changed."""
    changed = []
    for name in skill_names(stack, tools):
        source = tools / "skills" / name
        dest = app_dir / ".claude" / "skills" / name
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


def sync_callers(app_dir, stack, tools=TOOLS):
    """Copies the callers of [stack] from callers/, byte for byte. Returns changed paths."""
    workflows = app_dir / ".github" / "workflows"
    changed = []
    for name in STACKS[stack]["caller_files"]:
        content = (callers_dir(stack, tools) / name).read_bytes()
        target = workflows / name
        if not target.exists() or target.read_bytes() != content:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            changed.append(str(target.relative_to(app_dir)))
    return changed


def claude_block(stack):
    return {"kmp": kmp_claude_block, "next-js": next_js_claude_block}[stack]()


def next_js_claude_block():
    callers = "`, `".join(NEXT_JS_CALLERS)
    return (
        f"{BLOCK_BEGIN}\n"
        f"- `.claude/skills/` (`next-js-conventions`) and the callers `{callers}` in `.github/workflows/` are kept in sync from\n"
        f"  `LukeNeedham/ci-workflows` by CI, which keeps one PR titled \"Sync from ci-workflows\" open when they\n"
        f"  differ. Do not edit them here and do not copy them by hand: change them in ci-workflows. The callers\n"
        f"  hold no settings: every Next.js website is built the same way (see `docs/next-js-app.md` there).\n"
        f"- This is a website: it has no Android app and no APK. Every PR gets a preview deployment on Vercel, which CI\n"
        f"  checks and links in a PR comment. **Always give the user the preview URL when work on this site completes**:\n"
        f"  once CI's comment has it, paste it into the chat, as a link on a line of its own.\n"
        f"- **Always give the user the AppHub link when work on this site completes.** As soon as a PR is open,\n"
        f"  paste `📦 [Open in AppHub](https://www.lukeneedham.com/apphub/pr/<repo name>/<PR number>)` into the chat\n"
        f"  on a line of its own, never inside a sentence, and put the same line at the very top of the PR description.\n"
        f"- **`README.md` is generated by CI from `readme.yml`**: never edit `README.md`, edit `readme.yml` (write it once\n"
        f"  from `docs/readme-template-web.yml` in `LukeNeedham/ci-workflows` if it is missing) and keep it accurate. It is\n"
        f"  the format for websites, with no screenshots. `.prettierignore` leaves `/README.md` out. The skill has the details.\n"
        f"- **The Stop hook's git warnings** (\"unpushed commit(s)\", or commits \"Unverified\" with a `github-actions[bot]` email):\n"
        f"  run `git fetch origin` and check again, and do nothing else. CI can push commits of its own to a PR branch after you\n"
        f"  push, so your local copy of the remote branch is out of date and Git thinks commits are local only. Never amend,\n"
        f"  rebase or force-push to silence the hook, never edit the hook, and do not write about it at length.\n"
        f"{BLOCK_END}\n"
    )


def kmp_claude_block():
    callers = "`, `".join(CALLERS)
    return (
        f"{BLOCK_BEGIN}\n"
        f"- `.claude/skills/` (`lukeneedham-conventions` and the optional ones, such as `networking-setup`) and the callers `{callers}` in `.github/workflows/` are kept in sync from\n"
        f"  `LukeNeedham/ci-workflows` by CI, which keeps one PR titled \"Sync from ci-workflows\" open when they\n"
        f"  differ. Do not edit them here and do not copy them by hand: change them in ci-workflows. The callers\n"
        f"  hold no settings: every app is built the same way (see `docs/app-config.md` there).\n"
        f"- **Always give the user the AppHub link when work on this app completes.** As soon as a PR is open,\n"
        f"  paste `📦 [Open in AppHub](https://www.lukeneedham.com/apphub/pr/<repo name>/<PR number>)` into the chat\n"
        f"  on a line of its own, never inside a sentence (CI posts the same link as a PR comment), and put the same\n"
        f"  line at the very top of the PR description. Do not wait for the build and do not paste the APK link instead.\n"
        f"- **`README.md` is generated by CI from `readme.yml`**: never edit `README.md`, edit `readme.yml` (write it once\n"
        f"  from `docs/readme-template.yml` in `LukeNeedham/ci-workflows` if it is missing) and keep it accurate. Every app\n"
        f"  has a `LICENSE` file. The skill has the details.\n"
        f"- **Every page is an `XPage` plus a stateless `internal` `XPageContent`, always** (`XPage` gets its\n"
        f"  `XViewModel`; its route is always `Route.X`, a member of the one `sealed interface Route`; each of `XPage`,\n"
        f"  `XPageContent`, `XViewModel` and `XUiState` is in its own file; never `XScreen`). The README screenshots are private\n"
        f"  `@Preview`s in the package `screenshot` (in `src/debug`, or `src/androidDebug` in a Kotlin Multiplatform app), each owning its mock data (a page can have several,\n"
        f"  or none; nothing is shared); CI renders them into `docs/screenshots/`, never by hand. The skill has the details.\n"
        f"- **The Stop hook's git warnings** (\"unpushed commit(s)\", or commits \"Unverified\" with a `github-actions[bot]` email):\n"
        f"  run `git fetch origin` and check again, and do nothing else. CI pushes commits of its own to a PR branch after you\n"
        f"  push (the README, the screenshots), so your local copy of the remote branch is out of date and Git thinks commits are local only. Never amend,\n"
        f"  rebase or force-push to silence the hook, never edit the hook, and do not write about it at length.\n"
        f"{BLOCK_END}\n"
    )


def sync_claude_md(app_dir, stack):
    """Puts the managed block into the app's CLAUDE.md and removes the old copy-it-by-hand instruction. Returns changed paths."""
    path = app_dir / "CLAUDE.md"
    block = claude_block(stack)
    text = path.read_text() if path.is_file() else "# Instructions for Claude\n\n"
    if BLOCK_RE.search(text):
        # The instruction contradicts the block, so it goes even when the block is already there
        new = OLD_BULLET_RE.sub("", BLOCK_RE.sub(lambda _: block, text, count=1))
    elif OLD_BULLET_RE.search(text):
        new = OLD_BULLET_RE.sub(lambda _: block, text, count=1)
    else:
        new = text.rstrip("\n") + "\n\n" + block if text.strip() else block
    if new == text and path.is_file():
        return []
    path.write_text(new)
    return ["CLAUDE.md"]


def sync_app(app_dir, stack, tools=TOOLS):
    """Applies everything of [stack] to the checkout [app_dir]. Returns the paths that changed."""
    return sync_skills(app_dir, stack, tools) + sync_callers(app_dir, stack, tools) + sync_claude_md(app_dir, stack)


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


def encrypt_secret(public_key, value):
    """[value] sealed with [public_key] (base64, from GitHub), as GitHub wants a secret: a libsodium sealed box."""
    from nacl import encoding, public  # only needed here, and only when a secret is set

    key = public.PublicKey(public_key.encode(), encoding.Base64Encoder())
    return base64.b64encode(public.SealedBox(key).encrypt(value.encode())).decode()


def set_app_secret(token, repo, name, value):
    """Writes the Actions secret [name] of [repo], so that the workflows of the app can read it."""
    key = api(token, "GET", f"/repos/{repo}/actions/secrets/public-key")
    api(token, "PUT", f"/repos/{repo}/actions/secrets/{name}", {
        "encrypted_value": encrypt_secret(key["key"], value),
        "key_id": key["key_id"],
    })


def pr_body(changed, stack):
    files = "\n".join(f"- `{path}`" for path in sorted(changed))
    standard = "docs/next-js-app.md" if stack == "next-js" else "docs/app-config.md"
    return (
        "Keeps this repo in line with [`LukeNeedham/ci-workflows`](https://github.com/LukeNeedham/ci-workflows): "
        "the Claude skill, the workflow callers and the managed block in `CLAUDE.md`.\n\n"
        f"Changed:\n{files}\n\n"
        f"The callers hold no settings: every {stack} project is built the same way (`{standard}` in ci-workflows). This PR is "
        f"opened and updated by ci-workflows' `sync_apps.yml`; it stays one PR (`{BRANCH}`) until it is merged.\n"
    )


def readme_note(app_dir, stack="kmp"):
    """A one-line report on the app's readme.yml. Only reports: readme.yml is handwritten and CI renders README.md."""
    try:
        data = generate_readme.load(app_dir)
    except yaml.YAMLError:
        return "readme.yml is not valid YAML"
    if data is None:
        return "readme.yml is missing"
    # The README and the screenshot rules apply to an app from its readme.yml on: what it still lacks is its to-do list
    # (a website has no screenshot package to check)
    found = list(dict.fromkeys([*generate_readme.problems(data, app_dir, stack), *(setup_problems(app_dir) if stack == "kmp" else [])]))
    return "readme.yml is invalid: " + "; ".join(found) if found else ""


def sync_secret(app, token, commit_token, dry_run):
    """Gives the app the token that pushes the files CI generates (GENERATED_COMMIT_TOKEN, see docs/app-config.md).
    Returns a note for the result line, empty when there is nothing to say."""
    if not commit_token or dry_run:
        return ""
    set_app_secret(token, app["repo"], COMMIT_TOKEN_SECRET, commit_token)
    return f" (secret {COMMIT_TOKEN_SECRET} set)"


def sync_remote(app, token, dry_run, work, commit_token=None):
    """Syncs one app on GitHub. Returns a one-line result."""
    secret = sync_secret(app, token, commit_token, dry_run)
    repo = app["repo"]
    base = os.environ.get("SYNC_GIT_BASE", "https://github.com")
    checkout = Path(work) / repo.replace("/", "_")
    git(work, "clone", "--quiet", "--depth", "1", f"{base}/{repo}.git", str(checkout), token=token)
    git(checkout, "checkout", "--quiet", "-B", BRANCH)
    stack = stack_of(app)
    changed = sync_app(checkout, stack)
    # The screenshot package is the Kotlin apps' rule; both stacks have a readme.yml, in their own format
    note = readme_note(checkout, stack)
    note = f" ({note})" if note else ""
    if not changed:
        return f"{repo}: up to date{secret}{note}"
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
        api(token, "PATCH", f"/repos/{repo}/pulls/{open_prs[0]['number']}", {"title": PR_TITLE, "body": pr_body(changed, stack)})
        return f"{repo}: updated {open_prs[0]['html_url']}{secret}{note}"
    created = api(token, "POST", f"/repos/{repo}/pulls", {
        "title": PR_TITLE,
        "head": BRANCH,
        "base": default,
        "body": pr_body(changed, stack),
    })
    return f"{repo}: opened {created['html_url']}{secret}{note}"


def load_apps(path=TOOLS / "apps.json"):
    """The entries of apps.json. Every one must name a valid stack, and nothing is synced until they all do: a typo in
    one entry must not leave the others half-synced, or give an app the callers of the wrong stack."""
    apps = json.loads(path.read_text())
    errors = []
    for app in apps:
        try:
            stack_of(app)
        except ValueError as e:
            errors.append(str(e))
    if errors:
        sys.exit("apps.json is invalid:\n" + "\n".join(f"  - {e}" for e in errors))
    return apps


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apps", help="comma-separated names or repos to sync (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, push nothing")
    args = parser.parse_args()

    token = os.environ.get("SYNC_TOKEN")
    if not token and not args.dry_run:
        print("::error::The secret SYNC_TOKEN is not set. See docs/sync.md.")
        sys.exit(1)
    if token:
        print(f"::add-mask::{token}")
    commit_token = os.environ.get("GENERATED_COMMIT_TOKEN")
    if commit_token:
        print(f"::add-mask::{commit_token}")
    else:
        print("::notice::GENERATED_COMMIT_TOKEN is not set, so the apps get no secret for the generated commits. See docs/sync.md.")
    apps = load_apps()
    if args.apps:
        wanted = {a.strip() for a in args.apps.split(",")}
        apps = [a for a in apps if a["name"] in wanted or a["repo"] in wanted]
        if not apps:
            sys.exit(f"No app in apps.json matches {args.apps}")

    failures = 0
    lines = []
    work = tempfile.mkdtemp(prefix="sync_apps_")
    try:
        for app in apps:
            try:
                lines.append(sync_remote(app, token, args.dry_run, work, commit_token))
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
