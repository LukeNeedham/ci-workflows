#!/usr/bin/env python3
"""Publishes the debug APK of main as the rolling pre-release `main-build` (android_main_build.yml, docs/setup.md).

    python3 main_build.py publish --repo R --sha SHA --apk-path P --run-url URL

The release has one asset, `app-debug.apk`, which each run replaces, and the tag `main-build` is moved to the commit built,
so there is always an up-to-date main APK to test. The release notes start with the line `commit: <sha>`, which is what a
tool such as AppHub reads to tell which commit the APK is. Uses GH_TOKEN.
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from previews import gh, release_exists

TAG = "main-build"
ASSET = "app-debug.apk"
COMMIT_LINE = re.compile(r"^commit: ([0-9a-f]{40})\s*$", re.M)


def release_notes(sha, built_at, run_url):
    """The notes of the release; the first line is the one that tools read."""
    return (f"commit: {sha}\n\nDebug build of the default branch at {sha}, built {built_at}. "
            f"Replaced by every push to it ([run]({run_url})).")


def commit_of(notes):
    """The commit a release's notes say the APK is of, or None."""
    match = COMMIT_LINE.search(notes or "")
    return match.group(1) if match else None


def publish(repo, sha, apk_path, run_url):
    notes = release_notes(sha, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), run_url)
    if release_exists(repo, TAG):
        # The tag follows main: it has to point at the commit that was built
        gh("api", "-X", "PATCH", f"repos/{repo}/git/refs/tags/{TAG}", "-f", f"sha={sha}", "-F", "force=true")
        gh("release", "edit", TAG, "--repo", repo, "--notes", notes, "--prerelease", "--latest=false")
    else:
        gh("release", "create", TAG, "--repo", repo, "--prerelease", "--latest=false", "--target", sha,
           "--title", "Main build", "--notes", notes)
    # The asset is named the same for every app: the APK of the app is app-debug.apk whatever the file is called
    staged = Path(apk_path)
    if staged.name != ASSET:
        target = staged.with_name(ASSET)
        target.write_bytes(staged.read_bytes())
        staged = target
    gh("release", "upload", TAG, str(staged), "--repo", repo, "--clobber")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["publish"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--apk-path", required=True)
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()
    sys.exit(publish(args.repo, args.sha, args.apk_path, args.run_url))


if __name__ == "__main__":
    main()
