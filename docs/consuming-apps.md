# Consuming apps

Every project that consumes this repo: the shared **workflows**, the **library** (`common/`) and the Claude **skill**.
They all do it all: **every app uses all three**. **When the user says "all consuming apps" or "all my apps", these
are meant**, and "update all consuming apps to the latest library version" is every app in the list.

**The list is [`apps.json`](../apps.json)**, which the [sync](sync.md) also reads: one entry per app, just its `name`
and `repo`. Nothing else is configured per app ([app-config.md](app-config.md)), and every app gets the five workflow
callers and the skill by the sync.

Every app in this list must have `app-icon.png` at its repo root ([app-icon.md](app-icon.md)); the app hub
reads the icons from these repos. Every app also has a handwritten `readme.yml`, from which CI generates its `README.md` ([readme.md](readme.md)).

## Keeping this list complete

**Whenever a project starts consuming this repo in any way (workflows, library or skill), add it here
in the same change, or tell the user to**: add its entry to `apps.json`. That includes a new app (see
[new-app.md](new-app.md)). Remove an entry only when the project stops consuming everything.

## "Update all consuming apps to the latest library version"

For each app in `apps.json`, on a branch, set `common` in `gradle/libs.versions.toml` to the latest
`common-<version>` release of this repo (see [library.md](library.md#releasing)), make any change the
release notes need, and open a PR. Paste each PR's AppHub link into the chat as soon as the PR is open.
