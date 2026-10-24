#!/usr/bin/env python3
"""Commits files that CI generated to the branch of the pull request. When they are out of date and this run
cannot commit (not a pull request, or one from a fork), it fails and says how to regenerate them.

    python3 commit_generated.py --paths docs/screenshots --what "The screenshots" \\
        --source "the page previews" --regenerate "scripts/render_screenshots.py" --message "Regenerate ..."

Reads from the environment: IS_PR ("true" for a pull_request event), IS_FORK ("true" when the PR comes from a
fork) and BRANCH (the head branch of the PR). Used by the app-icon, screenshots and readme actions.

A push made with the workflow token does not start new workflow runs, so there is no loop. A push that races with
another job's (they commit to the same branch) is retried once, on top of it.
"""

import argparse
import os
import subprocess
import sys


def git(*args, check=True, cwd=None):
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def run(args, env, cwd=None):
    """Returns the exit code."""
    # A path that does not exist and was never tracked has nothing to add: no change
    git("add", "-A", "--", *args.paths, check=False, cwd=cwd)
    if git("diff", "--cached", "--quiet", "--", *args.paths, check=False, cwd=cwd).returncode == 0:
        print(f"{args.what} is up to date")
        return 0

    if env.get("IS_PR") != "true" or env.get("IS_FORK") == "true":
        print(f"::error file={args.paths[0]}::{args.what} does not match {args.source}, and this run cannot commit it "
              f"(it only does on a PR from this repo's own branches). Run {args.regenerate} and commit the result.")
        return 1

    branch = env.get("BRANCH")
    if not branch:
        print("::error::BRANCH is not set: the head branch of the pull request")
        return 1
    git("config", "user.name", "github-actions[bot]", cwd=cwd)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=cwd)
    git("commit", "-m", args.message, cwd=cwd)
    destination = f"HEAD:refs/heads/{branch}"
    if git("push", "origin", destination, check=False, cwd=cwd).returncode != 0:
        # A push to the branch since this run started: put the commit on top of it and push again
        git("pull", "--rebase", "origin", branch, cwd=cwd)
        git("push", "origin", destination, cwd=cwd)
    print(f"Committed {args.what[0].lower() + args.what[1:]} to {branch}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--paths", nargs="+", required=True, help="the generated files or folders")
    parser.add_argument("--what", required=True, help='what they are, for the messages: "The screenshots"')
    parser.add_argument("--source", required=True, help='what they are generated from: "the page previews"')
    parser.add_argument("--regenerate", required=True, help="how to generate them by hand, for the error")
    parser.add_argument("--message", required=True, help="the commit message")
    sys.exit(run(parser.parse_args(), os.environ))


if __name__ == "__main__":
    main()
