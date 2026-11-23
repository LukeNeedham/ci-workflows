"""The README of a website (stack `next-js`): its fields, the facts it reads from the project and its layout. The delegate
of generate_readme.py for `--stack next-js`; the layout is in docs/readme.md, "Websites"."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import next_js_project
from generate_readme import (HEADER, LICENSE_FILE, FactsError, common_problems, license_name, license_text,
                             missing_license)

CREDITS_FILE = "CREDITS.md"
# A website: what its visitors see is the site itself, so there are no screenshots and no install steps
LINKS = {}  # the production site is not a field: it is the `productionUrl` of the site in apps.json
KNOWN = {"name", "tagline", "description", "links", "developer", "sections"}
# The scripts of package.json that the README lists, in this order, with what each one does
SCRIPTS = [
    ("dev", "the site at http://localhost:3000"),
    ("lint", "the checks of CI"),
    ("format", "fix the formatting"),
    ("typecheck", "the types"),
    ("test", "unit tests"),
    ("build", "the production build"),
]
APPS_FILE = Path(__file__).resolve().parent.parent / "apps.json"


@dataclass
class Facts:
    """What the README of a website says that is not in readme.yml: it comes from the project."""
    manager: str = "yarn"
    install: str = "yarn install"
    run: str = "yarn"
    scripts: tuple = ()
    node: str = ""
    license: str = "All rights reserved"
    production_url: str = ""
    credits: bool = False


def production_url(repo, apps_file=APPS_FILE):
    """The `productionUrl` of the project [repo] (`owner/name`) in apps.json of ci-workflows, or "" when it has none (or is not listed yet)."""
    if not repo or not Path(apps_file).is_file():
        return ""
    for app in json.loads(Path(apps_file).read_text()):
        if app.get("repo", "").lower() == repo.lower():
            return str(app.get("productionUrl") or "")
    return ""


def facts(app_dir, repo=None, apps_file=APPS_FILE):
    """The [Facts] of the website [repo] in [app_dir]: the package manager (from the lockfile), the scripts of package.json that
    the README lists, the major Node version (`engines.node`), the license, and its production address (apps.json of ci-workflows)."""
    package = json.loads((app_dir / "package.json").read_text())
    found = next_js_project.detect(app_dir)
    if found is None:
        raise FactsError("there is no lockfile (yarn.lock, pnpm-lock.yaml or package-lock.json): the README takes the package manager from it")
    manager, _, run = found
    scripts = package.get("scripts") or {}
    node = re.search(r"\d+", str((package.get("engines") or {}).get("node") or ""))
    text = license_text(app_dir)
    return Facts(manager, f"{manager} install", run, tuple(name for name, _ in SCRIPTS if name in scripts),
                    node.group(0) if node else "", license_name(text) if text else "All rights reserved",
                    production_url(repo, apps_file), (app_dir / CREDITS_FILE).is_file())


def problems(data, app_dir=None):
    """What is wrong with the parsed readme.yml [data] of a website, as a list of sentences. With the folder of the site [app_dir],
    it also checks what the README needs from the project: its package.json and lockfile, a LICENSE file, and that CREDITS.md is
    not also a section. Without, it checks only the data."""
    found = common_problems(
        data, KNOWN, LINKS,
        hints={key: "a website has no screenshots and no install steps: see docs/readme.md" for key in ("screenshots", "user")},
        link_hints={"web": "`links.web` is not a field: the production address is the `productionUrl` of the site in apps.json of ci-workflows"})
    if not isinstance(data, dict) or app_dir is None:
        return found
    if not (app_dir / "package.json").is_file():
        found.append("the website has no package.json: the README takes its commands and Node version from it")
    elif next_js_project.detect(app_dir) is None:
        found.append("the website has no lockfile (yarn.lock, pnpm-lock.yaml or package-lock.json): the README takes its package manager from it")
    if (app_dir / CREDITS_FILE).is_file():
        for i, section in enumerate(s for s in data.get("sections") or [] if isinstance(s, dict)):
            if str(section.get("title", "")).strip().lower() == "credits":
                found.append(f"`sections[{i}]` is `Credits`, but the site has a {CREDITS_FILE} file, which the README links to: "
                             f"put the credits there")
    return found + missing_license(app_dir, "website")


def render(data, repo, facts):
    """The README.md text of a website, for the valid [data] of the GitHub repo [repo] (`owner/name`) and its [Facts]."""
    name = str(data["name"]).strip()
    repo_name = repo.split("/")[1]
    links = data.get("links") or {}
    shown = [("Website", facts.production_url)] if facts.production_url else []
    shown += [(str(o["title"]).strip(), o["url"].strip()) for o in links.get("other") or []]
    comments = dict(SCRIPTS)
    commands = [f"git clone https://github.com/{repo}.git", f"cd {repo_name}", facts.install]
    lines = [(f"{facts.run} {script}", comments[script]) for script in facts.scripts]
    width = max([len(c) for c, _ in lines], default=0) + 4
    commands += [f"{command:<{width}}# {comment}" for command, comment in lines]
    out = [
        HEADER,
        f"# {name}",
        "",
        str(data["tagline"]).strip(),
        "",
        *([" · ".join(f"[{title}]({url})" for title, url in shown), ""] if shown else []),
        "## Description",
        "",
        str(data["description"]).strip(),
        "",
        "## Getting started as a developer",
        "",
        f"Requirements: Node.js {facts.node} and {facts.manager}." if facts.node else f"Requirements: Node.js and {facts.manager}.",
        "",
        "```",
        *commands,
        "```",
        "",
        "Every pull request gets a preview on Vercel, which CI links in a comment, and `main` is deployed by Vercel, so do not "
        "push to `main` for any other reason than to release.",
        "",
        "Like all my websites, it follows the shared architecture and conventions (Next.js, TypeScript, Chakra UI, MVVM with "
        "every page split into a `Page` and a `PageContent`): "
        "see [ci-workflows](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/next-js-app.md).",
        "",
    ]
    notes = (data.get("developer") or {}).get("notes")
    if notes:
        out += [str(notes).strip(), ""]
    for section in data.get("sections") or []:
        out += [f"## {str(section['title']).strip()}", "", str(section["body"]).strip(), ""]
    if facts.credits:
        out += ["## Credits", "", f"See [{CREDITS_FILE}]({CREDITS_FILE}).", ""]
    out += [
        "## License",
        "",
        f"{facts.license}. See [{LICENSE_FILE}]({LICENSE_FILE}).",
    ]
    return "\n".join(out) + "\n"
