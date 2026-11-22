#!/usr/bin/env python3
"""Creates a new app repo and sets it up, with no LLM: the repo, its first files, the secret and the entry in apps.json.

What it does, in this order (see docs/create-app.md):
  1. creates the repo LukeNeedham/<name> with a README, so that `main` exists (and renames the default branch to `main`
     if the account's default is another)
  2. pushes the first commit to `main`: the first sync (the skill, the callers and the `CLAUDE.md` block, exactly as
     sync_apps.py makes them) and a project that builds: the Gradle wrapper, `settings.gradle.kts`, `.gitignore`,
     `LICENSE`, the committed `app/debug.keystore`, and the app of templates/new-app: Kotlin Multiplatform with the Android
     target only (the dependencies of the architecture, the app shell, the theme and a settings page that opens the debug pages
     in `commonMain`; `App`, `MainActivity` and the manifest in `androidMain`). The push starts the main build, which is the
     first check that the template still builds
  3. writes the Actions secret GENERATED_COMMIT_TOKEN into the repo
  3b. a next-js website only: sets it up on Vercel (vercel_setup.py): the project, connected to the repo, and Deployment Protection
     off for previews. Skipped, and said so, when there is no VERCEL_TOKEN
  4. adds the app to apps.json of this repo, with a commit to `main`. This is last, so that the sync it starts finds
     the app up to date and opens no PR

What step 2 pushes depends on the --stack (docs/create-app.md): `kmp` is the Android app above; `next-js` is the first sync of that
stack and a minimal Next.js website (templates/next-js, with yarn.lock made on the spot).

Every step can be repeated: with --resume an existing repo is carried on with, and a step that is done is skipped.

Needs PyYAML, PyNaCl (for the secret) and keytool (any JDK). Environment variables:
  NEW_APP_TOKEN          optional: may create repos for the account (a classic token with the scope `repo`, or a fine-grained one
                         with Repository creation or Administration, write). A caller that creates the repo itself, with its
                         own token, does not need it: the workflow is then run with --resume
  SYNC_TOKEN             the token of sync_apps.py (contents, workflows and secrets of the apps; contents of this repo)
  GENERATED_COMMIT_TOKEN the secret that every app holds (docs/sync.md)
  VERCEL_TOKEN           optional: a Vercel token, to set a website up on Vercel (docs/next-js-app.md). VERCEL_TEAM_ID is the team, if any

    python3 scripts/new_app.py LyricTutor --stack kmp        create the app LukeNeedham/LyricTutor
    python3 scripts/new_app.py MySite --stack next-js        create a Next.js website
    python3 scripts/new_app.py LyricTutor --stack kmp --private  as a private repo
    python3 scripts/new_app.py LyricTutor --stack kmp --resume   carry on with a repo that exists
    python3 scripts/new_app.py LyricTutor --stack kmp --dry-run  only check the name and show what would be done
"""

import argparse
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_readme
import sync_apps
import vercel_setup

TOOLS = sync_apps.TOOLS
OWNER = "LukeNeedham"
COMMON_REPO = f"{OWNER}/ci-workflows"
APPS_FILE = "apps.json"
DEFAULT_BRANCH = "main"
PACKAGE_PREFIX = "com.lukeneedham"
COMMIT_MESSAGE = "Set up the app from ci-workflows"

# The app of a new project: files with the tokens below, in the paths and in the text. `.tmpl` is taken off the name
TEMPLATE_DIRS = {"kmp": ("templates", "new-app"), "next-js": ("templates", "next-js")}
TEMPLATE_SUFFIX = ".tmpl"
TOKEN_RE = re.compile(r"__[A-Z][A-Z_]*__")
COMMON_TAG_RE = re.compile(r"^common-(\d+)\.(\d+)\.(\d+)$")
# The library lives in its own Maven repository (docs/using-the-library.md), asked only for its own group
MAVEN_REPOSITORY = '''        maven("https://lukeneedham.github.io/ci-workflows/maven") {
            content { includeGroup("com.lukeneedham") }
        }
'''

# Letters, digits, hyphens and underscores, starting with a letter: a name GitHub takes, that `com.lukeneedham.<name>`
# can be made from (the package keeps its letters and digits)
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*")
MIN_NAME, MAX_NAME = 2, 50

