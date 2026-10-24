#!/usr/bin/env bash
# Renders the README screenshots of the Android app in the current directory into docs/screenshots/, from the
# <Name>PageContentScreenshot composables of the app (docs/screenshots.md in LukeNeedham/ci-workflows).
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

# Start from nothing, so that a page that was removed or renamed drops out
rm -rf docs/screenshots
./gradlew testDebugUnitTest --tests '*PageScreenshotTest' \
  --init-script "$tools/screenshots.init.gradle" \
  -Pscreenshots.template="$tools/PageScreenshotTest.kt.template" \
  "$@"

if ! ls docs/screenshots/*.png > /dev/null 2>&1; then
  echo "The screenshot test rendered nothing. Every page needs a <Name>PageContentScreenshot composable (docs/screenshots.md)." >&2
  exit 1
fi
