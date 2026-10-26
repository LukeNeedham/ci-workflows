# The convention checks

**CI fails a pull request in any app that breaks the page, ViewModel, UiState or preview rules.** The check is the
`conventions` job of [`android_pr.yml`](../.github/workflows/android_pr.yml), which runs
[`scripts/lint_conventions.py`](../scripts/lint_conventions.py) on the app's sources. It reads the Kotlin files with no
Gradle build and no JDK, so it takes seconds, runs alongside the build and needs nothing in the app: every app gets it
from this repo, like the rest of its CI. The rules are the ones of [pages.md](pages.md), [app-conventions.md](app-conventions.md)
and [screenshots.md](screenshots.md); this page is the list of what is checked, by id.

Each violation is an error annotation on the line (`::error file=…,line=…,title=VM-2::…`) and a row in the run summary,
and any violation fails the job. There is no warning mode.

## The rules

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
| `VM-1` | A ViewModel is requested (`koinViewModel`, `viewModel`, `getViewModel`, `hiltViewModel`, `viewModels`, …) only inside an `XPage` (or the app's `Root`, [below](#the-app-root)), and only as `XViewModel` (`RootViewModel` for `Root`), with the type written out: `koinViewModel<HomeViewModel>()` or `val vm: HomeViewModel = koinViewModel()`. A Koin definition (`viewModel { … }`) is not a request |
| `VM-2` | A ViewModel class is requested by one page only. Two pages that ask for the same one are both reported |
| `VM-3` | No ViewModel is scoped to something several pages share: no `activityViewModel`, `sharedViewModel`, `viewModelStoreOwner =`, `LocalViewModelStoreOwner`, `ownerProducer`, and no owner, back stack entry, activity or navigation graph in the arguments of a request |
| `VM-4` | A ViewModel is never a Koin `single`, `factory` or `scoped` definition (`single { HomeViewModel(get()) }`, `singleOf(::HomeViewModel)`): a `single` is one instance for everyone. Use `viewModelOf` or `viewModel { }` |
| `VM-5` | A ViewModel holds no other ViewModel: none in its constructor, properties or body (`get<OtherViewModel>()`). A base class in its supertypes is not holding |
| `VM-6` | A concrete ViewModel (a class with a ViewModel supertype that is not `abstract` or `sealed`) is named `XViewModel` and has an `XPage` in its package. `RootViewModel` needs a `Root` composable in its package instead |
| `VM-7` | A ViewModel declares no `SharedFlow` or `MutableSharedFlow`: a one-off event goes through a `Channel` exposed with `receiveAsFlow()` ([app-conventions.md](app-conventions.md#one-off-events)) |

<a id="the-app-root"></a>
**The app root.** `Root` (the composable that decides what the app shows: a spinner, the permissions, the setup or the app)
is not a page, since it is not a destination of the navigation, but it may get its state from a ViewModel, which has to be
`RootViewModel`. That is the one exception to "only an `XPage` requests a ViewModel", and `Root` is the one composable
that has it. Nothing else may request `RootViewModel`.

State that pages share lives below the ViewModels, in a repository (a Koin `single`) that each page's own ViewModel uses
([pages.md](pages.md#names-and-files)).

### UiState

| Id | Rule |
|---|---|
| `UI-1` | An `XUiState` has an `XPage` in its package |
| `UI-2` | An `XUiState` is immutable: no `var`, no `MutableList`, `ArrayList`, `mutableStateOf` or other mutable type. Change it with `copy` |
| `UI-3` | An `XUiState` is plain data: it holds no `Flow`, `StateFlow`, `SharedFlow` or `Channel` |

### Previews and composables

| Id | Rule |
|---|---|
| `PRV-1` | Every `XPageContent` has a `private` `@Preview` function named exactly `Preview` in its file |
| `PRV-2` | A general preview is `private` and named `Preview`, or `Preview` and a capital differentiator (`PreviewEmpty`, `PreviewLoading`), once per file |
| `PRV-3` | A preview is in the file of the composable it previews: its body shows a composable declared in that file |
| `PRV-4` | A preview, and a screenshot, is wrapped in `AppTheme { … }` |
| `PRV-5` | A preview needs no ViewModel, Koin or Flow collection, and a URL in it comes with Coil's `LocalAsyncImagePreviewHandler`, so it never depends on the network |
| `PRV-6` | A `…Screenshot` preview is only in the `screenshot` package, and every preview in that package ends in `Screenshot` |
| `PRV-7` | A public or `internal` composable of **10 lines or more** has a `@Preview` in its file. Short ones are "trivial" ([app-conventions.md](app-conventions.md#composables-and-previews)), and a composable that returns a value (`remember…`) or mentions Koin, a ViewModel, navigation (`NavDisplay`, `NavHost`, `NavBackStack`, `NavController`) or `collectAs…` has nothing a preview can show, so none is asked for |
| `CMP-1` | A file has one public or `internal` composable, and the file is named after it. `private` helpers and previews are free |

### Screenshots

[`scripts/screenshots/check_screenshot_package.py`](../scripts/screenshots/check_screenshot_package.py) holds the rules of
the `screenshot` package. The job runs it too, so the failure is on the first push and not at render time:

| Id | Rule |
|---|---|
| `SHOT-1` | A file of the package holds nothing at the top level but private `@Preview` composables without parameters, each with its own data inside ([screenshots.md](screenshots.md#the-screenshot-package)) |
| `SHOT-2` | The package has an `order.txt` that lists every screenshot once and nothing else. Only for an app that has a `readme.yml`: the apps not migrated yet are not asked for it |

## What is checked, and where

All the Kotlin files under `src/<source set>/` of the app, in every module, except the test source sets (a name that
contains `test`) and anything under `build/`. The `screenshot` package is exempt from the page rules (`PAGE-*`, `CMP-1`),
since its files carry the names of the pages they show.

A page is found by its name: a `@Composable` function that ends in `Page` is an `XPage`, one that ends in `PageContent`
is an `XPageContent`, a class that ends in `ViewModel` is a ViewModel, and a type that ends in `UiState` is a state. Pages
are matched by `X` **and package**, so `XPage`, `XPageContent`, `XViewModel` and `XUiState` of a page are in one package.

It is a text scan, not a compiler. It does not know types, only names and the text of a declaration, which is enough for
these rules and cheap to run, and it means a few rules are heuristics (`PAGE-5`'s imports, `PRV-7`'s length, the name
patterns). It does not judge what only a person can: whether a composable is really trivial, or whether some state
belongs in a repository.

**Not checked yet:** the route of a page (`Route.X` in the one `sealed interface Route`, and the `entry<Route.X>` that
calls `XPage`), the touch targets, the strings in `strings.xml`, `MaterialTheme`, and the screenshot package's mock data
beyond what `SHOT-1` reads.

## When it is the exception: `lint:ignore`

If a rule does not fit one declaration, say why on the line or the line above it:

```kotlin
// lint:ignore PRV-7: only places a platform view, there is nothing to show
@Composable
internal fun CameraSurface(…) { … }
```

The reason is required: a `lint:ignore` with none, or for an id that is not in this page, is itself an error
(`IGNORE-1`) and silences nothing. The comment silences that one rule for the violation it sits above or beside: from the line above
the declaration (or its first annotation) down to the line the violation is reported on. It never silences a file. Use it for a real exception, not for a violation you have not got round to.

## Running it

```
python3 scripts/lint_conventions.py path/to/app      # prints the violations, exits 1 if there are any
python3 -m unittest discover -s tests                # the tests, with a failing and a passing case for every rule
```

## Adding or changing a rule

1. Add the id and its one line to `RULES` in `scripts/lint_conventions.py`, and the check in the `Lint` class.
2. Add a failing and a passing case to `tests/test_lint_conventions.py`.
3. Add the row above (a test fails if the ids here and in `RULES` differ), and the line in the skill
   ([skill.md](skill.md)).

A change to the script reaches every app's CI when it merges ([sync.md](sync.md#what-starts-a-sync)): a new rule fails
the PRs of the apps that break it, so check what it does to them first (clone an app, run the script).
