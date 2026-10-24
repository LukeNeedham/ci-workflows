#!/usr/bin/env bash
# Renders the README screenshots of the Android app in the current directory into docs/screenshots/, from the
# @Preview composables of the app's screenshot package (docs/screenshots.md in LukeNeedham/ci-workflows).
#
#   curl -fsSL https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/scripts/render_screenshots.sh | bash
#
# Extra arguments go to Gradle. TOOLS_REF (default main) is the branch or tag of ci-workflows to take the
# Gradle init script and the test template from: set it only to try a change to them.
set -euo pipefail

base="https://raw.githubusercontent.com/LukeNeedham/ci-workflows/${TOOLS_REF:-main}/scripts/screenshots"
tools="$(mktemp -d)"
curl -fsSL "$base/screenshots.init.gradle" -o "$tools/screenshots.init.gradle"
curl -fsSL "$base/PageScreenshotTest.kt.template" -o "$tools/PageScreenshotTest.kt.template"
curl -fsSL "$base/check_screenshot_package.py" -o "$tools/check_screenshot_package.py"

# Every screenshot owns its data: nothing in the package may be shared (docs/screenshots.md)
files="$(find app/src -path '*/screenshot/*.kt' -not -path '*/build/*')"
if [ -n "$files" ]; then
  # shellcheck disable=SC2086
  python3 "$tools/check_screenshot_package.py" $files
fi

# Start from nothing, so that a page that was removed or renamed drops out
rm -rf docs/screenshots
./gradlew testDebugUnitTest --tests '*PageScreenshotTest' \
  --init-script "$tools/screenshots.init.gradle" \
  -Pscreenshots.template="$tools/PageScreenshotTest.kt.template" \
  "$@"

if ! ls docs/screenshots/*.png > /dev/null 2>&1; then
  echo "The screenshot test rendered nothing. The app needs a screenshot package with a @Preview per screenshot (docs/screenshots.md)." >&2
  exit 1
fi
