#!/usr/bin/env python3
"""Says whether the app in the current directory has README screenshots to render (docs/screenshots.md), and writes
`skip=true` to $GITHUB_OUTPUT when it has not.

    python3 screenshots_wanted.py [app_dir]

Every app has at least one screenshot. The only app that renders none is one with no `screenshot` folder at all under
app/src that has committed its screenshots into docs/screenshots/ by hand (a WebView wrapper cannot render previews):
they stay as they are. In every other case there is something to render, and render_screenshots.py fails if the package
is missing, empty, without an order.txt or without a screenshot, or if the app has no screenshot of any kind.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
from check_screenshot_package import committed_screenshots, package_folders


def skip_reason(app_dir):
    """Why there is nothing to render, or None when there is."""
    if not package_folders(app_dir) and committed_screenshots(app_dir):
        return ("No screenshot package, so nothing is rendered: the screenshots committed by hand in docs/screenshots/ "
                "stay as they are. See docs/screenshots.md in LukeNeedham/ci-workflows.")
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
