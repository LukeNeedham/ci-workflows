# Creating an app repo

A new app repo is created and set up with no LLM. Claude cannot create repos (the integration gets a 403), so this
replaces creating the repo by hand in the browser. It is split in two, so that **this repo holds no token that can create
repos**:

1. **The repo is created by the caller**, with a token of its own that may create repos: a person, or a program that calls the
   dispatch API (below), such as the app hub.
2. **The setup of the repo is done here**, by **[`new_app.yml`](../.github/workflows/new_app.yml)**, which runs
   [`scripts/new_app.py`](../scripts/new_app.py) with the secrets this repo already has for the [sync](sync.md). The caller
   starts it, from the Actions tab or with the dispatch API, with *resume* on, as the repo is there already.

## What it does

In this order. Every step can be repeated, so a run that stopped half way is finished by running it again with
**resume**.

1. **The repo** `LukeNeedham/<name>`, with a README so that `main` exists, public by default (the
   images of the preview comment on PRs are served from the repo's public releases, [previews.md](previews.md), so a private repo has
   none; the **private** option makes it private), and its default branch is `main`. The caller does this before it starts the
   workflow. The workflow does it too, only when it has a token that may create repos (`NEW_APP_TOKEN`, optional, below);
   without one it needs the repo to exist, and *resume* on.
