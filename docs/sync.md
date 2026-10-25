# Syncing the apps

The apps in [`apps.json`](../apps.json) are kept in line with this repo by CI, not by hand and not by
Claude: nothing needs to remember to copy anything.

## What is synced

| What | Where in the app | How |
|---|---|---|
| The Claude skill | `.claude/skills/lukeneedham-conventions/` | Mirrored exactly: files that no longer exist here are deleted |
| The callers | `.github/workflows/`: `trigger_on_pull_request.yml`, `build_main.yml`, `delete_prereleases.yml`, `release.yml` | Copied **byte for byte** from [`callers/`](../callers), **all four to every app**. They hold no settings, so every app has identical files. `release.yml` fails with a clear message in an app that is not set up for releases |
| A note for Claude | A block in the app's `CLAUDE.md`, between `ci-workflows:begin` and `ci-workflows:end` | Replaced each time. Also tells Claude to always paste the PR's AppHub link into the chat when work completes (`CLAUDE.md` is always loaded, unlike the skill). The old "copy the skill by hand" line is replaced by it. The rest of `CLAUDE.md` is the app's |

Not synced: the app's `readme.yml`, which is handwritten, and its `README.md`, which the PR build generates from it
([readme.md](readme.md)); the sync only reports, in its run summary, which apps have no valid `readme.yml`. Also not
synced: the library version, and anything else in the app.

**The callers hold no settings.** Every app is built the same way ([app-config.md](app-config.md)), so there is
nothing to configure per app. The sync overwrites whatever the app has in a caller file, so an edit made in an app is lost.

## When it runs

[`sync_apps.yml`](../.github/workflows/sync_apps.yml) runs when `skills/`, `callers/`, `apps.json` or the script
change on `main`, every Monday, and by hand (*Actions → Sync Apps → Run workflow*, optionally for some apps).
For each app that differs it pushes the branch `sync/ci-workflows` and opens a PR, **Sync from ci-workflows**; if
that PR is already open it is updated (the branch is force-pushed: it belongs to the sync). Nothing is pushed to
an app's default branch, and an app that is already in line gets no PR. Merge the PRs when their CI is green;
CI does run on them, because they are opened with a token and not with `GITHUB_TOKEN`.

A run fails (and GitHub emails you) if any app failed, after trying all of them.

## apps.json

```json
{"name": "AppHub", "repo": "LukeNeedham/AppHub"}
```

| Field | Meaning |
|---|---|
| `name`, `repo` | The app's name and its `owner/name`, **spelled exactly as on GitHub** (`LukeNeedham/Stickerboard`, not `stickerboard`): nothing matches names case-insensitively, including `--apps`. The only fields: every app gets everything, and nothing is configured per app |

**A new app:** add it here (this is also the list "all consuming apps" means), then run *Sync Apps* for it. Its
first sync PR adds the callers, the skill and the `CLAUDE.md` block.

## The token (one-time setup)

The default `GITHUB_TOKEN` of a run cannot write to other repos, nor change workflow files, so the sync uses a
personal access token, kept as the secret `SYNC_TOKEN` of *this* repo.

1. Create a **fine-grained** token at <https://github.com/settings/personal-access-tokens/new>:
   - Resource owner: `LukeNeedham`. Expiration: the longest, 1 year.
   - Repository access: **All repositories** (a new app is then covered without touching the token), or only the apps.
   - Repository permissions: **Contents** read and write, **Pull requests** read and write, **Workflows** read
     and write, **Secrets** read and write (to write the token of the next section into the apps). (Metadata read is
     added by itself.)
2. In this repo: *Settings → Secrets and variables → Actions → New repository secret*, name `SYNC_TOKEN`,
   value the token.
3. Run *Sync Apps* by hand to check it.

The token expires: put the date in your calendar. When it does, runs fail with a 401 and need a new token in the
same secret. It is only ever sent to `github.com` and `api.github.com`, and is masked in the logs.

## The token of the generated commits

CI commits the screenshots, the icon and the README to the branch of a PR. With the workflow token, GitHub holds the
run that commit starts until someone approves it, so the jobs push with a token of the owner instead when the app has
the secret `GENERATED_COMMIT_TOKEN` ([app-config.md](app-config.md)). A workflow of this repo cannot hand its secrets
to the apps (`secrets: inherit` passes the app's own), and a personal account has no secrets shared by all its
repos, so the sync writes the secret into every app on each run.

1. Create a second **fine-grained** token, so that the one that is in every app can do little: Resource owner
   `LukeNeedham`, Repository access **All repositories**, Repository permissions **Contents** read and write only.
   That lets it push to any branch of the apps (which is all the jobs need) but not change workflows, secrets,
   settings or pull requests.
2. In this repo: *Settings → Secrets and variables → Actions → New repository secret*, name `GENERATED_COMMIT_TOKEN`,
   value the token. Give `SYNC_TOKEN` the **Secrets** permission (read and write) too.
3. Run *Sync Apps* by hand. Its summary says `secret GENERATED_COMMIT_TOKEN set` for each app. Without the secret
   the sync only prints a notice, and the apps push with the workflow token as before.

A renewed token reaches the apps on the next sync. Run it by hand after changing the secret.

## Running it yourself

```
SYNC_TOKEN=github_pat_... python3 scripts/sync_apps.py            # every app
python3 scripts/sync_apps.py --dry-run --apps AppHub              # clone, show the changes, push nothing
python3 -m unittest discover -s tests                  # the tests (needs pyyaml)
python3 scripts/generate_readme.py path/to/app --repo owner/name  # render an app's README.md (needs pyyaml)
```

`--dry-run` needs no token for a public repo.

## What starts a sync

[`sync_apps.yml`](../.github/workflows/sync_apps.yml) runs on a push to `main` that changes `skills/**`, `callers/**`,
`apps.json` or **`scripts/**`** (the whole folder: the scripts that the workflows and actions run on the apps, and the
sync itself), every Monday, and by hand.

**What `scripts/` means: a change here reaches every app's CI.** It is not "the folder of scripts" but the code that
the shared workflows and actions run inside the apps, so any change to it can change an app's build, and starts a sync.
That is why the whole folder is the trigger, with no list of files to keep up to date. Everything else that is only
for this repo, namely the tests in `tests/`, is outside it and starts no sync; a script used only inside this repo does
not belong in `scripts/`. The tests, and a lint of the workflows (actionlint), run in
[`test.yml`](../.github/workflows/test.yml).

## Changing what is synced

Change the file in `skills/` or `callers/` and merge: the next run opens the PRs. To sync something new (another
caller, say), add it to `callers/` and to `CALLERS` in the script, and to `docs/setup.md`. A new
setting that belongs to an app goes into `DEFAULTS` in `scripts/app_config.py`.

## Workflows only call scripts

The logic of every workflow is in `scripts/`, tested in `tests/`; a `run:` is a call or a few lines. The
workflows that run in an app (`android_pr_build.yml`, `android_pr_cleanup.yml`, `android_release.yml`) start with the
action [`ci-scripts`](../.github/actions/ci-scripts/action.yml), which sets `CI_SCRIPTS` to the `scripts/` of the same
version of this repo. Values from the event (a branch name, the notes) go in through `env:`, never straight into the
command line.

| Script | Used by |
|---|---|
| `pr_releases.py` | the PR build (stale comment, metadata, superseded) and the cleanup |
| `release.py` | `android_release.yml` |
| `library_release.py` | `library_release.yml` |
| `ghactions.py` | the helpers for step outputs, `GITHUB_ENV` and error annotations |
