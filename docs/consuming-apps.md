# Consuming apps

The apps that use the shared library (`common/`) and the shared workflows from this repo. **When the
user says "all consuming apps" or "all my apps", these five are meant.** Keep this list current: add
a row when a new app is started from [new-app.md](new-app.md), remove one when an app is retired.

| App | Repo |
|---|---|
| Android-Dock | [`LukeNeedham/Android-Dock`](https://github.com/LukeNeedham/Android-Dock) |
| FlagTutor | [`LukeNeedham/FlagTutor`](https://github.com/LukeNeedham/FlagTutor) |
| VideoDiary | [`LukeNeedham/VideoDiary`](https://github.com/LukeNeedham/VideoDiary) |
| PoetryBook | [`LukeNeedham/PoetryBook`](https://github.com/LukeNeedham/PoetryBook) |
| TurnThePage | [`LukeNeedham/TurnThePage`](https://github.com/LukeNeedham/TurnThePage) |

Not consuming apps: `krillion-wrapper` (a bare WebView, no library), and old or forked projects.

## "Update all consuming apps to the latest library version"

For each app above, on a branch, set `common` in `gradle/libs.versions.toml` to the latest
`common-<version>` release of this repo (see [library.md](library.md#releasing)), make any change the
release notes need, and open a PR. Paste each PR's APK link into the chat when the build comment appears.
