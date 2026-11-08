# The shared Claude skill

The conventions in these docs (project setup, CI, architecture with Koin, the shared library) are also
packaged as a Claude skill, [`skills/lukeneedham-conventions`](../skills/lukeneedham-conventions/SKILL.md).
Every consuming app keeps a copy in `.claude/skills/lukeneedham-conventions/`, so Claude in any app repo
knows the patterns without this repo being added to the session.

## How an app's copy stays current

CI does it: [`sync_apps.yml`](../.github/workflows/sync_apps.yml) mirrors the skill into every app in
[`apps.json`](../apps.json) and opens a PR, **Sync from ci-workflows**, where it differs, which merges itself once its checks pass (see [sync.md](sync.md)).
Neither Claude nor the app has to remember anything, and a Claude session in an app needs no access to this repo.

Never edit an app's copy by hand: change it here. The app's `CLAUDE.md` carries a managed block saying so.

## Adding it to an app

Add the app to [`apps.json`](../apps.json) and run *Sync Apps*: the first PR adds the skill, the callers and the
`CLAUDE.md` block. Every app has the skill.

## Optional skills

`skills/` can hold more skills than the conventions one, for what only some apps need. They are mirrored to every app
like the first (an app that never needs one just never loads it), so they cost nothing and an app's Claude finds them
without this repo. Today: [`networking-setup`](../skills/networking-setup/SKILL.md), the setup of Ktor, the `INTERNET`
permission, the client and the network log, for apps that make network calls ([networking.md](networking.md)). A new app
does not have what an optional skill adds.

## Changing the conventions

Edit the docs **and** `skills/lukeneedham-conventions/SKILL.md` in the same PR: the skill is the short
version that Claude always has, the docs are the long version.
