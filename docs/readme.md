# The README standard

Every app in [`apps.json`](../apps.json) has a `README.md` at its repo root in the same format, so any app can be
picked up and understood the same way. This page is the format; the skeleton to copy is
[`readme-template.md`](readme-template.md).

## Handwritten, never generated

The README is **written by hand** (by the user, or by Claude when it works on the app) and then maintained like any
other file. Nothing generates it, regenerates it or syncs it: not CI, not the [sync](sync.md), not a build step.
The sync only **reports** (in its run summary) which apps' READMEs do not follow this format yet; it never writes
one. An app that has no standard README yet gets one written once, from the template, as a normal PR.

When the app changes in a way that a reader would notice (a feature, the build steps, the requirements), update
the README in the same PR.

## The format

In this order. The title block and the headings marked *required* are checked by
[`scripts/check_readme.py`](../scripts/check_readme.py); anything else is up to the app.

1. **Title block** (required): the app's icon, then its name as the one `#` heading, then a one-line tagline.
   The icon is the repo's root `app-icon.png`, which [CI generates](app-icon.md): reference it, never copy it.
2. `## Description` (*required*): what the app is and who it is for, in a short paragraph or two.
3. `## Features` (*required*): a short bullet list of what it does.
4. `## Screenshots` (optional): images in the repo (such as `docs/screenshots/`), or leave it out.
5. `## Getting started as a user` (*required*): how to get the app and use it. Installing the latest build from
   the app hub (AppHub), or the release APK when the app has releases; minimum Android version; first-run steps.
6. `## Getting started as a developer` (*required*): how to build and run it. Requirements (JDK 17, Android
   Studio, SDK 36), clone, the build command, how to run the tests, and where CI builds a PR's APK.
7. `## Project structure` (*required*): where things are (`app/`, the main packages) and the architecture in a few
   lines, linking to [app-conventions.md](app-conventions.md) rather than repeating it.
8. `## Contributing` (*required*): how to propose a change: branch, open a PR to `main`, CI must be green.
9. `## License` (*required*): the license, with a `LICENSE` file at the repo root. Say "All rights reserved" if the
   app is not open source.

Other sections (Privacy, Roadmap, Credits, Known issues) go **between Project structure and Contributing**.

Keep it accurate over long: a short README that is true beats a long one that is stale. Do not paste the CI or
library documentation: link to <https://github.com/LukeNeedham/ci-workflows>.

## Checking

```
python3 scripts/check_readme.py path/to/README.md
```

prints what is missing and exits 1 if anything is. The sync runs it on every app in `apps.json` and lists the
apps that fail in its summary.

## Keeping the apps in line

The managed `CLAUDE.md` block that [the sync](sync.md) gives every app tells Claude to follow this format: write
`README.md` from the template when it is missing or not in the format, keep it up to date, and never script it.
The skill carries the same rule ([skill.md](skill.md)).
