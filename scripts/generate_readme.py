#!/usr/bin/env python3
"""Renders an app's README.md from its readme.yml, in the standard layout of docs/readme.md.

The layout lives here, the content in the app. Needs PyYAML.

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
REQUIRED_LISTS = ["features", "structure"]
KNOWN = {"name", "tagline", "description", "features", "screenshots", "user", "developer", "structure",
         "architecture", "sections", "license"}


def problems(data):
    """What is wrong with the parsed readme.yml [data], as a list of sentences."""
    if not isinstance(data, dict):
        return [f"{SOURCE} must be a mapping of fields"]
    found = [f"unknown field `{k}`" for k in data if k not in KNOWN]
    for key in REQUIRED_TEXT:
        if not str(data.get(key) or "").strip():
            found.append(f"`{key}` is required")
    for key in REQUIRED_LISTS:
        value = data.get(key)
        if not isinstance(value, list) or not value or not all(str(v).strip() for v in value):
            found.append(f"`{key}` must be a non-empty list")
    user = data.get("user")
    if not isinstance(user, dict) or not str(user.get("min-android") or "").strip():
        found.append("`user.min-android` is required")
    elif user.get("steps") is not None and not isinstance(user["steps"], list):
        found.append("`user.steps` must be a list")
    elif user.get("install") is not None and not str(user["install"]).strip():
        found.append("`user.install` must not be empty")
    for i, shot in enumerate(data.get("screenshots") or []):
        if not isinstance(shot, dict) or not shot.get("path") or not shot.get("alt"):
            found.append(f"`screenshots[{i}]` needs `path` and `alt`")
    for i, section in enumerate(data.get("sections") or []):
        if not isinstance(section, dict) or not section.get("title") or not section.get("body"):
            found.append(f"`sections[{i}]` needs `title` and `body`")
    return found


def render(data, repo):
    """The README.md text for the valid [data] of the GitHub repo [repo] (`owner/name`)."""
    name = str(data["name"]).strip()
    repo_name = repo.split("/")[1]
    user = data["user"]
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
        "## Features",
        "",
        *[f"- {str(f).strip()}" for f in data["features"]],
        "",
    ]
    if data.get("screenshots"):
        out += ["## Screenshots", "", *[f'<img src="{s["path"]}" width="240" alt="{s["alt"]}">' for s in data["screenshots"]], ""]
    out += [
        "## Getting started as a user",
        "",
        *[f"{i}. {s}" for i, s in enumerate(steps, 1)],
        "",
        f"Requires Android {str(user['min-android']).strip()} or newer.",
        "",
        "## Getting started as a developer",
        "",
        "Requirements: JDK 17 and the Android SDK (platform 36), for example through Android Studio.",
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
    ]
    notes = (data.get("developer") or {}).get("notes")
    if notes:
        out += [str(notes).strip(), ""]
    out += ["## Project structure", "", *[f"- {str(s).strip()}" for s in data["structure"]], ""]
    if data.get("architecture"):
        out += [str(data["architecture"]).strip(), ""]
    out += [
        "See the [shared conventions](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/app-conventions.md).",
        "",
    ]
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
    found = problems(data)
    if found:
        sys.exit("\n".join(f"{SOURCE}: {line}" for line in found))
    text = render(data, find_repo(app_dir, args.repo))
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