2. **Pushes the first commit to `main`** (not a PR: there is nothing to protect yet). It holds:
   - **the first sync**, made by the same code as [`sync_apps.py`](../scripts/sync_apps.py) (the skill, all the callers and the
     managed block of `CLAUDE.md`), so the next sync finds the app up to date and opens no PR;
   - **a Kotlin Multiplatform project that builds, with the Android target only**, so that the app starts where
     [new-app.md](new-app.md) leaves off after its project, shell and library steps. The files are the templates of
     [`templates/new-app/`](../templates/new-app), with the package (`com.lukeneedham.<name>`), the name, the versions of AGP,
     Kotlin and Compose Multiplatform of this repo (the ones the shared library is built with) and the latest version of the
     shared library filled in, plus the Gradle wrapper (a copy of this repo's), `settings.gradle.kts` (this repo's repository
     rules, the repository of the shared library, the app's name, and the module `:app`), `.gitignore`, `LICENSE` (*Copyright (c)
     year Luke Needham. All rights reserved.*, the default of [readme.md](readme.md)) and the committed `app/debug.keystore`
     ([new-app.md](new-app.md#2-debug-keystore)).

   **The app is Kotlin Multiplatform from the start**, as `:app` with the plugins `kotlinMultiplatform` and `androidApplication`
   together (the debug APK stays at `app/build/outputs/apk/debug/app-debug.apk`), and only the `androidTarget`. What is in each
   source set:
   - **`commonMain`**: everything that is the app, and nothing that only Android has: the shell, the theme, the pages, the Koin
     module, `initDebugKit(isDebug)`, and the strings as **Compose Multiplatform resources**
     (`composeResources/values/strings.xml`, read with `stringResource(Res.string.…)`; `Res` is generated in
     `<package>.generated.resources`). A test checks that no file of it imports `android.*`, `BuildConfig`, `java.*` or an
     Android-only library, so that another target can be added without moving code;
   - **`androidMain`**: `App` (`initDebugKit(BuildConfig.DEBUG)` first, then Koin with `androidContext`), `MainActivity` (only
     `setContent { Root() }`), the manifest and the Android resources (the app name, the theme, the launcher icon);
   - **`androidDebug`**: the `screenshot` package ([screenshots.md](screenshots.md));
   - **`commonTest`**: the tests (`kotlin.test`, names without spaces, so that they run on every target).

   The app of the templates has:
   - **the dependencies of the architecture** in `gradle/libs.versions.toml` and `app/build.gradle.kts`. In `commonMain`: Compose
     Multiplatform, Navigation 3 (the JetBrains artifacts) and the lifecycle, Koin, Coil 3, `kotlinx.serialization`, Ktor, the
     coroutines, `kotlinx-datetime` and the shared library. In `androidMain`, as they are not for every target: activity-compose,
     Koin's Android part, Room (with KSP, `kspAndroid`), DataStore, Media3, the OkHttp engines of Coil and Ktor and the coroutines'
     Android part; they move to the source set of the targets that have them. Release builds are minified, with the keep rules
     (`proguard-rules.pro`);
   - **`App`** and **`MainActivity`**, as above;
   - **the shell of [app-shell.md](app-shell.md)**: `Root` (`AppTheme`, `ProvideDebugSettings`, `AppNavigation()`),
     `AppNavigation`, an exhaustive `Router` and the one `sealed interface Route : NavKey` with `Settings`, `Debug`, `Logs`
     and `Crashes` (the three of the library's pages). The back stack is saved with a `SavedStateConfiguration` that registers
     every route, as iOS and the web need ([app-shell.md](app-shell.md#exceptions)): a new route is added there too;
   - **the app's own `AppTheme`** (a composition local, light and dark, no Material) and `toDebugTheme()`;
   - **one page, `SettingsPage`** ([pages.md](pages.md)): `SettingsPage`, `SettingsPageContent` (the title and the library's
     `DebugButton`, which opens the library's debug page) with its `Preview`, `SettingsViewModel` and `SettingsUiState`, each in its
     own file, its screenshot and a unit test of its ViewModel;
   - **a manifest and a placeholder adaptive launcher icon** (a white diamond: replace it).

   **Adding a target later** (iOS, the web): add it in `app/build.gradle.kts` (`iosArm64()` and `iosSimulatorArm64()`, never
   `iosX64`; the web needs Kotlin 2.3 or newer: [app-shell.md](app-shell.md#exceptions)), give it its entry point and its own
   `initDebugKit(...)` call, and move what is Android-only in `androidMain` to a source set that has it.
   - **a `readme.yml`** with the name and **placeholder text** (`TODO: ...`) for the tagline and the description, so that
     the README, its screenshots and the sync's report apply from the first PR. It is the app's to write: replace the text.

   What it does **not** make is what is the app's own: the real icon, the other pages, the release setup, and what the app does. That is the first session on the app, which follows [new-app.md](new-app.md). Nothing
   the app already has is overwritten.

   The push starts the **main build** of the new repo ([`build_main.yml`](../callers/build_main.yml)): it is the first check that
   the templates still build, as they cannot be compiled here. A red build of a new app means a template needs fixing.
3. **Writes the secret** `GENERATED_COMMIT_TOKEN` into the repo ([sync.md](sync.md#the-token-of-the-generated-commits)).
4. **Adds the app to [`apps.json`](../apps.json)** with a commit to `main` of this repo: one new line, nothing else, and not
   if the app is listed. It is last, so that the sync this starts finds nothing left to do. A commit that lands at the same
   moment is retried on top of it. If `main` requires PRs, this step fails with the error of GitHub: the repo exists
   and is set up, so run again with *resume* after adding the line by hand.

The run summary lists what was done, and **Next**: the repo, the package (`com.lukeneedham.<name lower case, letters and
digits>`), a link to start a Claude Code session on it, and the one step left that cannot be automated (below).

## The one step left: the Claude GitHub App

A session can only push to a repo that the Claude GitHub App may reach. If the installation covers **all repositories**
there is nothing to do. If it covers only some, add the new repo at
<https://github.com/apps/claude/installations/select_target>. Switching the installation to *All repositories* once
removes this step from every new app.

## Names

Letters, digits, hyphens and underscores, starting with a letter, 2 to 50 characters, no doubled or trailing hyphen or
underscore (`LyricTutor`, `LT-Companion`). The name is the repo and the entry `name` in `apps.json`, and
spelled exactly: nothing matches names case-insensitively ([sync.md](sync.md#appsjson)). The script refuses anything else,
and a name that is taken (a repo, or an entry of `apps.json`), unless *resume* is on.

## The tokens (one-time setup)

**Nothing new is needed in this repo.** The workflow uses the secrets of the sync:

| Secret | Used for | Notes |
|---|---|---|
| `SYNC_TOKEN` | The first commit, the secret, and the line of `apps.json` | The token of [sync.md](sync.md#the-token-one-time-setup): Contents, Workflows and Secrets on **All repositories**, which covers a repo made later; Contents on this repo. **It is not given the power to create repos** |
| `GENERATED_COMMIT_TOKEN` | Handed on to the new app | Already there for the sync |
| `NEW_APP_TOKEN` | *Optional.* Creating the repo from the workflow | Only for running the workflow by hand without making the repo first. Left out, the workflow needs the repo to exist. A token that can create repos is better kept off this repo: a caller that makes the repo itself does not need it |

**Outside this repo**, the caller has two tokens:

- **A token that starts the workflow**: the Actions permission (read and write) for this repo, to start it and read its run.
- **A token that creates the repo** (and renames its branch to `main`): kept by the caller, never in this repo's secrets, and it
  only creates repos. A **fine-grained** token for all repositories of `LukeNeedham` with **Repository creation** (write), or
  **Administration** (write) if the token page does not offer it; or a **classic** token with the scope `repo`. Prefer the
  fine-grained one with *Repository creation*: *Administration* also lets a token change settings and delete repos.

**Fine-grained tokens.** GitHub's own data for the permissions table of the REST API (`fine-grained-pat-permissions.json` of
`github/docs`) lists `POST /user/repos`, the call that creates a repo for a personal account, as available to fine-grained
personal access tokens, under two permissions, both at the level *write*: **Administration** (a repository permission) and
**Repository creation**. It is flagged as needing additional permissions, which the data does not spell out, so what this does
not tell is whether either one alone is enough, and whether the token page offers "Repository creation" to a personal
token. A fine-grained token is made for **All repositories**, so that it covers a repo that does not exist yet.

This was read from the documentation source, not tried with a token, so test the one you make before relying on it:

```
curl -s -o /dev/null -D - -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer github_pat_..." -H "Accept: application/vnd.github+json" \
  -d '{"name":"token-test-delete-me","private":true}' | grep -i "^HTTP\|x-accepted-github-permissions"
```

A `201` means it works (delete the test repo again); a `403` names the permission it wanted in
`x-accepted-github-permissions`. If it does not work, use a classic token with `repo`, which can write to every repo of the
account: keep it with the caller, not in this repo.

## Running it yourself

```
NEW_APP_TOKEN=... SYNC_TOKEN=... GENERATED_COMMIT_TOKEN=... python3 scripts/new_app.py LyricTutor [--private] [--resume]
python3 scripts/new_app.py LyricTutor --dry-run        # check the name, change nothing
python3 -m unittest discover -s tests                  # the tests (need pyyaml; `keytool` for the keystore test)
```

Without `NEW_APP_TOKEN` the repo has to exist: pass `--resume`.

## Starting the dispatch from another program

`POST /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/dispatches` with `{"ref": "main", "inputs": {"name":
"LyricTutor", "resume": "true"}}` (inputs are strings) and a token that may write Actions on this repo. It answers `204`
with no run id: the run is found in
`GET /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/runs?event=workflow_dispatch`, newest first, by its
`display_title`, which is `New App <name>` (the `run-name` of the workflow). A caller that may start the same app twice
notes the ids of the runs there are before it dispatches, and takes the new one.
