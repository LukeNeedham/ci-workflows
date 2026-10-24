#!/usr/bin/env python3
"""Renders an app's README.md from its readme.yml, in the standard layout of docs/readme.md.

The layout lives here, the content in the app. Needs PyYAML.

The screenshots are not listed in readme.yml: they are the PNGs of docs/screenshots/, which CI renders from the
app's screenshot package (docs/screenshots.md). They are required, unless readme.yml says `screenshots: false`.
The minimum Android version is not in readme.yml either: it is read from the minSdk of app/build.gradle.kts.

    python3 generate_readme.py [app_dir] [--repo owner/name] [--check]

--repo defaults to $GITHUB_REPOSITORY, then to the app's git `origin`. --check writes nothing and exits 1 if
README.md is missing or differs from what readme.yml renders to.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

SOURCE = "readme.yml"
HEADER = f"<!-- Generated from {SOURCE} by LukeNeedham/ci-workflows (docs/readme.md). Edit {SOURCE}, not this file. -->"
REQUIRED_TEXT = ["name", "tagline", "description", "license"]
SCREENSHOTS = "docs/screenshots"
KNOWN = {"name", "tagline", "description", "screenshots", "user", "developer", "sections", "license"}
BUILD_FILE = "app/build.gradle.kts"
CATALOG = "gradle/libs.versions.toml"
# The Android version name of each API level
ANDROID_VERSIONS = {21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10",
                    30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15", 36: "16"}


class SdkError(Exception):
    pass


def _level(build, catalog, key):
    """The API level that [key] (`minSdk`, `compileSdk`) is set to in the Gradle file text [build], or None."""
    build = re.sub(r"//.*", "", build)
    for pattern in (rf"\b{key}\s*=\s*(\d+)\b", rf"\b{key}Version\s*\(\s*(\d+)\s*\)", rf"\b{key}\b[^\n]*?\brelease\((\d+)"):
        match = re.search(pattern, build)
        if match:
            return int(match.group(1))
    match = re.search(rf"\b{key}\s*=\s*libs\.versions\.([A-Za-z0-9_.]+?)\.get\(\)", build)
    if match and catalog:
        wanted = re.sub(r"[-_.]", "", match.group(1)).lower()
        for name, value in re.findall(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*"(\d+)"', catalog, re.M):
            if re.sub(r"[-_.]", "", name).lower() == wanted:
                return int(value)
    return None


def sdk_levels(app_dir):
    """(minSdk, compileSdk) of the app, from app/build.gradle.kts. compileSdk is None when it cannot be read; an
    unreadable minSdk is an [SdkError], because the README must not guess it."""
    build_file = app_dir / BUILD_FILE
    if not build_file.is_file():
        raise SdkError(f"{BUILD_FILE} does not exist: the README takes the minimum Android version from it")
    catalog_file = app_dir / CATALOG
    catalog = catalog_file.read_text() if catalog_file.is_file() else ""
    build = build_file.read_text()
    minimum = _level(build, catalog, "minSdk")
    if minimum is None:
        raise SdkError(f"cannot read minSdk from {BUILD_FILE}: set it as `minSdk = 26` (or from the version catalog)")
    return minimum, _level(build, catalog, "compileSdk")


def android_version(api):
    """`26` -> `Android 8.0 (API 26)`"""
    name = ANDROID_VERSIONS.get(api)
    return f"Android {name} (API {api})" if name else f"Android API {api}"


def screenshot_files(app_dir):
    """The screenshots of the app, as paths relative to its root, in name order."""
    return sorted(p.relative_to(app_dir).as_posix() for p in (app_dir / SCREENSHOTS).glob("*.png"))


def problems(data, screenshots=None):
    """What is wrong with the parsed readme.yml [data], as a list of sentences.

    [screenshots] is the list from [screenshot_files]; None skips the check that an app has some.
    """
    if not isinstance(data, dict):
        return [f"{SOURCE} must be a mapping of fields"]
    found = [f"unknown field `{k}`" for k in data if k not in KNOWN]
    for key in REQUIRED_TEXT:
        if not str(data.get(key) or "").strip():
            found.append(f"`{key}` is required")
    user = data.get("user")
    if user is not None and not isinstance(user, dict):
        found.append("`user` must be a mapping")
    elif user:
        for key in user:
            if key not in ("install", "steps"):
                found.append(f"unknown field `user.{key}`")
        if user.get("steps") is not None and not isinstance(user["steps"], list):
            found.append("`user.steps` must be a list")
        if user.get("install") is not None and not str(user["install"]).strip():
            found.append("`user.install` must not be empty")
    developer = data.get("developer")
    if developer is not None and (not isinstance(developer, dict) or set(developer) - {"notes"}):
        found.append("`developer` can only have `notes`: what is specific to this app")
    if "screenshots" in data and data["screenshots"] is not False:
        found.append("`screenshots` can only be `false` (an app with no UI worth showing); the screenshots are rendered by CI into docs/screenshots/")
    elif screenshots is not None and data.get("screenshots") is not False and not screenshots:
        found.append("the app has no screenshots: set up the page previews and the screenshot test (docs/screenshots.md in "
                     "LukeNeedham/ci-workflows), or set `screenshots: false` if the app has no UI worth showing")
    for i, section in enumerate(data.get("sections") or []):
        if not isinstance(section, dict) or not section.get("title") or not section.get("body"):
            found.append(f"`sections[{i}]` needs `title` and `body`")
    return found


def alt_text(path):
    """`docs/screenshots/PullRequest.png` -> `Pull Request`"""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", Path(path).stem)


def render(data, repo, min_sdk, screenshots=(), compile_sdk=None):
    """The README.md text for the valid [data] of the GitHub repo [repo] (`owner/name`), the [min_sdk] and
    [compile_sdk] of the app and its [screenshots]."""
    name = str(data["name"]).strip()
    repo_name = repo.split("/")[1]
    user = data.get("user") or {}
    install = str(user.get("install") or "").strip() or (
        f"Install the latest build from the [AppHub](https://www.lukeneedham.com/apphub) app, or download the APK "
        f"from the [Releases](https://github.com/{repo}/releases) page."
    )
    steps = [
        install,
        *[str(s).strip() for s in user.get("steps") or []],
    ]
    out = [
        HEADER,
        '<p align="center">',
        f'  <img src="app-icon.png" width="128" alt="{name} icon">',
        "</p>",
        "",
        f"# {name}",
        "",
        str(data["tagline"]).strip(),
        "",
        "## Description",
        "",
        str(data["description"]).strip(),
        "",
    ]
    if screenshots and data.get("screenshots") is not False:
        out += ["## Screenshots", "", *[f'<img src="{s}" width="240" alt="{alt_text(s)}">' for s in screenshots], ""]
    out += [
        "## Getting started as a user",
        "",
        *[f"{i}. {s}" for i, s in enumerate(steps, 1)],
        "",
        f"Requires {android_version(min_sdk)} or newer.",
        "",
        "## Getting started as a developer",
        "",
        f"Requirements: JDK 17 and the Android SDK{f' (platform {compile_sdk})' if compile_sdk else ''}, for example through Android Studio.",
        "",
        "```",
        f"git clone https://github.com/{repo}.git",
        f"cd {repo_name}",
        "./gradlew assembleDebug    # the APK is in app/build/outputs/apk/debug/",
        "./gradlew test             # unit tests",
        "```",
        "",
        "Every pull request is built by CI, which comments on it with a link to install the APK.",
        "",
        "Like all my apps, it follows the shared architecture and conventions (single activity, Jetpack Compose, "
        "Navigation 3, MVVM with every page split into a `Page` and a `PageContent`, Koin): "
        "see [ci-workflows](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/new-app.md).",
        "",
    ]
    notes = (data.get("developer") or {}).get("notes")
    if notes:
        out += [str(notes).strip(), ""]
    for section in data.get("sections") or []:
        out += [f"## {str(section['title']).strip()}", "", str(section["body"]).strip(), ""]
    license_name = str(data["license"]).strip().rstrip(".")
    # A closed app has no LICENSE file to link to
    license_line = f"{license_name}." if license_name.lower().startswith("all rights reserved") else f"{license_name}. See [LICENSE](LICENSE)."
    out += [
        "## Contributing",
        "",
        "Branch from `main`, make the change, and open a pull request. CI must be green before it is merged.",
        "",
        "## License",
        "",
        license_line,
    ]
    return "\n".join(out) + "\n"


def load(app_dir):
    """The parsed readme.yml of [app_dir], or None if there is none."""
    path = app_dir / SOURCE
    return yaml.safe_load(path.read_text()) if path.is_file() else None


def find_repo(app_dir, given=None):
    repo = given or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=app_dir, capture_output=True, text=True).stdout
        match = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(\.git)?\s*$", url)
        repo = match.group(1) if match else None
    if not repo or repo.count("/") != 1:
        sys.exit("Cannot tell the GitHub repo: pass --repo owner/name")
    return repo


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("app_dir", nargs="?", default=".")
    parser.add_argument("--repo")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if README.md is out of date")
    args = parser.parse_args()
    app_dir = Path(args.app_dir)
    try:
        data = load(app_dir)
    except yaml.YAMLError as e:
        sys.exit(f"{SOURCE} is not valid YAML: {e}")
    if data is None:
        sys.exit(f"{app_dir / SOURCE} does not exist. Copy docs/readme-template.yml from LukeNeedham/ci-workflows.")
    shots = screenshot_files(app_dir)
    found = problems(data, shots)
    if found:
        sys.exit("\n".join(f"{SOURCE}: {line}" for line in found))
    try:
        min_sdk, compile_sdk = sdk_levels(app_dir)
    except SdkError as e:
        sys.exit(f"{SOURCE}: {e}")
    text = render(data, find_repo(app_dir, args.repo), min_sdk, shots, compile_sdk)
    readme = app_dir / "README.md"
    current = readme.read_text() if readme.is_file() else None
    if args.check:
        if current != text:
            sys.exit(f"README.md is out of date: regenerate it from {SOURCE}")
        return
    if current != text:
        readme.write_text(text)
        print("README.md written")
    else:
        print("README.md is up to date")


if __name__ == "__main__":
    main()
