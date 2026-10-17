# Instructions for Claude

- **Starting a new app or project**: before creating anything, read
  [`docs/new-app.md`](docs/new-app.md) and follow it. It covers the project setup, the committed debug
  keystore, the CI workflows and the standard architecture.
- This repo is the shared home for the CI workflows and the `common` library. Docs live in `docs/`.
- **"All consuming apps"** means the apps in [`docs/consuming-apps.md`](docs/consuming-apps.md). Any project that starts
  consuming this repo (workflows, library or skill) must be added to that list.
- When you change a convention in `docs/`, update `skills/lukeneedham-conventions/SKILL.md` too
  ([`docs/skill.md`](docs/skill.md)).
- Apps get the skill (and updates to it) as part of the next piece of work done on them, never in a PR of
  their own: see [`docs/skill.md`](docs/skill.md).
