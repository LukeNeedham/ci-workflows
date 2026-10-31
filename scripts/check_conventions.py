#!/usr/bin/env python3
"""Checks the Kotlin code of an app against the conventions of the docs (docs/lint.md).

    python3 check_conventions.py [APP_DIR]

The one entry point of the checks that CI runs in the `conventions` job of every PR: the Koin and naming rules, the page,
ViewModel, UiState, sheet and preview rules, and the screenshot package. The rules are in scripts/conventions/, one module
for each group, on the shared scanner and context of scan.py and core.py. Prints an error annotation (file, line, rule id)
for each violation and a summary, and exits 1 if there is any.
"""

import sys

from conventions.core import main

if __name__ == "__main__":
    sys.exit(main())
