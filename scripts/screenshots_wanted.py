#!/usr/bin/env python3
"""Says whether the app in the current directory has README screenshots to render (docs/screenshots.md), and writes
`skip=true` to $GITHUB_OUTPUT when it has not.

    python3 screenshots_wanted.py [app_dir]

An app has none to render when it has no screenshot package (a `screenshot/` folder of Kotlin files under app/src):
an app that cannot render previews, such as a WebView wrapper, commits its screenshots into docs/screenshots/ by hand,
and they stay as they are. Every app has screenshots; there is no option to go without.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
from check_screenshot_package import package_files


def skip_reason(app_dir):
    """Why there is nothing to render, or None when there is."""
    if not package_files(app_dir):
        return ("No screenshot package (a screenshot/ folder of Kotlin files in the app's package), so nothing is rendered: "
                "the screenshots in docs/screenshots/ stay as they are, and are committed by hand. "
                "See docs/screenshots.md in LukeNeedham/ci-workflows.")
    return None


def main():
    app_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    why = skip_reason(app_dir)
    if why is None:
        print("The app has screenshots to render")
        return
    print(f"::notice::{why}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("skip=true\n")


if __name__ == "__main__":
    main()
