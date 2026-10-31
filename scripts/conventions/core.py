"""What every check of the conventions shares: the Kotlin files of an app, a violation, the `lint:ignore` comments that
silence one, the annotations that report them, and the run that goes through all the rules (docs/lint.md)."""

import argparse
import bisect
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import scan as k
from .roles import page_of, role, sheet_role
from .violation import Violation

SKIP_DIRS = {"build", ".gradle", ".git", ".idea", ".kotlin", "node_modules", "out"}
PACKAGE = re.compile(r"^\s*package\s+([\w.]+)", re.M)
IMPORT = re.compile(r"^\s*import\s+([\w.*]+)", re.M)
IGNORE = re.compile(r"//\s*lint:ignore\s+([A-Z]+-\d+)\s*(?::\s*(\S.*))?")

RULES = {
    "IGNORE-1": "A lint:ignore names a rule of this list and gives a reason",
}


def is_test_path(rel):
    """Whether [rel] is in a test source set (`test`, `androidTest`, `commonTest`, `androidUnitTest`...)."""
    return any(part in {"test", "androidTest"} or part.endswith("Test") for part in rel.parts[:-1])


class SourceFile:
    def __init__(self, app_dir, rel):
        self.rel = rel
        self.path = rel.as_posix()
        self.stem = rel.stem
        self.raw = (app_dir / rel).read_text(encoding="utf-8", errors="replace")
        self.clean, self.decls = k.parse(self.raw)
        m = PACKAGE.search(self.clean)
        self.package = m.group(1) if m else ""
        self.imports = [(k.line_of(self.clean, m.start(1)), m.group(1)) for m in IMPORT.finditer(self.clean)]
        self.comments = k.comment_spans(self.raw)
        self.is_screenshot = rel.parent.name == "screenshot"
        self.is_test = is_test_path(rel)
        self.is_source = not self.is_test and "src" in rel.parts[:-1]  # a file of a source set of a module
        self.starts = [d.start for d in self.decls]

    def in_comment(self, offset):
        return any(a <= offset < b for a, b in self.comments)

    def decl_at(self, offset):
        i = bisect.bisect_right(self.starts, offset) - 1
        return self.decls[i] if i >= 0 and offset < self.decls[i].end else None


def kotlin_files(app_dir):
    """The Kotlin files of the app, relative to [app_dir]: every source set, the test ones too."""
    found = []
    for folder, dirs, names in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [(Path(folder) / name).relative_to(app_dir) for name in names if name.endswith(".kt")]
    return sorted(found)


class Context:
    """The app being checked, as the rules see it: its files, the pages and sheets in them, and the violations found."""

    def __init__(self, app_dir):
        self.app_dir = Path(app_dir)
        self.all_files = [SourceFile(self.app_dir, rel) for rel in kotlin_files(self.app_dir)]
        self.files = [f for f in self.all_files if f.is_source]  # the code of the app: the page and preview rules read these
        self.violations = []
        self.by_role = defaultdict(dict)  # role -> {(package, X): (file, declaration)}
        self.sheets = defaultdict(dict)  # SHEET or SHEET_CONTENT -> {(package, X): (file, declaration)}
        for f in self.files:
            if f.is_screenshot:
                continue
            for d in f.decls:
                if role(d):
                    self.by_role[role(d)].setdefault((f.package, page_of(d)), (f, d))
                if sheet_role(d):
                    self.sheets[sheet_role(d)].setdefault((f.package, d.name[:-len(sheet_role(d))]), (f, d))
        self.known = {x for pairs in self.by_role.values() for (_, x) in pairs}

    def add(self, f, line, rule, message, anchor=None):
        self.violations.append(Violation(f.path, line, rule, message, anchor or line))

    def add_path(self, path, line, rule, message):
        """A violation of something that is not in a Kotlin file (the app as a whole, a file of the screenshot package)."""
        self.violations.append(Violation(path, line, rule, message))

    def at(self, f, d, rule, message):
        self.add(f, d.line, rule, message, d.first_line)

    def has(self, kind, f, x):
        return (f.package, x) in self.by_role[kind]

    def apply_ignores(self, rules):
        """The violations that no `lint:ignore` silences; a malformed one is a violation (IGNORE-1) itself."""
        ignores = defaultdict(set)  # path -> {(rule, line)}
        for f in self.all_files:
            for m in IGNORE.finditer(f.raw):
                if not f.in_comment(m.start()):
                    continue
                line = k.line_of(f.raw, m.start())
                if m.group(1) not in rules or m.group(1) == "IGNORE-1":
                    self.add(f, line, "IGNORE-1", f"`{m.group(1)}` is not a rule that can be ignored (docs/lint.md lists them)")
                elif not m.group(2):
                    self.add(f, line, "IGNORE-1", f"lint:ignore {m.group(1)} gives no reason: `// lint:ignore {m.group(1)}: why`")
                else:
                    ignores[f.path].add((m.group(1), line))
        return [v for v in self.violations
                if not any((v.rule, n) in ignores[v.path] for n in range(v.anchor - 1, v.line + 1))]


def checks():
    """The modules with rules, each with a `RULES` dict (id -> what it demands) and a `check(ctx)` that adds violations."""
    from . import di, naming, pages, previews, screenshots, sheets, toplevel, viewmodels
    return [di, naming, toplevel, pages, sheets, viewmodels, previews, screenshots]


def all_rules():
    """Every rule id with what it demands, in the order of the modules (docs/lint.md lists the same ids)."""
    rules = {}
    for module in checks():
        rules.update(module.RULES)
    rules.update(RULES)
    return rules


def lint(app_dir):
    """The violations in the app at [app_dir], sorted."""
    return run(Context(app_dir))


def run(ctx):
    for module in checks():
        module.check(ctx)
    unique = {(v.path, v.line, v.rule, v.message): v for v in ctx.violations}
    ctx.violations = list(unique.values())
    return sorted(ctx.apply_ignores(all_rules()), key=lambda v: (v.path, v.line, v.rule))


def escape(text, prop=False):
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def summary(violations, count):
    if not violations:
        return f"### Conventions\n\nNo violations in {count} Kotlin files.\n"
    rows = "\n".join(f"| `{v.rule}` | `{v.path}:{v.line}` | {v.message} |" for v in violations[:300])
    more = f"\n\n…and {len(violations) - 300} more." if len(violations) > 300 else ""
    return (f"### Conventions: {len(violations)} violations\n\nThe rules are in `docs/lint.md` of LukeNeedham/ci-workflows.\n\n"
            f"| Rule | Where | What |\n|---|---|---|\n{rows}{more}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Checks an app's Kotlin code against the conventions (docs/lint.md).")
    parser.add_argument("app_dir", nargs="?", default=".")
    args = parser.parse_args(argv)
    ctx = Context(args.app_dir)
    violations = run(ctx)
    for v in violations:
        print(f"::error file={escape(v.path, True)},line={v.line},title={v.rule}::{escape(v.message)}")
        print(f"{v.path}:{v.line}: [{v.rule}] {v.message}")
    text = summary(violations, len(ctx.all_files))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a") as out:
            out.write(text)
    print(f"\n{len(violations)} violations in {len(ctx.all_files)} Kotlin files." if violations
          else f"Conventions: no violations in {len(ctx.all_files)} Kotlin files.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
