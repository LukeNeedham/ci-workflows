#!/usr/bin/env python3
"""The CI settings that every app shares, and whether a run has anything to do.

Every app is built the same way, so there is nothing to configure per app: the settings below are constants,
and an app has to follow them (the debug APK is built to app/build/outputs/apk/debug/app-debug.apk, PRs go to
main, and so on). The reusable workflows run the composite action .github/actions/app-config, which runs this
script and writes the settings to $GITHUB_OUTPUT. See docs/app-config.md.

It also sets `generate` and `cleanup` to false for a pull request run that has nothing to do:
  - the PR targets a branch other than BRANCH, or
  - every file the PR changes is under SKIPPED_PATHS (the Claude skill), so no APK can differ.

    python3 scripts/app_config.py --repo LukeNeedham/AppHub --event pull_request --action synchronize \\
        --base main --files changed_files.txt
"""

import argparse
import os
import sys
from pathlib import Path

# The one branch every app uses: PRs into it are built, PRs into anything else are not
BRANCH = "main"

# A PR that changes only files under these prefixes does not build an APK
SKIPPED_PATHS = [".claude/skills/"]

SETTINGS = {
    "apk-path": "app/build/outputs/apk/debug/app-debug.apk",
    "gradle-task": "assembleDebug",
    "java-version": "17",
    "java-distribution": "temurin",
    "timezone": "Europe/Amsterdam",
    "release-gradle-task": "assembleRelease",
    "release-apk-path": "app/build/outputs/apk/release/app-release.apk",
}


def settings(repo):
    """All settings of the app in [repo] (owner/name), as strings."""
    name = repo.split("/")[1]
    return {
        **SETTINGS,
        # The sticky PR comment's id, and the file name of the APK on a release
        "comment-header": name.lower() + "-app-link",
        "asset-name": name + ".apk",
    }


def only_skipped_files(files):
    """Whether [files] is not empty and all of it is under SKIPPED_PATHS."""
    return bool(files) and all(any(f.startswith(p) for p in SKIPPED_PATHS) for f in files)


def skip_reason(event, action, base, files):
    """Why this run has nothing to do, or None when it has."""
    if event != "pull_request":
        return None
    if base and base != BRANCH:
        return f"the PR targets {base}, and only PRs into {BRANCH} are built"
    if action != "closed" and only_skipped_files(files):
        return "the PR changes only " + " and ".join(SKIPPED_PATHS) + ", which cannot change the APK"
    return None


def read_files(path):
    """The changed file names listed one per line in the file [path], or [] when there is none."""
    if not path or not Path(path).is_file():
        return []
    return [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]


def run(repo, event, action, base, files):
    """The outputs for the workflow, and the lines to tell the user in the log."""
    reason = skip_reason(event, action, base, files)
    log = [f"::notice::Nothing to do: {reason}."] if reason else []
    closed = event == "pull_request" and action == "closed"
    # What the jobs of android_pr.yml do: everything but a closed PR builds and generates; a closed PR cleans up.
    # A run that has nothing to do has both false.
    todo = {
        "generate": reason is None and not closed,
        "cleanup": reason is None and closed,
    }
    return {**{k: "true" if v else "false" for k, v in todo.items()}, **settings(repo)}, log


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="owner/name of the repo running the workflow")
    parser.add_argument("--event", default="", help="github.event_name")
    parser.add_argument("--action", default="", help="github.event.action")
    parser.add_argument("--base", default="", help="the branch a pull request targets")
    parser.add_argument("--files", default="", help="file listing the files the pull request changes, one per line")
    args = parser.parse_args()

    outputs, log = run(args.repo, args.event, args.action, args.base, read_files(args.files))
    print("\n".join(log))
    for key, value in outputs.items():
        print(f"{key}={value}")
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as f:
            f.writelines(f"{key}={value}\n" for key, value in outputs.items())


if __name__ == "__main__":
    sys.exit(main())
