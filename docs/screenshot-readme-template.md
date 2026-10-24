# Screenshots

Everything in this package is a **README screenshot**. CI renders every `@Preview` here, with Robolectric on the JVM, into
`docs/screenshots/` and commits the images to the PR branch: never take or edit them by hand. The `README.md` at the
root of the repo shows them. How it works, in full: `docs/screenshots.md` in
[LukeNeedham/ci-workflows](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/screenshots.md).

## A file per page with screenshots, a preview per screenshot

A page that has screenshots has **a file here, named after the page** (`HomePage.kt`); not every page needs one. Each
screenshot is a
**private `@Preview` composable that owns its mock data** and renders the page's `…PageContent` composable with it:

```kotlin
@Preview
@Composable
private fun HomePageScreenshot() {
    val state = HomeUiState(/* the fake data of this screenshot */)
    AppTheme { HomePageContent(state = state, /* callbacks */) }
}
```

- The image is named after the composable without the trailing `Screenshot`: `HomePageScreenshot` is `HomePage.png`.
  Names must be unique in this package.
- **Any number of screenshots of a page**: more previews in its file, each with its own data.
- **No screenshot for a page**: no file for it. The app needs at least one screenshot in all, not one per page.

## Nothing is shared

Every screenshot owns its data, so changing one never changes another. Nothing is shared between pages, between the
screenshots of a page, with the general previews of the pages, or with the app. So a file here holds **only private
`@Preview` composables**, with the data and any helper inside their bodies: a top-level `val`, `object` or helper
function would be a way to share, and CI fails on it.

Mock data uses no network, Koin, ViewModel or clock. Remote images (Coil) are replaced by mock images with
`LocalAsyncImagePreviewHandler` and `LocalInspectionMode`, see `HomePage.kt`.

This package is in `src/debug`, so none of it ships in a release build.
