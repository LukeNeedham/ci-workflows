# Starting a new app

The checklist for starting a new Android app. **Read this whole page before creating a project**,
then follow it, and tell the user about anything you skipped and why.

- [Before you write code](#before-you-write-code)
- [1. The project](#1-the-project)
- [2. Debug keystore](#2-debug-keystore)
- [3. CI workflows](#3-ci-workflows)
- [4. App icon](#4-app-icon)
- [5. README](#5-readme)
- [6. App architecture](#6-app-architecture)
- [7. The shared library](#7-the-shared-library)
- [Apps that are not Compose](#apps-that-are-not-compose)
- [Done checklist](#done-checklist)

## Before you write code

> This guide is also available as a Claude skill, `lukeneedham-conventions`, which each app keeps a copy
> of (see [skill.md](skill.md)).

- **Ask for what you do not know**, in one go: app name, package name (`com.lukeneedham.<app>`), what
  the app does, and anything unusual (orientation, minimum Android version, login).
- **The repo.** Claude cannot create GitHub repos (the integration gets a 403). Ask the user to create
  an empty repo named after the app, **with a README** so `main` exists, and to give the Claude GitHub
  App access to it (<https://github.com/apps/claude/installations/select_target>). Until they have,
  pushing fails with a 403.
- **Work on a branch and open a PR to `main`.** The PR build (step 3) only runs on PRs.
- **Claude can never build or run the app**: the sandbox has no access to Gradle, Maven or the Android SDK. Builds
  and compile checks happen only on CI. Do not try to download Gradle or set up the SDK (a waste of tokens): write
  carefully, push, then read the PR build comment and fix what the build log says.

## 1. The project

| Thing | Use |
|---|---|
| Language | Kotlin, no Java |
| Build | Gradle Kotlin DSL, version catalog in `gradle/libs.versions.toml`, Gradle wrapper |
| Versions | Match this repo: AGP `8.13.2`, Kotlin `2.2.21`, Gradle `8.14.3` (see `gradle/libs.versions.toml`, `gradle/wrapper/gradle-wrapper.properties`). Bump all three together |
| `compileSdk` / `targetSdk` | 36 (the shared library needs 36) |
| `minSdk` | 23 or higher (the shared library needs 23) |
| JDK | 17 (the CI default) |
| Package | `com.lukeneedham.<app>`, used for both `namespace` and `applicationId` |

Copy the Gradle wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/`) from this repo. Copy
`settings.gradle.kts` too: it restricts which repositories may serve which groups. Add a
`.gitignore` with `.gradle/`, `build/`, `.kotlin/`, `local.properties`, `.idea/`.

The app module is `:app`. Do **not** ignore `*.keystore` (see the next step).

## 2. Debug keystore

**Every app commits a debug keystore.** Without one, each CI run signs the debug APK with a freshly
generated random key, and Android refuses to install a build over one signed with a different key
("package conflicts with an existing package"), so testers must uninstall between builds, and lose
the app's data each time.

Debug keystores are not secrets (these are the standard Android debug credentials), so committing
one is fine. Do not reuse a *release* key this way.

Generate it (any JDK has `keytool`) and put it in the app module:

```
keytool -genkeypair -keystore app/debug.keystore -storepass android \
  -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 36500 \
  -dname "CN=Android Debug,O=Android,C=US"
```

Use it in `app/build.gradle.kts`:

```kotlin
android {
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
}
```

Commit `app/debug.keystore`. Every build signed with it, on CI or on a developer's machine, can
update any other. Anyone who installed an earlier build signed with a different key must uninstall
once.

Permanent, signed **release** builds are separate (own key, kept in repo secrets): see
[setup.md](setup.md#3-permanent-releases-optional).

## 3. CI workflows

Every app uses the shared workflows in this repo. Follow **[setup.md](setup.md)**, which has the
details. In short, for a new app:

1. Copy [`callers/trigger_on_pull_request.yml`](../callers/trigger_on_pull_request.yml) to
   `.github/workflows/trigger_on_pull_request.yml`, unchanged. The callers have no settings.
2. Copy [`callers/delete_prereleases.yml`](../callers/delete_prereleases.yml) to
   `.github/workflows/delete_prereleases.yml`, unchanged.
3. Copy [`callers/build_main.yml`](../callers/build_main.yml) to `.github/workflows/build_main.yml`, unchanged.
   AppHub builds `main` on demand through it, so keep the file name.
4. Copy [`callers/release.yml`](../callers/release.yml) to `.github/workflows/release.yml`, unchanged. Every app has
   it. It fails at once, with a clear message, until the app has the release key and the Gradle script
   ([setup.md](setup.md#3-permanent-releases-optional)); only do that when the user wants installable releases (the
   four repo secrets are for the user to add).
5. Add the app to [`apps.json`](../apps.json) ([consuming-apps.md](consuming-apps.md)), **in the same change as
   the callers**: just its `name` and `repo`, there is nothing else to configure ([app-config.md](app-config.md)). The
   app has to follow the standard: module `:app`, so the debug APK is
   `app/build/outputs/apk/debug/app-debug.apk`, and the default branch `main`. CI then gives it the Claude skill and
   the `CLAUDE.md` block and keeps the callers above in line, through a "Sync from ci-workflows" PR
   ([sync.md](sync.md)): the callers are copied by hand only this once, so that the app's first PR has CI.
6. `ci-workflows` is a public repo, so don't worry about access.

Open a PR: CI first comments with an **AppHub** link (`https://www.lukeneedham.com/apphub/pr/<repo name>/<number>`,
the PR's page in the AppHub app, where the build can be downloaded and installed), then builds the debug APK and
comments with the APK link. The AppHub link depends only on the repo name and the PR number, so **paste it into the
chat as soon as the PR is open** on a line of its own as `📦 [Open in AppHub](<link>)`, and at the top of the PR
description, without waiting for the build, and not the APK link. If the build fails, read the log, fix it, push.

## 4. App icon

Give the app an adaptive launcher icon (`android:icon` pointing to a `mipmap-anydpi*` adaptive icon). The
`app-icon.png` at the repo root, which the app hub reads, is then **generated by CI**: the PR workflow renders
it from the adaptive icon and commits it to the PR branch, and keeps it in step whenever the launcher icon
changes. Do not create or edit it by hand. See [app-icon.md](app-icon.md).

## 5. README

Write the app's **`readme.yml`** by hand, from [readme-template.yml](readme-template.yml): name, tagline,
description (with the highlights of what the app does; no feature list), plus `links` (Play Store, F-Droid, the production
web deploy) if it has any and anything specific to developing the app. **Not the minimum Android version, the license, the
setup or the architecture**: the generator reads the minimum Android version from `minSdk` of the project and the license from
the **`LICENSE` file, which every app has** (an app without a license gets `Copyright (c) <year> Luke Needham. All rights
reserved.`), supplies the generic setup, and the architecture is the same in every app (below). CI renders
`README.md` from it in the standard layout ([readme.md](readme.md)) and commits it to the PR branch, so never edit
`README.md`. The icon in it is the CI-generated `app-icon.png`, so there is nothing to add for it.

**Every app has screenshots**: add a
`screenshot` package in `src/debug`, with a file for each page that has screenshots (a page can have several, or none;
each screenshot is a `@Preview` that owns its mock data and renders the page's content), an `order.txt` listing the
screenshots in README order ([screenshots.md](screenshots.md); the package README is generated by CI). CI then renders every preview of the package
into `docs/screenshots/` (numbered by the order) and the README shows them. The app holds no screenshot dependencies or test: those live in
ci-workflows.

## 6. App architecture

Defaults for a normal app. If the user asks for something else, do that instead.

- **Pages are `XPage` + `XPageContent`, always, each in its own file with its `XViewModel` and `XUiState`** ([pages.md](pages.md)). Each screen is a thin, public `XPage`
  composable that gets its `XViewModel` (always named after the page), collects the state and handles navigation as
  lambdas (its route is always `Route.X`), and delegates all UI to an
  `internal`, stateless `XPageContent` (state down, events up) that has the previews. Never `XScreen`, `XContent` or a
  screen that mixes the two. Any README screenshots of a page are previews in the `screenshot` package
  ([screenshots.md](screenshots.md)).
- **The app shell: single activity, `Root`, `AppNavigation`, `Router`.** One `MainActivity` (extending `ComponentActivity`)
  hosts the whole UI and only calls `setContent { Root() }`; screens are composables, never extra activities or fragments.
  The names, the code and the rules are defined in one place, **[app-shell.md](app-shell.md)**: follow it for every new
  app (existing apps are migrated to it by the same doc).
- **Jetpack Compose, themed by the app's own `AppTheme`** (a hand-made composition local, never
  `MaterialTheme`; see [app-conventions.md](app-conventions.md#theme)). No XML layouts.
- **Navigation 3** (`androidx.navigation3`) for navigation: destinations are `@Serializable` members of one
  `sealed interface Route : NavKey`, the back stack is state the app owns, and the entry provider is type exhaustive
  (an exhaustive `when` in `Router`, never the `entryProvider { entry<...> }` DSL). All of it is in
  **[app-shell.md](app-shell.md)**. The route of `XPage` is always `Route.X` ([pages.md](pages.md)): `Route.Home` is
  `HomePage`. Check the current stable versions and API before using them; Navigation 3 is newer than most
  documentation.
- **MVVM with unidirectional data flow.** Each screen has a `ViewModel` exposing one immutable
  `UiState` as a `StateFlow`; the composable collects it with `collectAsStateWithLifecycle()` and
  sends user actions as plain function calls up to the ViewModel. State goes down, events go up.
  Composables hold no business logic.
- **Coroutines and Flow** for async work; `viewModelScope` for work tied to a screen.
- **Layers.** UI (composables + ViewModels) → domain/data (repositories). Keep Android types out of
  the lower layer so it can be unit-tested on the JVM.
- **Dependency injection: Koin.** Use [Koin](https://insert-koin.io) for DI in every app. Declare
  modules with `module { }` (`singleOf`, `viewModelOf`, `factoryOf`), start it in `Application.onCreate`
  with `startKoin { androidContext(this@App); modules(...) }`, and get ViewModels in composables with
  `koinViewModel()` (`koin-androidx-compose`). Classes take their dependencies as constructor
  parameters and never call Koin themselves, so they stay unit-testable. Check the current Koin version
  and the BOM (`koin-bom`) before adding it.
- **Image loading: Coil 3.** Use [Coil](https://coil-kt.github.io/coil/) **version 3** (group
  `io.coil-kt.coil3`, not the older `io.coil-kt:coil-compose` 2.x) for every image that is not a bundled
  drawable: files, content URIs, and URLs. Add `coil-compose`, plus `coil-network-okhttp` only if the app
  loads images over the network (Coil 3 has no network layer by default). Show images with `AsyncImage`
  (or `rememberAsyncImagePainter` when a `Painter` is needed). Do not use Glide, Picasso, or hand-rolled
  `BitmapFactory` loading. Provide a `contentDescription` (or `null` if decorative), and give it a size so
  Coil can downsample. Check the current stable Coil 3 version before adding it.
- **Tests.** Unit tests for ViewModels and repositories (JUnit, `kotlinx-coroutines-test`).
- **More conventions** (serialization, Room, DataStore, Ktor, kotlinx-datetime, Media3, strings, theme,
  previews, one-off events, touch targets, minified release builds): see
  **[app-conventions.md](app-conventions.md)** and follow it.

## 7. The shared library

**Every app uses the shared library** (`common/`), Compose or not: logger and crash handler, and the optional debug,
logs and crashes pages. Follow **[using-the-library.md](using-the-library.md)** to add it, and use
`Logger` rather than `Log` or `println`.

The debug pages are optional. An app that shows them puts the library's `DebugButton` on a settings page (never a
floating button on the main page); see [A settings page](using-the-library.md#a-settings-page).

## Apps that are not Compose

Some apps are too small for the above, such as the Krillion web-game wrapper: one `WebView` in one
activity. Still do steps 1 to 5 (project, **debug keystore**, **CI workflows**, **app icon**, **README**) and the **shared
library** (logger and crash handler, debug pages), the **app shell** ([app-shell.md](app-shell.md), the same as for every app), and skip the rest. Say which
sections you skipped and why. Such an app has no `screenshot` package (no Compose, no `@Preview`): it sets `screenshots: manual` in `readme.yml` and commits at least one screenshot into `docs/screenshots/` by hand, and CI leaves it alone.

## Done checklist

- [ ] Package is `com.lukeneedham.<app>`; versions match this repo
- [ ] `app/debug.keystore` committed and used by the `debug` signing config
- [ ] All five callers copied unchanged (`trigger_on_pull_request.yml`, `build_main.yml`, `delete_prereleases.yml`, `release.yml`, `previews_main.yml`), module `:app`, default branch `main`
- [ ] Adaptive launcher icon in place (CI then generates `app-icon.png` at the repo root on the first PR)
- [ ] Every page is an `XPage` + `XPageContent`, named and split as in [pages.md](pages.md); a `screenshot` package with the screenshots worth showing (any number per page, none for some pages, at least one in all), and its `order.txt` ([screenshots.md](screenshots.md)), or, for an app that cannot render previews, `screenshots: manual` and at least one hand-committed screenshot in `docs/screenshots/`
- [ ] Handwritten `readme.yml` ([readme.md](readme.md)); CI generates `README.md` from it
- [ ] The app shell as in [app-shell.md](app-shell.md) (`MainActivity` calling only `Root`, `AppNavigation`, an exhaustive `Router`); Compose, Navigation 3, MVVM, Koin for DI, Coil 3 for images, or a stated reason for each departure
- [ ] [app-conventions.md](app-conventions.md) followed: strings in `strings.xml`, own `AppTheme` (no `MaterialTheme`), a preview per composable, 48dp touch targets
- [ ] Shared library added, `DebugKit.init` called first, `Logger` used (debug pages optional)
- [ ] PR opened, CI green, AppHub link pasted to the user
