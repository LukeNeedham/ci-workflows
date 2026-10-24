# Pages: `XPage` and `XPageContent`

**Every page of every app is exactly two composables, named after the page: `XPage` and `XPageContent`.** This is
the one way to build a screen in every app, so that any app reads like any other, and the previews and the README
screenshots work the same everywhere ([screenshots.md](screenshots.md)).

A **page** is a destination of the navigation: a full screen, one `entry<…>` of the `NavDisplay`. A reusable piece
(a card, a row, a toolbar), and a dialog or a sheet that belongs to a page, is **not** a page: it is a plain
composable in its own file, and a dialog or sheet is drawn by the `XPageContent` of its page.

## The two composables

| | `XPage` | `XPageContent` |
|---|---|---|
| Visibility | public (`fun`) | **`internal`** |
| Job | Connects the page to the app: gets the ViewModel, collects its state, handles lifecycle and one-off events, and turns navigation into plain lambdas | **All of the page's UI** |
| Takes | What the navigation gives it: the page's arguments and the navigation callbacks (`onBack`, `onOpenDetail`) | The page's `XUiState` and **one lambda per user action** (state down, events up) |
| Never | Draws any UI of its own: it only calls `XPageContent` | Touches a ViewModel, Koin, a `Flow`, a repository or a navigator; starts work of its own; holds business logic |
| Previewable | **No**: it needs Koin and a ViewModel | **Yes**: with fake state |

```kotlin
// ui/HomePage.kt

/** The page: connects to the ViewModel and the navigation, and delegates all UI. No preview. */
@Composable
fun HomePage(onOpenSettings: () -> Unit, onOpenDetail: (String) -> Unit) {
    val viewModel = koinViewModel<HomeViewModel>()
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { viewModel.onResume() }
    HomePageContent(
        state = state,
        onRefresh = viewModel::refresh,
        onOpenDetail = onOpenDetail,
        onOpenSettings = onOpenSettings,
    )
}

/** All of the page's UI. `internal`: the screenshots of the app use it too. */
@Composable
internal fun HomePageContent(
    state: HomeUiState,
    onRefresh: () -> Unit,
    onOpenDetail: (String) -> Unit,
    onOpenSettings: () -> Unit,
) { /* the whole screen */ }

/** For Android Studio, whatever helps while building the page: empty, loading, error, dark. */
@Preview
@Composable
private fun HomePageContentPreview() {
    AppTheme { HomePageContent(state = HomeUiState(isLoading = false), onRefresh = {}, onOpenDetail = {}, onOpenSettings = {}) }
}
```

A page with arguments gets them from its navigation key, and passes them on to its ViewModel:

```kotlin
@Composable
fun DetailPage(id: String, onBack: () -> Unit) {
    val viewModel = koinViewModel<DetailViewModel>(parameters = { parametersOf(id) })
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    DetailPageContent(state = state, onBack = onBack, onDelete = viewModel::delete)
}
```

A one-off event of the ViewModel (a snackbar, a share sheet) is collected in `XPage`, which then calls what is
needed, or passes it to `XPageContent` as a plain parameter ([app-conventions.md](app-conventions.md#one-off-events)).

## Names and files

- `HomePage` and `HomePageContent`; the ViewModel `HomeViewModel` and the state `HomeUiState`. **Never** `HomeScreen`,
  `HomeContent`, `HomeView` or `HomeScreenContent`: the suffix is always `Page` and `PageContent`.
- **One file per page, `HomePage.kt`, holding `HomePage`, `HomePageContent` and the general previews**
  (`HomePageContentPreview`: as many as help, named after what they show). The ViewModel and the state are in
  `HomeViewModel.kt`. This is the one exception to "one composable per file" ([app-conventions.md](app-conventions.md#composables-and-previews)).
- The navigation key is named after the destination (`Home`, `Settings`), plus `Key` if the name would clash with a
  class of the app (`PullRequestKey`). The entry only calls the page, with the navigation as lambdas:

  ```kotlin
  entry<Home> { HomePage(onOpenSettings = { backStack.add(Settings) }, onOpenDetail = { backStack.add(Detail(it)) }) }
  entry<Detail> { key -> DetailPage(id = key.id, onBack = { backStack.removeLastOrNull() }) }
  ```

  The `backStack` never goes below `AppNavigation`: neither `XPage` nor `XPageContent` gets it.
- The README screenshots of the pages are separate from the general previews: previews in the app's `screenshot`
  package, each owning its data ([screenshots.md](screenshots.md)).

## Why

State goes down and events go up, so the whole UI of a page is a function of its state: it can be previewed, rendered
for a screenshot and tested without Koin, a ViewModel or a network. All the wiring is in one small place, `XPage`.
Because the split and the names are the same in every app, a person or Claude can open any page of any app and know
where everything is.

## Migrating an existing app

Do this for every page of the app, in the same change as the rest of its migration:

1. A screen composable that gets the ViewModel (`XScreen`, `XRoute`, or the entry itself calling `koinViewModel`)
   becomes **`XPage`**. If the entry in `AppNavigation` holds the ViewModel, state and lifecycle code, move it into `XPage`.
2. The composable that draws the screen (`XContent`, `XScreenContent`, or the body of the old screen) becomes
   **`XPageContent`**, `internal`, taking only state and lambdas. If a screen is not split yet, split it: everything
   that needs the ViewModel, Koin or a `Flow` goes up into `XPage`.
3. Rename the file to `XPage.kt` and the ViewModel and state to `XViewModel` and `XUiState` if they differ.
4. A navigation key that is called `XPage` or `XScreen` is renamed after the destination (`X`, or `XKey`), so that the
   name `XPage` is the composable's.
5. Give `XPageContent` general previews, and (if the page deserves a screenshot) a file in the `screenshot` package.
6. Update every reference: tests, docs and the app's `CLAUDE.md` lines that name files.
7. **Not pages:** composables that are only parts of a page keep their names; nothing else gets the `Page` suffix.

A check of the result: `grep -rn "Screen\b\|Screen(" app/src/main` should find no page composables, and every
`entry<…>` of the navigation should call exactly one `XPage`.