# The Gradle wrapper, copied from this repo (docs/new-app.md, step 1)
WRAPPER_FILES = ["gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties"]
# docs/new-app.md, step 1: `*.keystore` is not ignored, as the debug keystore is committed
GITIGNORE = ".gradle/\nbuild/\n.kotlin/\nlocal.properties\n.idea/\n"
# What a Next.js website does not commit, as in PersonalWebsite
NEXT_JS_GITIGNORE = (
    "/node_modules\n/.pnp\n.pnp.js\n/coverage\n/.next/\n/out/\n/build\n.DS_Store\n*.pem\n"
    "npm-debug.log*\nyarn-debug.log*\nyarn-error.log*\n.env*.local\n.vercel\n*.tsbuildinfo\nnext-env.d.ts\n/src/generated\n.idea/\n"
)


# ---------------------------------------------------------------------------------------------------
# Pure functions: names, apps.json and the files of the scaffold. Tested without a network.
# ---------------------------------------------------------------------------------------------------

def check_name(name):
    """Raises ValueError saying what is wrong with [name], or returns it."""
    if not MIN_NAME <= len(name) <= MAX_NAME:
        raise ValueError(f"The name must be {MIN_NAME} to {MAX_NAME} characters long")
    if not NAME_RE.fullmatch(name):  # fullmatch: `$` would let a trailing newline through
        raise ValueError(
            "The name may only have letters, digits, hyphens and underscores, must start with a letter and must not end "
            "or double up on a hyphen or underscore"
        )
    return name


def check_stack(stack):
    """Raises ValueError unless [stack] is one the sync knows: there is no default, the caller says which kind of project it is."""
    if stack not in sync_apps.STACKS:
        raise ValueError(f"The stack must be one of {', '.join(sync_apps.STACKS)}, and is {stack!r}")
    return stack


def package_name(name):
    """`com.lukeneedham.lyrictutor` for `LyricTutor`: the letters and digits of the name, lower case."""
    return f"{PACKAGE_PREFIX}.{re.sub('[^A-Za-z0-9]', '', name).lower()}"


def add_to_apps_json(text, name, repo, stack):
    """[text] of apps.json with the project added as the last entry, with its [stack], in the layout of the file (one entry a line).
    Returns None when the app is already listed, by repo or by name (both exactly as spelled, like nothing else does)."""
    apps = json.loads(text)
    if any(a["repo"].lower() == repo.lower() or a["name"] == name for a in apps):
        return None
    last = text.rstrip().rindex("}")
    entry = f'  {{"name": {json.dumps(name)}, "repo": {json.dumps(repo)}, "stack": {json.dumps(stack)}}}'
    new = text[: last + 1] + ",\n" + entry + "\n]\n"
    if json.loads(new)[-1] != {"name": name, "repo": repo, "stack": stack}:  # the layout is only ours to keep; the data must be right
        raise ValueError("Could not add the app to apps.json")
    return new


def settings_gradle(tools=TOOLS):
    """`settings.gradle.kts` of this repo for an app: the same repository rules (they decide which repository may serve
    which group), the repository of the shared library, and the one module `:app`. The project name is still this repo's:
    `scaffold` sets it."""
    text = (tools / "settings.gradle.kts").read_text()
    head, found, tail = text.partition("dependencyResolutionManagement")
    after_central = tail.replace("        mavenCentral()\n", "        mavenCentral()\n" + MAVEN_REPOSITORY, 1)
    if not found or after_central == tail:
        raise ValueError("settings.gradle.kts has no dependencyResolutionManagement with mavenCentral() to add the library's repository to")
    return re.sub(r'(?m)^include\(":common"\)\n?', 'include(":app")\n', head + found + after_central)


def latest_common_version(tags):
    """The newest version of the shared library among [tags] (names like `common-0.8.0`, others ignored), as `0.8.0`."""
    versions = [tuple(int(part) for part in m.groups()) for m in map(COMMON_TAG_RE.match, tags) if m]
    if not versions:
        raise ValueError("No release of the shared library (a tag common-<version>) in " + COMMON_REPO)
    return ".".join(map(str, max(versions)))


def fetch_common_version(call):
    """The latest version of the shared library released from this repo (docs/library.md), from its releases and tags."""
    tags = [r["tag_name"] for r in call("GET", f"/repos/{COMMON_REPO}/releases?per_page=100") if not r.get("draft")]
    tags += [t["name"] for t in call("GET", f"/repos/{COMMON_REPO}/tags?per_page=100")]
    return latest_common_version(tags)


