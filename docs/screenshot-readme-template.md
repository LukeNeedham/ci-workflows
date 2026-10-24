# Screenshots

Everything in this package is a **README screenshot**. CI renders every `@Preview` here, with Robolectric on the JVM, into
`docs/screenshots/` and commits the images to the PR branch: never take or edit them by hand. The `README.md` at the
root of the repo shows them. How it works, in full: `docs/screenshots.md` in
[LukeNeedham/ci-workflows](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/screenshots.md).

## One file per page

Each page that gets a screenshot has **one file here, named after the page** (`HomePage.kt`). It holds:

1. the **mock data** of the screenshot, private to the file, and
2. a **`@Preview` composable** that renders the page's `…PageContent` composable with that data.

```kotlin
private val homeState = HomeUiState(/* fake data */)

@Preview
@Composable
private fun HomePageScreenshot() {
    AppTheme { HomePageContent(state = homeState, /* callbacks */) }
}
```

- The image is named after the composable without the trailing `Screenshot`: `HomePageScreenshot` is `HomePage.png`.
  Names must be unique in this package.
- **Several screenshots of one page**: more previews in its file, each with its own mock data.
- **No screenshot for a page**: no file for it.
- **Data shared by several pages** goes in `SharedMockData.kt`, and nothing else does.
- Mock data uses no network, Koin, ViewModel or clock. Remote images (Coil) are replaced by mock images with
  `LocalAsyncImagePreviewHandler` and `LocalInspectionMode`, see `HomePage.kt`.

This package is in `src/debug`, so none of it ships in a release build.
