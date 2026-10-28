# Creating an app repo

A new app repo is created and set up by a script, with no LLM: **[`new_app.yml`](../.github/workflows/new_app.yml)**
runs [`scripts/new_app.py`](../scripts/new_app.py). Start it from *Actions → New App → Run workflow*, or with the
**New app** button of AppHub, which calls the same workflow. Claude cannot create repos (the integration gets a 403), so
this replaces creating the repo by hand in the browser.

## What it does

In this order. Every step can be repeated, so a run that stopped half way is finished by running it again with
**resume**.

1. **Creates the repo** `LukeNeedham/<name>` with a README, so that `main` exists. Public by default, as AppHub lists
   public repos; the **private** input makes it private. A default branch that is not `main` is renamed to it.
2. **Pushes the first commit to `main`** (not a PR: there is nothing to protect or build yet). The message ends in
   `[skip ci]`, as there is no project for the build to run on. It holds:
   - **the first sync**, made by the same code as [`sync_apps.py`](../scripts/sync_apps.py) (the skill, all the callers and the
     managed block of `CLAUDE.md`), so the next sync finds the app up to date and opens no PR;
   - **the basic scaffold**: the Gradle wrapper (a copy of this repo's), `settings.gradle.kts` (this repo's repository rules,
     the app's name, and the module `:app`), `.gitignore`, `LICENSE` (*Copyright (c) year Luke Needham. All rights
     reserved.*, the default of [readme.md](readme.md)) and the committed `app/debug.keystore`
     ([new-app.md](new-app.md#2-debug-keystore)).

   What it does **not** make is the project itself: `build.gradle.kts`, the `:app` module, the app shell, the theme, the icon,
   `readme.yml` and the screenshots. That is the first session on the app, which follows [new-app.md](new-app.md). Nothing
   the app already has is overwritten.
3. **Writes the secret** `GENERATED_COMMIT_TOKEN` into the repo ([sync.md](sync.md#the-token-of-the-generated-commits)).
4. **Adds the app to [`apps.json`](../apps.json)** with a commit to `main` of this repo: one new line, nothing else, and not
   if the app is listed. It is last, so that the sync this starts finds nothing left to do. A commit that lands at the same
   moment is retried on top of it. If `main` requires PRs, this step fails with the error of GitHub: the repo exists
   and is set up, so run again with *resume* after adding the line by hand.

The run summary lists what was done, and **Next**: the repo, the package (`com.lukeneedham.<name lower case, letters and
digits>`), a link to start a Claude Code session on it, and the one step left that cannot be automated (below).

## The one step left: the Claude GitHub App

A session can only push to a repo that the Claude GitHub App may reach. If the installation covers **all repositories**
there is nothing to do. If it covers only some, add the new repo at
<https://github.com/apps/claude/installations/select_target>. Switching the installation to *All repositories* once
removes this step from every new app.

## Names

Letters, digits, hyphens and underscores, starting with a letter, 2 to 50 characters, no doubled or trailing hyphen or
underscore (`LyricTutor`, `LT-Companion`). The name is the repo and the entry `name` in `apps.json`, and
spelled exactly: nothing matches names case-insensitively ([sync.md](sync.md#appsjson)). The script refuses anything else,
and a name that is taken (a repo, or an entry of `apps.json`), unless *resume* is on.

## The tokens (one-time setup)

| Secret | Used for | Notes |
|---|---|---|
| `NEW_APP_TOKEN` | **Creating the repo** | Must be allowed to create repos for the account. A **classic** token with the scope `repo` can. Whether a fine-grained token can is not settled (see below). Without this secret `SYNC_TOKEN` is tried |
| `SYNC_TOKEN` | The first commit, the secret, and the line of `apps.json` | The token of [sync.md](sync.md#the-token-one-time-setup): Contents, Workflows and Secrets on **All repositories**, which covers a repo made later; Contents on this repo |
| `GENERATED_COMMIT_TOKEN` | Handed on to the new app | Already there for the sync |

1. Create the token at <https://github.com/settings/tokens/new> (classic): expiration the longest, scope **`repo`**. It
   only creates the repo; everything after that uses `SYNC_TOKEN`.
2. In this repo: *Settings → Secrets and variables → Actions → New repository secret*, name `NEW_APP_TOKEN`.

A classic token with `repo` can write to every repo of the account, so keep it to this one secret and renew it with the
rest ([sync.md](sync.md#the-token-one-time-setup)).

**Fine-grained tokens.** GitHub's reference for `POST /user/repos` says whether the endpoint accepts them and with which
permission; this was not confirmed when this was written. To test one, run the call with it and read the answer:

```
curl -s -o /dev/null -D - -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer github_pat_..." -H "Accept: application/vnd.github+json" \
  -d '{"name":"token-test-delete-me","private":true}' | grep -i "^HTTP\|x-accepted-github-permissions"
```

A `201` means it works (delete the repo again); a `403` names the permission it wanted in `x-accepted-github-permissions`.
If it works, use it as `NEW_APP_TOKEN` and drop the classic one.

## Running it yourself

```
NEW_APP_TOKEN=... SYNC_TOKEN=... GENERATED_COMMIT_TOKEN=... python3 scripts/new_app.py LyricTutor [--private] [--resume]
python3 scripts/new_app.py LyricTutor --dry-run        # check the name, change nothing
python3 -m unittest discover -s tests                  # the tests (need pyyaml; `keytool` for the keystore test)
```

## Starting the dispatch from another program (AppHub)

`POST /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/dispatches` with `{"ref": "main", "inputs": {"name":
"LyricTutor", "private": "false"}}` (inputs are strings) and a token that may write Actions on this repo (the token of
AppHub that builds main is enough). It answers `204` with no run id: the run is found in
`GET /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/runs?event=workflow_dispatch`, newest first, by its
`display_title`, which is `New App <name>` (the `run-name` of the workflow). A caller that may start the same app twice
notes the ids of the runs there are before it dispatches, and takes the new one.
