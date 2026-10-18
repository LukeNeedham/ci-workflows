# Consuming apps

Every project that consumes anything from this repo: the shared **workflows**, the **library**
(`common/`), or the Claude **skill**. **When the user says "all consuming apps" or "all my apps", these
are meant**; for "update all consuming apps to the latest library version", that is the apps with a
library tick.

| App | Repo | Workflows | Library | Skill |
|---|---|:-:|:-:|:-:|
| Android-Dock | [`LukeNeedham/Android-Dock`](https://github.com/LukeNeedham/Android-Dock) | yes | yes | |
| FlagTutor | [`LukeNeedham/FlagTutor`](https://github.com/LukeNeedham/FlagTutor) | yes | yes | |
| VideoDiary | [`LukeNeedham/VideoDiary`](https://github.com/LukeNeedham/VideoDiary) | yes | yes | |
| PoetryBook | [`LukeNeedham/PoetryBook`](https://github.com/LukeNeedham/PoetryBook) | yes | yes | |
| StickerBoard | [`LukeNeedham/Stickerboard`](https://github.com/LukeNeedham/Stickerboard) | yes | yes | |
| Krillion wrapper | [`LukeNeedham/krillion-wrapper`](https://github.com/LukeNeedham/krillion-wrapper) | yes | not yet (may be added later) | |
| AppHub | [`LukeNeedham/AppHub`](https://github.com/LukeNeedham/AppHub) | yes | yes | yes |
| PicCollage | [`LukeNeedham/PicCollage-Android`](https://github.com/LukeNeedham/PicCollage-Android) | yes | | yes |

The Skill column is filled in as each app gets the skill ([skill.md](skill.md)), the next time Claude works on it; none have it yet.

Every app in this list must have `app-icon.png` at its repo root ([app-icon.md](app-icon.md)); the app hub
reads the icons from these repos.

## Keeping this list complete

**Whenever a project starts consuming this repo in any way (workflows, library or skill), add it here
in the same change, or tell the user to.** That includes a new app (see [new-app.md](new-app.md)) and an
existing app that adopts one more part, such as Krillion wrapper adding the library: update its row.
Remove a row only when the project stops consuming everything.

## "Update all consuming apps to the latest library version"

For each app with a library tick, on a branch, set `common` in `gradle/libs.versions.toml` to the latest
`common-<version>` release of this repo (see [library.md](library.md#releasing)), make any change the
release notes need, and open a PR. Paste each PR's AppHub link into the chat as soon as the PR is open.
