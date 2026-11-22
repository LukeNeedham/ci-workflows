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
| Scripts | `lint` and `build`. `typecheck` and `test` are run when the project has them (the scaffold has both) |
| Branch | PRs go to `main` |
| Hosting | The repo is connected to a project on [Vercel](https://vercel.com), which deploys every PR as a preview and `main` as production |

What does not apply: `app-icon.png`, `readme.yml`, the screenshots and previews of Compose, the conventions check, the
releases, the APK links, the `common` library and the `lukeneedham-conventions` skill. The README is the project's own.

## The architecture

The standard follows the pattern of the Kotlin apps ([pages.md](pages.md)), in Next.js. The first project, PersonalWebsite,
has the layers; the new-project scaffold ([`templates/next-js/`](../templates/next-js)) is the reference.

```
src/
  app/           the routes, and nothing else; layout.tsx and providers.tsx
  domain/        what the site knows, with no UI: model/ (plain types) and provider/ (objects that hand out data)
  presentation/  common/ (shared), theme/ (the Chakra system) and feature/<name>/ (one folder per page)
```

**Every page is `XPage` and `XPageContent`**, each in its own file in `presentation/feature/<x>/`, next to
`useXViewModel.ts` and `XUiState.ts`. This is the one way to build a page, as in the Kotlin apps:

| | `XPage` | `XPageContent` |
|---|---|---|
| Job | Connects the page to the app: gets the state and the actions from `useXViewModel`, and hands them down. **No UI of its own** | **All of the page's UI** |
| State | Stateful: a client component (`'use client'`) | **Stateless**: no hooks, no `'use client'` of its own. State down, events up |
| Takes | What the route gives it (the params) | `XUiState` and **one callback per user action**, such as `onButtonClick` |

- A route file (`src/app/<x>/page.tsx`) only renders `<XPage />`. It has no UI and no logic.
- `useXViewModel` is the view model: a hook that returns `{ uiState, ...actions }` and knows nothing of how the page looks.
  `XUiState` is a plain interface. A page with no state of its own has no view model, and `XPage` passes what it reads from a provider.
- `XPageContent` is easy to test: render it with a state and click. The view model is tested with `renderHook`. The scaffold has both tests.
- A reusable piece (a card, a row) is **not** a page: it is a plain component in its own file. Never `XView` or `XScreen`.

**TypeScript only, no JavaScript at all.** Not a page, not a script, not a config: the ESLint config is `eslint.config.ts`
(loaded with `jiti`), the Next config `next.config.ts` and the Vitest config `vitest.config.mts`. `tsconfig.json` has
`allowJs: false`, and the ESLint config has a rule that **fails the lint on any `.js`, `.jsx`, `.mjs` or `.cjs` file**, wherever it
is, saying to write TypeScript. A project that is older than the template (PersonalWebsite has a `next.config.js`, which Next 13
cannot read as TypeScript) takes it on when it is upgraded.

**One way to import: the alias `@/`** (the folder `src/`), never a relative path that climbs out of a folder (`../`). ESLint
fails it (`no-restricted-imports`).

**Routes and shared data are in one place.** `UrlProvider` has every route of the site, so a path is never typed out in a component. A
provider is a plain object (`export const UrlProvider = { ... }`), not a class with an instance.

**Text is never sized in a component**: the theme (`presentation/theme/system.ts`) has named `textStyles` (`mainTitle`,
`subTitle`, `body`, `fine`), and a component picks one with `textStyle`.

**Build time and runtime are kept apart.** A `scripts/` folder, if the site has one (PersonalWebsite renders its blog from markdown),
runs at build time only and writes to `src/generated/` (git-ignored). `src/` only imports the output, and never reads files or builds content.

**Static by default.** A route with a known set of pages is built ahead (`generateStaticParams` with `dynamicParams = false`).

**Formatting is Prettier's** (no semicolons, single quotes, 100 columns), checked by `lint`, fixed by `yarn format`.

**Stack and versions**: Next.js, React and **Chakra UI v3** at their newest, TypeScript 6 (typescript-eslint does not support 7 yet, so
`typescript` is pinned to `~6.0`), ESLint 10 with `eslint-config-next`, Vitest (which is built on Vite, so `vite` is installed too; it is
used by the tests only) with Testing Library, Prettier and `yarn`. The versions are
carets in the template and `yarn.lock` pins what was installed on the day the project was created.

## What the sync gives it

| What | Where in the project |
|---|---|
| The skill [`next-js-conventions`](../skills/next-js-conventions/SKILL.md) | `.claude/skills/next-js-conventions/` |
| The caller [`callers/next-js/web_pr.yml`](../callers/next-js/web_pr.yml) | `.github/workflows/web_pr.yml` |
| A block in `CLAUDE.md` | Says the same, and to always give the user the preview URL and the AppHub link ([sync.md](sync.md)) |

## The PR flow

[`web_pr.yml`](../.github/workflows/web_pr.yml) runs on every PR into `main`:

1. **`check`**: installs from the lockfile, runs `lint`, `typecheck` and `test` (if the project has the scripts) and `build`.
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

## Vercel setup

[`vercel_setup.py`](../scripts/vercel_setup.py) sets a website up on Vercel, with the REST API, and every step can be repeated:

1. **The project** `<repo name, lower case>`, framework Next.js, **connected to the GitHub repo**, so that every PR gets a preview and
   `main` is deployed. A project of that name that is connected to another repo, or to none, is an error, never taken over.
2. **Deployment Protection off for previews** (`ssoProtection: null`), so that a preview opens without a login. The answer is read
   back: a setting that did not take (a plan that does not allow it) is an error, not a success.

It runs in two places:
- **New App** (`stack` `next-js`), after the first commit and before the project is listed in `apps.json`. Without the secret
  `VERCEL_TOKEN` the step is skipped and the run summary says what is left to do by hand.
- **[Vercel Setup](../.github/workflows/vercel_setup.yml)** (*Actions → Vercel Setup → Run workflow*, with the repo and an optional
  dry run) for a website that exists, such as PersonalWebsite.

**One-time setup, once for all the websites:**
1. The **Vercel GitHub app** is installed for the account, with access to all repositories (https://github.com/apps/vercel), so that Vercel
   can see a repo that was created a moment ago. Vercel refuses to connect a repo it cannot see, and the error says so.
2. A **Vercel token** (https://vercel.com/account/tokens, scope: the account or team of the sites), kept as the secret `VERCEL_TOKEN`
   of *this* repo (*Settings → Secrets and variables → Actions*). For a team, the team's id (Team Settings → General) is the secret
   `VERCEL_TEAM_ID`; a personal account has none. The token is only ever sent to `api.vercel.com`, and is masked in the logs. It can
   create and change the projects of the account: keep it here and nowhere else.

## For AppHub

The preview URL is in the comment of the PR as a line of its own:

```
<!-- preview-url: https://personal-website-git-branch-owner.vercel.app -->
```

The comment is the one with the header `web-preview-link` (`<!-- Sticky Pull Request Commentweb-preview-link -->`), and
it is updated by every push, so it always has the URL of the newest commit. The AppHub side comes later.

## A new project

From **AppHub's New project**, choosing the stack `next-js` (or *Actions → New App → Run workflow* with `stack` set to
`next-js`; [create-app.md](create-app.md)), which makes the repo, pushes the first commit and adds the entry to `apps.json`.
The first commit holds the sync of this stack and the minimal site of [`templates/next-js/`](../templates/next-js): one page,
`HomePage` and `HomePageContent`, with the view model, the theme, the lint, typecheck and test setup and a `yarn.lock`, so
the first pull request already builds. **The run also sets the site up on Vercel** ([below](#vercel-setup)), so what is left is yours:

1. Start a session on the repo and write the site.

To bring an **existing** website: add it to [`apps.json`](../apps.json) with `"stack": "next-js"` and run *Sync Apps* for it.
Its first sync PR adds the callers, the skill and the `CLAUDE.md` block; the project itself is the project's own. Run
*Vercel Setup* for it if its Vercel project is not set up the way the standard needs ([below](#vercel-setup)).

## Changing the template

[`templates/next-js/`](../templates/next-js) is checked by running the scaffold into a folder and running `yarn install`,
`lint`, `typecheck`, `test` and `build` there, which only needs the network and Node 24. A change to the template, or to the
versions in its `package.json`, has to pass all of that before it is merged: the tests of `tests/` check its rules, not that it builds.

## Changing the standard

Change the workflow, the caller or the skill here and merge: the sync opens the PRs. When a convention changes, update
this page and [`skills/next-js-conventions/SKILL.md`](../skills/next-js-conventions/SKILL.md) together.
