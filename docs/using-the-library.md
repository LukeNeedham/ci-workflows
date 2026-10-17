# Using the shared library in an app

How to add [`common/`](../common) (logger, crash handler, logs/crashes/debug pages, debug button,
animation speed) to an app. What the library is and how it works
is in [library.md](library.md); this page is the step-by-step.

- [Before you start](#before-you-start)
- [The five steps, in short](#the-five-steps-in-short)
- [Adding it to an app](#adding-it-to-an-app)
- [Always wrap the UI in `ProvideDebugSettings`](#always-wrap-the-ui-in-providedebugsettings)
- [Wiring the pages into your navigation](#wiring-the-pages-into-your-navigation)
- [Turning it off in release builds](#turning-it-off-in-release-builds)
- [Check that it works](#check-that-it-works)
- [Updating the library](#updating-the-library)
- [Troubleshooting](#troubleshooting)

## Before you start

| Needs | Why |
|---|---|
| A published version of the library | Run **Library Release** once (see [library.md](library.md#releasing)) and turn on GitHub Pages for the `gh-pages` branch. The examples below use `0.1.0`: use the version you released |
| Jetpack Compose with Material 3 | The pages are composables. A View-based app cannot show them |
| Android `minSdk` 23 or higher | Jetpack Compose 1.10, which the library is built on, needs 23; the library's own code needs less. A lower app `minSdk` fails the manifest merge |
| Kotlin 2.2 or newer | The library is compiled with 2.2.21, and a compiler more than a minor version older may not be able to read it. This matters most for Kotlin Multiplatform apps and their klibs |
| `compileSdk` 36 | The library is built against 36 and brings Compose 1.10. If AGP stops with a `checkAarMetadata` error, raise `compileSdk` to the number it names |

The library brings its own Compose Multiplatform 1.10 / Material 3 1.4. If your app is on an older
Compose, Gradle upgrades it to match, so test the app's screens after adding the library.

## The five steps, in short

Every app does the same five things:

1. **Add the repository** to `settings.gradle.kts`.
2. **Add the dependency** to the app module.
3. **Call `DebugKit.init(...)` once, as early as possible** (before anything can crash or log).
4. **Wrap the UI in `ProvideDebugSettings`**, and place a `DebugButton`. Every app does this, even one that reads no debug setting yet (see [Always wrap the UI](#always-wrap-the-ui-in-providedebugsettings)).
5. **Add the three pages** (`DebugPage`, `LogsPage`, `CrashesPage`) to your navigation.

Then use `Logger` instead of `Log`/`println`. `Logger` has four levels (`d`, `i`, `w`, `e`), and
`tag` names the origin. To keep a rule such as "debug logs only in debug builds", set `minLogLevel`:

```kotlin
DebugKit.init(
    DebugKitConfig(
        enabled = BuildConfig.DEBUG,
        minLogLevel = if (BuildConfig.DEBUG) LogLevel.Debug else LogLevel.Info,
    ),
)
```

`Logger` does nothing until `DebugKit.init` has run, so lines logged before it are dropped: call `init`
first thing in `Application.onCreate`. Plain JVM unit tests never start the app; there `Logger` is a
harmless no-op that needs no Android context.

## Adding it to an app

### 1. The repository and the dependency

`settings.gradle.kts`:

```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven("https://lukeneedham.github.io/ci-workflows/maven") {
            content { includeGroup("com.lukeneedham") }   // only ask it for this library
        }
    }
}
```

`gradle/libs.versions.toml`:

```toml
[versions]
common = "0.1.0"

[libraries]
common = { module = "com.lukeneedham:common", version.ref = "common" }
```

### 2a. A plain Android app

In `app/build.gradle.kts`:

```kotlin
android {
    compileSdk = 36
    defaultConfig { minSdk = 23 }
    buildFeatures { buildConfig = true }   // for BuildConfig.DEBUG, used below
}

dependencies {
    implementation(libs.common)
}
```

Gradle picks the Android variant of the library by itself.

An `Application` class, registered with `android:name=".App"` on `<application>` in the manifest:

```kotlin
class App : Application() {
    override fun onCreate() {
        super.onCreate()
        DebugKit.init(DebugKitConfig(enabled = BuildConfig.DEBUG))
    }
}
```

Then jump to [Wiring the pages into your navigation](#wiring-the-pages-into-your-navigation).

### 2b. A Kotlin Multiplatform app (Android, iOS, web)

In the shared module's `build.gradle.kts`, add it once to `commonMain`:

```kotlin
kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation(libs.common)
        }
    }
}
```

Write one shared function that every platform calls from its entry point:

```kotlin
// commonMain
fun initDebugKit(isDebug: Boolean) {
    DebugKit.init(DebugKitConfig(enabled = isDebug))
}
```

`isDebug` differs per platform, so each platform passes its own (see
[Turning it off in release builds](#turning-it-off-in-release-builds)):

```kotlin
// Android: App.onCreate()
initDebugKit(BuildConfig.DEBUG)

// iOS: the top of MainViewController(), before ComposeUIViewController { ... }
initDebugKit(Platform.isDebugBinary)          // @OptIn(ExperimentalNativeApi::class)

// Web: the top of main(), before ComposeViewport { ... }
initDebugKit(isDebugBuild)                    // however your web build says it is a debug build
```

## Always wrap the UI in `ProvideDebugSettings`

`ProvideDebugSettings` is the single place where the library hands composition locals to the app.
It provides `LocalDebugSettings` (every debug setting that applies to the UI, as one value) and a
local for each setting that has its own, today `LocalAnimationSpeed`.

**Every app wraps its content in it once, near the root, including apps that read no setting yet.**
An app with no animation to scale today may need another debug setting tomorrow. If the app is
already wrapped, a setting added to the library later reaches every screen with a library version
bump and nothing else, instead of a change to every consuming app.

```kotlin
setContent {
    ProvideDebugSettings {
        AppTheme { AppNavigation() }
    }
}
```

It goes outside the app's own theme and navigation, so everything below can read the locals. Outside
debugging (`enabled = false`) it provides the neutral defaults, so a setting saved while debugging
never changes a release build.

**For the library's maintainers:** any composition local that the library offers to an app must be
provided inside `ProvideDebugSettings`, and nowhere else, so that an app only ever makes this one
call. The steps for adding one are in the KDoc of `ProvideDebugSettings`.

## Wiring the pages into your navigation

The pages never navigate themselves: they call the lambdas you pass, so they fit any navigation
library. Three routes are needed (Debug, Logs, Crashes), plus a way to open Debug.

**Opening the debug page.** Put a `DebugButton` over your content. It draws nothing when debugging
is off, so it can stay in the code for release builds:

```kotlin
Box(Modifier.fillMaxSize()) {
    AppNavigation()
    DebugButton(
        onClick = { navigateToDebug() },
        modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp),
    )
}
```

If the app already has a settings entry that opens its debug page (some apps already do), keep that and skip the button.

**Navigation 3 or a hand-written back stack** :

```kotlin
internal enum class Route { /* ... */ Debug, Logs, Crashes }

when (route) {
    // ...
    Route.Debug -> DebugPage(
        onBack = back,
        onOpenLogs = { backStack.add(Route.Logs) },
        onOpenCrashes = { backStack.add(Route.Crashes) },
    )
    Route.Logs -> LogsPage(onBack = back)
    Route.Crashes -> CrashesPage(onBack = back)
}
```

**Voyager** (FlagTutor's style):

```kotlin
class DebugScreen : Screen {
    @Composable
    override fun Content() {
        val navigator = LocalNavigator.currentOrThrow
        DebugPage(
            onBack = navigator::pop,
            onOpenLogs = { navigator.push(LogsScreen()) },
            onOpenCrashes = { navigator.push(CrashesScreen()) },
        )
    }
}

class LogsScreen : Screen {
    @Composable
    override fun Content() = LogsPage(onBack = LocalNavigator.currentOrThrow::pop)
}

class CrashesScreen : Screen {
    @Composable
    override fun Content() = CrashesPage(onBack = LocalNavigator.currentOrThrow::pop)
}
```

**Anything else** (a hand-rolled page router, a sealed `Page` class): add three cases and pass
`onBack` your existing back action. Nothing about the pages depends on the navigation library.

**On the web**, if the app syncs routes with the browser address (FlagTutor does), register the
three routes there too, and only when debugging is on.

The pages draw with `MaterialTheme`, so they take the app's colours and typography. Each has its
own top bar with a back arrow. A variant without the bar is not provided yet.

## Turning it off in release builds

`enabled` controls the debug UI: the button, and whether the saved animation speed applies. The
logger and the crash handler run whatever it is, so release builds still save crashes (the pages
are what you hide).

Pages should be unreachable in release too, so gate the navigation to them like this:

| Platform | A debug flag |
|---|---|
| Android | `BuildConfig.DEBUG` (turn on `buildFeatures { buildConfig = true }`), or `(applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0`  |
| iOS | `Platform.isDebugBinary` from `kotlin.native`, with `@OptIn(ExperimentalNativeApi::class)` |
| Web | whatever the page sets, e.g. FlagTutor's `globalThis.appDebug === true` |

A common shape for Kotlin Multiplatform:

```kotlin
// commonMain
expect val isDebugBuild: Boolean
// androidMain: actual val isDebugBuild: Boolean = BuildConfig.DEBUG
// iosMain:     actual val isDebugBuild: Boolean = Platform.isDebugBinary
```

and then `DebugKit.init(DebugKitConfig(enabled = isDebugBuild))`, plus `if (isDebugBuild)` around the
routes.

## Check that it works

Add a throwaway "crash" button somewhere reachable in a debug build (the app's own debug page is the
natural place; the library's page has no slot for one), then go through this once per platform:

```kotlin
OutlinedButton(onClick = { error("Test crash") }) { Text("Crash the app") }
```

1. Put a `Logger.i("hello from the app")` somewhere that runs at launch.
2. Open **Debug > Logs**: the line is there, with a timestamp.
3. Tap **Crash the app**. The app closes as it normally would on a crash.
4. Reopen it, then **Debug > Crashes**: the crash is listed. Tap it for the stack trace and the log
   lines from just before it.
5. Back on Debug, choose **0.5x** animation speed, close the app from the app switcher, reopen it:
   0.5x is still selected, and animations are slower.
6. Build a **release** build: no Debug button, no route to the pages, and animations at normal
   speed even though 0.5x was saved. (Crashes are still saved in release; there is just no page to
   read them on.)

Delete the crash button afterwards.

## Updating the library

Change `common` in `gradle/libs.versions.toml` and sync. New versions come from running **Library
Release**. A version is never overwritten, so an app's build is the same tomorrow as today.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Could not find com.lukeneedham:common:0.1.0` | The version has not been released yet, GitHub Pages is not turned on for the `gh-pages` branch, or the `maven(...)` repository is missing from `dependencyResolutionManagement`. Open `https://lukeneedham.github.io/ci-workflows/maven/com/lukeneedham/common/maven-metadata.xml` in a browser: it should list the versions |
| `uses-sdk:minSdkVersion 21 cannot be smaller than version 23 declared in library` | Raise the app's `minSdk` to 23 |
| `checkAarMetadata` fails, asking for a higher `compileSdk` | Raise `compileSdk` to the number it names (36) |
| Kotlin: `Class 'X' was compiled with an incompatible version of Kotlin` or an unreadable klib | The app's Kotlin is older than 2.2. Upgrade Kotlin |
| The Logs page is empty although the app logs | Check `DebugKit.init` runs before the lines are logged (earlier calls are dropped), and that the lines go through `Logger`, not `Log`/`println`. Also check `minLogLevel` is not above the level you log at |
| Unit tests fail with `UninitializedPropertyAccessException` in `CommonInitProvider` | Fixed in 0.2.1 (use that or newer). From 0.3.0, `Logger` is also a no-op until `DebugKit.init` runs, so plain JVM unit tests never reach the context or `android.util.Log` |
| Crashes are not saved | `DebugKit.init` runs too late, or never. It must run before the crash. A crash during `Application` construction itself cannot be caught |
| Crashes are saved twice | Another crash handler is also installed. Remove it |
| The animation speed does not change anything | `ProvideDebugSettings` is missing at the root, `enabled` is `false`, or the app's animations use fixed numbers. Every duration must go through `scale(...)` |
| Logs or crashes are blank in a minified build | The library has not been tested with R8. Check **Logs** and **Crashes** in a minified build before relying on it. If serialization breaks there, add a `-keep` rule for `com.lukeneedham.common.logger.LogEntry` and `com.lukeneedham.common.crash.CrashEntry` |
