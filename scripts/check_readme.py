#!/usr/bin/env python3
"""Checks that a README.md follows the standard format of docs/readme.md. Checks only, never writes.

    python3 scripts/check_readme.py path/to/README.md

Prints what is wrong and exits 1 if anything is.
"""

import re
import sys
from pathlib import Path

REQUIRED = [
    "Description",
    "Features",
    "Getting started as a user",
    "Getting started as a developer",
    "Project structure",
    "Contributing",
    "License",
]
ICON_RE = re.compile(r"""(!\[[^\]]*\]\(\s*(\./)?app-icon\.png[\s)]|<img\b[^>]*\bsrc=["'](\./)?app-icon\.png["'])""")


def problems(text):
    """What is wrong with the README [text], as a list of sentences. Empty when it follows the format."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    found = []
    lines = text.splitlines()
    titles = [i for i, line in enumerate(lines) if re.match(r"^# \S", line)]
    if len(titles) != 1:
        found.append(f"needs exactly one `# <App name>` heading (found {len(titles)})")
    elif not ICON_RE.search("\n".join(lines[:titles[0]])):
        found.append("the app icon (`app-icon.png`) must come before the `# <App name>` heading")
    headings = [m.group(1).strip().lower() for m in (re.match(r"^## (.+?)\s*$", l) for l in lines) if m]
    last = -1
    for name in REQUIRED:
        if name.lower() not in headings:
            found.append(f"missing the `## {name}` section")
        elif headings.index(name.lower()) < last:
            found.append(f"`## {name}` is out of order (the order is {', '.join(REQUIRED)})")
        else:
            last = headings.index(name.lower())
    return found


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    if not path.is_file():
        sys.exit(f"{path}: no README.md")
    found = problems(path.read_text())
    for line in found:
        print(f"{path}: {line}")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