def template_values(name, common_version, tools=TOOLS):
    """What each token of the templates stands for. The versions of the build tools (AGP, Kotlin, Compose Multiplatform) are
    this repo's own, which the shared library is built with, so that new apps start on the ones the docs name (docs/new-app.md). The longer token comes first: one is the start of the other."""
    catalog = (tools / "gradle" / "libs.versions.toml").read_text()

    def version(key):
        found = re.search(rf'(?m)^{key} = "([^"]+)"', catalog)
        if not found:
            raise ValueError(f"gradle/libs.versions.toml has no {key} version")
        return found.group(1)

    package = package_name(name)
    return {
        "__PACKAGE_PATH__": package.replace(".", "/"),
        "__PACKAGE__": package,
        "__APP_NAME__": name,
        "__AGP__": version("agp"),
        "__KOTLIN__": version("kotlin"),
        "__COMPOSE_PLUGIN__": version("compose-plugin"),
        "__COMMON_VERSION__": common_version,
    }


def next_js_template_values(name):
    """What each token of templates/next-js stands for: the name, and the name as an npm package (lower case, no underscores)."""
    return {"__APP_NAME__": name, "__PACKAGE_NAME__": name.lower().replace("_", "-")}


def render_templates(app_dir, values, changed, stack, tools=TOOLS):
    """Writes the files of the templates of [stack] into [app_dir], with the tokens of [values] replaced in the paths and the text.
    A file that is there is not touched. Fails if a token is left over, which is a typo in a template."""
    root = tools.joinpath(*TEMPLATE_DIRS[stack])
    for source in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = source.relative_to(root).as_posix()
        text = source.read_text()
        for token, value in values.items():
            relative = relative.replace(token, value)
            text = text.replace(token, value)
        relative = relative.removesuffix(TEMPLATE_SUFFIX)
        left = TOKEN_RE.findall(relative + text)
        if left:
            raise ValueError(f"{source.relative_to(root)} has a token that nothing fills: {sorted(set(left))}")
        write_new(app_dir, relative, text, changed)


def write_new(app_dir, relative, content, changed, mode=None):
    """Writes [relative] under [app_dir] unless it is there (a file of the app is never overwritten). Notes it in [changed]."""
    target = app_dir / relative
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content if isinstance(content, bytes) else content.encode())
    if mode is not None:
        target.chmod(mode)
    changed.append(relative)


def make_debug_keystore(path):
    """The standard Android debug keystore (docs/new-app.md, step 2): not a secret, committed so that every build is signed
    with the same key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["keytool", "-genkeypair", "-keystore", str(path), "-storepass", "android", "-alias", "androiddebugkey",
         "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048", "-validity", "36500",
         "-dname", "CN=Android Debug,O=Android,C=US"],
        check=True, capture_output=True, text=True,
    )


def scaffold(app_dir, name, common_version, tools=TOOLS, keystore=make_debug_keystore, year=None):
    """A new app that builds: the Gradle wrapper, `settings.gradle.kts`, `.gitignore`, `LICENSE`, `app/debug.keystore`, and
    the app of templates/new-app, on version [common_version] of the shared library. Nothing that is already there is
    touched. Returns the paths written."""
    changed = []
    for relative in WRAPPER_FILES:
        source = tools / relative
        write_new(app_dir, relative, source.read_bytes(), changed, mode=stat.S_IMODE(source.stat().st_mode))
    settings = settings_gradle(tools).replace('rootProject.name = "ci-workflows"', f'rootProject.name = "{name}"')
    write_new(app_dir, "settings.gradle.kts", settings, changed)
    write_new(app_dir, ".gitignore", GITIGNORE, changed)
    # What an app without a license gets (docs/readme.md): the user changes it if the app has another
    write_new(app_dir, "LICENSE", f"Copyright (c) {year or date.today().year} Luke Needham. All rights reserved.\n", changed)
    if not (app_dir / "app" / "debug.keystore").exists():
        keystore(app_dir / "app" / "debug.keystore")
        changed.append("app/debug.keystore")
    render_templates(app_dir, template_values(name, common_version, tools), changed, "kmp", tools)
    return changed


def install_dependencies(app_dir):
    """Makes yarn.lock for the website in [app_dir]: the dependencies of package.json at their newest allowed versions, which
    the lockfile then pins, so that CI and Vercel build what was installed here. Needs yarn (classic) and a Node of the
    engines of package.json."""
    subprocess.run(["yarn", "install", "--non-interactive", "--ignore-scripts"], cwd=app_dir, check=True, capture_output=True, text=True)


def is_github_readme_stub(text, name):
    """Whether [text] is the README that GitHub makes when a repo is created with one: the title `# <name>` and at most one line under
    it (the description). That is no README of the project's own, and it fails the Prettier check of `yarn lint`."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return 1 <= len(lines) <= 2 and lines[0] == f"# {name}"


