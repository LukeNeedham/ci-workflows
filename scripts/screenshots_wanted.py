#!/usr/bin/env python3
"""Says whether the app in the current directory has README screenshots to render (docs/screenshots.md), and writes
`skip=true` to $GITHUB_OUTPUT when it has not.

    python3 screenshots_wanted.py [app_dir]

Every app has at least one screenshot. The only app that renders none is one that has opted out in its readme.yml with
`screenshots: manual` (a WebView wrapper cannot render previews) and has no `screenshot` folder: its screenshots in
docs/screenshots/ are committed by hand and stay as they are. In every other case there is something to render, and
render_screenshots.py fails if the package is missing, empty, without an order.txt or without a screenshot, or if the
app opted out and has a package anyway.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
from check_screenshot_package import manual_screenshots, package_folders


def skip_reason(app_dir):
    """Why there is nothing to render, or None when there is."""
    if manual_screenshots(app_dir) and not package_folders(app_dir):
        return ("readme.yml says `screenshots: manual`, so nothing is rendered: the screenshots committed by hand in "
                "docs/screenshots/ stay as they are. See docs/screenshots.md in LukeNeedham/ci-workflows.")
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
