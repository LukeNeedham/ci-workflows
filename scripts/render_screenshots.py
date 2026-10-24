#!/usr/bin/env python3
"""Renders the README screenshots of an Android app into docs/screenshots/, from the @Preview composables of the
app's screenshot package (docs/screenshots.md in LukeNeedham/ci-workflows).

    python3 render_screenshots.py [--app DIR] [gradle arguments...]

It checks that the package shares nothing, deletes docs/screenshots/, and runs the app's Gradle with an init script
that adds the test dependencies and generates the test (scripts/screenshots/). Needs the Android SDK. The CI
runs it through the `screenshots` action; to run it yourself, clone ci-workflows and point it at an app:

    python3 ci-workflows/scripts/render_screenshots.py --app path/to/app
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCREENSHOTS = Path(__file__).resolve().parent / "screenshots"
sys.path.insert(0, str(SCREENSHOTS))
from check_screenshot_package import package_files, problems


def check_package(app_dir):
    """Every screenshot owns its data: prints what is shared and returns False if anything is."""
    ok = True
    for path in package_files(app_dir):
        for number, line in problems(path.read_text()):
            ok = False
            print(f"{path.relative_to(app_dir)}:{number}: `{line}` is shared or not a screenshot. A file of the screenshot "
                  f"package holds only private @Preview composables with their own data inside (docs/screenshots.md).")
    return ok


def render(app_dir, gradle_args):
    """Returns the exit code."""
    if not package_files(app_dir):
        print("The app has no screenshot package: add a screenshot/ folder of Kotlin files (docs/screenshots.md).", file=sys.stderr)
        return 1
    if not check_package(app_dir):
        return 1
    # Start from nothing, so that a page that was removed or renamed drops out
    shutil.rmtree(app_dir / "docs" / "screenshots", ignore_errors=True)
    result = subprocess.run(
        [str(app_dir / "gradlew"), "testDebugUnitTest", "--tests", "*PageScreenshotTest",
         "--init-script", str(SCREENSHOTS / "screenshots.init.gradle"),
         f"-Pscreenshots.template={SCREENSHOTS / 'PageScreenshotTest.kt.template'}", *gradle_args],
        cwd=app_dir,
    )
    if result.returncode != 0:
        return result.returncode
    if not list((app_dir / "docs" / "screenshots").glob("*.png")):
        print("The screenshot test rendered nothing. The screenshot package needs a @Preview per screenshot "
              "(docs/screenshots.md).", file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=".", help="the app's root folder (default: the current folder)")
    args, gradle_args = parser.parse_known_args()
    sys.exit(render(Path(args.app).resolve(), gradle_args))


if __name__ == "__main__":
    main()
