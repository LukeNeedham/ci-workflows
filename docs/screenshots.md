# Page screenshots

The README of every app with a UI shows screenshots of the app: of the pages worth showing, one or several for each. They are **rendered by CI from the `@Preview`
composables of the app's `screenshot` package**, never taken by hand, and committed to `docs/screenshots/`. This page
is the pattern and how it works. The README side is [readme.md](readme.md).

**Every app has at least one screenshot, and CI fails without one.** A missing `screenshot` package, an empty one (no
Kotlin files), one without an `order.txt` or without a `@Preview`, and an app with no screenshot at all each fail the
`screenshots` job, with a message that says what is missing. The only exception is an app that cannot render previews,
such as the Krillion WebView wrapper (no Compose, so no `@Preview`): it has no `screenshot` folder at all and commits at
least one screenshot into `docs/screenshots/` by hand, and CI leaves it alone.

**The app holds almost nothing for it**: the dependencies, the test and the Gradle setup live here, in
[`scripts/screenshots/`](../scripts/screenshots), so a version bump reaches every app at once. The app only has its
pages and its `screenshot` package.

## The page pattern

The screenshots rely on how every page is built, defined in **[pages.md](pages.md)**: each page is an `XPage` (it gets
the ViewModel; no preview) and an `internal`, stateless `XPageContent` (all the UI, with the general previews
`XPageContentPreview`). A screenshot renders the `XPageContent` of its page with mock data, and is separate from the
general previews.

## The `screenshot` package

All the screenshot code is in **one package, `<the app's package>.screenshot`**, in `src/debug` (so that the mock data
is not in the release APK; `internal` composables of `src/main` are visible from it). **A page that has screenshots has
a file here, named after the page; not every page needs one, and a page can have several screenshots.** Each file
holds the screenshots of its page, and **each screenshot is one private `@Preview` composable that owns its mock data
and renders the page's content with it**:

```kotlin
// screenshot/HomePage.kt
package com.lukeneedham.<app>.screenshot

/** Rendered by CI to docs/screenshots/<position in order.txt>-HomePage.png. */
@Preview
@Composable
private fun HomePageScreenshot() {
    val state = HomeUiState(isLoading = false, items = listOf(/* the fake data of this screenshot */))
    AppTheme { HomePageContent(state = state, onRefresh = {}, onOpenSettings = {}) }
}
```

- **Every `@Preview` in the package is a screenshot, and nothing outside it is.** Its name is the name of the
  composable without a trailing `Screenshot`: `HomePageScreenshot` is `HomePage`. Names must be unique across the
  package (the test fails otherwise).
- **The package has an `order.txt`** next to its Kotlin files: the screenshots in the order the README shows them, one
  name per line, with blank lines and `#` comments allowed:

  ```
  # the order of the README: a user's first look to the details
  HomePage
  PullRequestPage
  SettingsPage
  ```

  Every screenshot is listed once and nothing else is (the render fails otherwise, naming the difference). CI numbers the
  images by their position, `docs/screenshots/01-HomePage.png`, `02-PullRequestPage.png`, and the README lists them in that
  order. To reorder, move a line; there are no numbers to maintain in the Kotlin names. A new screenshot is a new
  preview and a new line.
- **A page can have any number of screenshots**: several previews in its file, each with its own data
  (`HomePageScreenshot`, `HomeEmptyPageScreenshot`), as many as are worth showing. **A page can have none**: a page
  with no file has no screenshot, so leave out the pages that are not worth showing. The app needs at least one
  screenshot in all, not one per page, and always at least one.
- **Nothing is shared.** Every screenshot owns its data, so that changing one never changes another, and the
  screenshots are independent of the app and of the general previews:
  - not between pages, and not between the screenshots of one page: a second screenshot has its own copy of what it
    shows, even if it looks the same;
  - not with the general previews (`XPageContentPreview`), nor with any sample data of the app.

  So a file holds **nothing at the top level but private `@Preview` composables** without parameters, with the data and
  any helper inside the body. A top-level `val`, `object` or helper function, or a non-private declaration, would be a way
  to share, and **fails the `screenshots` job** (`scripts/screenshots/check_screenshot_package.py`).
