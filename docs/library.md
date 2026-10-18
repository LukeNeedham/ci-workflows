# The shared library (`common/`)

A Kotlin Multiplatform library (Android, iOS, web/wasm) holding the debug tools that every app
needs, so they are written once instead of copied between apps.

| Part | What it does |
|---|---|
| `Logger` | Logs to Logcat/the console **and** to a file on disk, so logs persist across restarts and crashes |
| Crash handler | Catches every uncaught exception, writes it to disk with the last 50 log lines, then lets the app crash as normal |
| `LogsPage`, `CrashesPage` | Read the saved logs and crashes back. Text is selectable, so it can be copied |
| `DebugPage` | The library's own debug page: the app's package and current version (the application id and version name and code on Android, the bundle id and version on iOS, the page host on web), debug settings (animation speed, saved) and links to the logs and crashes pages. It shows only those; an app's own debug tools go on the app's own debug page, which links to this one |
| `DebugButton` | A button that opens the debug page. Shows nothing unless debugging is enabled. Always placed on the app's settings page, never as a floating button over the main page |
| Animation speed | A debug setting (0.25x to 2x), saved to disk, that scales every animation duration |
| `ProvideDebugSettings` | The one composable that provides every debug setting to the UI as composition locals (`LocalDebugSettings`, `LocalAnimationSpeed`, ...), and the `DebugTheme` the pages are drawn with. **Every app wraps its content in it**, whether or not it uses a setting yet |
| `DebugTheme` | The colours and font family of the library's pages and button, passed by the app to `ProvideDebugSettings`. The library uses no Material and reads no app theme |

There is no Room, DataStore or navigation library inside it: it keeps plain files (`localStorage`
on the web), and the pages do not navigate by themselves, so any app can adopt it.

## Using it in an app

**See [using-the-library.md](using-the-library.md)** for the step-by-step: adding it to a new app and
to an existing one, wiring the pages into the app's navigation (Navigation 3, Voyager or anything
else), removing the old logger and crash handler, and a checklist to verify it works.

In short, the five steps are: add the repository, add the dependency, call `DebugKit.init(...)`
once and early, wrap the UI in `ProvideDebugSettings` (and place a `DebugButton` on the app's settings page, which every app has), and add the
three pages to the navigation. Then log with `Logger.i(...)`, `Logger.e(...)` and so on.

## How the pieces work

- **Files.** Logs are one JSON object per line in `log.jsonl`; when the file passes 512,000 characters
  its oldest half is dropped. Crashes are in `crashes.jsonl` (newest 20). Debug settings are in
  `debug_settings.json`. On Android they live in `filesDir/common`, on iOS in Application Support,
  on the web in `localStorage` under keys starting `common:`.
- **The logger is a no-op until `DebugKit.init` runs.** `Logger` writes to a sink that does nothing and
  needs nothing (no application context, no `android.util.Log`, no files), and `DebugKit.init` swaps in
  the real one. So code that runs without the app having started, such as plain JVM unit tests,
  can call `Logger` freely: the calls are dropped and `Logger.entries()` is empty. The cost is that
  anything logged before `init` is lost, so call it first thing in `Application.onCreate`.
- **Storage without an application context.** In a running app the context is set before
  `Application.onCreate`. Where `init` runs without it (a Robolectric test that starts the app's
  `Application`, say) the file store keeps things in memory until the context is known, so that
  does not throw either.
- **Logging is synchronous.** Each call appends to the file on the calling thread. That is fine for
  a debug log; do not log inside a tight loop.
- **The crash handler** chains to the handler that was installed before it, so Android's own crash
  dialog and any other crash reporter still run. On iOS it uses Kotlin's unhandled-exception hook
  (a Kotlin exception never reaches `NSSetUncaughtExceptionHandler`) plus that handler for
  Objective-C exceptions. On the web it listens for `error` and `unhandledrejection` events and does
  not stop them, so the browser still reports them.
- **Not covered:** native crashes and ANRs on Android (`ApplicationExitInfo` could add them), and
  sharing logs as a file.

## Releasing

Run **Library Release** (Actions tab) with a version like `0.1.0`. It tests, publishes the
artifacts to the `gh-pages` branch, and creates the release `common-0.1.0`. Pull requests that
touch `common/` are checked by **Library CI**. A published version cannot be overwritten.

One-time setup: Settings > Pages > Source "Deploy from a branch", branch `gh-pages`, folder `/ (root)`.
The first release creates the branch.

### Why not use the release assets as the repository?

A Kotlin Multiplatform library publishes one set of files per target (`common`, `common-android`,
`common-iosarm64`, `common-wasm-js`, ...), and Gradle's module metadata finds them by relative paths like
`../../common-android/0.1.0/common-android-0.1.0.module`. A GitHub release is a flat list of files, so
those paths cannot resolve. A static Maven repository on GitHub Pages has the folder layout Gradle
expects, needs no login (unlike GitHub Packages), and is free. Publishing to Maven Central later
needs only a change of repository.
