# Next.js websites (stack `next-js`)

A project in [`apps.json`](../apps.json) with `"stack": "next-js"` is a **website only**: built with Next.js and React,
with no Android app, no APK, no Gradle and no `common` library. It follows its own standard, below, and not the one of
[the Kotlin Multiplatform apps](app-config.md) (`"stack": "kmp"`). `PersonalWebsite` is the first.

Nothing is configured per project: every `next-js` project follows the same standard, so its caller holds no settings.

## What a project has to be

| | |
|---|---|
| Framework | Next.js with React and TypeScript |
| Lockfile | One of `yarn.lock`, `pnpm-lock.yaml`, `package-lock.json`, committed. CI finds the package manager from it, and installs exactly what it says |
| Node | The version in `engines.node` of `package.json` |
| Scripts | `lint` and `build`. `test` is run when the project has it |
| Branch | PRs go to `main` |
| Hosting | The repo is connected to a project on [Vercel](https://vercel.com), which deploys every PR as a preview and `main` as production |

What does not apply: `app-icon.png`, `readme.yml`, the screenshots and previews of Compose, the conventions check, the
releases, the APK links, the `common` library and the `lukeneedham-conventions` skill. The README is the project's own.

## What the sync gives it

| What | Where in the project |
|---|---|
| The skill [`next-js-conventions`](../skills/next-js-conventions/SKILL.md) | `.claude/skills/next-js-conventions/` |
| The caller [`callers/next-js/web_pr.yml`](../callers/next-js/web_pr.yml) | `.github/workflows/web_pr.yml` |
| A block in `CLAUDE.md` | Says the same, and to always give the user the preview URL and the AppHub link ([sync.md](sync.md)) |

## The PR flow

[`web_pr.yml`](../.github/workflows/web_pr.yml) runs on every PR into `main`:

1. **`check`**: installs from the lockfile, runs `lint`, `test` (if the project has the script) and `build`.
2. **`preview`**: waits for the preview that Vercel deploys for the commit, checks that it **opens without a login**, and
   posts one comment per PR (header `web-preview-link`) with the URL. The AppHub link is posted once, as for the apps.
3. **`automerge`**: merges the sync PR once the jobs have passed ([sync.md](sync.md#merging-the-prs)).

There is no cleanup job: Vercel removes the previews of a closed PR itself.

### Why Vercel's own preview

Vercel's GitHub integration builds each PR and reports the deployment to GitHub, with the URL in its status. CI reads
that ([`web_preview.py`](../scripts/web_preview.py)), so there is **no Vercel token** in CI and nothing is deployed twice.

### The preview must be public

Vercel asks for a login to open a preview by default (*Deployment Protection → Vercel Authentication*). A preview is
for anyone with the link, so **turn it off for previews** in the project's settings on Vercel: a one-time setting of each
project, which CI cannot change without a token. The check requests the preview with no login and **fails the PR** when it
gets a 401 or a redirect to the login of Vercel, with a comment saying what to change. (The price: anyone who has the URL
can see unreleased changes.)

## For AppHub

The preview URL is in the comment of the PR as a line of its own:

```
<!-- preview-url: https://personal-website-git-branch-owner.vercel.app -->
```

The comment is the one with the header `web-preview-link` (`<!-- Sticky Pull Request Commentweb-preview-link -->`), and
it is updated by every push, so it always has the URL of the newest commit. The AppHub side comes later.

## A new project

1. Create the repo, connect it to a Vercel project, and turn Deployment Protection off for previews.
2. Add it to [`apps.json`](../apps.json) with `"stack": "next-js"` and run *Sync Apps* for it.
3. Merge the sync PR (it merges itself once its checks pass).

## Changing the standard

Change the workflow, the caller or the skill here and merge: the sync opens the PRs. When a convention changes, update
this page and [`skills/next-js-conventions/SKILL.md`](../skills/next-js-conventions/SKILL.md) together.
