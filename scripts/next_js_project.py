#!/usr/bin/env python3
"""What the checks of a Next.js website (web_pr.yml) need to know about the project: its package manager, from the
lockfile, and whether it has a `test` script. Sets step outputs; a project has no settings (docs/next-js-app.md).

    python3 next_js_project.py [project directory]

Outputs: `manager` (yarn, pnpm or npm), `install` (the command that installs exactly what the lockfile says),
`run` (the command prefix that runs a script, such as `yarn` or `npm run`), `has-typecheck` and `has-test` ("true" or "false").
Exits 1 when there is no lockfile or no package.json: a project without a lockfile does not build the same twice.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import error, output

# The lockfile of each package manager, in the order they are looked for, and how to install and run with it
MANAGERS = [
    ("pnpm-lock.yaml", "pnpm", "pnpm install --frozen-lockfile", "pnpm"),
    ("yarn.lock", "yarn", "yarn install --frozen-lockfile", "yarn"),
    ("package-lock.json", "npm", "npm ci", "npm run"),
]


def detect(project):
    """(manager, install command, run prefix) of the project in the directory [project], or None without a lockfile."""
    for lockfile, manager, install, run in MANAGERS:
        if (project / lockfile).is_file():
            return manager, install, run
    return None


def has_script(project, name):
    scripts = json.loads((project / "package.json").read_text()).get("scripts", {})
    return name in scripts


def main():
    project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not (project / "package.json").is_file():
        error("There is no package.json: this is not a Next.js project.", "No package.json")
        sys.exit(1)
    found = detect(project)
    if not found:
        names = ", ".join(m[0] for m in MANAGERS)
        error(f"There is no lockfile ({names}): commit one, so that CI builds what you built.", "No lockfile")
        sys.exit(1)
    manager, install, run = found
    output("manager", manager)
    output("install", install)
    output("run", run)
    output("has-typecheck", "true" if has_script(project, "typecheck") else "false")
    output("has-test", "true" if has_script(project, "test") else "false")


if __name__ == "__main__":
    main()
