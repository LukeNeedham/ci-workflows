# Preview changes on a PR

**When a PR changes how a `@Preview` looks, the PR shows the before and after.** Every composable has a preview
([app-conventions.md](app-conventions.md)), so the previews are the app's UI catalogue; a PR comment lists the ones that
changed, with the image from `main` next to the image from the PR.

## How it works

- `scripts/screenshots/test/AllPreviewsTest.kt` renders **every** `@Preview` of the app's package (private ones too), with
  Roborazzi and Robolectric like the README screenshots, to `app/build/previews/<class>.<function>.png`.
  [`scripts/previews.py`](../scripts/previews.py) runs it and hashes the images into a manifest. A preview that cannot be
  rendered is an error that **fails the PR** (below): a preview that does not render does not work in Android Studio either.
- **Main.** On each push to the default branch the main build ([`android_main_build.yml`](../.github/workflows/android_main_build.yml),
  [setup.md](setup.md#4-the-main-build-every-push-to-main)) renders the previews and keeps them as the
  assets of the pre-release `previews-main` (and `previews-manifest.json`). It also builds the APK, which does not stop the previews.
- **A PR.** The build job of [`android_pr_build.yml`](../.github/workflows/android_pr_build.yml) renders them again after the
  APK (nothing is built twice), uploads **all** of them to the PR build's own pre-release, and posts the comment: the previews
  that are new, modified or removed against `previews-main`, under the headings New, Removed and Changed, a subheading per composable, and its previews side by side at the same size
  (before (main) and after (PR) for the changed ones). More than 20
  previews are listed by name. Unchanged previews are not shown.
- **Main moves while a PR is open.** After publishing, the main workflow redoes the comment of every open PR against the new
  images of main (from the manifest of the PR's latest build release), so the comment never compares with an old main. Until
  that has run, the comment says `main` has moved on.
- Until main has been rendered once there is nothing to compare with, and the comment says so.

Neither the images nor the comment need the app to do anything: the previews are the ones the app already has.

## Every preview must render

If any preview cannot be rendered, `previews.py render` fails and lists them as error annotations. In a PR the build job
still publishes the APK, then the `previews` job of [`android_pr.yml`](../.github/workflows/android_pr.yml) fails (no preview
comment is posted), so the PR cannot be merged once that check is required. On main the main build still publishes the APK, fails the run, and keeps
the last good previews. Fix the preview, or mock what it needs (camera, video).

**To block merging**, make the check `android / previews` required in the repo's branch protection.

## Things to know

- An app with no `@Preview` at all (a WebView wrapper, with no composables) has nothing to render: the render step succeeds,
  the comment says the app has no previews, and nothing fails.
- `previews-main` is a pre-release that is not a build: the "delete pre-releases" sweep skips it, and PR cleanup never
  matches it (a build tag is `<branch>-<run>-<attempt>`).
- A comparison is by the hash of the PNG, so a preview that draws something different on each render (time, animation, a
  random value) shows as modified every time. Give it fixed data.
- The images are served from the repo's public releases, so this needs the repo to be public.
