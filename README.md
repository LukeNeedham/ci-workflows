# ci-workflows

Shared GitHub Actions workflows for Android projects. A project keeps only thin "caller" workflows;
the real logic lives here, so a fix made once reaches every project.

| Workflow | What it does | Runs when |
|---|---|---|
| [`android_pr_build.yml`](.github/workflows/android_pr_build.yml) | Builds the debug APK, publishes it as a pre-release, keeps one sticky PR comment up to date | PR opened or pushed to |
| [`android_pr_cleanup.yml`](.github/workflows/android_pr_cleanup.yml) | Deletes the PR's build pre-releases and tags | PR closed |
| [`delete_prereleases.yml`](.github/workflows/delete_prereleases.yml) | Deletes **all** pre-releases and tags in the repo | Run by hand |

These are [reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows):
a project calls them with `uses:`. Everything below uses
[FlagTutor](https://github.com/LukeNeedham/FlagTutor) as the worked example.

## Using the workflows in a project

A project needs one small file per workflow it wants. FlagTutor's `.github/workflows/` contains:

```
trigger_on_pull_request.yml   calls android_pr_build.yml (plus a project-specific iOS job)
on_pull_request_closed.yml    calls android_pr_cleanup.yml
delete_prereleases.yml        calls delete_prereleases.yml (manual)
```

The caller owns the **triggers** (`on:`) and the **permissions**; the shared workflow owns the steps.
A reusable workflow cannot decide when it runs, and it can never be granted more permissions than
the caller gives it.

### 1. Build the APK and comment on the PR

`.github/workflows/trigger_on_pull_request.yml`:

```yaml
name: On Pull Request

on:
  workflow_dispatch: {}
  pull_request:
    branches:
      - main

permissions:
  contents: write       # create the release that holds the APK
  pull-requests: write  # post the sticky comment

jobs:
  build:
    uses: LukeNeedham/ci-workflows/.github/workflows/android_pr_build.yml@main

  # Project-specific jobs can sit next to the shared one. FlagTutor has an opt-in iOS build:
  build-ios:
    if: github.event_name == 'workflow_dispatch'
    runs-on: macos-14
    steps:
      # ...
```

With no `with:` block the defaults are used, which match FlagTutor's layout. Override whatever
differs in your project:

```yaml
  build:
    uses: LukeNeedham/ci-workflows/.github/workflows/android_pr_build.yml@main
    with:
      gradle-task: assembleDebug
      apk-path: app/build/outputs/apk/debug/app-debug.apk
```

| Input | Default | Meaning |
|---|---|---|
| `gradle-task` | `assembleDebug` | Gradle task that produces the APK |
| `apk-path` | `composeApp/build/outputs/apk/debug/composeApp-debug.apk` | APK location relative to the repo root |
| `java-version` | `17` | JDK version |
| `java-distribution` | `zulu` | JDK distribution |
| `timezone` | `Europe/Amsterdam` | Timezone for the timestamps in the comment and release |
| `comment-header` | `example-app-link` | Id of the sticky comment. Change it only if a PR needs several separate APK comments |

**What the PR sees.** One comment, edited in place as the build progresses, always with the same
layout (a heading with the state's emoji, then a bullet list):

```
### ⏳ Build in progress
- Commit: `be7d718`            (linked to the commit)
- Started: 09/10/2026 12:56:20
- Run: #210                    (linked to the run)
- Previous APK: download ⚠️ stale, does not include this commit

### ✅ Build succeeded
- APK: 📦 Download
- Commit / Built / Run

### ❌ Build failed  /  ### 🚫 Build cancelled
- Commit / Started / Run / Previous APK (stale)
```

- The comment switches to "in progress" as the first step of the job, before the build starts. The
  previous APK link is kept, flagged stale, so reviewers still have something to install.
- If a build fails, or is cancelled by hand, the comment says so instead of claiming it is still
  running.
- A newer push to the same PR **cancels** the running build (see [Concurrency](#concurrency)).
- On a manual run (`workflow_dispatch`) there is no PR, so nothing is commented. The release is
  still created.

**What is published.** A pre-release tagged `<branch>-<run number>-<attempt>` (the branch is
lower-cased and anything other than letters, digits, `.`, `_`, `-` becomes `-`), with the APK as its
asset. The APK link in the comment points at that asset.

### 2. Clean up the releases when the PR closes

Every build creates a release, so they pile up. `.github/workflows/on_pull_request_closed.yml`:

```yaml
name: On Pull Request Closed

on:
  pull_request:
    types: [closed]
    branches:
      - main

permissions:
  contents: write       # delete releases and tags

jobs:
  cleanup:
    uses: LukeNeedham/ci-workflows/.github/workflows/android_pr_cleanup.yml@main
    with:
      merged-only: false
```

| Input | Default | Meaning |
|---|---|---|
| `merged-only` | `true` | `true`: only clean up when the PR was merged. `false`: also when it was closed without merging (FlagTutor uses this) |

It finds the PR's releases by the tag scheme above and only touches **pre-releases**, so real
releases are never deleted. Because it depends on that tag scheme, keep the two workflows on the
same version.

Builds from a manual run have no PR, so nothing ever cleans them up. Use the sweep below for those.

### 3. Sweep all pre-releases by hand

`.github/workflows/delete_prereleases.yml`:

```yaml
name: Delete Pre-releases

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  delete-prereleases:
    uses: LukeNeedham/ci-workflows/.github/workflows/delete_prereleases.yml@main
```

Deletes every pre-release and its tag in the repository, whatever created it, and leaves full
releases alone. Run it from the Actions tab. Use it to clear old builds from before the automatic
cleanup existed, or manual-run builds.

## Things to know

- **Permissions.** `contents: write` and (for the build) `pull-requests: write` must be granted in
  the **caller**. If the shared workflow needs more than the caller allows, the run fails at start.
- **Access.** The calling repo must be allowed to use this repo's workflows: automatic if this repo
  is public; if it is private, enable *Settings → Actions → General → Access*.
- **Pull requests from forks** get a read-only token, so publishing the release and commenting
  fail. The shared workflows do not work around that.
- **Concurrency.** The build job cancels the in-progress build for the same PR when a new push
  arrives, so an older build can never finish last and overwrite the newer build's comment. A run
  cancelled this way stays silent; one cancelled by hand reports "cancelled". Builds for different
  PRs do not affect each other.
- **Versions.** `@main` always runs the latest version, so a fix here reaches every project
  immediately, and so does a mistake. To get stability, call a tag (`@v1`) instead and move the tag
  forward deliberately.
- **Status checks in expressions.** `success()`, `failure()`, `cancelled()` and `always()` only work
  in `if:`. Use `job.status` anywhere else (for example inside a step's `with:`), otherwise GitHub
  rejects the whole workflow and every caller fails at start with no jobs.

## Changing these workflows

Changes to `main` affect every project at once, so:

1. Make the change on a branch and open a PR.
2. To try it before merging, point a test PR in a consuming repo at the branch
   (`...android_pr_build.yml@my-branch`), then switch it back to `@main`.
3. Merge, then watch the next real run in a consuming repo.

When a consuming project's CI behaves oddly, the project's own caller files are usually fine; look
here first.