def scaffold_next_js(app_dir, name, tools=TOOLS, year=None, install=install_dependencies):
    """A new Next.js website that builds: `.gitignore`, `LICENSE`, the files of templates/next-js (with `readme.yml`) and `yarn.lock`,
    and the `README.md` that CI would render from `readme.yml`. Nothing that is already there is touched, except the stub README
    that GitHub made with the repo, which the generated one replaces. Returns the paths written."""
    changed = []
    readme = app_dir / "README.md"
    if readme.is_file() and is_github_readme_stub(readme.read_text(), name):
        readme.unlink()
    write_new(app_dir, ".gitignore", NEXT_JS_GITIGNORE, changed)
    write_new(app_dir, "LICENSE", f"Copyright (c) {year or date.today().year} Luke Needham. All rights reserved.\n", changed)
    render_templates(app_dir, next_js_template_values(name), changed, "next-js", tools)
    if not (app_dir / "yarn.lock").exists():
        install(app_dir)
        changed.append("yarn.lock")
    # The README is written here too, so that the first PR already has it (CI renders the same one, and the next ones when readme.yml changes)
    if not readme.exists():
        generate_readme.write_web(app_dir, f"{OWNER}/{name}")
        changed.append("README.md")
    return changed


def set_up_app(app_dir, name, common_version, stack, tools=TOOLS, keystore=make_debug_keystore, install=install_dependencies):
    """The first sync and the scaffold of [stack], applied to the checkout [app_dir]. Returns the paths that changed.
    [common_version] is the shared library's, which only a kmp app has."""
    synced = sync_apps.sync_app(app_dir, stack, tools)
    if stack == "next-js":
        return synced + scaffold_next_js(app_dir, name, tools, install=install)
    return synced + scaffold(app_dir, name, common_version, tools, keystore)


# ---------------------------------------------------------------------------------------------------
# GitHub. `call(method, path, body=None)` is sync_apps.api with a token: tests give another.
# ---------------------------------------------------------------------------------------------------

def caller(token):
    return lambda method, path, body=None: sync_apps.api(token, method, path, body)


def not_found(error):
    return isinstance(error, RuntimeError) and " returned 404:" in str(error)


def repo_exists(call, repo):
    try:
        call("GET", f"/repos/{repo}")
        return True
    except RuntimeError as e:
        if not_found(e):
            return False
        raise


DESCRIPTIONS = {"kmp": "an Android app", "next-js": "a website"}


def create_repo(call, name, private, stack, resume=False, owner=OWNER):
    """Creates [owner]/[name] with a README and makes sure its default branch is `main`. Returns the repo, `owner/name`.
    An existing repo is an error, unless [resume]: then it is carried on with."""
    repo = f"{owner}/{name}"
    login = call("GET", "/user")["login"]
    if login.lower() != owner.lower():
        raise RuntimeError(f"The token belongs to {login}, and apps are created for {owner}")
    if repo_exists(call, repo):
        if not resume:
            raise RuntimeError(f"{repo} already exists. Run again with resume to carry on with it")
        return repo
    created = call("POST", "/user/repos", {
        "name": name,
        "private": private,
        "auto_init": True,
        "description": f"{name}, {DESCRIPTIONS[stack]}",
    })
    default = created.get("default_branch", DEFAULT_BRANCH)
    if default != DEFAULT_BRANCH:
        call("POST", f"/repos/{repo}/branches/{default}/rename", {"new_name": DEFAULT_BRANCH})
    return repo


