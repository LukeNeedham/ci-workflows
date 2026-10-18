# The app icon

Every app exposes its icon at a fixed path, so tooling such as the app hub can show it without
building or unpacking the app.

## The rule

- The file is **`app-icon.png`, at the repo root**.
- It is a **PNG, square, at least 512x512**. Transparency is fine.
- It lives on `main`, so the icon of any app is at
  `https://raw.githubusercontent.com/LukeNeedham/<repo>/main/app-icon.png`. The repos are public, so no
  auth is needed. The repo names are in [consuming-apps.md](consuming-apps.md).

The launcher icon inside the app is usually adaptive XML or vector, which the hub cannot render, so this
PNG is a separate copy. **When the launcher icon changes, update `app-icon.png` in the same PR.**

## Enforcement

[`android_pr.yml`](../.github/workflows/android_pr.yml) has a `check-icon` job that fails the PR (check
`android / check-icon`) when the file is missing, is not a PNG, is not square, or is under 512x512. Every
app already calls that workflow, so the rule reaches all of them as soon as it is on `main`. An app that
has no icon yet fails its next PR until it adds one.

The path is hard-coded in the workflow and cannot be overridden, because it must be the same in every
app.
