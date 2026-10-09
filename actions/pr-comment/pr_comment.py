"""Builds the sticky APK comment for a PR build (in progress / success / failed / cancelled).

The previous APK link is read back out of the existing comment so it can be kept, flagged stale,
while a new build is running.
"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

APK_URL_PATTERN = re.compile(r"https://github\.com/[^ )]+/releases/download/[^ )]+\.apk")
STATES = ("in-progress", "success", "failed", "cancelled")


def find_previous_url(body):
    """First release APK link in a comment body, or None."""
    match = APK_URL_PATTERN.search(body or "")
    return match.group(0) if match else None


def marker(header):
    """Hidden marker the sticky comment action embeds in the comment it manages."""
    return f"Sticky Pull Request Comment{header} "


def find_comment_body(comment_bodies, header):
    return next((b for b in comment_bodies if marker(header) in b), "")


def format_time(timezone, now=None):
    return (now or datetime.now(ZoneInfo(timezone))).strftime("%d/%m/%Y %H:%M:%S")


def build_message(state, sha, run_url, time, apk_url=None, previous_url=None):
    if state not in STATES:
        raise ValueError(f"unknown state: {state}")
    stale = (
        f"\n\nPrevious build (⚠️ stale, does not include this commit): {previous_url}"
        if previous_url
        else ""
    )
    if state == "success":
        return (
            f"App apk at:\n{apk_url}\n\n"
            f"* **Triggered by:** PR Commit `{sha}`\n"
            f"* **Built at:** {time}\n"
        )
    if state == "in-progress":
        return (
            f"⏳ **New build in progress** ([run]({run_url}))\n\n"
            f"* **Triggered by:** PR Commit `{sha}`\n"
            f"* **Started at:** {time}{stale}\n"
        )
    return (
        f"❌ **Build {state}** ([run]({run_url}))\n\n"
        f"* **Triggered by:** PR Commit `{sha}`{stale}\n"
    )


def fetch_comment_bodies(repo, pr_number):
    """All comment bodies on the PR, via the gh CLI. Empty on any failure (cosmetic data only)."""
    result = subprocess.run(
        ["gh", "api", "--paginate", f"repos/{repo}/issues/{pr_number}/comments", "--jq", ".[].body | @json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, choices=STATES)
    parser.add_argument("--header", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--apk-url", default="")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--output", required=True, help="file to write the message to")
    args = parser.parse_args(argv)

    previous_url = None
    if args.state != "success":
        bodies = fetch_comment_bodies(args.repo, args.pr_number)
        previous_url = find_previous_url(find_comment_body(bodies, args.header))

    message = build_message(
        args.state, args.sha, args.run_url, format_time(args.timezone), args.apk_url or None, previous_url
    )
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(message)


if __name__ == "__main__":
    main()
