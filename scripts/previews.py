#!/usr/bin/env python3
"""Shows the PR what its change did to the @Preview composables of the app (docs/previews.md in LukeNeedham/ci-workflows).

    python3 previews.py render        [--app DIR] [gradle arguments...]
    python3 previews.py publish-main  --repo R --sha SHA [--app DIR]
    python3 previews.py pr            --repo R --pr N --tag TAG --sha SHA [--app DIR]
    python3 previews.py refresh       --repo R --base BRANCH

`render` renders every preview of the app to app/build/previews/ (AllPreviewsTest); it fails if any preview cannot be
rendered, so a PR cannot be merged with one that does not render. `publish-main` keeps the images of main as the assets of the pre-release `previews-main`.
`pr` uploads all the images of a PR build to the pre-release TAG of that build and comments on the PR with the previews
that differ from main's. `refresh` redoes that comment for every open PR into BASE, after main moved. Uses GH_TOKEN.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pr_releases import is_build_tag

SCREENSHOTS = HERE / "screenshots"
MAIN_TAG = "previews-main"
MANIFEST = "previews-manifest.json"
MARKER = "<!-- previews-diff -->"
# More than this many changed previews are listed by name only, so the comment stays readable
MAX_SHOWN = 20


# ---------------------------------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------------------------------

def manifest_of(images_dir, sha):
    """{"sha": SHA, "previews": {name: sha256 of the PNG}} for the PNGs in [images_dir]."""
    previews = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(images_dir).glob("*.png"))}
    return {"sha": sha, "previews": previews}


def diff(base, head):
    """The previews that changed from [base] to [head], both {name: hash}: (added, changed, removed), sorted."""
    added = sorted(set(head) - set(base))
    removed = sorted(set(base) - set(head))
    changed = sorted(n for n in set(base) & set(head) if base[n] != head[n])
    return added, changed, removed


def short_name(name):
    """`com.app.ui.HomePageContentKt.PreviewEmpty` -> `HomePageContent` `PreviewEmpty`: the file and the function."""
    cls, _, function = name.rpartition(".")
    return f"{cls.rpartition('.')[2].removesuffix('Kt')} · {function}"


def asset_url(repo, tag, name):
    return f"https://github.com/{repo}/releases/download/{tag}/{name}.png"


def image(repo, tag, name):
    return f'<img src="{asset_url(repo, tag, name)}" width="180" alt="{short_name(name)}">'


def comment_body(repo, pr_tag, head, base, main_sha_now=None):
    """The PR comment. [head] and [base] are manifests; [base] is None while main has no images yet."""
    lines = [MARKER, "### 🖼️ Preview changes", ""]
    if base is None:
        lines.append("Main's previews are not rendered yet, so there is nothing to compare with. They are rendered "
                     "when the next push to main has been built.")
        return "\n".join(lines) + "\n"
    added, changed, removed = diff(base["previews"], head["previews"])
    lines.append(f"Compared with `main` at `{base['sha'][:7]}`; this PR at `{head['sha'][:7]}`. "
                 f"{len(head['previews'])} previews rendered.")
    if main_sha_now and main_sha_now != base["sha"]:
        lines.append(f"⚠️ `main` has moved on to `{main_sha_now[:7]}`; this comment updates when its previews are rendered.")
    lines.append("")
    if not head["previews"] and not base["previews"]:
        lines.append("This app has no previews.")
        return "\n".join(lines) + "\n"
    total = len(added) + len(changed) + len(removed)
    if total == 0:
        lines.append("No preview changed ✅")
        return "\n".join(lines) + "\n"
    lines.append(f"**{total} changed:** {len(added)} new, {len(changed)} modified, {len(removed)} removed.")
    lines.append("")
    rows = [(n, "new") for n in added] + [(n, "modified") for n in changed] + [(n, "removed") for n in removed]
    lines += ["| Preview | Before (main) | After (this PR) |", "|---|---|---|"]
    for name, kind in rows[:MAX_SHOWN]:
        before = image(repo, MAIN_TAG, name) if kind != "new" else "—"
        after = image(repo, pr_tag, name) if kind != "removed" else "—"
        lines.append(f"| `{short_name(name)}` ({kind}) | {before} | {after} |")
    if len(rows) > MAX_SHOWN:
        lines += ["", "Not shown: " + ", ".join(f"`{short_name(n)}`" for n, _ in rows[MAX_SHOWN:])]
    lines += ["", f"All of this PR's previews are assets of its [build release]"
                  f"(https://github.com/{repo}/releases/tag/{pr_tag})."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------
# GitHub, through the gh CLI
# ---------------------------------------------------------------------------------------------------

def gh(*args, check=True, text=True):
    return subprocess.run(["gh", *args], capture_output=True, text=text, check=check)


def release_exists(repo, tag):
    return gh("release", "view", tag, "--repo", repo, check=False).returncode == 0


def asset_names(repo, tag):
    out = gh("release", "view", tag, "--repo", repo, "--json", "assets", "--jq", ".assets[].name").stdout
    return set(out.split())


def upload(repo, tag, images_dir, manifest):
    """Uploads the PNGs and the manifest of [images_dir] as assets of the release [tag], replacing same-named ones."""
    files = sorted(Path(images_dir).glob("*.png"))
    manifest_file = Path(images_dir) / MANIFEST
    manifest_file.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    paths = [str(p) for p in files] + [str(manifest_file)]
    for i in range(0, len(paths), 50):
        gh("release", "upload", tag, *paths[i:i + 50], "--repo", repo, "--clobber")


def read_manifest(repo, tag):
    """The manifest of the release [tag], or None if there is no such release or it has none."""
    result = gh("release", "download", tag, "--repo", repo, "--pattern", MANIFEST, "--output", "-", check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def upsert_comment(repo, pr, body):
    """Edits the comment of ours on the PR (found by its marker), or posts it."""
    jq = f'.[] | select(.body | contains("{MARKER}")) | .id'
    ids = gh("api", "--paginate", f"repos/{repo}/issues/{pr}/comments", "--jq", jq).stdout.split()
    if ids:
        gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{ids[0]}", "-f", f"body={body}")
    else:
        gh("api", "-X", "POST", f"repos/{repo}/issues/{pr}/comments", "-f", f"body={body}")


# ---------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------

def failed_previews(images_dir):
    """The previews AllPreviewsTest could not render, one `name: reason` line each (empty if all rendered)."""
    path = Path(images_dir) / "failed.txt"
    return [l for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def render(app_dir, gradle_args):
    """Renders every preview into app/build/previews/. Returns the exit code."""
    rendered = app_dir / "app" / "build" / "previews"
    shutil.rmtree(rendered, ignore_errors=True)
    result = subprocess.run(
        [str(app_dir / "gradlew"), "testDebugUnitTest", "--tests", "*AllPreviewsTest",
         "--init-script", str(SCREENSHOTS / "screenshots.init.gradle"),
         f"-Pscreenshots.sources={SCREENSHOTS / 'test'}", "-Ppreviews.allowEmpty=true", *gradle_args],
        cwd=app_dir,
    )
    if result.returncode != 0:
        return result.returncode
    rendered.mkdir(parents=True, exist_ok=True)
    failures = failed_previews(rendered)
    for line in failures:
        print(f"::error title=Preview could not be rendered::{line}")
    if failures:
        print(f"{len(failures)} preview(s) could not be rendered: a preview that does not render does not work in "
              f"Android Studio either. Fix it, or mock what it needs (docs/app-conventions.md).", file=sys.stderr)
        return 1
    if not list(rendered.glob("*.png")):
        # An app with no @Preview at all: nothing to render, and nothing to compare
        print("::notice::The app has no previews, so there is nothing to render.")
    return 0


def images_dir(app_dir):
    return app_dir / "app" / "build" / "previews"


def publish_main(repo, sha, app_dir):
    """Keeps the images of main as the assets of the pre-release `previews-main`; assets of removed previews go."""
    out = images_dir(app_dir)
    manifest = manifest_of(out, sha)
    if release_exists(repo, MAIN_TAG):
        gh("release", "edit", MAIN_TAG, "--repo", repo, "--notes", f"Previews of main at {sha}", "--prerelease")
    else:
        gh("release", "create", MAIN_TAG, "--repo", repo, "--prerelease", "--target", sha,
           "--title", "Previews of main", "--notes", f"Previews of main at {sha}")
    upload(repo, MAIN_TAG, out, manifest)
    for stale in asset_names(repo, MAIN_TAG) - {f"{n}.png" for n in manifest["previews"]} - {MANIFEST}:
        gh("release", "delete-asset", MAIN_TAG, stale, "--repo", repo, "--yes")
    return 0


def pr_comment(repo, pr, tag, head, base_branch):
    base = read_manifest(repo, MAIN_TAG)
    upsert_comment(repo, pr, comment_body(repo, tag, head, base, main_sha_now=current_sha(repo, base_branch)))


def current_sha(repo, branch):
    result = gh("api", f"repos/{repo}/commits/{branch}", "--jq", ".sha", check=False)
    return result.stdout.strip() or None


def publish_pr(repo, pr, tag, sha, app_dir, base_branch):
    out = images_dir(app_dir)
    head = manifest_of(out, sha)
    upload(repo, tag, out, head)
    pr_comment(repo, pr, tag, head, base_branch)
    return 0


def refresh(repo, base_branch):
    """Redoes the comment of every open PR into [base_branch], against the main previews that were just published."""
    prs = json.loads(gh("api", "--paginate", f"repos/{repo}/pulls?state=open&base={base_branch}").stdout or "[]")
    releases = json.loads(gh("api", "--paginate", f"repos/{repo}/releases?per_page=100").stdout or "[]")
    for pr in prs:
        tags = [r for r in releases if is_build_tag(r["tag_name"], pr["head"]["ref"])]
        if not tags:
            continue
        latest = max(tags, key=lambda r: r["created_at"])["tag_name"]
        head = read_manifest(repo, latest)
        if head is None:
            continue
        print(f"Refreshing the previews of PR #{pr['number']} ({latest})")
        pr_comment(repo, pr["number"], latest, head, base_branch)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["render", "publish-main", "pr", "refresh"])
    parser.add_argument("--app", default=".")
    parser.add_argument("--repo")
    parser.add_argument("--pr")
    parser.add_argument("--tag")
    parser.add_argument("--sha")
    parser.add_argument("--base", default="main")
    args, gradle_args = parser.parse_known_args()
    app = Path(args.app).resolve()
    if args.command == "render":
        sys.exit(render(app, gradle_args))
    if args.command == "publish-main":
        sys.exit(publish_main(args.repo, args.sha, app))
    if args.command == "pr":
        sys.exit(publish_pr(args.repo, args.pr, args.tag, args.sha, app, args.base))
    sys.exit(refresh(args.repo, args.base))


if __name__ == "__main__":
    main()
