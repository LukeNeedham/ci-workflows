"""NAME-1: an acronym is an ordinary word in a camel case name (docs/app-conventions.md#naming)."""

import re

from . import scan as k
from .violation import Violation

RULES = {
    "NAME-1": "An acronym is an ordinary word in a camel case name: IosSdkManager, not iOSSDKManager",
}


def acronym_problem(name):
    """The word in [name] that is an acronym written in capitals, or None. A run of capitals followed by a lower case
    letter ends with the first letter of the next word, so it is an acronym from three letters (`HTTPClient`); a run of two
    is a one-letter word and a word (`parsesAUri`, `selectedXOffset`). A run at the end or before a digit is an acronym."""
    name = name.strip("_")
    if not name or re.fullmatch(r"[A-Z0-9_]+", name):
        return None
    for match in re.finditer(r"[A-Z]{2,}", name):
        run, after = match.group(), name[match.end():match.end() + 1]
        if after == "" or after.isdigit() or after == "_":
            return run
        if len(run) >= 3:
            return run[:-1]
    return None


def lower_acronyms(name):
    """[name] with its acronyms as ordinary words, as a suggestion."""
    def fix(match):
        run, after = match.group(), name[match.end():match.end() + 1]
        if after and after.islower():
            if len(run) < 3:
                return run
            return run[0] + run[1:-1].lower() + run[-1]
        return run[0] + run[1:].lower()
    return re.sub(r"[A-Z]{2,}", fix, name)


DECLARATIONS = [
    re.compile(r"\b(?:class|object|interface|typealias)\s+(\w+)"),
    re.compile(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.<>?,\s]+\.)?(\w+)\s*[(<]"),
    re.compile(r"\b(?:val|var)\s+(?:<[^>]*>\s*)?(?:[\w.<>?]+\.)?(\w+)"),
    re.compile(r"(?<![\w.@:])(\w+)\s*:(?!:)"),
]


def acronym_rule(path, raw, clean):
    """acronym-naming: the names the file declares, and its own file name."""
    found = []
    raw_lines = raw.splitlines()
    for part in path.name.removesuffix(".kt").split("."):
        if acronym_problem(part):
            found.append(Violation(path, 1, "NAME-1", f"file name `{path.name}`: write `{lower_acronyms(part)}` "
                                   "(an acronym is an ordinary word in a camel case name)"))
    seen = set()
    for pattern in DECLARATIONS:
        for match in pattern.finditer(clean):
            name, line = match.group(1), k.line_of(clean, match.start(1))
            if (name, line) in seen or not acronym_problem(name):
                continue
            before = clean[clean.rfind("\n", 0, match.start()) + 1:match.start()]
            if re.search(r"\boverride\b", before):
                continue
            nearby = raw_lines[max(line - 2, 0):line]
            if any("AcronymNaming" in text for text in nearby):
                continue
            seen.add((name, line))
            found.append(Violation(path, line, "NAME-1", f"`{name}`: an acronym is an ordinary word in a camel case "
                                   f"name, e.g. `{lower_acronyms(name)}` (docs/app-conventions.md#naming)"))
    return found


def check(ctx):
    for f in ctx.all_files:
        ctx.violations += acronym_rule(f.rel, f.raw, f.clean)
