# App shell: `MainActivity`, `Root`, `AppNavigation`, `Router`

**This is the one place that defines how every app is put together around its pages: the activity, the root composable and
the navigation.** A new app is built this way from the start ([new-app.md](new-app.md)), and an existing app is migrated to it
([below](#migrating-an-existing-app)). Other docs link here and never repeat it. The pages themselves (`XPage`,
`XPageContent`, `XViewModel`) are in [pages.md](pages.md).

## The names

**The names are fixed in every app**, each in its own file named after it (`MainActivity.kt`, `Root.kt`, ...), so any app
reads like any other:

| Name | What it is |
|---|---|
| `App` | The `Application` class: starts Koin and the library. |
| `MainActivity` | **The one activity, always with this name**: never `HomeActivity`, `AppActivity` or a second activity, and no fragments. It only calls `setContent { Root() }`. |
| `Root` | The one composable `MainActivity` calls: `AppTheme`, `ProvideDebugSettings` and the other app-wide providers, then `AppNavigation()`. Never `App`, `AppRoot`, `MainScreen` or `MainContent`. |
| `AppNavigation` | Owns the `backStack` and the `NavDisplay`, with `routeEntryProvider`. It is the only composable that calls `NavDisplay`, and `Root` the only one that calls it. |
| `Router` | The exhaustive `when (route)` and the common navigation actions (`navigateTo`, `onBack`); the only place that calls `XPage`s. Not a page: it is never called `RoutePage`, and has no `XPageContent` or ViewModel. |
| `Route` | The one `sealed interface Route : NavKey`, in `Route.kt`; every page has a member of it ([pages.md](pages.md#names-and-files)). |
| `AppTheme` | The app's own theme ([app-conventions.md](app-conventions.md#theme)). |

No other composable sets up the theme, the providers or the navigation, and none of these has a variant name (`MainRoot`,
`AppRouter`, `NavHost`).

## The code

```kotlin
// MainActivity.kt
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { Root() }
    }
}

// Root.kt
@Composable
fun Root() {
    AppTheme {
        ProvideDebugSettings(theme = AppTheme.current.toDebugTheme()) {
            AppNavigation()
        }
    }
}

// Route.kt
@Serializable
sealed interface Route : NavKey {
    @Serializable data object Home : Route
    @Serializable data class Detail(val id: String) : Route
}

// AppNavigation.kt
@Composable
fun AppNavigation() {
    val backStack = rememberNavBackStack(Route.Home)
    NavDisplay(
        backStack = backStack,
        onBack = { backStack.removeLastOrNull() },
        entryProvider = { key -> routeEntryProvider(backStack, key) },
    )
}

private fun routeEntryProvider(backStack: NavBackStack<NavKey>, key: NavKey): NavEntry<NavKey> {
    val route = key as Route
    return NavEntry(route) {
        Router(backStack, route)
    }
}

// Router.kt
@Composable
fun Router(backStack: NavBackStack<NavKey>, route: Route) {
    // The common actions are defined once here, never repeated in each branch
    fun navigateTo(target: Route) { backStack.add(target) }
    fun onBack() { backStack.removeLastOrNull() }

    when (route) { // exhaustive: no `else`
        Route.Home -> HomePage(onOpenDetail = { navigateTo(Route.Detail(it)) })
        is Route.Detail -> DetailPage(id = route.id, onBack = ::onBack)
    }
}
```

## The rules

- **`MainActivity` and `Root`.** `MainActivity` has nothing but `setContent { Root() }`. `Root` sets up everything the UI
  sits in, in this order: `AppTheme`, then `ProvideDebugSettings`
  ([using-the-library.md](using-the-library.md#wrap-the-ui-in-providedebugsettings)) and the other app-wide providers, then
  `AppNavigation()`.
- **The entry provider is type exhaustive.** Every route is a member of the one `sealed interface Route`, so the entry
  provider is a plain function and `Router` has a `when (route)` over it, **never the `entryProvider { entry<...> { } }`
  DSL**: the DSL does not know the routes are sealed, so a route without an entry only fails at runtime. With the `when`,
  adding a `Route` member without a branch is a compile error. **No `else` branch**, ever, as it would turn that compile
  error back into a runtime one.
- **The common navigation actions are functions of `Router`** (`navigateTo(route)`, `onBack()`, and any other the app
  repeats, e.g. `navigateToAndClear(route)`), so the branches only name them (`onBack = ::onBack`,
  `{ navigateTo(Route.Detail(it)) }`) and no page repeats `backStack.add(...)` or `backStack.removeLastOrNull()`. The
  `backStack` is used only in those functions, and never goes below the `Router`: neither `XPage` nor `XPageContent` gets it.
- **A branch only calls the page**, with the navigation as lambdas. A route that needs its own `NavEntry` options
  (`metadata`, e.g. a dialog scene) cannot share the one `NavEntry` in `routeEntryProvider` and builds its own.
- With a navigation library that has no `NavKey`, `Route` is the same sealed interface with that library's base type, e.g.
  `Parcelable`.

## Migrating an existing app

A new app is created with the shell above. **An existing app gets the same shell in its migration PR**, together with its
pages ([pages.md](pages.md#migrating-an-existing-app)). Rename with the IDE (or `git mv` and a project-wide replace), and
update what a rename misses: the `AndroidManifest.xml` (`android:name` of the application and of the activity), shortcuts,
deep links, tests, and the lines of the app's `CLAUDE.md` that name files.

1. **One activity, `MainActivity`.** The launcher activity becomes `MainActivity` (`MainActivity.kt`) whatever it is called
   now. Every other activity and every fragment becomes a page with a `Route.X` member (`Route.kt`), reached through the
   `Router`. Its `onCreate` ends in `setContent { Root() }` and holds nothing else in it.
2. **`Root`.** Whatever composable `setContent` wraps now (`AppRoot`, `MainScreen`, `MyApp`, `App`) is renamed `Root`
   (`Root.kt`). The theme (`AppTheme`), `ProvideDebugSettings` and the other app-wide providers that sit in `MainActivity`
   or in other composables move into it, and it ends in `AppNavigation()`. A `MaterialTheme` is replaced by `AppTheme`
   ([app-conventions.md](app-conventions.md#theme)).
3. **`AppNavigation`, `Router`, `Route`.** An app already on Navigation 3 moves the `rememberNavBackStack` and the
   `NavDisplay` into `AppNavigation` (`AppNavigation.kt`); replaces the `entryProvider { entry<...> { } }` DSL with
   `routeEntryProvider` and the exhaustive `Router` (`Router.kt`); and moves the `backStack.add(...)` and
   `removeLastOrNull()` of the branches into `navigateTo` and `onBack`. An app on another library (Navigation Compose
   `NavHost`, a hand-made navigator) migrates to Navigation 3: the destinations become the members of the one
   `sealed interface Route : NavKey`, the `NavHost` becomes `AppNavigation`, and its `composable(...)` entries become the
   branches of the `Router`.
4. **`App`.** The `Application` class becomes `App` (`App.kt`), and the manifest's `android:name` follows.
5. **Check.** The first finds nothing, the other two find only `MainActivity.kt`:

   ```sh
   grep -rn "NavHost(\|entryProvider {\|MaterialTheme" app/src/main
   grep -rln "ComponentActivity()" app/src/main      # only MainActivity.kt
   grep -rn "setContent" app/src/main                # only MainActivity.kt, and it is `setContent { Root() }`
   ```
