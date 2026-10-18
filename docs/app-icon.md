# The app icon

Every app exposes its icon at a fixed path, so tooling such as the app hub can show it without
building or unpacking the app.

## The rule

- The file is **`app-icon.png`, at the repo root**, and **CI generates it**: you never draw or edit it.
- It is a **512x512 PNG drawn as a circle on a transparent background**: the circle is filled with the
  adaptive launcher icon's **background**, and the **foreground** sits centred on it at the same size and
  position as in the adaptive icon. In other words it looks exactly like the launcher icon under a circular
  launcher mask, which shows the centre 72dp of the 108dp adaptive canvas.
- It lives on `main`, so the icon of any app is at
  `https://raw.githubusercontent.com/LukeNeedham/<repo>/main/app-icon.png`. The repos are public, so no
  auth is needed. The repo names are in [consuming-apps.md](consuming-apps.md).
- The only requirement on the app: it has an **adaptive launcher icon** (`android:icon` in the manifest
  points to a `mipmap-anydpi*` adaptive icon), whose layers are colours, vector drawables or images.

## How it stays in step

The `app-icon` job of [`android_pr.yml`](../.github/workflows/android_pr.yml) runs on every PR, alongside
the build:

1. It fetches [`scripts/render_app_icon.py`](../scripts/render_app_icon.py) from this repo (`main`) and
   renders the icon from the app's adaptive icon.
2. If the result differs visibly from the committed `app-icon.png` (or there is none), it **commits the new
   file to the PR's branch** as `github-actions[bot]`. If it is the same it does nothing. Tiny differences
   (the renderer's edge anti-aliasing, a colour shift of 1 or 2 in one channel) are ignored so the file
   does not churn.
3. If the app has no adaptive icon the job fails and says so.

So changing the launcher icon needs no extra step: the PR gets a regenerated `app-icon.png` commit on its
own, and a PR that does not touch the icon gets nothing. This is why every app caller must grant
`contents: write` (the example callers already do).

Things to know:

- **Pull the bot's commit** before pushing again (`git pull --rebase`), as with any commit on your
  branch. A push that races with the bot's is handled by the job (it rebases and retries).
- **Checks do not re-run** on the bot's commit: pushes made with the workflow token do not start workflow
  runs. The APK does not contain `app-icon.png`, so the build is still valid.
- **PRs from forks** cannot be committed to. There the job fails with instructions to run the script
  yourself.
- **A manual run** (`workflow_dispatch`) cannot commit: it fails if `app-icon.png` is out of date.
- **Script changes** apply to every app at once (it is fetched from `main`). To test one, set `tools-ref`
  to your branch in a caller (see the README).

## Previewing it locally

Not needed, but to look at the result before pushing, from the app's repo root:

```
pip install cairosvg pillow
curl -fsSL https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/scripts/render_app_icon.py -o /tmp/render_app_icon.py
python3 /tmp/render_app_icon.py
```

(Do not commit the output by hand; CI will do it, and overwrite anything that differs.)

The path is hard-coded in the workflow and cannot be overridden, because it must be the same in every
app.
