# Creating an app repo

A new app repo is created and set up with no LLM. Claude cannot create repos (the integration gets a 403), so this
replaces creating the repo by hand in the browser. It is split in two, so that **this repo holds no token that can create
repos**:

1. **The repo is created by AppHub**, with its own token, kept on the phone (the **New app** button).
2. **The setup of the repo is done here**, by **[`new_app.yml`](../.github/workflows/new_app.yml)**, which runs
   [`scripts/new_app.py`](../scripts/new_app.py) with the secrets this repo already has for the [sync](sync.md). AppHub
   starts it with the dispatch API, with *resume* on, as the repo is there already.

## What it does

In this order. Every step can be repeated, so a run that stopped half way is finished by running it again with
**resume**.

1. **The repo** `LukeNeedham/<name>`, with a README so that `main` exists, public by default (AppHub lists public repos;
   the **private** option makes it private), and its default branch is `main`. AppHub does this before it starts the
   workflow. The workflow does it too, only when it has a token that may create repos (`NEW_APP_TOKEN`, optional, below);
   without one it needs the repo to exist, and *resume* on.
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

**Nothing new is needed in this repo.** The workflow uses the secrets of the sync:

| Secret | Used for | Notes |
|---|---|---|
| `SYNC_TOKEN` | The first commit, the secret, and the line of `apps.json` | The token of [sync.md](sync.md#the-token-one-time-setup): Contents, Workflows and Secrets on **All repositories**, which covers a repo made later; Contents on this repo. **It is not given the power to create repos** |
| `GENERATED_COMMIT_TOKEN` | Handed on to the new app | Already there for the sync |
| `NEW_APP_TOKEN` | *Optional.* Creating the repo from the workflow | Only for running the workflow by hand without making the repo first. Left out, the workflow needs the repo to exist. A token that can create repos is better kept off this repo: AppHub does not need it |

**In AppHub** (on the phone, Keystore-encrypted), the **New app** page uses two tokens:

- **The token of Settings**, with the Actions permission (read and write) for this repo: it starts the workflow and reads its run.
- **A repo creation token**, entered on the New app page: it only creates the repo (and renames its branch to `main`). A
  **fine-grained** token for all repositories of `LukeNeedham` with **Repository creation** (write), or **Administration**
  (write) if the token page does not offer it; or a **classic** token with the scope `repo`. Prefer the fine-grained one with
  *Repository creation*: *Administration* also lets a token change settings and delete repos.

**Fine-grained tokens.** GitHub's own data for the permissions table of the REST API (`fine-grained-pat-permissions.json` of
`github/docs`) lists `POST /user/repos`, the call that creates a repo for a personal account, as available to fine-grained
personal access tokens, under two permissions, both at the level *write*: **Administration** (a repository permission) and
**Repository creation**. It is flagged as needing additional permissions, which the data does not spell out, so what this does
not tell is whether either one alone is enough, and whether the token page offers "Repository creation" to a personal
token. A fine-grained token is made for **All repositories**, so that it covers a repo that does not exist yet.

This was read from the documentation source, not tried with a token, so test the one you make before relying on it:

```
curl -s -o /dev/null -D - -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer github_pat_..." -H "Accept: application/vnd.github+json" \
  -d '{"name":"token-test-delete-me","private":true}' | grep -i "^HTTP\|x-accepted-github-permissions"
```

A `201` means it works (delete the test repo again); a `403` names the permission it wanted in
`x-accepted-github-permissions`. If it does not work, use a classic token with `repo`, which can write to every repo of the
account: it is kept in AppHub only.

## Running it yourself

```
NEW_APP_TOKEN=... SYNC_TOKEN=... GENERATED_COMMIT_TOKEN=... python3 scripts/new_app.py LyricTutor [--private] [--resume]
python3 scripts/new_app.py LyricTutor --dry-run        # check the name, change nothing
python3 -m unittest discover -s tests                  # the tests (need pyyaml; `keytool` for the keystore test)
```

Without `NEW_APP_TOKEN` the repo has to exist: pass `--resume`.

## Starting the dispatch from another program (AppHub)

`POST /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/dispatches` with `{"ref": "main", "inputs": {"name":
"LyricTutor", "resume": "true"}}` (inputs are strings) and a token that may write Actions on this repo. It answers `204`
with no run id: the run is found in
`GET /repos/LukeNeedham/ci-workflows/actions/workflows/new_app.yml/runs?event=workflow_dispatch`, newest first, by its
`display_title`, which is `New App <name>` (the `run-name` of the workflow). A caller that may start the same app twice
notes the ids of the runs there are before it dispatches, and takes the new one.
