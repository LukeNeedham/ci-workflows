# Setting up a project

How to start using these workflows in a new project, or move an existing project over to them. The
caller files are in [`callers/`](../callers) and have no settings: copy them as they are (all of them). For an app
in `apps.json` the [sync](sync.md) copies the callers by itself.

For what each workflow does, its inputs and the PR comment it posts, see the
[README](../README.md).

## What lives where

A project keeps small **caller** files in its own `.github/workflows/`; the steps live in this repo.
GitHub does not let a shared workflow choose its own triggers or permissions, so each caller owns:

- **when it runs** (`on:`),
- **what it may do** (`permissions:`).

Everything else is shared, so a fix here reaches every project. There are no per-project settings: every
project is built the same way ([app-config.md](app-config.md)).

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

**File:** [`callers/trigger_on_pull_request.yml`](../callers/trigger_on_pull_request.yml): copy it, unchanged, to
`.github/workflows/trigger_on_pull_request.yml` in your project. There is nothing to edit in it.

It runs on all the pull request types (`opened`, `reopened`, `synchronize`, `closed`): `closed` runs the cleanup of the PR's
builds, the others build. Only PRs into `main` are built; the shared workflow skips the rest.

### Settings

There are none: every app is built the same way ([app-config.md](app-config.md)). The debug APK has to be at
`app/build/outputs/apk/debug/app-debug.apk` (module `:app`), and PRs are built when they go to `main`.

A PR that changes only the Claude skill (`.claude/skills/`) does not build; see
[app-config.md](app-config.md#runs-that-do-nothing).

### Other jobs in the same file

Project-specific jobs can sit next to `android:` in the same `jobs:` block. They are not part of
the shared workflows and are not affected by them.

## 2. Sweep all pre-releases (optional)

A manual button that deletes **every** pre-release and tag in the repo. Useful once when migrating
(to clear old builds the cleanup never saw) and for builds from manual runs, which have no PR to
clean them up.

**File:** [`callers/delete_prereleases.yml`](../callers/delete_prereleases.yml): copy it, unchanged, to
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
2. **`release.yml`** is already in the app (every app has it, from the sync). Until steps 1 and 3 are done, running it
   fails in its first step, before anything is tagged or built, with one error that lists what is missing: the four repo
   secrets of step 3 and the Gradle script of step 1.
3. **Make a signing key** and add four repo secrets (*Settings → Secrets and variables → Actions*):
   `RELEASE_KEYSTORE_BASE64` (the keystore, base64 on one line), `RELEASE_KEYSTORE_PASSWORD`,
   `RELEASE_KEY_ALIAS`, `RELEASE_KEY_PASSWORD`. Keep a copy of the key somewhere safe: an app signed
   with a new key cannot update the old one, so testers would have to reinstall.
4. **Run it**: *Actions → Release → Run workflow* on the default branch, with a version.

Release builds are signed with a different key from the debug builds on pull requests, so a tester
moving from a PR build to a release uninstalls once. The tester link is
`https://github.com/<owner>/<repo>/releases/latest/download/<RepoName>.apk`.

## 4. Build main on demand (optional, expected by AppHub)

A manual build of the default branch that keeps its APK for one day, as a workflow artifact. AppHub shows a
*Build main* button for every repo that has it, starts the run through the API, reports its progress, and
offers the APK to install. It can also be run from the *Actions* tab.

**File:** [`callers/build_main.yml`](../callers/build_main.yml): copy it, unchanged, to
`.github/workflows/build_main.yml` in your project.
**Keep the file name**: AppHub starts `build_main.yml` on `main`. It must be on `main` before it can be run.

Starting it from AppHub needs a GitHub token with **Actions: Read and write** on the repo; downloading the
APK needs *Actions: Read*. See the AppHub README for creating one.

## 5. Previews of main

On each push to `main`, renders every `@Preview` of the app and keeps the images as the baseline that PRs compare their previews
with ([previews.md](previews.md)). It needs no settings and does not build or publish an APK.

**File:** [`callers/previews_main.yml`](../callers/previews_main.yml): copy it, unchanged, to
`.github/workflows/previews_main.yml` in your project.

## Setting up a new project

1. Add the project to [`apps.json`](../apps.json): its `name` and `repo`.
2. Copy all the files of `callers/` to `.github/workflows/` in the project, unchanged. After the first
   copy the [sync](sync.md) keeps them in line.
3. Commit them on a branch and open a PR to the target branch.
4. [Check it works](#check-that-it-works).

## Migrating an existing project

Assuming the project already builds an APK on pull requests with its own workflow(s).

1. **Make the project follow the standard** ([app-config.md](app-config.md)), because the workflows have no
   settings: module `:app` (so the debug APK is at `app/build/outputs/apk/debug/app-debug.apk`), JDK 17, and
   `main` as the branch PRs go to. Rename the module or the default branch first if they differ.
2. **Replace the old build workflow** with `callers/trigger_on_pull_request.yml`, unchanged. Keep any jobs in
   it that the shared workflows do not cover in the same `jobs:` block.
3. **Delete the old cleanup workflow**, if there is one: the cleanup now runs from the same file.
   Make sure the project has exactly one workflow reacting to PR closes, otherwise releases are
   deleted twice.
4. **Check branch protection.** The checks are now named `<caller job> / build / build` (caller
   job / shared wrapper job / build job), so `android / build / build` with the file above. If a
   rule requires the old check name, update it, or PRs will wait for a check that no longer exists. A PR that
   does not build (see [app-config.md](app-config.md#runs-that-do-nothing)) never reports `android / build / build`,
   so require `android / build`.
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
| The build step cannot find the APK | The project does not follow the standard: the debug APK has to be at `app/build/outputs/apk/debug/app-debug.apk`, so the module must be `:app` ([app-config.md](app-config.md)) |
| The run is skipped | The PR changes only `.claude/skills/`, or does not target `main` ([app-config.md](app-config.md#runs-that-do-nothing)) |
| Releases are not deleted when the PR closes | `closed` is missing from the caller's `types` list |
| The PR waits forever for a check | Branch protection still requires the old check name (see migration step 4) |
| Old PR builds are still listed | They predate the cleanup: run *Delete Pre-releases* |
