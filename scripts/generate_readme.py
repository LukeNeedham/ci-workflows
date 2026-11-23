#!/usr/bin/env python3
"""Renders an app's README.md from its readme.yml, in the standard layout of docs/readme.md.

The layout lives here, the content in the app. Needs PyYAML. This file is the caller: the command line, the checks that
both stacks share (the license helpers, the fields every readme.yml has) and the choice of the delegate of the stack, which
has that stack's own fields, facts from the project and layout:

- `readme_kmp.py`, an Android app (`--stack kmp`, the default). What comes from the project is not in readme.yml: the
  screenshots (the PNGs of docs/screenshots/, which CI renders from the app's screenshot package, docs/screenshots.md),
  the minimum Android version (the minSdk of app/build.gradle.kts) and, if there is a LICENSE file, the license.
- `readme_web.py`, a website (`--stack next-js`). A smaller format (docs/readme.md, "Websites"): no icon, screenshots or
  install steps; the project facts are the package manager (from the lockfile), the scripts of package.json, the Node
  version (`engines.node`), the production address (`productionUrl` in apps.json), and the CREDITS.md and LICENSE files, which each add a section when they exist.

    python3 generate_readme.py [app_dir] [--repo owner/name] [--stack kmp|next-js] [--check]

--repo defaults to $GITHUB_REPOSITORY, then to the app's git `origin`. --check writes nothing and exits 1 if
README.md is missing or differs from what readme.yml renders to.

A delegate is a module with `problems(data, app_dir=None)`, `facts(app_dir, repo)` and `render(data, repo, facts)`.
"""

import argparse
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

SOURCE = "readme.yml"
HEADER = f"<!-- Generated from {SOURCE} by LukeNeedham/ci-workflows (docs/readme.md). Edit {SOURCE}, not this file. -->"
REQUIRED_TEXT = ["name", "tagline", "description"]
LICENSE_FILE = "LICENSE"
# The stack of a project (`stack` in apps.json) and the module that delegates for it
DELEGATES = {"kmp": "readme_kmp", "next-js": "readme_web"}
STACKS = tuple(DELEGATES)


class FactsError(Exception):
    """What the README needs from the project cannot be read: the message says what to fix."""


def delegate(stack):
    """The module of [stack], which has `problems`, `facts` and `render`. Imported here and not at the top: it imports this file."""
    return importlib.import_module(DELEGATES[stack])


def license_text(app_dir):
    """The text of the LICENSE file of the app, or None when there is none."""
    path = app_dir / LICENSE_FILE
    return path.read_text(errors="ignore") if path.is_file() else None


def license_of(app_dir):
    """The name of the license of the app in [app_dir], from its LICENSE file, or None when it has no (or an empty) one: then
    the README has no License section, as it has no Credits section without a CREDITS.md."""
    text = license_text(app_dir)
    return license_name(text) if text and text.strip() else None


def license_section(license):
    """The lines of the `## License` section for the license named [license], none when it is None (no LICENSE file)."""
    return ["## License", "", f"{license}. See [{LICENSE_FILE}]({LICENSE_FILE})."] if license else []


def end_of(out, license):
    """The README text made of the lines [out] (which end with a blank line), with the License section after them if there is one."""
    lines = out + license_section(license)
    while lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


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


def common_problems(data, known, link_titles, hints=None, link_hints=None):
    """What is wrong with the fields that every readme.yml has, in the parsed [data], as a list of sentences: the field names
    ([known]), the required text, `links` (the keys of [link_titles], and `other`), `developer` and `sections`, and that free text
    cannot add a section of its own. [hints] adds a sentence to the unknown-field error of a key, and [link_hints] replaces the
    error of a key of `links`. A stack's own fields are checked by its delegate."""
    if not isinstance(data, dict):
        return [f"{SOURCE} must be a mapping of fields"]
    hints, link_hints = hints or {}, link_hints or {}
    found = []
    for key in data:
        if key == "license":
            found.append(f"`license` is not a field: the license is the one in the {LICENSE_FILE} file of the app")
        elif key not in known:
            found.append(f"unknown field `{key}`" + (f" ({hints[key]})" if key in hints else ""))
    for key in REQUIRED_TEXT:
        if not str(data.get(key) or "").strip():
            found.append(f"`{key}` is required")
    links = data.get("links")
    if links is not None and not isinstance(links, dict):
        found.append("`links` must be a mapping")
    elif links:
        for key, value in links.items():
            if key == "other":
                for i, link in enumerate(value or []):
                    if not isinstance(link, dict) or not link.get("title") or not is_url(link.get("url")):
                        found.append(f"`links.other[{i}]` needs a `title` and an https `url`")
            elif key in link_hints:
                found.append(link_hints[key])
            elif key not in link_titles:
                found.append(f"unknown field `links.{key}` (one of {', '.join(link_titles)}, or `other`)" if link_titles
                             else f"unknown field `links.{key}` (only `other`)")
            elif not is_url(value):
                found.append(f"`links.{key}` must be an https URL")
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
    return found


def problems(data, app_dir=None, stack="kmp"):
    """What is wrong with the parsed readme.yml [data] of a project of [stack], as a list of sentences. With the folder of the
    project [app_dir], it also checks what the README needs from the project. Without, it checks only the data."""
    return delegate(stack).problems(data, app_dir)


def facts(app_dir, repo=None, stack="kmp"):
    """What the README of the project in [app_dir] says that is not in readme.yml. Raises [FactsError] when it cannot be read."""
    return delegate(stack).facts(app_dir, repo)


def render(data, repo, facts, stack="kmp"):
    """The README.md text for the valid [data] of the GitHub repo [repo] (`owner/name`) and its [facts]."""
    return delegate(stack).render(data, repo, facts)


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


def write(app_dir, repo, stack):
    """Renders README.md of the project in [app_dir] from its readme.yml, as the command line does. Returns True when it wrote.
    For the scaffold of a new website."""
    data = load(app_dir)
    found = problems(data, app_dir, stack)
    if found:
        raise ValueError("\n".join(f"{SOURCE}: {line}" for line in found))
    text = render(data, repo, facts(app_dir, repo, stack), stack)
    readme = app_dir / "README.md"
    if readme.is_file() and readme.read_text() == text:
        return False
    readme.write_text(text)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("app_dir", nargs="?", default=".")
    parser.add_argument("--repo")
    parser.add_argument("--stack", choices=STACKS, default="kmp",
                        help="what the project is built with: kmp (an Android app, the default) or next-js (a website)")
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
        template = "docs/readme-template-web.yml" if args.stack == "next-js" else "docs/readme-template.yml"
        message = f"There is no {SOURCE}. Write one from {template} in LukeNeedham/ci-workflows; CI then generates README.md from it."
        if args.skip_if_missing:
            print(f"::warning file=README.md::{message}")
            return
        sys.exit(message)
    found = problems(data, app_dir, args.stack)
    if found:
        sys.exit("\n".join(f"{SOURCE}: {line}" for line in found))
    repo = find_repo(app_dir, args.repo)
    try:
        app_facts = facts(app_dir, repo, args.stack)
    except FactsError as e:
        sys.exit(f"{SOURCE}: {e}")
    text = render(data, repo, app_facts, args.stack)
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
    # The delegates import this file by name: run it as that module, so that there is one copy of it
    import generate_readme
    generate_readme.main()
