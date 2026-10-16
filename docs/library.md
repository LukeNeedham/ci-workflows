# The shared library (`common/`)

A Kotlin Multiplatform library (Android, iOS, web/wasm) holding the debug tools that every app
needs, so they are written once instead of copied between apps.

| Part | What it does |
|---|---|
| `Logger` | Logs to Logcat/the console **and** to a file on disk, so logs persist across restarts and crashes |
| Crash handler | Catches every uncaught exception, writes it to disk with the last 50 log lines, then lets the app crash as normal |
| `LogsPage`, `CrashesPage` | Read the saved logs and crashes back. Text is selectable, so it can be copied |
| `DebugPage` | The hub: debug settings (animation speed, saved) and links to the logs and crashes pages |
| `DebugButton` | A button that opens the debug page. Shows nothing unless debugging is enabled |
| Animation speed | A debug setting (0.25x to 2x), saved to disk, that scales every animation duration |

There is no Room, DataStore or navigation library inside it: it keeps plain files (`localStorage`
on the web), and the pages do not navigate by themselves, so any app can adopt it.

## Using it in an app

Add the repository and the dependency:

```kotlin
// settings.gradle.kts
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven("https://lukeneedham.github.io/ci-workflows/maven")
    }
}

// build.gradle.kts of the module: commonMain.dependencies in a KMP module, or just dependencies
// in a plain Android one (Gradle picks the Android variant itself).
implementation("com.lukeneedham:common:0.1.0")
```

Start it as early as possible, once:

```kotlin
// Android: Application.onCreate. iOS and web: wherever the app starts.
DebugKit.init(DebugKitConfig(enabled = BuildConfig.DEBUG))
```

`enabled` switches on the debug UI (the button, and the saved debug settings taking effect). The
logger and the crash handler work either way, so crashes in release builds are still saved.

Wire the pages into the app's own navigation, and apply the animation speed:

```kotlin
ProvideAnimationSpeed {                        // once, near the root
    AppNavigation(...)
    Box(Modifier.fillMaxSize()) {
        DebugButton(onClick = { navigate(Debug) }, modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp))
    }
}

// the three pages, each given a back action:
DebugPage(onBack = ..., onOpenLogs = { navigate(Logs) }, onOpenCrashes = { navigate(Crashes) }) {
    // optional: the app's own debug tools go here
}
LogsPage(onBack = ...)
CrashesPage(onBack = ...)
```

Take every animation duration through the speed, never from a raw number, so the setting reaches all
of them:

```kotlin
tween(durationMillis = LocalAnimationSpeed.current.scale(300))
```

Outside debugging `ProvideAnimationSpeed` always provides 1x, so a speed saved while debugging
cannot slow down a release build.

Logging:

```kotlin
Logger.i("Loaded 12 flags", tag = "Flags")
Logger.e("Could not load", throwable, tag = "Flags")
```

## How the pieces work

- **Files.** Logs are one JSON object per line in `log.jsonl`; when the file passes 512,000 characters
  its oldest half is dropped. Crashes are in `crashes.jsonl` (newest 20). Debug settings are in
  `debug_settings.json`. On Android they live in `filesDir/common`, on iOS in Application Support,
  on the web in `localStorage` under keys starting `common:`.
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
