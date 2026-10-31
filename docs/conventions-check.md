# The conventions check

Every pull request of an app runs the **`conventions`** job of [`android_pr.yml`](../.github/workflows/android_pr.yml). It reads the Kotlin
code with [`scripts/check_conventions.py`](../scripts/check_conventions.py) and fails the PR with an annotation (file and line) on every line
that breaks one of the rules below. It builds nothing, so it needs no settings and no setup in the app, and it runs alongside the build.
To run it on your machine: `python3 scripts/check_conventions.py path/to/app`.

It checks the **code**, not the Gradle files, and skips `build/`, `.gradle/` and the like. The tests (`test/`, `androidTest/`,
`commonTest/`, ...) are checked for the two rules at the end only, since a test may build a Koin module of its own.

| Rule | What fails | From |
|---|---|---|
| `koin-required` | An app that does not use Koin, or has no `KoinModules.kt` | [new-app.md](new-app.md#6-app-architecture) |
| `koin-modules-file` | `KoinModules.kt` or `KoinQualifier.kt` that holds anything but its `object` (a `const val`, a helper, a second class), is not in a package ending `.di`, or an `object KoinModules` / `KoinQualifier` in a file of another name; the names `KoinModule` and `KoinQualifiers` | [app-shell.md](app-shell.md#the-names) |
| `module-in-object` | A `module { }` at the top level of a file, or in a file that is not in a `di` folder: it is in `KoinModules` or in a feature object it uses | [new-app.md](new-app.md#6-app-architecture) |
| `koin-wiring-only` | A binding with more than wiring in it: a string or a number, a block inside the binding (a builder or a DSL such as `HttpClient(OkHttp) { ... }`), an operator (`+`, `*`), `if` / `when` / `val`, or chained calls (`Builder().cache(...).build()`, `Factory(context).create()`, `androidContext().cacheDir`). Only `get()` (with `named(KoinQualifier.X)`), `androidContext()`, the runtime parameters of a `viewModel { (id: String) -> ... }` and names are allowed; `get<T>().member()` is the one chain that is | [new-app.md](new-app.md#6-app-architecture) |
| `koin-qualifier` | `named("...")`: a qualifier is a constant of `KoinQualifier` (the object itself may build its names) | [app-shell.md](app-shell.md#the-names) |
| `koin-start` | A `modules(...)` call outside `di/` that does not use `KoinModules` | [new-app.md](new-app.md#6-app-architecture) |
| `no-android-view-model` | `AndroidViewModel` in code, in the tests too | [new-app.md](new-app.md#6-app-architecture) |
| `acronym-naming` | A name that a file declares (class, object, interface, typealias, function, property, parameter) or a file name with an acronym in capitals: `iOSSDKManager` for `IosSdkManager`, `userID` for `userId` | [app-conventions.md](app-conventions.md#naming) |

## The acronym rule, in detail

A run of capitals that ends a name, or comes before a digit, is an acronym (`userID`, `newPP`, `UTF8Decoder`). A run of three or more before
a lower case letter is an acronym followed by a word (`HTTPClient`: `HTTP` and `Client`). A run of **two** before a lower case letter is a
one-letter word and a word (`parsesAUri`, `selectedXOffset`), and passes. `UPPER_SNAKE_CASE` constants pass. The names the code only uses
(`JSONArray`, `IOException`, `Dispatchers.IO`) are not looked at, and neither is an `override`, whose name the supertype fixed. For the
rare name that has to stay, put `@Suppress("AcronymNaming")` on its line or the one above.

## Changing a rule

The rule goes in the docs it comes from first, then in the script, with a test in
[`tests/test_check_conventions.py`](../tests/test_check_conventions.py) for what it finds and for what it must leave alone. Run the script on the
apps before it is merged: the job runs at `@main` in every app, so a rule that the apps break fails all their PRs at once.
