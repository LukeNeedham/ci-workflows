# Consuming apps

Every project that consumes anything from this repo: the shared **workflows**, the **library**
(`common/`), or the Claude **skill**. **When the user says "all consuming apps" or "all my apps", these
are meant**; for "update all consuming apps to the latest library version", that is the apps with
`"library": true`.

**The list is [`apps.json`](../apps.json)**, which the [sync](sync.md) also reads: one entry per app, with its name,
its repo and whether it uses the library (`"library": true`), plus the settings the app's CI needs when they differ from
the defaults (`apk-path`, `branches` and so on: [app-config.md](app-config.md)). All of them get the workflow callers
and the skill by the sync, unless an entry opts out. Krillion wrapper does not use the library yet (it may be added later).

Every app in this list must have `app-icon.png` at its repo root ([app-icon.md](app-icon.md)); the app hub
reads the icons from these repos.

## Keeping this list complete

**Whenever a project starts consuming this repo in any way (workflows, library or skill), add it here
in the same change, or tell the user to**: add or edit its entry in `apps.json`. That includes a new app (see
[new-app.md](new-app.md)) and an existing app that adopts one more part, such as Krillion wrapper adding the library
(`"library": true`). Remove an entry only when the project stops consuming everything.

## "Update all consuming apps to the latest library version"

For each app with `"library": true` in `apps.json`, on a branch, set `common` in `gradle/libs.versions.toml` to the latest
`common-<version>` release of this repo (see [library.md](library.md#releasing)), make any change the
release notes need, and open a PR. Paste each PR's AppHub link into the chat as soon as the PR is open.
