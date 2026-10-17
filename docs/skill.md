# The shared Claude skill

The conventions in these docs (project setup, CI, architecture with Koin, the shared library) are also
packaged as a Claude skill, [`skills/lukeneedham-conventions`](../skills/lukeneedham-conventions/SKILL.md).
Every app keeps a copy in `.claude/skills/lukeneedham-conventions/`, so Claude in any app repo knows the
patterns without this repo being added to the session.

## Adding it to an app

1. Copy [`examples/sync_skill.yml`](../examples/sync_skill.yml) to `.github/workflows/sync_skill.yml`.
2. In the app's repo settings, turn on *Actions > General > Allow GitHub Actions to create and approve
   pull requests*.
3. Run *Actions > Sync Claude skill* once. It opens a PR that adds the skill; merge it.

After that it runs weekly, and opens a PR whenever the skill here changed. Run it by hand to pick up a
change straight away.

## Changing the conventions

Edit the docs **and** `skills/lukeneedham-conventions/SKILL.md` in the same PR: the skill is the short
version that Claude always has, the docs are the long version. Never edit the copy inside an app.
`docs/consuming-apps.md` lists the apps that receive it.
