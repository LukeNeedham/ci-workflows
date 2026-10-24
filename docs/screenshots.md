# Page screenshots

The README of every app with a UI shows screenshots of its pages. They are **rendered by CI from the `@Preview`
composables of the app's `screenshot` package**, never taken by hand, and committed to `docs/screenshots/`. This page
is the pattern and how it works. The README side is [readme.md](readme.md).

An app with no UI worth showing (the Krillion WebView wrapper) opts out with `screenshots: false` in its
`readme.yml` and skips all of this. Every other app needs at least one screenshot: its `readme.yml` is invalid without.

**The app holds almost nothing for it**: the dependencies, the test and the Gradle setup live here, in
[`scripts/screenshots/`](../scripts/screenshots), so a version bump reaches every app at once. The app only has its
pages and its `screenshot` package.

## The page pattern

Every page (screen) of an app is **two composables**:

```kotlin
/** The page: gets its ViewModel, collects the state and delegates. No preview, nothing else. */
@Composable
fun HomePage(onOpenSettings: () -> Unit) {
    val viewModel = koinViewModel<HomeViewModel>()
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    HomePageContent(state = state, onRefresh = viewModel::refresh, onOpenSettings = onOpenSettings)
}

/** All of the page's UI: state down, events up. No ViewModel, no Koin. `internal`, so the screenshots can use it. */
@Composable
internal fun HomePageContent(state: HomeUiState, onRefresh: () -> Unit, onOpenSettings: () -> Unit) { /* ... */ }

/** For Android Studio, whatever helps while building the page: empty, loading, error, dark. */
@Preview
@Composable
private fun HomePageContentPreview() {
    AppTheme { HomePageContent(state = HomeUiState(isLoading = false), onRefresh = {}, onOpenSettings = {}) }
}
```

- **`XPage`** holds the ViewModel (and one-off event collection, lifecycle effects) and passes state and callbacks on.
  It is **not previewable**: it needs Koin and a ViewModel.
- **`XPageContent`** renders everything and takes only state and callbacks, so it can be previewed with fake state.
- **`XPageContentPreview`**, next to the page, are the general previews, for development. Nothing renders them in CI.

## The `screenshot` package

All the screenshot code is in **one package, `<the app's package>.screenshot`**, in `src/debug` (so that the mock data
is not in the release APK; `internal` composables of `src/main` are visible from it). **One file per page that gets a
screenshot**, named after the page. The file holds the page's screenshots, and **each screenshot is one private
`@Preview` composable that owns its mock data and renders the page's content with it**:

```kotlin
// screenshot/HomePage.kt
package com.lukeneedham.<app>.screenshot

/** Rendered by CI to docs/screenshots/HomePage.png. */
@Preview
@Composable
private fun HomePageScreenshot() {
    val state = HomeUiState(isLoading = false, items = listOf(/* the fake data of this screenshot */))
    AppTheme { HomePageContent(state = state, onRefresh = {}, onOpenSettings = {}) }
}
```

- **Every `@Preview` in the package is a screenshot, and nothing outside it is.** The image takes the name of the
  composable without a trailing `Screenshot`: `HomePageScreenshot` becomes `docs/screenshots/HomePage.png`. Names must be
  unique across the package (the test fails otherwise); the README lists the images in alphabetical order.
- **Several screenshots of one page** are several previews in its file (`HomePageScreenshot`,
  `HomeEmptyPageScreenshot`). **A page with no file has no screenshot**: leave out the pages that are not worth showing.
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

The `screenshots` job of [`android_pr.yml`](../.github/workflows/android_pr.yml) runs on every PR, before the
[README](readme.md) job:

1. It skips, with a warning, if the app has no `screenshot` package with Kotlin files yet, or if `readme.yml` says
   `screenshots: false`.
2. It runs [`scripts/render_screenshots.sh`](../scripts/render_screenshots.sh) in the app. The script fetches the
   Gradle init script [`screenshots.init.gradle`](../scripts/screenshots/screenshots.init.gradle), the test
   [template](../scripts/screenshots/PageScreenshotTest.kt.template) and the
   [package check](../scripts/screenshots/check_screenshot_package.py), fails if the package shares anything,
   deletes `docs/screenshots/`, and runs
   `./gradlew testDebugUnitTest --tests '*PageScreenshotTest' --init-script …`.
3. The init script, applied only for that run, adds the test dependencies (Roborazzi, Robolectric, the Compose test
   rule, the preview scanner), turns on resources for unit tests, and generates `PageScreenshotTest` from the
   template, for the app's namespace. The test renders every preview of the `screenshot` package on the JVM
   (Robolectric native graphics, no emulator) at a fixed phone size and writes the PNGs. It fails if nothing was rendered.
4. If the PNGs differ from the committed ones, the job **commits them to the PR branch** (like the app icon and the
   README): pull the bot's commit before pushing again.

PRs from forks cannot be committed to, so there the job fails if the screenshots are out of date. The job runs on a
Temurin JDK, because the Zulu build that `setup-java` resolves to is a CRaC build under which the Robolectric native
runtime aborted at random.

## In the app

Only this, once:

- `androidx.compose.ui:ui-tooling-preview` as an `implementation` dependency (for `@Preview`), and `ui-tooling` as
  `debugImplementation` for Android Studio. Nothing else: no Roborazzi, Robolectric or test dependencies, no plugin,
  no test class.
- The `screenshot` package, with its README.

To see the screenshots without CI, from the app's root (needs the Android SDK):

```
curl -fsSL https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/scripts/render_screenshots.sh | bash
```

## Notes

- Robolectric downloads its Android jar the first time it runs; CI has network.
- **Changing the setup** (a version, the phone size, the test): edit the files in `scripts/screenshots/` here and run
  an app's PR to read the diff of the PNGs.
