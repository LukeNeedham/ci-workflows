# Syncing the apps

The apps in [`apps.json`](../apps.json) are kept in line with this repo by CI, not by hand and not by
Claude: nothing needs to remember to copy anything.

## What is synced

| What | Where in the app | How |
|---|---|---|
| The Claude skill | `.claude/skills/lukeneedham-conventions/` | Mirrored exactly: files that no longer exist here are deleted |
| The callers | `.github/workflows/`: `trigger_on_pull_request.yml`, `build_main.yml`, `delete_prereleases.yml` | Rendered from [`examples/`](../examples), **keeping the app's own settings** (see below) |
| A note for Claude | A block in the app's `CLAUDE.md`, between `ci-workflows:begin` and `ci-workflows:end` | Replaced each time. Also tells Claude to always paste the PR's AppHub link into the chat when work completes (`CLAUDE.md` is always loaded, unlike the skill). The old "copy the skill by hand" line is replaced by it. The rest of `CLAUDE.md` is the app's |

Not synced: the app's `README.md`, which is handwritten ([readme.md](readme.md)); the sync only reports, in its run
summary, which READMEs are missing or not in the standard format. Also not synced: `release.yml` (it needs the app's signing secrets, so an app opts in with `callers`, below), the
library version, and anything else in the app.

**An app's own settings stay.** In a caller, the `with:` settings `apk-path`, `gradle-task`, `java-version`,
`java-distribution`, `timezone` and `comment-header`, and the `branches:` list, are read from the app's
current file and put into the new one. `build_main.yml` takes any it lacks from the app's PR caller, so
`apk-path` is set once. An app with no caller yet gets the example's `apk-path` and a `comment-header` of
`<repo name>-app-link`. To set one from here instead, use `inputs` in `apps.json`.

## When it runs

[`sync_apps.yml`](../.github/workflows/sync_apps.yml) runs when `skills/`, `examples/`, `apps.json` or the script
change on `main`, every Monday, and by hand (*Actions → Sync Apps → Run workflow*, optionally for some apps).
For each app that differs it pushes the branch `sync/ci-workflows` and opens a PR, **Sync from ci-workflows**; if
that PR is already open it is updated (the branch is force-pushed: it belongs to the sync). Nothing is pushed to
an app's default branch, and an app that is already in line gets no PR. Merge the PRs when their CI is green;
CI does run on them, because they are opened with a token and not with `GITHUB_TOKEN`.

A run fails (and GitHub emails you) if any app failed, after trying all of them.

## apps.json

```json
{"name": "AppHub", "repo": "LukeNeedham/AppHub", "library": true}
```

| Field | Default | Meaning |
|---|---|---|
| `name`, `repo` | required | The app's name and its `owner/name` |
| `library` | `false` | Whether it uses the shared library: for [consuming-apps.md](consuming-apps.md), not used by the sync |
| `skill` | `true` | `false`: do not sync the skill |
| `callers` | the three above | The caller files to sync, from `examples/` (add `release.yml` here); `[]` for none |
| `inputs` | none | Settings to force in the callers, such as `{"apk-path": "app/build/outputs/apk/debug/x.apk"}` |
| `branches` | the app's own | The branches the PR caller builds PRs for |

**A new app:** add it here (this is also the list "all consuming apps" means), then run *Sync Apps* for it. Its
first sync PR adds the callers, the skill and the `CLAUDE.md` block.

## The token (one-time setup)

The default `GITHUB_TOKEN` of a run cannot write to other repos, nor change workflow files, so the sync uses a
personal access token, kept as the secret `SYNC_TOKEN` of *this* repo.

1. Create a **fine-grained** token at <https://github.com/settings/personal-access-tokens/new>:
   - Resource owner: `LukeNeedham`. Expiration: the longest, 1 year.
   - Repository access: **All repositories** (a new app is then covered without touching the token), or only the apps.
   - Repository permissions: **Contents** read and write, **Pull requests** read and write, **Workflows** read
     and write. (Metadata read is added by itself.)
2. In this repo: *Settings → Secrets and variables → Actions → New repository secret*, name `SYNC_TOKEN`,
   value the token.
3. Run *Sync Apps* by hand to check it.

The token expires: put the date in your calendar. When it does, runs fail with a 401 and need a new token in the
same secret. It is only ever sent to `github.com` and `api.github.com`, and is masked in the logs.

## Running it yourself

```
SYNC_TOKEN=github_pat_... python3 scripts/sync_apps.py            # every app
python3 scripts/sync_apps.py --dry-run --apps AppHub              # clone, show the changes, push nothing
python3 -m unittest discover -s scripts                           # the tests
python3 scripts/check_readme.py README.md                         # is a README in the standard format
```

`--dry-run` needs no token for a public repo.

## Changing what is synced

Change the file in `skills/` or `examples/` and merge: the next run opens the PRs. To sync something new (another
caller, say), add it to `examples/` and to `DEFAULT_CALLERS` in the script, and to `docs/setup.md`. The
settings that belong to an app are `INPUT_KEYS` in the script.
