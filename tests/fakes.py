"""Test doubles for the tools that the scripts call: a `gh` that records its arguments and answers from a table."""

import json
import os
import stat
import tempfile
from pathlib import Path

STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
for prefix, (code, out) in json.load(open(os.environ["FAKE_GH_ANSWERS"])).items():
    if " ".join(args).startswith(prefix):
        sys.stdout.write(out)
        sys.exit(code)
"""


class FakeGh:
    """Put in front of PATH while it is entered. `answers` maps the start of a command line (`release list`) to an
    (exit code, stdout) pair; any other command succeeds and prints nothing. `calls` lists the argument lists seen."""

    def __init__(self, answers=None):
        self.answers = answers or {}

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        base = Path(self.dir.name)
        stub = base / "gh"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        (base / "answers.json").write_text(json.dumps(self.answers))
        self.log = base / "calls.log"
        self.saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_GH_LOG", "FAKE_GH_ANSWERS")}
        os.environ["PATH"] = f"{base}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_GH_LOG"] = str(self.log)
        os.environ["FAKE_GH_ANSWERS"] = str(base / "answers.json")
        return self

    def __exit__(self, *exc):
        self._calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.dir.cleanup()

    @property
    def calls(self):
        return self._calls
