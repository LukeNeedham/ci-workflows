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
| JDK | 17, Zulu |
| Timezone of the timestamps | `Europe/Amsterdam` |
| PR comment id | `<repo name, lower case>-app-link` |
| Library | The shared library ([library.md](library.md)), with `DebugKit.init` called first thing and `Logger` used for logging. The debug pages are optional |
| Workflow files | All four callers in `.github/workflows/`: `trigger_on_pull_request.yml`, `build_main.yml`, `delete_prereleases.yml` and `release.yml` |

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
- **every file the PR changes is under `.claude/skills/`**, so the APK cannot differ. A single other file builds as
  usual. A renamed file counts at its old path too. `SKIPPED_PATHS` in `scripts/app_config.py` is the list; to skip
  more (say `CLAUDE.md`), add to it.

A skipped run still starts (the `config` job runs) and shows `android / build` and the other jobs as *skipped*, which a
required check on them accepts. A rule that requires the job *inside* the call (`android / build / build`) would never
see it reported and wait for ever, so require `android / build` instead. A PR that is closed is only skipped for the
branch rule: its cleanup finds no releases when nothing was built. Manual runs are never skipped. If the list of the PR's
files cannot be read, the PR is built.

## Every app has the release caller

`release.yml` is in every app, so it is always there to run. An app that is not set up for releases yet fails in its
first step, before anything is tagged or built, with one error that lists what is missing: the four repo secrets
(`RELEASE_KEYSTORE_BASE64`, `RELEASE_KEYSTORE_PASSWORD`, `RELEASE_KEY_ALIAS`, `RELEASE_KEY_PASSWORD`) and the
`gradle/android-release.gradle` script in the app's build file, with a link to
[how to set it up](setup.md#3-permanent-releases-optional).

## What stays in the caller

What GitHub only reads from the caller file itself, so it is the same in every app: the triggers (`on:`), the
`permissions:`, and the inputs of a manual run (the version and notes of `release.yml`).
