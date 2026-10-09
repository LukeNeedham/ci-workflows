# ci-workflows

Shared GitHub Actions workflows, reused across projects via `workflow_call`.

## `android_pr_build.yml`

Builds the APK, publishes it as a pre-release asset, and posts/updates a sticky PR comment with the
download link. As soon as a build starts the comment is switched to "new build in progress" with
the previous APK link kept but flagged stale, and to "build failed"/"cancelled" if the job dies.

Use it from a project with a thin caller at `.github/workflows/trigger_on_pull_request.yml`:

```yaml
name: On Pull Request

on:
  pull_request:
    branches: [main]
  workflow_dispatch: {}

permissions:
  contents: write       # create releases
  pull-requests: write  # sticky comment

jobs:
  build:
    uses: LukeNeedham/ci-workflows/.github/workflows/android_pr_build.yml@main
    secrets: inherit
    # with:
    #   gradle-task: assembleDebug
    #   apk-path: composeApp/build/outputs/apk/debug/composeApp-debug.apk
```

Inputs: `gradle-task`, `apk-path`, `java-version`, `java-distribution`, `timezone`, `comment-header`
(all optional; defaults match FlagTutor).

`@main` always runs the latest version. Pin to a tag (e.g. `@v1`) for stability: a bad push to `main`
would otherwise break every project at once.

## `android_pr_cleanup.yml`

Deletes the pre-releases and tags created by `android_pr_build.yml` for the PR's branch when the PR
merges. Add a second caller (or extend the first):

```yaml
name: On Pull Request Closed

on:
  pull_request:
    types: [closed]

permissions:
  contents: write

jobs:
  cleanup:
    uses: LukeNeedham/ci-workflows/.github/workflows/android_pr_cleanup.yml@main
    # with:
    #   merged-only: false   # also clean up when closed without merging
```

Releases are matched by tag `<branch>-<run>-<attempt>` (the scheme `android_pr_build.yml` uses) and
must be pre-releases, so other releases are never touched.

Notes: the repo must be public (or have Actions access sharing enabled) for other repos to call it;
`on:` triggers and `permissions:` always stay in the caller.

## Composite actions (shared logic)

The workflows keep the orchestration; the logic lives in small composite actions in `actions/`, backed
by stdlib-only Python scripts that have unit tests (`tests/`, run by `.github/workflows/test.yml`,
or locally with `python3 -m unittest discover -s tests`).

| Action | What it does |
|---|---|
| `actions/branch-tag` | `<clean-branch>-<run>-<attempt>` release tag; the single definition of the scheme |
| `actions/pr-comment` | Builds and posts the sticky comment (in progress / success / failed / cancelled), keeping the previous APK link flagged stale |
| `actions/delete-pr-releases` | Deletes a branch's PR-build pre-releases and tags, using the same tag scheme |

Note: the workflows reference these actions with `@main`. A caller pinned to a workflow tag (e.g. `@v1`)
would still run the actions from `main`, so if you start pinning, also pin the `uses:` lines inside the
workflows to the same tag.