def register_app(call, name, repo, stack, attempts=3):
    """Adds the app to apps.json of the common repo, with a commit to `main`. Returns False when it is already listed.
    A commit that lands in between (the file has a new `sha`) is retried on top of the new file."""
    for attempt in range(attempts):
        file = call("GET", f"/repos/{COMMON_REPO}/contents/{APPS_FILE}?ref={DEFAULT_BRANCH}")
        text = base64.b64decode(file["content"]).decode()
        new = add_to_apps_json(text, name, repo, stack)
        if new is None:
            return False
        try:
            call("PUT", f"/repos/{COMMON_REPO}/contents/{APPS_FILE}", {
                "message": f"Add {name} to apps.json",
                "content": base64.b64encode(new.encode()).decode(),
                "sha": file["sha"],
                "branch": DEFAULT_BRANCH,
            })
            return True
        except RuntimeError as e:
            if attempt == attempts - 1 or not re.search(r" returned (409|422):", str(e)):
                raise
    return False  # not reached


def clone_new_repo(repo, token, work, attempts=6, wait=3):
    """Clones the new repo. Its first commit (the README) may take a moment to be there, so it tries again."""
    base = os.environ.get("SYNC_GIT_BASE", "https://github.com")
    checkout = Path(work) / repo.replace("/", "_")
    for attempt in range(attempts):
        try:
            sync_apps.git(work, "clone", "--quiet", "--depth", "1", f"{base}/{repo}.git", str(checkout), token=token)
            if (checkout / ".git").is_dir() and sync_apps.git(checkout, "rev-parse", "HEAD", check=False).strip():
                return checkout
        except RuntimeError:
            pass
        shutil.rmtree(checkout, ignore_errors=True)
        if attempt < attempts - 1:
            time.sleep(wait)
    raise RuntimeError(f"Could not clone {repo}, which has no commit yet")


def push_first_commit(repo, name, token, work, common_version, stack, keystore=make_debug_keystore, install=install_dependencies):
    """Clones the new repo, sets it up for its [stack] and pushes the commit to its default branch. Returns the paths written."""
    checkout = clone_new_repo(repo, token, work)
    changed = set_up_app(checkout, name, common_version, stack, keystore=keystore, install=install)
    if changed:
        sync_apps.git(checkout, "add", "-A")
        sync_apps.git(checkout, "commit", "--quiet", "-m", COMMIT_MESSAGE)
        sync_apps.git(checkout, "push", "--quiet", "origin", f"HEAD:{DEFAULT_BRANCH}", token=token)
    return changed


def create_app(name, stack, private=False, resume=False, create_token=None, sync_token=None, commit_token=None,
               push=push_first_commit, make_caller=caller, vercel_token=None, vercel_team=None, make_vercel_call=vercel_setup.make_call):
    """The whole job for a project of [stack] (there is no default). Returns the lines to report, one per step. [push] and
    [make_caller] are for the tests."""
    check_name(name)
    check_stack(stack)
    sync_token = sync_token or create_token
    create_token = create_token or sync_token
    if not create_token:
        raise RuntimeError("No token: set NEW_APP_TOKEN (or SYNC_TOKEN). See docs/create-app.md")
    lines = []

    try:
        repo = create_repo(make_caller(create_token), name, private, stack, resume)
    except RuntimeError as e:
        if " returned 403:" in str(e) and "/user/repos" in str(e):
            raise RuntimeError(
                f"{e}\nThis token may not create repositories, and the repo does not exist. Create it first (the caller does, with its own "
                "token) and run again with resume, or set NEW_APP_TOKEN. See docs/create-app.md") from None
        raise
    lines.append(f"repo https://github.com/{repo} ({'private' if private else 'public'})")

    # Only a kmp app uses the shared library
    common_version = None
    if stack == "kmp":
        common_version = fetch_common_version(make_caller(sync_token))
        lines.append(f"shared library common {common_version}")

    work = tempfile.mkdtemp(prefix="new_app_")
    try:
        changed = push(repo, name, sync_token, work, common_version, stack)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    lines.append(f"stack {stack}")
    lines.append(f"first commit on {DEFAULT_BRANCH}: {len(changed)} files" if changed else "first commit: nothing to add, already done")

    # The secret goes in before the app is listed, so that the sync that listing starts finds nothing left to do
    secret = sync_apps.sync_secret({"repo": repo}, sync_token, commit_token, dry_run=False)
    lines.append(f"secret {sync_apps.COMMIT_TOKEN_SECRET} " + ("set" if secret else "not set (no token for it)"))

    if stack == "next-js":
        lines += set_up_vercel(repo, name, vercel_token, vercel_team, make_vercel_call)

    added = register_app(make_caller(sync_token), name, repo, stack)
    lines.append(f"apps.json: {name} " + ("added" if added else "was already listed"))
    return lines


