#!/usr/bin/env python3
"""Looks up the CI settings of the app that is running a workflow, and decides whether the run has anything to do.

The callers in the apps carry no settings: the reusable workflows run the composite action
.github/actions/app-config, which runs this script. It finds the app's entry in apps.json by the repo the
workflow runs in (github.repository), fills in the defaults below for what the entry leaves out, and writes
the result to $GITHUB_OUTPUT. See docs/app-config.md.

It also sets `skip=true` for a pull request run that has nothing to build:
  - the PR targets a branch that is not in the app's `branches`, or
  - every file the PR changes is under SKIPPED_PATHS (the Claude skill), so no APK can differ.

    python3 scripts/app_config.py --repo LukeNeedham/AppHub --event pull_request --action synchronize \\
        --base main --files changed_files.txt
"""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent

# Every setting an app can have in apps.json, with its default. The defaults live here and only here.
DEFAULTS = {
    "apk-path": "app/build/outputs/apk/debug/app-debug.apk",
    "gradle-task": "assembleDebug",
    "java-version": "17",
    "java-distribution": "zulu",
    "timezone": "Europe/Amsterdam",
    "release-gradle-task": "assembleRelease",
    "release-apk-path": "app/build/outputs/apk/release/app-release.apk",
    # Empty: the release asset is named after the repo, e.g. Android-Dock.apk
    "asset-name": "",
}
# Not in DEFAULTS because it depends on the repo: <repo name, lower case>-app-link
COMMENT_HEADER = "comment-header"
DEFAULT_BRANCHES = ["main"]

# A PR that changes only files under these prefixes does not build an APK
SKIPPED_PATHS = [".claude/skills/"]

# What apps.json may hold in an entry, besides the settings above. Checked by the tests.
ENTRY_KEYS = {"name", "repo", "library", "skill", "callers", "branches", COMMENT_HEADER, *DEFAULTS}


def find_app(apps, repo):
    """The entry of [repo] (owner/name, any case) in [apps], or None."""
    for app in apps:
        if app["repo"].lower() == repo.lower():
            return app
    return None


def settings(app, repo):
    """All settings of [repo], as strings: the entry's own where it has them, else the defaults. [app] may be None."""
    app = app or {}
    result = {key: str(app.get(key, default)) for key, default in DEFAULTS.items()}
    result[COMMENT_HEADER] = str(app.get(COMMENT_HEADER, repo.split("/")[1].lower() + "-app-link"))
    return result


def branches(app):
    return (app or {}).get("branches") or DEFAULT_BRANCHES


def targets_branch(app, base):
    """Whether PRs into [base] are this app's business. A pattern in `branches` may use * as in GitHub's filters."""
    return any(fnmatch.fnmatchcase(base, pattern) for pattern in branches(app))


def only_skipped_files(files):
    """Whether [files] is not empty and all of it is under SKIPPED_PATHS."""
    return bool(files) and all(any(f.startswith(p) for p in SKIPPED_PATHS) for f in files)


def skip_reason(app, event, action, base, files):
    """Why this run has nothing to do, or None when it has."""
    if event != "pull_request":
        return None
    if base and not targets_branch(app, base):
        return f"the PR targets {base}, which is not one of this app's branches ({', '.join(branches(app))})"
    if action != "closed" and only_skipped_files(files):
        return "the PR changes only " + " and ".join(SKIPPED_PATHS) + ", which cannot change the APK"
    return None


def read_files(path):
    """The changed file names listed one per line in the file [path], or [] when there is none."""
    if not path or not Path(path).is_file():
        return []
    return [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]


def run(repo, event, action, base, files, apps):
    """The outputs for the workflow, and the lines to tell the user in the log."""
    app = find_app(apps, repo)
    log = []
    if app is None:
        log.append(f"::warning::{repo} is not in apps.json, so the defaults are used. Add it (docs/consuming-apps.md).")
    reason = skip_reason(app, event, action, base, files)
    if reason:
        log.append(f"::notice::Nothing to do: {reason}.")
    return {"skip": "true" if reason else "false", **settings(app, repo)}, log


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="owner/name of the repo running the workflow")
    parser.add_argument("--event", default="", help="github.event_name")
    parser.add_argument("--action", default="", help="github.event.action")
    parser.add_argument("--base", default="", help="the branch a pull request targets")
    parser.add_argument("--files", default="", help="file listing the files the pull request changes, one per line")
    parser.add_argument("--apps", default=str(TOOLS / "apps.json"), help="the apps.json to read")
    args = parser.parse_args()

    apps = json.loads(Path(args.apps).read_text())
    outputs, log = run(args.repo, args.event, args.action, args.base, read_files(args.files), apps)
    print("\n".join(log))
    for key, value in outputs.items():
        print(f"{key}={value}")
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as f:
            f.writelines(f"{key}={value}\n" for key, value in outputs.items())


if __name__ == "__main__":
    sys.exit(main())
