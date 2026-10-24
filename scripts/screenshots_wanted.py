#!/usr/bin/env python3
"""Says whether the app in the current directory has README screenshots to render (docs/screenshots.md), and writes
`skip=true` to $GITHUB_OUTPUT when it has not.

    python3 screenshots_wanted.py [app_dir]

An app has none to render when its readme.yml says `screenshots: false` (no UI worth showing), or when it has no
screenshot package yet (a `screenshot/` folder of Kotlin files under app/src).
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
from check_screenshot_package import package_files


def skip_reason(app_dir):
    """(why, is_warning) when there is nothing to render, or None when there is."""
    readme = app_dir / "readme.yml"
    if readme.is_file() and re.search(r"^screenshots:[ \t]*false\b", readme.read_text(), re.M):
        return "readme.yml says screenshots: false", False
    if not package_files(app_dir):
        return ("No screenshot package yet (a screenshot/ folder of Kotlin files in the app's package). "
                "See docs/screenshots.md in LukeNeedham/ci-workflows."), True
    return None


def main():
    app_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    skip = skip_reason(app_dir)
    if skip is None:
        print("The app has screenshots to render")
        return
    why, warning = skip
    print(f"::warning::{why}" if warning else why)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("skip=true\n")


if __name__ == "__main__":
    main()
