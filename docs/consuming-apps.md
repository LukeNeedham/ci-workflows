# Consuming apps

Every project that consumes this repo: the shared **workflows**, the **library** (`common/`) and the Claude **skill**.
A `kmp` app uses all three; a `next-js` project uses the workflows and the skill, not the library. **When the user says "all consuming apps" or "all my apps", these
are meant**, and "update all consuming apps to the latest library version" is every app in the list.

**The list is [`apps.json`](../apps.json)**, which the [sync](sync.md) also reads: one entry per project, its `name`, its
`repo` and its `stack`, which is always written out, with no default: `kmp` (Kotlin Multiplatform: an Android app that also
builds for iOS and the web) or `next-js` (a website only, [next-js-app.md](next-js-app.md)). Nothing else is configured per
project ([app-config.md](app-config.md)): every project of a stack gets that stack's workflow callers and skill by the sync.

Every `kmp` app in this list must have `app-icon.png` at its repo root ([app-icon.md](app-icon.md)); the app hub
reads the icons from these repos. Every `kmp` app also has a handwritten `readme.yml`, from which CI generates its `README.md` ([readme.md](readme.md)).
A `next-js` project has neither.

## Keeping this list complete

**Whenever a project starts consuming this repo in any way (workflows, library or skill), add it here
in the same change, or tell the user to**: add its entry to `apps.json`, with its stack. That includes a new app (see
[new-app.md](new-app.md)). Remove an entry only when the project stops consuming everything.

## "Update all consuming apps to the latest library version"

For each `kmp` app in `apps.json` (a `next-js` project has no `common`), on a branch, set `common` in `gradle/libs.versions.toml` to the latest
`common-<version>` release of this repo (see [library.md](library.md#releasing)), make any change the
release notes need, and open a PR. Paste each PR's AppHub link into the chat as soon as the PR is open.
