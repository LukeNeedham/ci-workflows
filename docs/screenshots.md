# Page screenshots

The README of every app with a UI shows a screenshot of each of its pages. They are **rendered by CI from a
`<Name>PageContentScreenshot` composable of each page**, never taken by hand, and committed to `docs/screenshots/`.
This page is the pattern and how it works. The README side is [readme.md](readme.md).

An app with no UI worth showing (the Krillion WebView wrapper) opts out with `screenshots: false` in its
`readme.yml` and skips all of this. Every other app needs it: its `readme.yml` is invalid without screenshots.

**The app holds almost nothing for it**: the dependencies, the test and the Gradle setup all live here, in
[`scripts/screenshots/`](../scripts/screenshots), so a version bump reaches every app at once. The app only has its
pages, their screenshot composables and its mock data.

## The page pattern

Every page (screen) of an app is **two composables**, and each has its own previews:

```kotlin
/** The page: gets its ViewModel, collects the state and delegates. No preview, nothing else. */
@Composable
fun HomePage(onOpenSettings: () -> Unit) {
    val viewModel = koinViewModel<HomeViewModel>()
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    HomePageContent(state = state, onRefresh = viewModel::refresh, onOpenSettings = onOpenSettings)
}

/** All of the page's UI: state down, events up. No ViewModel, no Koin. */
@Composable
internal fun HomePageContent(state: HomeUiState, onRefresh: () -> Unit, onOpenSettings: () -> Unit) { /* ... */ }

/** For Android Studio, whatever helps while building the page: empty, loading, error, dark. */
@Preview
@Composable
private fun HomePageContentPreview() {
    AppTheme { HomePageContent(state = HomeUiState(isLoading = false), onRefresh = {}, onOpenSettings = {}) }
}

/** For the README screenshot only: never reuse it for anything else. */
@Preview
@Composable
private fun HomePageContentScreenshot() {
    AppTheme { HomePageContent(state = AppScreenshotMockData.homeState, onRefresh = {}, onOpenSettings = {}) }
}
```

- **`XPage`** holds the ViewModel (and one-off event collection, lifecycle effects) and passes state and callbacks on.
  It is **not previewable**: it needs Koin and a ViewModel.
- **`XPageContent`** renders everything and takes only state and callbacks, so it can be previewed with fake state.
- **`XPageContentPreview`** is the general preview, for development. Nothing renders it in CI: write as many as help.
- **`XPageContentScreenshot`** is the **only** thing CI renders, and is used for nothing else. It shows the page
  at its best, with the data of the app's `AppScreenshotMockData`. Its name gives the file: `HomePageContentScreenshot`
  becomes `docs/screenshots/Home.png`. It is annotated `@Preview` so that the scanner finds it (and so it shows in
  Android Studio next to the others).
- **`AppScreenshotMockData`** is a Kotlin `object` of the app (any package of the app, in `src/main`, usually
  `ui/AppScreenshotMockData.kt`) holding the sample data of the screenshots: one place for the app's fake people,
  titles and states, so the screenshots tell one story. It uses no network, Koin, ViewModel or clock.

## What CI does

The `screenshots` job of [`android_pr.yml`](../.github/workflows/android_pr.yml) runs on every PR, before the
[README](readme.md) job:

1. It skips, with a warning, if the app has no `…PageContentScreenshot` composable yet, or if `readme.yml` says
   `screenshots: false`.
2. It runs [`scripts/render_screenshots.sh`](../scripts/render_screenshots.sh) in the app. The script fetches the
   Gradle init script [`screenshots.init.gradle`](../scripts/screenshots/screenshots.init.gradle) and the test
   [template](../scripts/screenshots/PageScreenshotTest.kt.template), deletes `docs/screenshots/`, and runs
   `./gradlew testDebugUnitTest --tests '*PageScreenshotTest' --init-script …`.
3. The init script, applied only for that run, adds the test dependencies (Roborazzi, Robolectric, the Compose test
   rule, the preview scanner), turns on resources for unit tests, and generates `PageScreenshotTest` from the
   template, for the app's namespace. The test renders every `…PageContentScreenshot` on the JVM (Robolectric native
   graphics, no emulator) at a fixed phone size and writes the PNGs. It fails if nothing was rendered.
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
- A `…PageContentScreenshot` per page and the `AppScreenshotMockData` object.

To see the screenshots without CI, from the app's root (needs the Android SDK):

```
curl -fsSL https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/scripts/render_screenshots.sh | bash
```

## Notes

- Mock data must not touch the network, Koin, a ViewModel or the clock. Images from a URL (Coil) show their
  placeholder offline, or the real image if the run has network, so prefer sample data without remote images.
- Robolectric downloads its Android jar the first time it runs; CI has network.
- **Changing the setup** (a version, the phone size, the test): edit the files in `scripts/screenshots/` here and run
  an app's PR to read the diff of the PNGs.
