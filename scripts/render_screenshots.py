#!/usr/bin/env python3
"""Renders the README screenshots of an Android app into docs/screenshots/, from the @Preview composables of the
app's screenshot package (docs/screenshots.md in LukeNeedham/ci-workflows).

    python3 render_screenshots.py [--app DIR] [gradle arguments...]

It checks that the package shares nothing and runs the app's Gradle with an init script that adds the test dependencies
and generates the test (scripts/screenshots/). The test renders into app/build/screenshots/; only when every
screenshot is rendered does that replace docs/screenshots/ (so a failed run leaves the committed ones as they are),
with the package's order.txt next to them, which says the order of the README (HomePage.png, order.txt). Needs the Android SDK. The CI
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
from check_screenshot_package import (ORDER_FILE, manual_screenshots, order_problems, package_dir, package_files,
                                      package_folders, problems, read_order)


def check_package(app_dir):
    """Every screenshot owns its data: prints what is shared and returns False if anything is."""
    ok = True
    for path in package_files(app_dir):
        for number, line in problems(path.read_text()):
            ok = False
            print(f"{path.relative_to(app_dir)}:{number}: `{line}` is shared or not a screenshot. A file of the screenshot "
                  f"package holds only private @Preview composables with their own data inside (docs/screenshots.md).")
    for line in order_problems(app_dir):
        ok = False
        print(f"{line}")
    return ok


def listed(order):
    """The file name of each screenshot of the order: `HomePage` is `HomePage.png`, whatever its position."""
    return {name: f"{name}.png" for name in order}


def render(app_dir, gradle_args):
    """Returns the exit code."""
    if manual_screenshots(app_dir) and package_folders(app_dir):
        print("readme.yml says `screenshots: manual`, but the app has a screenshot package. Remove one: the package "
              "(CI renders the screenshots) or the option (the screenshots are committed by hand). See docs/screenshots.md.",
              file=sys.stderr)
        return 1
    if not package_files(app_dir):
        if package_folders(app_dir):
            why = "The screenshot package has no Kotlin files: it needs a file with a @Preview per screenshot."
        else:
            why = ("The app has no screenshot package, and every app has at least one screenshot: add a screenshot/ folder "
                   "with a Kotlin file, an order.txt and a README. (An app that cannot render previews opts out with "
                   "`screenshots: manual` in readme.yml and commits a screenshot into docs/screenshots/ by hand.)")
        print(f"{why} See docs/screenshots.md.", file=sys.stderr)
        return 1
    if not check_package(app_dir):
        return 1
    rendered = app_dir / "app" / "build" / "screenshots"
    shutil.rmtree(rendered, ignore_errors=True)
    result = subprocess.run(
        [str(app_dir / "gradlew"), "testDebugUnitTest", "--tests", "*PageScreenshotTest",
         "--init-script", str(SCREENSHOTS / "screenshots.init.gradle"),
         f"-Pscreenshots.sources={SCREENSHOTS / 'test'}", *gradle_args],
        cwd=app_dir,
    )
    if result.returncode != 0:
        return result.returncode
    if not list(rendered.glob("*.png")):
        print("The screenshot test rendered nothing. The screenshot package needs a @Preview per screenshot "
              "(docs/screenshots.md).", file=sys.stderr)
        return 1
    order_text = (package_dir(app_dir) / ORDER_FILE).read_text()
    names = listed(read_order(order_text))
    missing = [n for n in names if not (rendered / f"{n}.png").is_file()]
    if missing:
        print(f"The screenshot test did not render {', '.join(missing)}, which {ORDER_FILE} lists.", file=sys.stderr)
        return 1
    # Replace the committed ones as a whole, so that a page that was removed or renamed drops out
    target = app_dir / "docs" / "screenshots"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for name, file in names.items():
        shutil.copyfile(rendered / f"{name}.png", target / file)
    # The README lists the images in this order: the package's own order.txt, which names them
    (target / ORDER_FILE).write_text(order_text)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=".", help="the app's root folder (default: the current folder)")
    args, gradle_args = parser.parse_known_args()
    sys.exit(render(Path(args.app).resolve(), gradle_args))


if __name__ == "__main__":
    main()
