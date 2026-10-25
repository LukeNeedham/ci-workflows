#!/usr/bin/env python3
"""The logic of the PR build and cleanup workflows (android_pr_build.yml, android_pr_cleanup.yml): the pre-release
that holds a pull request's APK, its tag, and the sticky comment that links to it.

    python3 pr_releases.py stale      --repo R --pr N --header H --timezone TZ --sha SHA
    python3 pr_releases.py meta       --timezone TZ --apk-path P --branch B --run-number N --run-attempt A
    python3 pr_releases.py superseded --repo R --pr N --sha SHA
    python3 pr_releases.py cleanup    --branch B

`stale`, `meta` and `superseded` set step outputs. `cleanup` and the `gh` calls use GH_TOKEN and GH_REPO.

The tag scheme is `<clean branch>-<run number>-<run attempt>`: `release_tag` makes it, and `is_build_tag` recognises
it again in the cleanup, so the two cannot drift apart.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import output

APK_LINK = re.compile(r"https://github\.com/[^ )\n]+/releases/download/[^ )\n]+\.apk")


def clean_branch(raw):
    """A branch name as part of a tag: special characters become dashes, and it is lower case."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", raw).lower()


def release_tag(branch, run_number, run_attempt):
    return f"{clean_branch(branch)}-{run_number}-{run_attempt}"


def is_build_tag(tag, branch):
    """Whether [tag] is a tag of [release_tag] for [branch], whatever the run."""
    prefix = clean_branch(branch) + "-"
    return tag.startswith(prefix) and re.fullmatch(r"[0-9]+-[0-9]+", tag[len(prefix):]) is not None


def now(timezone):
    return datetime.now(ZoneInfo(timezone)).strftime("%d/%m/%Y %H:%M:%S")


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def stale(repo, pr, header, timezone, sha):
    """The outputs for the comment that says a build is on its way, and the link of the previous APK, kept in it."""
    output("short-sha", sha[:7])
    output("time", now(timezone))
    # The sticky comment action embeds this marker in the comment it manages
    marker = f"Sticky Pull Request Comment{header} "
    jq = f".[] | select(.body | contains({json.dumps(marker)})) | .body"
    result = gh("api", "--paginate", f"repos/{repo}/issues/{pr}/comments", "--jq", jq)
    match = APK_LINK.search(result.stdout)
    output("old-url", match.group(0) if match else "")
    return 0


def meta(timezone, apk_path, branch, run_number, run_attempt):
    output("time", now(timezone))
    output("apk-name", os.path.basename(apk_path))
    output("tag", release_tag(branch, run_number, run_attempt))
    return 0


def superseded(repo, pr, sha):
    """Says whether a newer push has replaced the commit [sha] of the PR since this run started."""
    result = gh("api", f"repos/{repo}/pulls/{pr}", "--jq", ".head.sha")
    current = result.stdout.strip() if result.returncode == 0 else ""
    if current and current != sha:
        output("superseded", "true")
    return 0


def cleanup(branch):
    """Deletes the pre-releases and tags that the builds of [branch] made."""
    listed = gh("release", "list", "--limit", "1000", "--json", "tagName,isPrerelease")
    if listed.returncode != 0:
        print(listed.stderr, file=sys.stderr)
        return listed.returncode
    tags = [r["tagName"] for r in json.loads(listed.stdout) if r["isPrerelease"] and is_build_tag(r["tagName"], branch)]
    if not tags:
        print(f"No PR build releases found for branch '{branch}'")
        return 0
    for tag in tags:
        print(f"Deleting release and tag: {tag}")
        deleted = gh("release", "delete", tag, "--yes", "--cleanup-tag")
        if deleted.returncode != 0:
            print(deleted.stderr, file=sys.stderr)
            return deleted.returncode
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("stale")
    for name in ("repo", "pr", "header", "timezone", "sha"):
        p.add_argument(f"--{name}", required=True)
    p = commands.add_parser("meta")
    for name in ("timezone", "apk-path", "branch", "run-number", "run-attempt"):
        p.add_argument(f"--{name}", required=True)
    p = commands.add_parser("superseded")
    for name in ("repo", "pr", "sha"):
        p.add_argument(f"--{name}", required=True)
    commands.add_parser("cleanup").add_argument("--branch", required=True)
    a = parser.parse_args()
    if a.command == "stale":
        code = stale(a.repo, a.pr, a.header, a.timezone, a.sha)
    elif a.command == "meta":
        code = meta(a.timezone, a.apk_path, a.branch, a.run_number, a.run_attempt)
    elif a.command == "superseded":
        code = superseded(a.repo, a.pr, a.sha)
    else:
        code = cleanup(a.branch)
    sys.exit(code)


if __name__ == "__main__":
    main()
