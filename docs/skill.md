# The shared Claude skill

The conventions in these docs (project setup, CI, architecture with Koin, the shared library) are also
packaged as a Claude skill, [`skills/lukeneedham-conventions`](../skills/lukeneedham-conventions/SKILL.md).
Every consuming app keeps a copy in `.claude/skills/lukeneedham-conventions/`, so Claude in any app repo
knows the patterns without this repo being added to the session.

## How an app's copy stays current

There is no scheduled job and no PR just for the skill. **Whenever Claude is asked to do work on a
consuming app, it first checks whether the skill here has changed, and if so copies the new files into
the app as part of that same work.** The skill update then lands in the PR the work produces.

1. Fetch the skill from this repo's `main` (it is public): read the files under
   `skills/lukeneedham-conventions/` with the GitHub tools, or `git clone --depth 1
   https://github.com/LukeNeedham/ci-workflows` into a scratch directory.
2. Compare with the app's `.claude/skills/lukeneedham-conventions/`.
3. If they differ (or the app has none yet), replace the app's folder with the shared one, exactly.
4. Commit it with the rest of the work, and mention in the PR description that the skill was updated.

Never edit the app's copy by hand: change it here, and apps pick it up on their next piece of work.

The skill itself contains this instruction, and so does the app's `CLAUDE.md` (one line, see below), so
it is followed even in a session that has not heard of this repo.

## Adding it to an app

When Claude first works on a consuming app that has no copy:

1. Copy `skills/lukeneedham-conventions/` into the app's `.claude/skills/`.
2. Add this line to the app's `CLAUDE.md`, creating the file if needed:

   > Before starting work, check that `.claude/skills/lukeneedham-conventions` matches
   > `skills/lukeneedham-conventions` on `main` of `LukeNeedham/ci-workflows`; if not, copy it over and
   > include that in this work's PR. See that repo's `docs/skill.md`.

3. Fill in the Skill column for the app in [consuming-apps.md](consuming-apps.md).

## Changing the conventions

Edit the docs **and** `skills/lukeneedham-conventions/SKILL.md` in the same PR: the skill is the short
version that Claude always has, the docs are the long version.