- Mock data uses no network, Koin, ViewModel or clock. Images from a URL (Coil) cannot be fetched on CI: wrap the
  screenshot in `LocalInspectionMode provides true` and a `LocalAsyncImagePreviewHandler` (Coil's mock images), so the
  render never depends on the network.
- **The package has a `README.md`** that explains this to whoever opens the folder, written from
  [`screenshot-readme-template.md`](screenshot-readme-template.md).

## What CI does

The screenshots are made by **two jobs of [`android_pr.yml`](../.github/workflows/android_pr.yml)**, so that the app is
compiled once: the `build` job renders them right after the APK, and the `screenshots` job commits them.

1. In the `build` job ([`android_pr_build.yml`](../.github/workflows/android_pr_build.yml)), after the APK is built and
   published (so the APK is never held up by the screenshots):
   - [`screenshots_wanted.py`](../scripts/screenshots_wanted.py) skips the rendering, with a notice, only for an app with
     no `screenshot` folder at all that has committed screenshots in `docs/screenshots/`: they stay. Everything else is
     rendered, and the render fails for a package that is missing, empty or incomplete.
   - [`render_screenshots.py`](../scripts/render_screenshots.py) fails if the package shares anything, and runs `./gradlew testDebugUnitTest --tests '*PageScreenshotTest' --init-script …`, with the
     Gradle init script [`screenshots.init.gradle`](../scripts/screenshots/screenshots.init.gradle) and the test
     [template](../scripts/screenshots/PageScreenshotTest.kt.template) next to it.
   - The init script, applied only for that run, adds the test dependencies (Roborazzi, Robolectric, the Compose test
     rule, the preview scanner), turns on resources for unit tests, and generates `PageScreenshotTest` from the template,
     for the app's namespace. **That test is the only unit test of the run**: the app's own unit tests are left out of the
     source set, so a broken test of the app cannot fail the screenshots. It renders every preview of the `screenshot`
     package on the JVM (Robolectric native graphics, no emulator) at a fixed phone size and writes the PNGs. It fails if
     nothing was rendered. The test always runs (never up to date, never from the build cache), and writes into
     `app/build/screenshots/`; **only once all of them are rendered does the script replace `docs/screenshots/` with them**,
     so a failed run leaves the committed screenshots as they are.
   - The PNGs are uploaded as the artifact `screenshots`. A failure of the rendering **does not fail the build** (the APK is
     fine); the `screenshots` job fails instead.
2. The `screenshots` job ([`.github/actions/screenshots`](../.github/actions/screenshots/action.yml)) is skipped when
   nothing was rendered. Otherwise it checks out the PR branch, replaces `docs/screenshots/` with the artifact and
   [`commit_generated.py`](../scripts/commit_generated.py) (shared with the app icon and README actions) **commits the PNGs
   to the PR branch** if they differ from the committed ones: pull the bot's commit before pushing again. If the rendering
   failed, the job fails and points at the `Render the screenshots` step of the build job.

The images are rendered from the merge commit that the build checks out, and committed to the PR branch.

PRs from forks cannot be committed to, so there the job fails if the screenshots are out of date. The build runs on a
Temurin JDK (the shared setting), because the Zulu build that `setup-java` resolves to is a CRaC build under which the
Robolectric native runtime aborted at random.

## In the app

Only this, once:

- `androidx.compose.ui:ui-tooling-preview` as an `implementation` dependency (for `@Preview`), and `ui-tooling` as
  `debugImplementation` for Android Studio. Nothing else: no Roborazzi, Robolectric or test dependencies, no plugin,
  no test class.
- The `screenshot` package, with its README.

To see the screenshots without CI (needs the Android SDK), clone ci-workflows once and point the script at the app:

```
git clone --depth 1 https://github.com/LukeNeedham/ci-workflows /tmp/ci-workflows
python3 /tmp/ci-workflows/scripts/render_screenshots.py --app path/to/app
```

## Notes

- Robolectric downloads its Android jar the first time it runs; CI has network.
- **Changing the setup** (a version, the phone size, the test): edit the files in `scripts/screenshots/` here and run
  an app's PR to read the diff of the PNGs.