def set_up_vercel(repo, name, token, team, make_call=vercel_setup.make_call):
    """The Vercel step of a website: the lines to report. Without a token it is skipped and says what is left to do by hand."""
    if not token:
        return ["vercel: not set up (no VERCEL_TOKEN): connect the repo to Vercel and turn Deployment Protection off for previews yourself"]
    try:
        return vercel_setup.set_up(make_call(token, team), repo)
    except vercel_setup.VercelError as e:
        # The repo and its first commit are made by now, and every step can be repeated: say how to carry on
        raise vercel_setup.VercelError(
            f"{e} The repo and its first commit are made: fix this, then run New App again for {repo.split('/')[1]} with resume on "
            "(Actions > New App > Run workflow), and it carries on from here (docs/create-app.md).", e.status, e.code) from None


def next_steps(name, stack, vercel_done=False):
    """What is left for the user, as a Markdown list for the run summary."""
    if stack == "next-js":
        by_hand = (
            "" if vercel_done else
            f"- **Connect the repo to a project on Vercel** (https://vercel.com/new), and in the project's settings turn **Deployment "
            f"Protection** off for previews: CI fails the pull request when the preview asks for a login (docs/next-js-app.md)\n"
        )
        return (
            f"### Next\n\n"
            f"- Open the repo: https://github.com/{OWNER}/{name}\n"
            f"{by_hand}"
            f"- Give the Claude GitHub App access to the repo, unless its installation covers all repositories: "
            f"https://github.com/apps/claude/installations/select_target\n"
            f"- Start a Claude Code session on it: https://claude.ai/code/new?repo={OWNER}%2F{name}\n"
        )
    package = package_name(name)
    return (
        f"### Next\n\n"
        f"- Open the repo: https://github.com/{OWNER}/{name}\n"
        f"- Package for the app: `{package}`\n"
        f"- Give the Claude GitHub App access to the repo, unless its installation covers all repositories: "
        f"https://github.com/apps/claude/installations/select_target\n"
        f"- Start a Claude Code session on it: https://claude.ai/code/new?repo={OWNER}%2F{name}\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="the name of the project and of its repo")
    parser.add_argument("--stack", required=True, choices=list(sync_apps.STACKS),
                        help="what the project is built with: kmp (an Android app) or next-js (a website). Required: there is no default")
    parser.add_argument("--private", action="store_true", help="create a private repo (default: public)")
    parser.add_argument("--resume", action="store_true", help="carry on with a repo that already exists")
    parser.add_argument("--dry-run", action="store_true", help="check the name and say what would be done; change nothing")
    args = parser.parse_args()

    try:
        check_name(args.name)
    except ValueError as e:
        print(f"::error::{e}")
        sys.exit(1)

    if args.dry_run:
        print(f"Would create {'private' if args.private else 'public'} {args.stack} repo {OWNER}/{args.name}"
              f"{' (package ' + package_name(args.name) + ')' if args.stack == 'kmp' else ''}, "
              f"push the first commit to {DEFAULT_BRANCH}, set {sync_apps.COMMIT_TOKEN_SECRET} and add the app to {APPS_FILE}")
        return

    tokens = {k: os.environ.get(k) for k in ("NEW_APP_TOKEN", "SYNC_TOKEN", "GENERATED_COMMIT_TOKEN", "VERCEL_TOKEN")}
    for value in tokens.values():
        if value:
            print(f"::add-mask::{value}")
    try:
        lines = create_app(
            args.name, args.stack, args.private, args.resume,
            create_token=tokens["NEW_APP_TOKEN"], sync_token=tokens["SYNC_TOKEN"], commit_token=tokens["GENERATED_COMMIT_TOKEN"],
            vercel_token=tokens["VERCEL_TOKEN"], vercel_team=os.environ.get("VERCEL_TEAM_ID"),
        )
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"::error::{e}")
        sys.exit(1)

    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"### New app {args.name}\n\n" + "\n".join(f"- {l}" for l in lines) + "\n\n" + next_steps(args.name, args.stack, vercel_done=any(l.startswith("vercel project") for l in lines)))


if __name__ == "__main__":
    main()
