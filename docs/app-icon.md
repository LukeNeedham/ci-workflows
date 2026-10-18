# The app icon

Every app exposes its icon at a fixed path, so tooling such as the app hub can show it without
building or unpacking the app.

## The rule

- The file is **`app-icon.png`, at the repo root**.
- It is a **512x512 PNG, drawn as a circle on a transparent background**: the circle is filled with the
  adaptive launcher icon's **background**, and the **foreground** sits centred on it at the same size and
  position as in the adaptive icon. In other words it looks exactly like the launcher icon under a circular
  launcher mask, which shows the centre 72dp of the 108dp adaptive canvas.
- It lives on `main`, so the icon of any app is at
  `https://raw.githubusercontent.com/LukeNeedham/<repo>/main/app-icon.png`. The repos are public, so no
  auth is needed. The repo names are in [consuming-apps.md](consuming-apps.md).

## Rendering it

Do not draw it by hand: run the script that ships with the skill, from the app's repo root:

```
pip install cairosvg pillow
python3 .claude/skills/lukeneedham-conventions/scripts/render_app_icon.py
```

(In this repo it is [`skills/lukeneedham-conventions/scripts/render_app_icon.py`](../skills/lukeneedham-conventions/scripts/render_app_icon.py).)
It reads the app's adaptive icon (the `android:icon` of the manifest: its background and foreground, a
colour, a vector drawable with groups, clips and gradients, or a raster image) and writes `app-icon.png`
next to it. Check the result by looking at it. If an app has no adaptive icon, give it one first.

## Keeping it in step

The PNG is a separate copy of the launcher icon. **Whenever a change touches the launcher icon (the
`ic_launcher*` mipmaps or drawables, the adaptive icon XML, its foreground, background or monochrome
layers, or their colors), re-run the script in the same PR** and say so in the description. CI cannot
check that the two match, so this rule is in the [skill](skill.md) that every app's Claude follows.

## Enforcement

[`android_pr.yml`](../.github/workflows/android_pr.yml) has a `check-icon` job that fails the PR (check
`android / check-icon`) when the file is missing, is not a square 8-bit RGBA PNG of at least 512x512, or
is not drawn as a circle (the corners, including the spot just inside each corner of the square, must be
transparent and the centre opaque). Every app already calls that workflow, so the rule reaches all of them
as soon as it is on `main`. An app whose icon is not in this form fails its next PR until it is.

The path is hard-coded in the workflow and cannot be overridden, because it must be the same in every
app.
