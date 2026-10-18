# Setting up a project

How to start using these workflows in a new project, or move an existing project over to them. The
caller files are below, ready to copy. Parts you must or may change per project are marked
`CONFIGURE`; everything else should be copied as is.

For what each workflow does, its inputs and the PR comment it posts, see the
[README](../README.md).

## What lives where

A project keeps small **caller** files in its own `.github/workflows/`; the steps live in this repo.
GitHub does not let a shared workflow choose its own triggers or permissions, so each caller owns:

- **when it runs** (`on:`),
- **what it may do** (`permissions:`),
- **which settings to pass** (`with:`).

Everything else is shared, so a fix here reaches every project.

## Before you start

- The Gradle project must be able to build an Android debug APK from the command line, with a
  Gradle wrapper (`./gradlew`) in the repo root.
- The app must sign its debug builds with a **committed debug keystore**, or each CI build gets a
  random key and cannot be installed over the previous one. See
  [new-app.md](new-app.md#2-debug-keystore).
- If this repo is private, the project's repo must be allowed to use its workflows:
  *Settings → Actions → General → Access* in this repo. (Not needed while it is public.)
- Workflows must be allowed to write. The callers below request `contents: write` and
  `pull-requests: write` themselves, so the repo's default token setting does not matter, but an
  organisation or enterprise policy that restricts token permissions can still cap them, and the
  runs then fail at start.

## 1. The PR flow (required)

Builds the APK on every PR push, comments the download link, and deletes the PR's builds when it
closes.

**File:** [`examples/trigger_on_pull_request.yml`](../examples/trigger_on_pull_request.yml): copy it to
`.github/workflows/trigger_on_pull_request.yml` in your project. Lines marked `CONFIGURE` are the
ones to adjust.

Keep as is: `name`, the `types` list, `permissions`, `uses`.

### Settings to configure

| Setting | Where | Default | Change it when |
|---|---|---|---|
| `branches` | `on.pull_request` | `main` | your PRs target a different branch |
| `apk-path` | `with:` | **none, required** | always: it is the path to the APK your build writes. Find it by running the build locally |
| `gradle-task` | `with:` | `assembleDebug` | you want another variant (for example `assembleStaging`); update `apk-path` to match |
| `java-version` | `with:` | `17` | your Gradle build needs another JDK |
| `java-distribution` | `with:` | `zulu` | you need another JDK distribution |
| `timezone` | `with:` | `Europe/Amsterdam` | you want timestamps in another timezone |
| `comment-header` | `with:` | `example-app-link` | one PR needs more than one APK comment (give each a different id) |
| `detekt-task` | `with:` | `detekt` | your Detekt Gradle task has another name |

### Detekt

The same workflow also runs a `detekt` job on every PR push, next to the build. The project must apply
the Detekt Gradle plugin ([app-conventions.md](app-conventions.md#detekt)); without a `detekt` task the
job fails with a message saying so. The check shows up as `android / detekt`.

### Other jobs in the same file

Project-specific jobs can sit next to `android:` in the same `jobs:` block. They are not part of
the shared workflows and are not affected by them.

## 2. Sweep all pre-releases (optional)

A manual button that deletes **every** pre-release and tag in the repo. Useful once when migrating
(to clear old builds the cleanup never saw) and for builds from manual runs, which have no PR to
clean them up.

**File:** [`examples/delete_prereleases.yml`](../examples/delete_prereleases.yml): copy it to
`.github/workflows/delete_prereleases.yml` in your project.

Nothing to configure. Run it from the *Actions* tab. It only deletes pre-releases, never full
releases, but it deletes **all** of them, whoever made them. If the repo publishes real releases
that are marked as pre-release (for example betas), do not add this file.

## 3. Permanent releases (optional)

A manual button that publishes a signed release with a fixed download link, for testers. The version
comes from a git tag (`0.3.0`, no `v`), which the workflow creates.

1. **In the app's `build.gradle.kts`**, right after the `plugins {}` block, add:
   ```kotlin
   apply(from = "https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/gradle/android-release.gradle")
   ```
   and remove the app's own `versionCode`, `versionName` and release signing config; the script
   sets them. Builds then need network to fetch the script the first time, and
   `--refresh-dependencies` picks up a changed script on a machine that cached the old one.
2. **Copy** [`examples/release.yml`](../examples/release.yml) to `.github/workflows/release.yml`.
3. **Make a signing key** and add four repo secrets (*Settings → Secrets and variables → Actions*):
   `RELEASE_KEYSTORE_BASE64` (the keystore, base64 on one line), `RELEASE_KEYSTORE_PASSWORD`,
   `RELEASE_KEY_ALIAS`, `RELEASE_KEY_PASSWORD`. Keep a copy of the key somewhere safe: an app signed
   with a new key cannot update the old one, so testers would have to reinstall.
4. **Run it**: *Actions → Release → Run workflow* on the default branch, with a version.

Release builds are signed with a different key from the debug builds on pull requests, so a tester
moving from a PR build to a release uninstalls once. The tester link is
`https://github.com/<owner>/<repo>/releases/latest/download/<RepoName>.apk`.

## Setting up a new project

1. Copy `examples/trigger_on_pull_request.yml` to `.github/workflows/trigger_on_pull_request.yml`
   and set `apk-path` (and anything else marked `CONFIGURE`).
2. Optionally copy `examples/delete_prereleases.yml` to `.github/workflows/delete_prereleases.yml`.
3. Commit both on a branch and open a PR to the target branch.
4. [Check it works](#check-that-it-works).

## Migrating an existing project

Assuming the project already builds an APK on pull requests with its own workflow(s).

1. **Collect the project's current settings** from the old workflow, because they become the
   `with:` values:
   - the Gradle task it runs → `gradle-task`
   - where the APK ends up → `apk-path`
   - the JDK version and distribution → `java-version`, `java-distribution`
   - the branch(es) it triggers on → `branches`
2. **Replace the old build workflow** with the file from section 1, filled in with those values.
   Keep any jobs in it that the shared workflows do not cover in the same `jobs:` block.
3. **Delete the old cleanup workflow**, if there is one: the cleanup now runs from the same file.
   Make sure the project has exactly one workflow reacting to PR closes, otherwise releases are
   deleted twice.
4. **Check branch protection.** The checks are now named `<caller job> / build / build` (caller
   job / shared wrapper job / build job), so `android / build / build` with the file above. If a
   rule requires the old check name, update it, or PRs will wait for a check that no longer exists.
5. **Replace the manual delete workflow**, if the project has one, with section 2.
6. **Open a PR** and [check it works](#check-that-it-works).
7. **Clear the old releases** once it works: run *Delete Pre-releases* (section 2) to remove builds
   made by the old workflow, which the new cleanup does not know about.

To roll back, restore the old workflow files from git. Nothing else is changed in the repo.

## Check that it works

On the PR you opened:

1. A comment appears within seconds: **⏳ Build in progress**.
2. When the build finishes it becomes **✅ Build succeeded** with a *Download* link. Install that
   APK to confirm it is the one from the right commit (the comment links the commit).
3. Push another commit. The first build is cancelled if still running, the comment goes back to
   **⏳ Build in progress** and keeps the previous link as *stale*, then ends on the new build.
4. Close or merge the PR. The *Releases* page should lose the PR's `<branch>-<run>-<attempt>`
   pre-releases. (If a build was still running when you closed it, that build is cancelled and its
   comment ends as **🚫 Build cancelled**.)

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| The run fails immediately with no jobs | The caller file is invalid, or a permission it requests is not allowed. Check the *Actions* run page for the message; confirm `permissions:` is as above and that the repo may use this repo's workflows (private repos need *Access* enabled here) |
| No comment appears on the PR | The caller is missing `pull-requests: write`, or the PR comes from a fork (forks get a read-only token) |
| The release step fails with "no files found" | `apk-path` is wrong. Build locally and use the real path, relative to the repo root |
| Releases are not deleted when the PR closes | `closed` is missing from the caller's `types` list |
| The PR waits forever for a check | Branch protection still requires the old check name (see migration step 4) |
| Old PR builds are still listed | They predate the cleanup: run *Delete Pre-releases* |
