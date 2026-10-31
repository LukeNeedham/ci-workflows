# The convention checks

**CI fails a pull request in any app that breaks the architecture, naming, page, ViewModel, UiState, sheet, preview or
screenshot rules.** It is one check, the `conventions` job of [`android_pr.yml`](../.github/workflows/android_pr.yml), which
runs [`scripts/check_conventions.py`](../scripts/check_conventions.py) on the app's sources. It reads the Kotlin files with no
Gradle build and no JDK, so it takes seconds, runs alongside the build and needs nothing in the app: every app gets it
from this repo, like the rest of its CI. The rules are the ones of [new-app.md](new-app.md), [app-shell.md](app-shell.md),
[pages.md](pages.md), [app-conventions.md](app-conventions.md) and [screenshots.md](screenshots.md); this page is the list of what
is checked, by id.

Each violation is an error annotation on the line (`::error file=…,line=…,title=VM-2::…`) and a row in the run summary,
and any violation fails the job. There is no warning mode.

## The rules

### Koin and naming

The architecture rules of [new-app.md](new-app.md#6-app-architecture) and [app-shell.md](app-shell.md#the-names). They are checked
in the tests too, except `DI-2`..`DI-6`, since a test may build a Koin module of its own.

| Id | Rule |
|---|---|
| `DI-1` | The app uses Koin, and has a `KoinModules.kt` |
| `DI-2` | `KoinModules.kt` and `KoinQualifier.kt` hold only their `object` (no `const val`, helper or second class), in a package ending `.di`; an `object KoinModules` / `KoinQualifier` is in a file of that name; the names `KoinModule` and `KoinQualifiers` are wrong |
| `DI-3` | A `module { }` is declared in an object of a file in a `di` folder (`KoinModules`, or a feature object it uses), never at the top level |
| `DI-4` | A binding only wires. Not allowed in it: a string or a number, a block inside the binding (a builder or a DSL such as `HttpClient(OkHttp) { ... }`), an operator (`+`, `*`), `if` / `when` / `val`, chained calls (`Builder().cache(...).build()`, `androidContext().cacheDir`). Allowed: `get()` (with `named(KoinQualifier.X)`), `androidContext()`, the runtime parameters of a `viewModel { (id: String) -> ... }` and names; `get<T>().member()` is the one chain that is |
| `DI-5` | A qualifier is a constant of `KoinQualifier`: `named("...")` is not (the object itself may build its names) |
| `DI-6` | A `modules(...)` call outside `di/` uses `KoinModules` |
| `NAME-1` | A name that a file declares (class, object, interface, typealias, function, property, parameter), or a file name, has no acronym in capitals: `IosSdkManager` for `iOSSDKManager`, `userId` for `userID` ([app-conventions.md](app-conventions.md#naming)) |

The acronym rule in detail: a run of capitals that ends a name, or comes before a digit, is an acronym (`userID`, `newPP`,
`UTF8Decoder`). A run of three or more before a lower case letter is an acronym followed by a word (`HTTPClient`: `HTTP` and
`Client`). A run of **two** before a lower case letter is a one-letter word and a word (`parsesAUri`, `selectedXOffset`), and
passes. `UPPER_SNAKE_CASE` constants pass. The names the code only uses (`JSONArray`, `IOException`, `Dispatchers.IO`) are not
looked at, and neither is an `override`, whose name the supertype fixed. For the rare name that has to stay, put
`@Suppress("AcronymNaming")` on its line or the one above (or a `lint:ignore NAME-1` with its reason).

### Top-level functions

| Id | Rule |
|---|---|
| `TOP-1` | The only functions at the top level of a file are extension functions (`fun String?.orDash()`, a function-type receiver too) and `@Composable` functions, previews included, and the ones the platform needs there: `expect` / `actual` / `external` functions and `main`; any other, `private` ones too, is a member of a class or an `object` ([app-conventions.md](app-conventions.md#no-top-level-functions)). The tests are not checked. Properties and constants are not covered. That an extension is generic (a standard or library type, usable in any app) is not checked: it is for the review |

### Pages and files

| Id | Rule |
|---|---|
| `PAGE-1` | `XPage`, `XPageContent`, `XViewModel` and `XUiState` are each in their own file, named after them (`HomePage.kt`, …). A file named after one of them declares it, and no other non-`private` top-level declaration: nested types and `private` helpers are fine, a sibling `HomeEvent` is not |
| `PAGE-2` | Every `XPage` has an `XPageContent` in the same package, and every `XPageContent` has an `XPage` |
| `PAGE-3` | `XPage` is public. `XPageContent` is `internal` (not public, not `private`) |
| `PAGE-4` | A page composable is never `XScreen` or `XScreenContent`, and `XView` or `XContent` of a page `X` is `XPageContent`. A ViewModel is never `XPageViewModel` or `XScreenViewModel` |
| `PAGE-5` | `XPage` calls `XPageContent` exactly once, has no `@Preview` in its file, and draws no UI of its own: its file imports nothing from `androidx.compose.foundation` or `androidx.compose.material*`. (That last part is a heuristic for "draws nothing" and the one most likely to need a `lint:ignore`) |
| `PAGE-6` | `XPageContent` is stateless: it mentions no ViewModel, Koin, `Flow` (or `collectAs…`), repository or navigator (`NavController`, `NavBackStack`, `backStack`), and when the page has an `XUiState` it takes one as a parameter |

### ViewModels: one per page, never shared

| Id | Rule |
|---|---|
| `VM-1` | A ViewModel is requested (`koinViewModel`, `viewModel`, `getViewModel`, `hiltViewModel`, `viewModels`, …) only inside an `XPage`, and only as `XViewModel`, with the type written out: `koinViewModel<HomeViewModel>()` or `val vm: HomeViewModel = koinViewModel()`. A Koin definition (`viewModel { … }`) is not a request |
| `VM-2` | A ViewModel class is requested by one page only. Two pages that ask for the same one are both reported |
| `VM-3` | No ViewModel is scoped to something several pages share: no `activityViewModel`, `sharedViewModel`, `viewModelStoreOwner =`, `LocalViewModelStoreOwner`, `ownerProducer`, and no owner, back stack entry, activity or navigation graph in the arguments of a request |
| `VM-4` | A ViewModel is never a Koin `single`, `factory` or `scoped` definition (`single { HomeViewModel(get()) }`, `singleOf(::HomeViewModel)`): a `single` is one instance for everyone. Use `viewModelOf` or `viewModel { }` |
| `VM-5` | A ViewModel holds no other ViewModel: none in its constructor, properties or body (`get<OtherViewModel>()`). A base class in its supertypes is not holding |
| `VM-6` | A concrete ViewModel (a class with a ViewModel supertype that is not `abstract` or `sealed`) is named `XViewModel` and has an `XPage` in its package |
| `VM-7` | A ViewModel declares no `SharedFlow` or `MutableSharedFlow`: a one-off event goes through a `Channel` exposed with `receiveAsFlow()` ([app-conventions.md](app-conventions.md#one-off-events)) |
| `VM-8` | No `AndroidViewModel`, in the tests too: a ViewModel extends `ViewModel` and takes what it needs as constructor parameters, never an `Application` or `Context` |

**Only an `XPage` requests a ViewModel**, so `Root` (the root composable, which is not a page) does not. A state-driven `Root`
holds a `RootCoordinator` instead: a plain class, registered with `single { }` and obtained with `koinInject()`
([app-shell.md](app-shell.md#a-state-driven-root)). The checks do not look at it: it is not a ViewModel.

State that pages share lives below the ViewModels, in a repository (a Koin `single`) that each page's own ViewModel uses
([pages.md](pages.md#names-and-files)).

### UiState

| Id | Rule |
|---|---|
| `UI-1` | An `XUiState` has an `XPage` in its package |
| `UI-2` | An `XUiState` is immutable: no `var`, no `MutableList`, `ArrayList`, `mutableStateOf` or other mutable type. Change it with `copy` |
| `UI-3` | An `XUiState` is plain data: it holds no `Flow`, `StateFlow`, `SharedFlow` or `Channel` |

### Bottom sheets

A bottom sheet is `XSheet` (the container: the sheet itself, its scrim, state, animation) that puts `XSheetContent` (what it shows,
in its own file with its own preview) in it ([pages.md](pages.md)). A composable is an `XSheet` when its name ends in `Sheet` and an
`XSheetContent` when it ends in `SheetContent`; they are matched by `X` **and package**, like the files of a page.

| Id | Rule |
|---|---|
| `SHEET-1` | Every `XSheet` has an `XSheetContent` in its package and calls it: the sheet delegates its content |
| `SHEET-2` | Every `XSheetContent` has an `XSheet` in its package |
| `SHEET-3` | A bottom sheet (`ModalBottomSheet`, `ModalBottomSheetLayout`, `BottomSheetScaffold`, `BottomSheetDialog`, …) is only used inside an `XSheet` composable (or a `private` helper in its file); a page, a card or a preview that wants a sheet calls `XSheet` |
| `SHEET-4` | `XSheetContent` knows nothing of the sheet around it: it uses no sheet, no sheet state (`SheetState`, `rememberModalBottomSheetState`) and no shared sheet layout (`SheetLayout`, `SheetDefaults`) |
| `SHEET-5` | `XSheetContent` is stateless: it mentions no ViewModel, Koin, `Flow` (or `collectAs…`), repository or navigator, like `XPageContent` (`PAGE-6`) |

Its preview is `PRV-1`, its file name and the one public composable per file `CMP-1`. The `screenshot` package is not checked for these.

### Previews and composables

| Id | Rule |
|---|---|
| `PRV-1` | Every `XPageContent` and every `XSheetContent` has a `private` `@Preview` function named exactly `Preview` in its file |
| `PRV-2` | A general preview is `private` and named `Preview`, or `Preview` and a capital differentiator (`PreviewEmpty`, `PreviewLoading`), once per file |
| `PRV-3` | A preview is in the file of the composable it previews: its body shows a composable declared in that file |
| `PRV-4` | A preview, and a screenshot, is wrapped in `AppTheme { … }` |
| `PRV-5` | A preview needs no ViewModel, Koin or Flow collection, and a URL in it comes with Coil's `LocalAsyncImagePreviewHandler`, so it never depends on the network |
| `PRV-6` | A `…Screenshot` preview is only in the `screenshot` package, and every preview in that package ends in `Screenshot` |
| `PRV-7` | Every public or `internal` composable has a `@Preview` in its file, however short; a `private` helper does not. Exempt: a composable that returns a value (`remember…`: there is nothing to show), `Root`, `AppNavigation`, `Router` and `AppTheme` of the [app shell](app-shell.md). One that needs the camera, a video or Koin has a preview too, with those mocked; one that draws nothing (an effect) takes a `lint:ignore PRV-7` with its reason |
| `CMP-1` | A file has one public or `internal` composable, and the file is named after it. `private` helpers and previews are free |

### Screenshots

[`scripts/conventions/screenshots.py`](../scripts/conventions/screenshots.py) holds the rules of the `screenshot` package, and the
helpers that the render and README scripts read the package with. The failure is on the first push and not at render time:

| Id | Rule |
|---|---|
| `SHOT-1` | A file of the package holds nothing at the top level but private `@Preview` composables without parameters, each with its own data inside ([screenshots.md](screenshots.md#the-screenshot-package)) |
| `SHOT-2` | The package has an `order.txt` that lists every screenshot once and nothing else. Only for an app that has a `readme.yml`: the apps not migrated yet are not asked for it |

## What is checked, and where

All the Kotlin files of the app, except anything under `build/`. The page, ViewModel, sheet and preview rules read the files under
`src/<source set>/` of every module except the test source sets (a name that ends in `test`); the `DI-*` rules read every file but
the tests, and `NAME-1` and `VM-8` read the tests too. The `screenshot` package is exempt from the page rules (`PAGE-*`,
`CMP-1`), since its files carry the names of the pages they show.

A page is found by its name: a `@Composable` function that ends in `Page` is an `XPage`, one that ends in `PageContent`
is an `XPageContent`, a class that ends in `ViewModel` is a ViewModel, and a type that ends in `UiState` is a state. Pages
are matched by `X` **and package**, so `XPage`, `XPageContent`, `XViewModel` and `XUiState` of a page are in one package.

It is a text scan, not a compiler. It does not know types, only names and the text of a declaration, which is enough for
these rules and cheap to run, and it means a few rules are heuristics (`PAGE-5`'s imports, the name patterns). It does not judge what only a person can: whether a preview really shows the composable, or whether some state
belongs in a repository.

**Not checked yet:** the route of a page (`Route.X` in the one `sealed interface Route`, and the `entry<Route.X>` that
calls `XPage`), the touch targets, the strings in `strings.xml`, `MaterialTheme`, and the screenshot package's mock data
beyond what `SHOT-1` reads.

## When it is the exception: `lint:ignore`

If a rule does not fit one declaration, say why on the line or the line above it:

```kotlin
// lint:ignore PRV-7: an effect, it draws nothing
@Composable
internal fun CameraSurface(…) { … }
```

The reason is required: a `lint:ignore` with none, or for an id that is not in this page, is itself an error
(`IGNORE-1`) and silences nothing. The comment silences that one rule for the violation it sits above or beside: from the line above
the declaration (or its first annotation) down to the line the violation is reported on. It never silences a file. Use it for a real exception, not for a violation you have not got round to.

## How it is built

[`scripts/check_conventions.py`](../scripts/check_conventions.py) is the one entry point. The rules are in
[`scripts/conventions/`](../scripts/conventions/), one module for each group of ids on a shared base:

| Module | |
|---|---|
| `scan.py` | The Kotlin scanner (comments, strings, top-level declarations); not a parser |
| `core.py`, `violation.py` | The files of the app, a `Violation`, the `lint:ignore` comments, the annotations and summary, and the run through every module |
| `roles.py` | Which declaration is a page, a content, a ViewModel, a state or a sheet |
| `di.py`, `naming.py`, `toplevel.py` | `DI-*`; `NAME-1`; `TOP-1` |
| `pages.py`, `viewmodels.py`, `sheets.py`, `previews.py` | `PAGE-*`; `VM-*` and `UI-*`; `SHEET-*`; `PRV-*` and `CMP-1` |
| `screenshots.py` | `SHOT-*`, and the screenshot package helpers |

Every rule module has a `RULES` dict (id and one line) and a `check(ctx)` that adds violations to the shared context.

## Running it

```
python3 scripts/check_conventions.py path/to/app     # prints the violations, exits 1 if there are any
python3 -m unittest discover -s tests                # the tests, with a failing and a passing case for every rule
```

## Adding or changing a rule

1. Put the rule in the docs it comes from first, then add the id and its one line to `RULES` of the module of its group
   (`scripts/conventions/`), and the check in that module's `check(ctx)`. A new group is a new module, added to `checks()` in `core.py`.
   Build on the shared `ctx` (its files, `ctx.add`, the page and sheet roles) and the scanner rather than a scan of your own.
2. Add a failing and a passing case, in `tests/test_conventions_di.py` (`DI-*`, `NAME-1`, `VM-8`, `TOP-1`), `tests/test_conventions_pages.py`
   (the rest) or `tests/test_conventions_screenshots.py`.
3. Add the row above (a test fails if the ids here and in the `RULES` differ), and the line in the skill ([skill.md](skill.md)).

A change to the script reaches every app's CI when it merges ([sync.md](sync.md#what-starts-a-sync)): a new rule fails
the PRs of the apps that break it, so check what it does to them first (clone an app, run the script).
