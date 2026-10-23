# App settings

The callers in the apps carry **no settings**: every app has byte-for-byte the same caller files
([`examples/`](../examples)), copied in by the [sync](sync.md). What differs per app (where its APK ends up, which
branches it builds PRs for, and so on) is its entry in [`apps.json`](../apps.json), the one place for it.

## How it works

Each shared workflow starts by running the composite action
[`.github/actions/app-config`](../.github/actions/app-config/action.yml), which runs
[`scripts/app_config.py`](../scripts/app_config.py). It finds the entry of the repo the workflow runs in
(`github.repository`, any letter case), fills in the defaults for what the entry leaves out, and hands the result to
the build steps. Nothing is passed in by the caller. A change to `apps.json` on `main` therefore applies to the next
run of the app, with no sync PR.

A repo that is not in `apps.json` runs with the defaults and a warning in the log: add it
([consuming-apps.md](consuming-apps.md)).

## The settings

All optional; the default applies when an entry leaves a setting out. The defaults live in `DEFAULTS` in
`scripts/app_config.py` and only there.

| Key | Default | Meaning |
|---|---|---|
| `apk-path` | `app/build/outputs/apk/debug/app-debug.apk` | The debug APK, relative to the repo root. Used by the PR flow and *Build main*. Find it by running the build locally |
| `gradle-task` | `assembleDebug` | Gradle task that produces it. If you change it, change `apk-path` to match |
| `java-version` | `17` | JDK version |
| `java-distribution` | `zulu` | JDK distribution |
| `timezone` | `Europe/Amsterdam` | Timezone of the timestamps in the PR comment and release |
| `comment-header` | `<repo name, lower case>-app-link` | Id of the sticky PR comment. Change it only if a PR needs several APK comments |
| `branches` | `["main"]` | The branches PRs are built for (`*` works as a wildcard, like `release/*`) |
| `release-gradle-task` | `assembleRelease` | Gradle task of the release workflow |
| `release-apk-path` | `app/build/outputs/apk/release/app-release.apk` | The signed APK the release workflow publishes |
| `asset-name` | the repo name, e.g. `Android-Dock.apk` | File name of the APK on a release |

The other keys of an entry (`name`, `repo`, `library`, `skill`, `callers`) are about the sync and the app list:
[sync.md](sync.md#appsjson).

Example, an app whose module is `composeApp` and whose PRs go to `master`:

```json
{"name": "Demo", "repo": "LukeNeedham/Demo", "library": true,
 "apk-path": "composeApp/build/outputs/apk/debug/composeApp-debug.apk", "branches": ["master"]}
```

## Runs that do nothing

For a pull request the `config` job also decides whether there is anything to build, and **skips the whole run**
(no build, no app-icon check, no comment) when:

- the PR targets a branch that is not in the app's `branches`. This is why the callers have no `branches:` filter:
  GitHub only lets the caller file filter triggers, so the callers start for every PR and the check happens here;
- **every file the PR changes is under `.claude/skills/`**, so the APK cannot differ. A single other file builds as
  usual. A renamed file counts at its old path too. `SKIPPED_PATHS` in `scripts/app_config.py` is the list; to skip
  more (say `CLAUDE.md`), add to it.

A skipped run still starts (the `config` job runs) and shows `android / build` and the other jobs as *skipped*, which a
required check on them accepts. A rule that requires the job *inside* the call (`android / build / build`) would never
see it reported and wait for ever, so require `android / build` instead. A PR that is closed is only skipped for
the branch rule: its cleanup finds no releases when nothing was built. Manual runs are never skipped. If the list
of the PR's files cannot be read, the PR is built.

## What stays in the caller

What GitHub only reads from the caller file itself, so it is the same in every app: the triggers (`on:`), the
`permissions:`, and the inputs of a manual run (the version and notes of `release.yml`).
