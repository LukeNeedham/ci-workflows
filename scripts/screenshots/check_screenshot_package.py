#!/usr/bin/env python3
"""Checks the Kotlin files of an app's screenshot package against the rules of docs/screenshots.md.

    python3 check_screenshot_package.py File.kt ...

Every screenshot owns its data, and nothing is shared: not between pages, not between the screenshots of one page,
not with the general previews or the app. So a file of the package holds nothing at the top level but private
`@Preview` composables without parameters, each with its mock data inside its own body. Anything else (a top-level
`val`, an object, a helper function, a public or `internal` declaration) is a way to share, and fails the check.
Prints what is wrong and exits 1 if anything is.
"""

import re
import sys

PREVIEW_FUNCTION = re.compile(r"private fun \w+\(\s*\)\s*\{?\s*$")
ANNOTATION_ONLY = re.compile(r"@\w+(\.\w+)*(\([^)]*\))?\s*$")


def problems(text):
    """The (line number, line) of every top-level declaration in [text] that is not a private @Preview composable."""
    found = []
    annotations = []
    in_comment = False
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if in_comment:
            in_comment = "*/" not in line
            continue
        if line.lstrip().startswith("/*"):
            in_comment = "*/" not in line
            continue
        if line.startswith("//") or line[0] in " \t" or line.startswith(("package ", "import ")):
            continue
        if line[0] in "})":
            annotations = []
            continue
        if ANNOTATION_ONLY.match(line):
            annotations.append(line.split("(")[0].strip())
            continue
        if "@Preview" not in annotations or not PREVIEW_FUNCTION.match(line):
            found.append((number, line.strip()))
        annotations = []
    return found


def main():
    failed = False
    for path in sys.argv[1:]:
        with open(path) as f:
            for number, line in problems(f.read()):
                failed = True
                print(f"{path}:{number}: `{line}` is shared or not a screenshot. A file of the screenshot package holds "
                      f"only private @Preview composables with their own data inside (docs/screenshots.md).")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
