"""The README of an Android app (stack `kmp`): its fields, the facts it reads from the project and its layout. The delegate
of generate_readme.py for `--stack kmp`; the layout is in docs/readme.md."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# check_screenshot_package.py is in a folder of its own
sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
from app_config import SETTINGS  # noqa: E402
from check_screenshot_package import package_folders  # noqa: E402
from generate_readme import (  # noqa: E402
    HEADER, LICENSE_FILE, FactsError, common_problems, license_name, license_text, missing_license)

LINKS = {"play-store": "Google Play", "f-droid": "F-Droid", "web": "Web app"}
SCREENSHOTS = "docs/screenshots"
KNOWN = {"name", "tagline", "description", "links", "screenshots", "user", "developer", "sections"}
BUILD_FILE = "app/build.gradle.kts"
CATALOG = "gradle/libs.versions.toml"
# The Android version name of each API level
ANDROID_VERSIONS = {21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10",
                    30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15", 36: "16"}


class SdkError(FactsError):
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


@dataclass
class Facts:
    """What the README says that is not in readme.yml: it comes from the project."""
    min_sdk: int
    compile_sdk: int = None
    screenshots: tuple = ()
    license: str = "All rights reserved"


def facts(app_dir, repo=None):
    """The [Facts] of the app ([repo] is not needed: they come from the files). Raises [SdkError] when the minimum Android version cannot be read."""
    min_sdk, compile_sdk = sdk_levels(app_dir)
    text = license_text(app_dir)
    return Facts(min_sdk, compile_sdk, tuple(screenshot_files(app_dir)), license_name(text) if text else "All rights reserved")


def screenshot_files(app_dir):
    """The screenshots of the app, as paths relative to its root, in name order."""
    return sorted(p.relative_to(app_dir).as_posix() for p in (app_dir / SCREENSHOTS).glob("*.png"))


def problems(data, app_dir=None):
    """What is wrong with the parsed readme.yml [data] of an Android app, as a list of sentences. With the folder of the app
    [app_dir], it also checks what the README needs from the project: the screenshots of docs/screenshots/ and the LICENSE
    file. Without, it checks only the data."""
    found = common_problems(data, KNOWN, LINKS)
    if not isinstance(data, dict):
        return found
    if "screenshots" in data and data["screenshots"] != "manual":
        found.append("`screenshots` can only be `manual` (the screenshots are committed by hand, because the app cannot "
                     "render previews); without it, CI renders them from the app's screenshot package")
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
    if app_dir is not None:
        manual = data.get("screenshots") == "manual"
        if manual and package_folders(app_dir):
            found.append("`screenshots: manual` but the app has a screenshot package: remove one of them")
        if not screenshot_files(app_dir):
            found.append("the app has no screenshots in docs/screenshots/: every app has at least one. "
                         + ("It says `screenshots: manual`, so commit one into docs/screenshots/" if manual else
                            "Add a screenshot package (docs/screenshots.md in LukeNeedham/ci-workflows), or, for an app "
                            "that cannot render previews, set `screenshots: manual` and commit one into docs/screenshots/"))
        found += missing_license(app_dir, "app")
    return found


def alt_text(path):
    """`docs/screenshots/02-PullRequest.png` -> `Pull Request` (the number only orders the images)"""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", re.sub(r"^\d+-", "", Path(path).stem))


def render(data, repo, facts):
    """The README.md text for the valid [data] of the GitHub repo [repo] (`owner/name`) and the [Facts] of the app."""
    name = str(data["name"]).strip()
    repo_name = repo.split("/")[1]
    links = data.get("links") or {}
    shown = [(title, links[key].strip()) for key, title in LINKS.items() if links.get(key)]
    shown += [(str(o["title"]).strip(), o["url"].strip()) for o in links.get("other") or []]
    stores = [f"[{title}]({url})" for title, url in shown if title in ("Google Play", "F-Droid")]
    user = data.get("user") or {}
    install = str(user.get("install") or "").strip() or (
        f"Install it from {' or '.join(stores)}, or get the latest build from the [AppHub](https://www.lukeneedham.com/apphub) app "
        f"or the [Releases](https://github.com/{repo}/releases) page."
        if stores else
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
        *([" · ".join(f"[{title}]({url})" for title, url in shown), ""] if shown else []),
        "## Description",
        "",
        str(data["description"]).strip(),
        "",
    ]
    if facts.screenshots:
        out += ["## Screenshots", "", *[f'<img src="{s}" width="240" alt="{alt_text(s)}">' for s in facts.screenshots], ""]
    out += [
        "## Getting started as a user",
        "",
        *[f"{i}. {s}" for i, s in enumerate(steps, 1)],
        "",
        f"Requires {android_version(facts.min_sdk)} or newer.",
        "",
        "## Getting started as a developer",
        "",
        f"Requirements: JDK {SETTINGS['java-version']} and the Android SDK"
        f"{f' (platform {facts.compile_sdk})' if facts.compile_sdk else ''}, for example through Android Studio.",
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
    out += [
        "## License",
        "",
        f"{facts.license}. See [{LICENSE_FILE}]({LICENSE_FILE}).",
    ]
    return "\n".join(out) + "\n"
