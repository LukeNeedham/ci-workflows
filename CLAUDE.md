# Instructions for Claude

- **Starting a new app or project**: before creating anything, read
  [`docs/new-app.md`](docs/new-app.md) and follow it. It covers the project setup, the committed debug
  keystore, the CI workflows and the standard architecture.
- This repo is the shared home for the CI workflows and the `common` library. Docs live in `docs/`.
- **"All consuming apps"** means the apps in [`apps.json`](apps.json) ([`docs/consuming-apps.md`](docs/consuming-apps.md)). Any
  project that starts consuming this repo (workflows, library or skill) must be added to that file.
- When you change a convention in `docs/`, update `skills/lukeneedham-conventions/SKILL.md` too
  ([`docs/skill.md`](docs/skill.md)).
- Apps get the skill, the workflow callers and a `CLAUDE.md` block from CI (`sync_apps.yml`), as a "Sync from
  ci-workflows" PR: never copy them by hand and never edit an app's copy. See [`docs/sync.md`](docs/sync.md).
  A new caller or a change to one in `callers/` reaches the apps this way too. The callers hold no settings and an app
  has no options: every app follows the same standard ([`docs/app-config.md`](docs/app-config.md)), so `apps.json` lists
  only `name` and `repo`.
- **AppHub link**: whenever work on an app completes (a PR is open), always paste the PR's AppHub link
  (`https://www.lukeneedham.com/apphub/pr/<repo name>/<number>`, also posted by CI as a PR comment) into the chat
  straight away. This rule reaches the apps through the managed `CLAUDE.md` block of `sync_apps.py`.
