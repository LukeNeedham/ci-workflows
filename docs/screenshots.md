# Page screenshots

The README of every app with a UI shows a screenshot of each of its pages. They are **rendered by CI from the
`@Preview` of every `PageContent` composable**, never taken by hand, and committed to `docs/screenshots/`. This page
is the pattern and the setup. The README side is [readme.md](readme.md).

An app with no UI worth showing (the Krillion WebView wrapper) opts out with `screenshots: false` in its
`readme.yml` and skips all of this. Every other app needs it: its `readme.yml` is invalid without screenshots.

## The page pattern

Every page (screen) of an app is **two composables**:

```kotlin
/** The page: gets its ViewModel, collects the state and delegates. No preview, nothing else. */
@Composable
fun HomePage(onOpenSettings: () -> Unit) {
    val viewModel = koinViewModel<HomeViewModel>()
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    HomePageContent(
        state = state,
        onRefresh = viewModel::refresh,
        onOpenSettings = onOpenSettings,
    )
}

/** All of the page's UI: state down, events up. No ViewModel, no Koin. */
@Composable
internal fun HomePageContent(state: HomeUiState, onRefresh: () -> Unit, onOpenSettings: () -> Unit) { /* ... */ }

@Preview
@Composable
private fun HomePageContentPreview() {
    AppTheme { HomePageContent(state = sampleHomeState(), onRefresh = {}, onOpenSettings = {}) }
}
```

- **`XPage`** holds the ViewModel (and one-off event collection, lifecycle effects) and passes state and callbacks on.
  It is **not previewable**: it needs Koin and a ViewModel.
- **`XPageContent`** renders everything and takes only state and callbacks, so it can be previewed with fake state.
- **Each `XPageContent` has a preview named `<Name>PageContentPreview`**, wrapped in the app's `AppTheme`, using
  sample data and no network. The screenshot takes its name from it: `HomePageContentPreview` becomes
  `docs/screenshots/Home.png`. A page with several interesting states has a preview for each
  (`HomeEmptyPageContentPreview` becomes `HomeEmpty.png`).
- The CI renders **every** preview whose function name ends in `PageContentPreview`, and nothing else. Previews of
  smaller composables are for Android Studio only.

## What CI does

The `screenshots` job of [`android_pr.yml`](../.github/workflows/android_pr.yml) runs on every PR, before the
[README](readme.md) job:

1. It skips with a warning if the app has no screenshot test yet (no `roborazzi` in `gradle/libs.versions.toml`),
   or if `readme.yml` says `screenshots: false`.
2. It deletes `docs/screenshots/` and runs `./gradlew recordRoborazziDebug`. The test below renders each page
   preview on the JVM (Robolectric, no emulator) and writes the PNGs. It fails if nothing was rendered.
3. If the PNGs differ from the committed ones, it **commits them to the PR branch** (like the app icon and the
   README): pull the bot's commit before pushing again.

PRs from forks cannot be committed to, so there the job fails if the screenshots are out of date.

## Setting it up in an app

Do this once, in the app's first README PR. Check the current stable versions first; these are the ones last used.

`gradle/libs.versions.toml`:

```toml
[versions]
roborazzi = "1.76.0"
robolectric = "4.17"
composablePreviewScanner = "0.9.3"

[libraries]
compose-ui-tooling = { module = "androidx.compose.ui:ui-tooling" }
compose-ui-tooling-preview = { module = "androidx.compose.ui:ui-tooling-preview" }
compose-ui-test-junit4 = { module = "androidx.compose.ui:ui-test-junit4" }
compose-ui-test-manifest = { module = "androidx.compose.ui:ui-test-manifest" }
roborazzi = { module = "io.github.takahirom.roborazzi:roborazzi", version.ref = "roborazzi" }
roborazzi-compose = { module = "io.github.takahirom.roborazzi:roborazzi-compose", version.ref = "roborazzi" }
robolectric = { module = "org.robolectric:robolectric", version.ref = "robolectric" }
composable-preview-scanner = { module = "io.github.sergio-sastre.ComposablePreviewScanner:android", version.ref = "composablePreviewScanner" }

[plugins]
roborazzi = { id = "io.github.takahirom.roborazzi", version.ref = "roborazzi" }
```

Root `build.gradle.kts`: `alias(libs.plugins.roborazzi) apply false`. `app/build.gradle.kts`:

```kotlin
plugins { alias(libs.plugins.roborazzi) }

android {
    testOptions { unitTests { isIncludeAndroidResources = true } }
}

dependencies {
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)

    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.compose.ui.test.junit4)
    testImplementation(libs.robolectric)
    testImplementation(libs.composable.preview.scanner)
}
```

`app/src/test/kotlin/com/lukeneedham/<app>/PageScreenshotTest.kt` (change the package, twice):

```kotlin
package com.lukeneedham.<app>

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import sergio.sastre.composable.preview.scanner.android.AndroidComposablePreviewScanner
import sergio.sastre.composable.preview.scanner.android.AndroidPreviewInfo
import sergio.sastre.composable.preview.scanner.core.preview.ComposablePreview

/** Renders the preview of every PageContent composable to docs/screenshots/ (docs/screenshots.md in ci-workflows). */
@RunWith(ParameterizedRobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class PageScreenshotTest(private val preview: ComposablePreview<AndroidPreviewInfo>) {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun render() {
        composeRule.setContent { preview() }
        // The tests run in the app module's directory
        composeRule.onRoot().captureRoboImage("../docs/screenshots/${preview.methodName.removeSuffix(SUFFIX)}.png")
    }

    companion object {
        private const val SUFFIX = "PageContentPreview"

        @JvmStatic
        @ParameterizedRobolectricTestRunner.Parameters(name = "{0}")
        fun previews(): List<Array<Any>> =
            AndroidComposablePreviewScanner()
                .scanPackageTrees("com.lukeneedham.<app>")
                .includePrivatePreviews()
                .getPreviews()
                .filter { it.methodName.endsWith(SUFFIX) }
                .map { arrayOf(it) }
    }
}
```

Run `./gradlew recordRoborazziDebug` to see them (the PNGs land in `docs/screenshots/`); CI does the same and commits them.
The fixed size and the JVM renderer keep the output the same from run to run, so a PR that does not change a page's
UI gets no screenshot commit.

## Notes

- Previews must not touch the network, Koin, a ViewModel or the clock. Images from a URL (Coil) render as their
  placeholder, so give the preview a placeholder worth seeing or sample data without remote images.
- Robolectric downloads its Android jar the first time it runs; CI has network.
- Roborazzi and the scanner are updated often: when bumping them, run the task and read the diff of the PNGs.
