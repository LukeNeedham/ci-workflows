#!/usr/bin/env python3
"""Commits files that CI generated to the branch of the pull request. When they are out of date and this run
cannot commit (not a pull request, one from a fork, or Dependabot's, whose token is read-only), it fails and says how to
regenerate them.

    python3 commit_generated.py app-icon | screenshots | readme [--also PATH ...]

--also adds files to the kind: the README of the screenshot package, whose folder is the app's own.

Runs in the checkout of the PR branch and reads the GitHub environment itself (GITHUB_EVENT_NAME, GITHUB_HEAD_REF,
GITHUB_REPOSITORY, GITHUB_ACTOR and the event payload). Used by the app-icon, screenshots and readme actions.

A run only commits on top of the commit it was started for (`pull_request.head.sha` of the event), or of what CI itself has added to
it since. If a newer push has put code on the branch, the generated files were made from the old code: they are not committed, because
they would be wrong, and because a commit of only generated files is not built (app_config.py), which would leave the new code unbuilt.
The newer push has a run of its own that generates them.

The push is made with whatever token the checkout used: the owner's GENERATED_COMMIT_TOKEN when the app has it, so that the checks
run on the new commit, else the workflow token (whose commit leaves the checks waiting for approval). Either way there is
no loop: app_config.py skips a run whose push changed only generated files. The three jobs commit to the same branch, so a push that races with another's is retried
on top of it, up to PUSH_ATTEMPTS times.
"""

import argparse
import json
import os
import subprocess
import sys
from types import SimpleNamespace

from app_config import only_generated_files

PUSH_ATTEMPTS = 3

KINDS = {
    "app-icon": SimpleNamespace(
        paths=["app-icon.png"], what="app-icon.png", source="the adaptive launcher icon",
        regenerate="scripts/render_app_icon.py (see docs/app-icon.md)",
        message="Regenerate app-icon.png from the adaptive launcher icon"),
    "screenshots": SimpleNamespace(
        paths=["docs/screenshots"], what="The screenshots", source="the screenshot previews",
        regenerate="scripts/render_screenshots.py (see docs/screenshots.md)",
        message="Regenerate the screenshots from the page previews"),
    "readme": SimpleNamespace(
        paths=["README.md"], what="README.md", source="readme.yml",
        regenerate="scripts/generate_readme.py (see docs/readme.md)",
        message="Regenerate README.md from readme.yml"),
}


def git(*args, check=True, cwd=None):
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def head_repo(env):
    """The full name of the repository that the PR comes from, or None when the event has no PR."""
    path = env.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return None
    with open(path) as f:
        return (((json.load(f).get("pull_request") or {}).get("head") or {}).get("repo") or {}).get("full_name")


def built_sha(env):
    """The commit this run was started for (the head of the PR when the event happened), or None when the event does not say."""
    path = env.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return None
    with open(path) as f:
        return ((json.load(f).get("pull_request") or {}).get("head") or {}).get("sha")


def why_branch_moved_on(built, branch, cwd=None):
    """Why files generated from the commit [built] must not be committed to [branch] as it is now, or None when they can.

    They can when the branch is still at [built], or when all that has been added to it since is generated files (the commit of
    another of the jobs that commit). Anything else is a newer push of code."""
    if git("fetch", "--no-tags", "--depth=200", "origin", branch, check=False, cwd=cwd).returncode != 0:
        return "the branch could not be read, so it is not known whether it has moved on"
    tip = git("rev-parse", "FETCH_HEAD", cwd=cwd).stdout.strip()
    if tip == built:
        return None
    # The commit may exist here and not be part of the branch any more: a force-push replaced the history
    if git("merge-base", "--is-ancestor", built, tip, check=False, cwd=cwd).returncode != 0:
        return "the commit this run was started for is no longer in the branch (it was force-pushed)"
    changed = git("diff", "--name-only", built, tip, cwd=cwd).stdout.split()
    if only_generated_files(changed):
        return None
    return "the branch has new commits of code since this run started, and a run of their own generates the files for them"


def why_cannot_commit(env):
    """Why this run cannot push to the branch of the PR, or None when it can."""
    if env.get("GITHUB_EVENT_NAME") != "pull_request":
        return "it is not a pull request run"
    if head_repo(env) != env.get("GITHUB_REPOSITORY"):
        return "the pull request comes from a fork"
    if env.get("GITHUB_ACTOR") == "dependabot[bot]":
        return "Dependabot's token is read-only"
    if not env.get("GITHUB_HEAD_REF"):
        return "the head branch of the pull request is unknown"
    return None


def run(kind, env, cwd=None):
    """Returns the exit code. [kind] says what to commit (see [KINDS])."""
    # A path that does not exist and was never tracked has nothing to add: no change
    git("add", "-A", "--", *kind.paths, check=False, cwd=cwd)
    if git("diff", "--cached", "--quiet", "--", *kind.paths, check=False, cwd=cwd).returncode == 0:
        print(f"{kind.what} is up to date")
        return 0

    reason = why_cannot_commit(env)
    if reason:
        print(f"::error file={kind.paths[0]}::{kind.what} does not match {kind.source}, and this run cannot commit it "
              f"({reason}). Run {kind.regenerate} and commit the result.")
        return 1

    branch = env["GITHUB_HEAD_REF"]
    built = built_sha(env)
    if built:
        moved_on = why_branch_moved_on(built, branch, cwd)
        if moved_on:
            print(f"::notice::{kind.what} not committed: {moved_on}.")
            return 0
    git("config", "user.name", "github-actions[bot]", cwd=cwd)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=cwd)
    git("commit", "-m", kind.message, cwd=cwd)
    destination = f"HEAD:refs/heads/{branch}"
    for attempt in range(PUSH_ATTEMPTS):
        if git("push", "origin", destination, check=False, cwd=cwd).returncode == 0:
            print(f"Committed {kind.what[0].lower() + kind.what[1:]} to {branch}")
            return 0
        if attempt < PUSH_ATTEMPTS - 1:
            # Another job pushed to the branch since this run started: put the commit on top of it, unless that was a push of code
            if built:
                moved_on = why_branch_moved_on(built, branch, cwd)
                if moved_on:
                    print(f"::notice::{kind.what} not committed: {moved_on}.")
                    return 0
            git("pull", "--rebase", "origin", branch, cwd=cwd)
    print(f"::error::Could not push {kind.what} to {branch} after {PUSH_ATTEMPTS} attempts")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=sorted(KINDS))
    parser.add_argument("--also", nargs="*", default=[], help="more files or folders to commit with it")
    args = parser.parse_args()
    kind = SimpleNamespace(**{**vars(KINDS[args.kind]), "paths": [*KINDS[args.kind].paths, *[p for p in args.also if p]]})
    sys.exit(run(kind, os.environ))


if __name__ == "__main__":
    main()
