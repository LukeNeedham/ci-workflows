# One standard for every app

Every app is built the same way, so there is **nothing to configure per app**: not in the app's workflow files, and
not in [`apps.json`](../apps.json), which only lists the apps (`name` and `repo`). An app follows the standard; it does not
get an option to differ from it.

## The standard

| | |
|---|---|
| Module | `:app`, built with `./gradlew assembleDebug` |
| Debug APK | `app/build/outputs/apk/debug/app-debug.apk` |
| Release APK | `app/build/outputs/apk/release/app-release.apk` (`assembleRelease`), published as `<RepoName>.apk` |
| Branch | `main`. PRs into any other branch are not built |
| JDK | 17, Temurin |
| Timezone of the timestamps | `Europe/Amsterdam` |
| PR comment id | `<repo name, lower case>-app-link` |
| Library | The shared library ([library.md](library.md)), with `DebugKit.init` called first thing and `Logger` used for logging. The debug pages are optional. An app that makes network calls adds `NetworkLogInterceptor()` to its HTTP client |
| Workflow files | All callers of [`callers/`](../callers) in `.github/workflows/` ([setup.md](setup.md) documents each) |

The values are in `scripts/app_config.py` and only there. Changing one changes it for every app, so change the apps
first if they do not match yet. An app that cannot follow a rule has to be changed, not given an exception.

## How the workflows get them

Each shared workflow starts by running the composite action
[`.github/actions/app-config`](../.github/actions/app-config/action.yml), which runs
[`scripts/app_config.py`](../scripts/app_config.py) and hands the values to the build steps. The callers in the apps
pass nothing in: they are identical in every app, and the [sync](sync.md) copies them byte for byte.

## Runs that do nothing

For a pull request the same step decides whether there is anything to build, and **skips the whole run** (no build, no
app-icon check, no comment) when:

- the PR targets a branch other than `main`. GitHub only lets the caller file filter triggers, so the callers start
  for every PR and the check happens here;
- **no file the PR changes is an Android source file**: every file is under `docs/` or `.claude/` (the skill), or is a
  Markdown file outside a `src/` folder (Markdown under `src/` can be packaged as an asset or raw resource). The APK
  cannot differ. A single other file builds as usual. A renamed file counts at its old path too. `SKIPPED_PATHS` and
  `is_skipped_file` in `scripts/app_config.py` are the rule; to skip more, extend them;
- **the push that started the run changed only files that CI generates** (`docs/screenshots/`, `README.md`,
  `app-icon.png`, the README of the screenshot package): that is CI's own commit, which cannot change the APK.
  `GENERATED_PATHS` in `scripts/app_config.py` is the list. This looks at the push (`github.event.before` to `after`),
  not at the whole PR, so a PR that also changes code skips only these commits. If the push cannot be listed (a
  force-push, say), the run builds. **It is skipped only if the commit before the push was built**
  ([`scripts/was_built.py`](../scripts/was_built.py) reads the sticky comment of the PR, which names the commit of the latest build and
  whether it was cancelled): two pushes within seconds (yours, then CI's) can leave the first without a run, and it must not then be
  skipped for being "under" a generated commit. If the comment cannot be read, the run builds.

### Generated files are made for the commit that was built

The jobs that commit generated files (app-icon, screenshots, readme) start from the head of the PR as it is when they start, but their files
are made from the commit the run was started for. If a newer push has put code on the branch since, committing them would put files made
from old code on top of new code, and, being only generated files, that commit is not built. So
[`scripts/commit_generated.py`](../scripts/commit_generated.py) commits only while the branch is at the commit of the run, or has gained
nothing but generated files since (another job's commit); otherwise it leaves them out and says so, and the newer push's own run
generates them. A force-pushed branch is treated the same way.

### The token of the generated commits

The jobs that commit generated files push with the secret `GENERATED_COMMIT_TOKEN` of the app when it has it, and with the workflow
token otherwise. A commit pushed with the workflow token does start a run, but GitHub holds it until someone approves
it; one pushed with a token of the owner starts without. The run is then skipped by the rule above, so the commit has
its checks and costs no build. The callers pass the app's own secrets on (`secrets: inherit`; a reusable workflow
cannot read the secrets of this repo), so every app needs the secret itself: *Sync Apps* writes it into each app
([sync.md](sync.md#the-token-of-the-generated-commits)). Its token needs only write access to the contents of the apps.

A skipped run still starts (the `config` job runs) and shows `android / build` and the other jobs as *skipped*, which a
required check on them accepts. A rule that requires the job *inside* the call (`android / build / build`) would never
see it reported and wait for ever, so require `android / build` instead. A PR that is closed is only skipped for the
branch rule: its cleanup finds no releases when nothing was built. Manual runs are never skipped. If the list of the PR's
files cannot be read, the PR is built.

## What stays in the caller

What GitHub only reads from the caller file itself, so it is the same in every app: the triggers (`on:`), the
`permissions:`, and the inputs of a manual run (the version and notes of the release caller). The files in
[`callers/`](../callers) carry one comment, that they are copied from here and not to be edited in the app; what each one
does is documented in [setup.md](setup.md), the one place that describes the callers.
