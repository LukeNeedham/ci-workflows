#!/usr/bin/env python3
"""Merges the sync PR of ci-workflows once the checks of its run have passed (the `automerge` job of android_pr.yml).

    python3 automerge.py --repo R --pr N --run-sha SHA

Uses GH_TOKEN, which must be a token of the owner: a merge made with the workflow token starts no workflow, so
build_main.yml would not run on the merged commit.

It merges only a PR that is open, from a branch of the same repo, called SYNC_BRANCH and titled with TITLE_TAG, and
only when the PR is still the one the run checked: the head of the run (--run-sha) must be an ancestor of the head
now. CI adds commits of its own to the PR branch (the README, the screenshots), which keeps it so; a new sync, which
force-pushes the branch, does not, and the run of that push merges it instead. Anything else is skipped with a notice.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import error

# sync_apps.py puts this at the start of the title of the PRs it opens, and pushes them from this branch
TITLE_TAG = "[auto-merge]"
SYNC_BRANCH = "sync/ci-workflows"

# The states of a comparison of the run's head with the head now, in which the PR is still what the run checked
SAME_PR = ("ahead", "identical")


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def skip_reason(pr, repo):
    """Why [pr] (the GitHub API's description of it) must not be merged, or None when it may be."""
    if pr["state"] != "open":
        return f"the PR is {pr['state']}"
    if not pr["title"].startswith(TITLE_TAG):
        return f"the title does not start with {TITLE_TAG}"
    if pr["head"]["ref"] != SYNC_BRANCH:
        return f"the branch is {pr['head']['ref']}, not {SYNC_BRANCH}"
    if (pr["head"]["repo"] or {}).get("full_name") != repo:
        return "the branch is not in this repo"
    return None


def merge(repo, pr_number, run_sha):
    """Returns the exit code: 0 when the PR was merged or must be left alone, 1 when the merge failed."""
    answer = gh("api", f"repos/{repo}/pulls/{pr_number}")
    if answer.returncode != 0:
        error(f"Could not read the PR: {answer.stderr.strip()}", "Auto-merge")
        return 1
    pr = json.loads(answer.stdout)
    reason = skip_reason(pr, repo)
    if reason:
        print(f"Not merged: {reason}.")
        return 0
    head = pr["head"]["sha"]
    compare = gh("api", f"repos/{repo}/compare/{run_sha}...{head}", "--jq", ".status")
    status = compare.stdout.strip()
    if compare.returncode != 0 or status not in SAME_PR:
        # A new sync replaced the branch: the run of that push merges it, after its own checks
        print(f"Not merged: the PR changed since this run started ({status or 'comparison failed'}).")
        return 0
    merged = gh("pr", "merge", str(pr_number), "--repo", repo, "--merge", "--match-head-commit", head)
    if merged.returncode != 0:
        error(f"The merge failed: {(merged.stderr or merged.stdout).strip()}", "Auto-merge")
        return 1
    print(f"Merged #{pr_number} ({head[:7]}).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--run-sha", required=True)
    args = parser.parse_args()
    return merge(args.repo, args.pr, args.run_sha)


if __name__ == "__main__":
    sys.exit(main())
