#!/usr/bin/env python3
"""Renders an app's README.md from its readme.yml, in the standard layout of docs/readme.md.

The layout lives here, the content in the app. Needs PyYAML.

What comes from the project is not in readme.yml: the screenshots (the PNGs of docs/screenshots/, which CI renders from
the app's screenshot package, docs/screenshots.md), the minimum Android version (the minSdk of app/build.gradle.kts)
and the license (the LICENSE file). Every app has all three.

    python3 generate_readme.py [app_dir] [--repo owner/name] [--check]

--repo defaults to $GITHUB_REPOSITORY, then to the app's git `origin`. --check writes nothing and exits 1 if
README.md is missing or differs from what readme.yml renders to.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_config import SETTINGS
from conventions.screenshots import package_folders

SOURCE = "readme.yml"
HEADER = f"<!-- Generated from {SOURCE} by LukeNeedham/ci-workflows (docs/readme.md). Edit {SOURCE}, not this file. -->"
REQUIRED_TEXT = ["name", "tagline", "description"]
LICENSE_FILE = "LICENSE"
LINKS = {"play-store": "Google Play", "f-droid": "F-Droid", "web": "Web app"}
SCREENSHOTS = "docs/screenshots"
KNOWN = {"name", "tagline", "description", "links", "screenshots", "user", "developer", "sections"}
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


def license_text(app_dir):
    """The text of the LICENSE file of the app, or None when there is none."""
    path = app_dir / LICENSE_FILE
    return path.read_text(errors="ignore") if path.is_file() else None


def license_name(text):
    """The name of the license in the LICENSE file [text]: a well-known one by its wording, else its first line."""
    flat = " ".join(text.split())
    known = [
        (r"\bMIT License\b|Permission is hereby granted, free of charge", "MIT"),
        (r"Apache License,? Version 2\.0", "Apache 2.0"),
        (r"GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
        (r"GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
        (r"GNU GENERAL PUBLIC LICENSE\s+Version 3", "GPL 3.0"),
        (r"GNU GENERAL PUBLIC LICENSE\s+Version 2", "GPL 2.0"),
        (r"Mozilla Public License", "MPL 2.0"),
        (r"This is free and unencumbered software released into the public domain", "Unlicense"),
        (r"Redistribution and use in source and binary forms", "BSD"),
        (r"All rights reserved", "All rights reserved"),
    ]
    for pattern, name in known:
        if re.search(pattern, flat, re.I):
            return name
    return next((line.strip() for line in text.splitlines() if line.strip()), "See LICENSE")


@dataclass
class Facts:
    """What the README says that is not in readme.yml: it comes from the project."""
    min_sdk: int
    compile_sdk: int = None
    screenshots: tuple = ()
    license: str = "All rights reserved"


def facts(app_dir):
    """The [Facts] of the app. Raises [SdkError] when the minimum Android version cannot be read."""
    min_sdk, compile_sdk = sdk_levels(app_dir)
    text = license_text(app_dir)
    return Facts(min_sdk, compile_sdk, tuple(screenshot_files(app_dir)), license_name(text) if text else "All rights reserved")


def screenshot_files(app_dir):
    """The screenshots of the app, as paths relative to its root, in name order."""
    return sorted(p.relative_to(app_dir).as_posix() for p in (app_dir / SCREENSHOTS).glob("*.png"))


def headings(text):
    """The lines of the Markdown [text] that are a `#` or `##` heading (outside code), which would add a section of
    their own to the README."""
    found, fenced = [], False
    for line in str(text).splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,2}\s", line):
            found.append(line.strip())
    return found


def is_url(value):
    return isinstance(value, str) and re.fullmatch(r"https://\S+", value.strip()) is not None


def problems(data, app_dir=None):
    """What is wrong with the parsed readme.yml [data], as a list of sentences.

    With the folder of the app [app_dir], it also checks what the README needs from the project: the screenshots of
    docs/screenshots/ and the LICENSE file. Without, it checks only the data.
    """
    if not isinstance(data, dict):
        return [f"{SOURCE} must be a mapping of fields"]
    found = []
    for key in data:
        if key == "license":
            found.append(f"`license` is not a field: the license is the one in the {LICENSE_FILE} file of the app")
        elif key not in KNOWN:
            found.append(f"unknown field `{key}`")
    for key in REQUIRED_TEXT:
        if not str(data.get(key) or "").strip():
            found.append(f"`{key}` is required")
    if "screenshots" in data and data["screenshots"] != "manual":
        found.append("`screenshots` can only be `manual` (the screenshots are committed by hand, because the app cannot "
                     "render previews); without it, CI renders them from the app's screenshot package")
    links = data.get("links")
    if links is not None and not isinstance(links, dict):
        found.append("`links` must be a mapping")
    elif links:
        for key, value in links.items():
            if key == "other":
                for i, link in enumerate(value or []):
                    if not isinstance(link, dict) or not link.get("title") or not is_url(link.get("url")):
                        found.append(f"`links.other[{i}]` needs a `title` and an https `url`")
            elif key not in LINKS:
                found.append(f"unknown field `links.{key}` (one of {', '.join(LINKS)}, or `other`)")
            elif not is_url(value):
                found.append(f"`links.{key}` must be an https URL")
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
    for i, section in enumerate(data.get("sections") or []):
        if not isinstance(section, dict) or not section.get("title") or not section.get("body"):
            found.append(f"`sections[{i}]` needs `title` and `body`")
    # The layout is the standard one: free text cannot add a section of its own (use `sections`)
    texts = {"description": data.get("description"), "developer.notes": (developer or {}).get("notes") if isinstance(developer, dict) else None}
    for i, section in enumerate(s for s in data.get("sections") or [] if isinstance(s, dict)):
        texts[f"sections[{i}].body"] = section.get("body")
    for name, text in texts.items():
        for line in headings(text or ""):
            found.append(f"`{name}` has the heading `{line}`: it would add a section of its own. Use `###` or deeper, "
                         f"or a `sections` entry")
    if app_dir is not None:
        manual = data.get("screenshots") == "manual"
        if manual and package_folders(app_dir):
            found.append("`screenshots: manual` but the app has a screenshot package: remove one of them")
        if not screenshot_files(app_dir):
            found.append("the app has no screenshots in docs/screenshots/: every app has at least one. "
                         + ("It says `screenshots: manual`, so commit one into docs/screenshots/" if manual else
                            "Add a screenshot package (docs/screenshots.md in LukeNeedham/ci-workflows), or, for an app "
                            "that cannot render previews, set `screenshots: manual` and commit one into docs/screenshots/"))
        text = license_text(app_dir)
        if text is None or not text.strip():
            found.append(f"the app has no {LICENSE_FILE} file: every app has one. For an app that had no license, add one "
                         f"holding `Copyright (c) <year> Luke Needham. All rights reserved.`")
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
        "## Contributing",
        "",
        "Branch from `main`, make the change, and open a pull request. CI must be green before it is merged.",
        "",
        "## License",
        "",
        f"{facts.license}. See [{LICENSE_FILE}]({LICENSE_FILE}).",
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
    parser.add_argument("--skip-if-missing", action="store_true",
                        help="an app without a readme.yml yet only gets a warning, and keeps its README.md")
    args = parser.parse_args()
    app_dir = Path(args.app_dir)
    try:
        data = load(app_dir)
    except yaml.YAMLError as e:
        sys.exit(f"{SOURCE} is not valid YAML: {e}\nA value with a colon followed by a space (`Optional: add a token`) or "
                 f"starting with a quote, `*` or `&` has to be wrapped in quotes.")
    if data is None:
        message = f"There is no {SOURCE}. Write one from docs/readme-template.yml in LukeNeedham/ci-workflows; CI then generates README.md from it."
        if args.skip_if_missing:
            print(f"::warning file=README.md::{message}")
            return
        sys.exit(message)
    found = problems(data, app_dir)
    if found:
        sys.exit("\n".join(f"{SOURCE}: {line}" for line in found))
    try:
        app_facts = facts(app_dir)
    except SdkError as e:
        sys.exit(f"{SOURCE}: {e}")
    text = render(data, find_repo(app_dir, args.repo), app_facts)
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
