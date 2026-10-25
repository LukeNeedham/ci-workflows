# Pages: `XPage` and `XPageContent`

**Every page of every app is exactly two composables, named after the page: `XPage` and `XPageContent`, each in its own
file, next to its `XViewModel` and `XUiState`.** This is
the one way to build a screen in every app, so that any app reads like any other, and the previews and the README
screenshots work the same everywhere ([screenshots.md](screenshots.md)).

A **page** is a destination of the navigation: a full screen, one `entry<Route.X>` of the `NavDisplay`. A reusable piece
(a card, a row, a toolbar), and a dialog or a sheet that belongs to a page, is **not** a page: it is a plain
composable in its own file, and a dialog or sheet is drawn by the `XPageContent` of its page.

## The two composables

| | `XPage` | `XPageContent` |
|---|---|---|
| Visibility | public (`fun`) | **`internal`** |
| Job | Connects the page to the app: gets its ViewModel (**`XViewModel`**), collects its state, handles lifecycle and one-off events, and turns navigation into plain lambdas | **All of the page's UI** |
| Takes | What the navigation gives it: the page's arguments and the navigation callbacks (`onBack`, `onOpenDetail`) | The page's `XUiState` and **one lambda per user action** (state down, events up) |
| Never | Draws any UI of its own: it only calls `XPageContent` | Touches a ViewModel, Koin, a `Flow`, a repository or a navigator; starts work of its own; holds business logic |
| Previewable | **No**: it needs Koin and a ViewModel | **Yes, always**: every `XPageContent` has at least one `private` `@Preview` composable, named `Preview`, in the same file, with fake state |

```kotlin
// ui/HomePage.kt: only the page

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

// ui/HomePageContent.kt: the content, and its previews

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
private fun Preview() {
    AppTheme { HomePageContent(state = HomeUiState(isLoading = false), onRefresh = {}, onOpenDetail = {}, onOpenSettings = {}) }
}
```

A page with arguments gets them from its route (`Route.Detail`, below), and passes them on to its ViewModel:

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

- **One ViewModel per page, and it is never shared.** `HomeViewModel` belongs to `HomePage` and to no other page.
  **Shared ViewModels are not allowed, in any form**: not one ViewModel for a whole feature or flow (a
  `PoemBookViewModel` behind a shelf, a book and a search page), not one for the app, not a ViewModel scoped to the
  activity, the navigation graph or a parent so that several pages get the same instance, and not a ViewModel that holds
  or calls another page's ViewModel. State that more than one page needs lives **below** the ViewModels, in a
  repository or other domain/data class (a Koin `single`) that each page's own ViewModel reads and writes: the pages
  then stay in step through that class, and each one is still previewable and testable on its own. A page that needs
  nothing from a ViewModel (no state, no work) has none; it never borrows another page's.
- `HomePage` and `HomePageContent`. **The ViewModel that `HomePage` holds is named `HomeViewModel`**: always
  `XViewModel` for `XPage` (one ViewModel per page), never `HomePageViewModel`, `HomeScreenViewModel` or a name that
  does not match the page; and its state is `HomeUiState`. **Never** `HomeScreen`, `HomeContent`, `HomeView` or
  `HomeScreenContent` for the composables: the suffix is always `Page` and `PageContent`.
- **Each of `XPage`, `XPageContent`, `XViewModel` and `XUiState` lives in its own file, named after it**: `HomePage.kt`,
  `HomePageContent.kt`, `HomeViewModel.kt` and `HomeUiState.kt`, in the page's package. Never two of them in one file
  (not the state in the ViewModel's file, not the page and its content together). **The general previews are in
  `HomePageContent.kt`, with the composable they preview**: every `XPageContent` has at least one, and each is `private`
  in that file, named `Preview` (see [Previews](app-conventions.md#previews) for the name when there are several).
  This is the one exception to "one composable per file" ([app-conventions.md](app-conventions.md#composables-and-previews)).
  A page whose state is a single type of the domain, or that has no state of its own, has no `XUiState.kt`: but a page
  that has a state class never keeps it in another file.
- **The route of `XPage` is `Route.X`** (`HomePage` is `Route.Home`, `PullRequestPage` is `Route.PullRequest`).
  **`Route` is one `sealed interface`, in `Route.kt`, and every page has a member of it**: a `data object`, or a
  `data class` with the page's arguments. `Route.Home` maps to `HomePage`, `Route.Detail` to `DetailPage`; never a
  top-level `HomeNavKey`, `HomeKey`, `HomeRoute` or a bare `Home`. The entry only calls the page, with the navigation as
  lambdas:

  ```kotlin
  // Route.kt
  @Serializable
  sealed interface Route : NavKey {
      @Serializable data object Home : Route
      @Serializable data class Detail(val id: String) : Route
  }

  // in AppNavigation
  entry<Route.Home> {
      HomePage(onOpenSettings = { backStack.add(Route.Settings) }, onOpenDetail = { backStack.add(Route.Detail(it)) })
  }
  entry<Route.Detail> { route -> DetailPage(id = route.id, onBack = { backStack.removeLastOrNull() }) }
  ```

  (With a navigation library that has no `NavKey`, `Route` is the same sealed interface with that library's base type, e.g.
  `Parcelable`.) The `backStack` never goes below `AppNavigation`: neither `XPage` nor `XPageContent` gets it.
- Any README screenshots of a page (a page can have several, or none) are separate from the general previews: previews in the app's `screenshot`
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
3. **Split any shared ViewModel into one per page**: give each page its own `XViewModel` and `XUiState`, holding only what
   that page needs, and move whatever the pages truly share into a repository (a Koin `single`) they all use. Then
   **split the files**: `XPage.kt` (the page only), `XPageContent.kt` (the content and its previews), `XViewModel.kt` and
   `XUiState.kt`, each holding only what its name says. Rename **the ViewModel the page holds to `XViewModel`** (not
   `XPageViewModel`, `XScreenViewModel` or anything else) and its state to `XUiState`, if they differ.
4. **The route of the page is `Route.X`**, a member of the app's one `sealed interface Route` in `Route.kt`, whatever the
   destination is called now (`X`, `XKey`, `XNavKey`, `XRoute`, `XPage` or `XScreen`). A destination called `XPage` has to
   change in any case, because that name is the composable's.
5. Give `XPageContent` its `private` previews in `XPageContent.kt` (at least one), and (if the page deserves a screenshot) a file in the `screenshot` package.
6. Update every reference: tests, docs and the app's `CLAUDE.md` lines that name files.
7. **Not pages:** composables that are only parts of a page keep their names; nothing else gets the `Page` suffix.

A check of the result: `grep -rn "Screen\b\|Screen(" app/src/main` should find no page composables, and every
`entry<…>` of the navigation should be an `entry<Route.X>` that calls exactly one `XPage`.
