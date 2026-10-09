# ci-workflows

Shared GitHub Actions workflows for Android projects (Android only for now). A project keeps only thin "caller" workflows;
the real logic lives here, so a fix made once reaches every project.

| Workflow | What it does | Runs when |
|---|---|---|
| [`android_pr.yml`](.github/workflows/android_pr.yml) | **The whole PR flow in one call**: runs the build while the PR is open and the cleanup when it closes | PR opened, pushed to, or closed |
| [`android_pr_build.yml`](.github/workflows/android_pr_build.yml) | *Building block.* Builds the debug APK, publishes it as a pre-release, keeps one sticky PR comment up to date | PR opened or pushed to |
| [`android_pr_cleanup.yml`](.github/workflows/android_pr_cleanup.yml) | *Building block.* Deletes the PR's build pre-releases and tags | PR closed |
| [`delete_prereleases.yml`](.github/workflows/delete_prereleases.yml) | Deletes **all** pre-releases and tags in the repo | Run by hand |

`android_pr.yml` just chooses between the build and the cleanup workflow from the event. It is the
one to call: it owns the input defaults, and the build and cleanup workflows are its building
blocks (all of their inputs are required, with no defaults of their own). `delete_prereleases.yml`
is a separate manual job.

These are [reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows):
a project calls them with `uses:`.

## Setting up a project

**See [docs/setup.md](docs/setup.md)** for the caller files to copy, which parts to configure per
project, and how to migrate an existing project.

In short: a project keeps small caller files that own the **triggers** (`on:`), the **permissions**
and the **settings** (`with:`); the steps live here. A reusable workflow cannot decide when it
runs, and it can never be granted more permissions than the caller gives it, so those cannot be
moved here.

## Reference

### `android_pr.yml`

Inputs (the defaults live here and only here; `apk-path` is the one required input):

| Input | Default | Meaning |
|---|---|---|
| `gradle-task` | `assembleDebug` | Gradle task that produces the APK |
| `apk-path` | **required** | APK location relative to the repo root |
| `java-version` | `17` | JDK version |
| `java-distribution` | `zulu` | JDK distribution |
| `timezone` | `Europe/Amsterdam` | Timezone for the timestamps in the comment and release |
| `comment-header` | `example-app-link` | Id of the sticky comment. Change it only if a PR needs several separate APK comments |
| `merged-only` | `true` | `true`: only clean up when the PR was merged. `false`: also when it was closed without merging |

`closed` has to be among the caller's `pull_request` types: that is the event that triggers the
cleanup. Everything else (`opened`, `reopened`, `synchronize`) runs the build. A manual run
(`workflow_dispatch`) builds.

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
- A newer push to the same PR **cancels** the running build (see [Concurrency](#things-to-know)).
- On a manual run (`workflow_dispatch`) there is no PR, so nothing is commented. The release is
  still created.

**What is published.** A pre-release tagged `<branch>-<run number>-<attempt>` (the branch is
lower-cased and anything other than letters, digits, `.`, `_`, `-` becomes `-`), with the APK as its
asset. The APK link in the comment points at that asset.

**What the cleanup does.** When the PR closes it finds that PR's releases by the tag scheme above
and deletes them with their tags. It only touches **pre-releases**, so real releases are never
deleted. Builds from a manual run have no PR, so nothing ever cleans them up; use
`delete_prereleases.yml` for those.

### `delete_prereleases.yml`

Deletes every pre-release and its tag in the repository, whatever created it, and leaves full
releases alone. Use it to clear old builds from before the automatic cleanup existed, or builds
from manual runs.

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
  PRs do not affect each other. The cleanup shares the same group, so closing a PR also cancels a
  build still running for it; otherwise that build could publish a release after the cleanup ran.
- **Check names.** Through `android_pr.yml` the jobs show up in PR checks as `android / build / build`
  (caller job / wrapper job / build job) instead of `build / build`. If branch protection requires a
  specific check name, update it after switching.
- **Input defaults.** They are defined once, in `android_pr.yml`. The build and cleanup workflows
  take every input as required, so calling one of them directly means passing all of its inputs.
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
