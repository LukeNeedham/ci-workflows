#!/usr/bin/env python3
"""The checks and git steps of the library release workflow (library_release.yml), run in this repo's checkout.

    python3 scripts/library_release.py check-version --version 0.7.0
    python3 scripts/library_release.py ensure-gh-pages            (uses GITHUB_SHA)
    python3 scripts/library_release.py check-unpublished --version 0.7.0
    python3 scripts/library_release.py push --version 0.7.0       (in the checkout of gh-pages)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import error
from release import is_semver

BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


def git(*args, check=True, cwd=None):
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def as_bot(cwd=None):
    git("config", "user.name", BOT[0], cwd=cwd)
    git("config", "user.email", BOT[1], cwd=cwd)


def check_version(version):
    if not is_semver(version):
        error(f"The version must be major.minor.patch, but it is '{version}'")
        return 1
    return 0


def ensure_gh_pages(sha, cwd=None):
    """Creates the empty gh-pages branch, which holds the Maven repository, if there is none yet, and goes back to the
    commit that is being released."""
    cwd = Path(cwd or ".")
    if git("ls-remote", "--exit-code", "--heads", "origin", "gh-pages", check=False, cwd=cwd).returncode == 0:
        return 0
    as_bot(cwd)
    git("switch", "--orphan", "gh-pages", cwd=cwd)
    (cwd / ".nojekyll").touch()
    git("add", ".nojekyll", cwd=cwd)
    git("commit", "-m", "Start the Maven repository", cwd=cwd)
    git("push", "origin", "gh-pages", cwd=cwd)
    # Back to the commit being released. `git switch -` does not work here: the checkout action leaves no previous
    # branch to return to.
    git("switch", "--detach", sha, cwd=cwd)
    return 0


def check_unpublished(version, pages="pages"):
    if (Path(pages) / "maven" / "com" / "lukeneedham" / "common" / version).is_dir():
        error(f"Version {version} is already published. Pick a new one.")
        return 1
    return 0


def push(version, cwd=None):
    """Commits everything that was published into the gh-pages checkout, and pushes it."""
    cwd = Path(cwd or ".")
    as_bot(cwd)
    (cwd / ".nojekyll").touch()
    git("add", "-A", cwd=cwd)
    git("commit", "-m", f"Publish common {version}", cwd=cwd)
    git("push", "origin", "HEAD:gh-pages", cwd=cwd)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ensure-gh-pages")
    for name in ("check-version", "check-unpublished", "push"):
        commands.add_parser(name).add_argument("--version", required=True)
    a = parser.parse_args()
    try:
        if a.command == "check-version":
            code = check_version(a.version)
        elif a.command == "ensure-gh-pages":
            code = ensure_gh_pages(os.environ["GITHUB_SHA"])
        elif a.command == "check-unpublished":
            code = check_unpublished(a.version)
        else:
            code = push(a.version)
    except RuntimeError as e:
        print(f"::error::{e}")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
