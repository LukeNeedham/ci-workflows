#!/usr/bin/env python3
"""Checks the Kotlin code of an app against the architecture and naming rules of the docs.

    python3 check_conventions.py [APP_DIR]

Prints every violation as `path:line: [rule] message` (as a GitHub annotation when run by GitHub Actions) and exits 1 if
there is any. The rules, each in docs/conventions-check.md with the docs it comes from:

- koin-required      the app uses Koin and has a `KoinModules.kt` (docs/new-app.md)
- koin-modules-file  `KoinModules.kt` and `KoinQualifier.kt` hold only their object, in a `di` package (docs/app-shell.md)
- module-in-object   a `module { }` is declared in an object of a file in a `di` folder, never at the top level
- koin-wiring-only   a binding calls get(), androidContext(), runtime parameters and named constants and nothing else:
                     no literals, DSL blocks, operators, control flow or chained calls (docs/new-app.md)
- koin-qualifier     a qualifier is a constant of `KoinQualifier`, never a string literal
- koin-start         Koin is started with `KoinModules`
- no-android-view-model  no `AndroidViewModel`
- acronym-naming     an acronym is an ordinary word in a camel case name: `IosSdkManager`, not `iOSSDKManager`
                     (docs/app-conventions.md#naming)

A declaration can be exempted from `acronym-naming` with `@Suppress("AcronymNaming")` on its line or the one before.
Tests are checked for `no-android-view-model` and `acronym-naming` only.
"""

import os
import re
import sys
from pathlib import Path

SKIPPED_FOLDERS = {"build", ".gradle", ".git", "node_modules", ".idea", "out"}
DECLARATION_START = re.compile(
    r"^(?:(?:public|private|internal|protected|data|sealed|enum|abstract|open|inline|annotation|expect|actual|suspend|"
    r"operator|lateinit|const|override|fun|val|var|object|class|interface|typealias|companion)\b)")
BINDINGS = {"single", "factory", "scoped", "viewModel", "singleOf", "factoryOf", "scopedOf", "viewModelOf"}
GET_CALLS = {"get", "getOrNull"}
CONTROL_FLOW = re.compile(r"\b(if|else|when|for|while|return|try|catch|throw|object|fun|val|var)\b")
OPERATORS = re.compile(r"&&|\|\||\?:|==|!=|<=|>=|\?\.|!!|[+*/%!]|(?<![-=])-(?!>)")
NUMBER = re.compile(r"(?<![\w.])\d")


class Violation:
    def __init__(self, path, line, rule, message):
        self.path, self.line, self.rule, self.message = path, line, rule, message

    def __repr__(self):
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def sanitize(text):
    """[text] with the comments and the contents of the strings and chars replaced by spaces, newlines and quotes kept, so
    that a position and a line number mean the same in both."""
    out, i, n = [], 0, len(text)

    def blank(chunk):
        return "".join(c if c == "\n" else " " for c in chunk)

    while i < n:
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(blank(text[i:j]))
            i = j
        elif two == "/*":
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            out.append(blank(text[i:j]))
            i = j
        elif text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j == -1 else j + 3
            out.append('"' + blank(text[i + 1:j - 1]) + '"')
            i = j
        elif text[i] in "\"'":
            quote, j = text[i], i + 1
            while j < n and text[j] != quote and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(quote + blank(text[i + 1:j - 1]) + quote)
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def kotlin_files(root):
    root = Path(root)
    found = []
    for folder, folders, files in os.walk(root):
        folders[:] = [f for f in folders if f not in SKIPPED_FOLDERS]
        found += [Path(folder) / f for f in files if f.endswith(".kt")]
    return sorted(found)


def is_test(path):
    return any(part in {"test", "androidTest"} or part.endswith("Test") for part in path.parts[:-1])


def in_di_folder(path):
    return path.parent.name == "di"


def matching(text, open_index):
    """The index of the bracket that closes the one at [open_index], or -1."""
    pairs = {"{": "}", "(": ")", "[": "]"}
    opener, closer, depth = text[open_index], pairs[text[open_index]], 0
    for i in range(open_index, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return i
    return -1


def top_level_declarations(clean):
    """The (line, header) of every declaration at the top level of the sanitized file [clean]."""
    found, depth = [], 0
    for number, line in enumerate(clean.splitlines(), 1):
        stripped = line.strip()
        if depth == 0 and stripped and not stripped.startswith(("package ", "import ")):
            stripped = re.sub(r"^(@[\w.:]+(\([^)]*\))?\s*)+", "", stripped)
            if stripped and DECLARATION_START.match(stripped):
                found.append((number, stripped))
        depth += sum(line.count(c) for c in "{(") - sum(line.count(c) for c in "})")
    return found


def package_of(clean):
    match = re.search(r"^\s*package\s+([\w.]+)", clean, re.M)
    return match.group(1) if match else ""


def file_rules(path, clean):
    """koin-modules-file: `KoinModules.kt` and `KoinQualifier.kt` hold only their object, in a `di` package."""
    found = []
    for name in ("KoinModules", "KoinQualifier"):
        declared = re.search(rf"\bobject\s+{name}\b", clean)
        if path.name == f"{name}.kt":
            declarations = top_level_declarations(clean)
            if len(declarations) != 1 or not re.match(rf"(public\s+)?object\s+{name}\b", declarations[0][1]):
                extra = [d for d in declarations if not re.match(rf"(public\s+)?object\s+{name}\b", d[1])] or declarations
                line = extra[0][0] if extra else 1
                found.append(Violation(path, line, "koin-modules-file",
                                       f"{name}.kt holds the `object {name}` and nothing else: no other top-level declaration "
                                       f"(a qualifier name goes in `object KoinQualifier`, any other object in a file of its own)"))
            if not package_of(clean).endswith(".di"):
                found.append(Violation(path, 1, "koin-modules-file", f"{name} is in the package `<app package>.di`"))
        elif declared:
            found.append(Violation(path, line_of(clean, declared.start()), "koin-modules-file",
                                   f"`object {name}` is the only thing in a file named {name}.kt"))
    wrong = re.search(r"\bobject\s+(KoinModule|KoinQualifiers)\b", clean)
    if wrong:
        right = "KoinModules" if wrong.group(1) == "KoinModule" else "KoinQualifier"
        found.append(Violation(path, line_of(clean, wrong.start()), "koin-modules-file",
                               f"`{wrong.group(1)}` is called `{right}`"))
    return found


def enclosing_headers(clean, index):
    """The text before each `{` that is still open at [index], outermost first."""
    stack = []
    for i in range(index):
        if clean[i] == "{":
            start = max(clean.rfind("\n", 0, i), clean.rfind("{", 0, i), clean.rfind("}", 0, i), clean.rfind(";", 0, i))
            stack.append(clean[start + 1:i])
        elif clean[i] == "}" and stack:
            stack.pop()
    return stack


def module_blocks(clean):
    """(index of the `{`, index of its `}`) of every `module { }` call of the sanitized file."""
    blocks = []
    for match in re.finditer(r"\bmodule\s*\{", clean):
        open_index = match.end() - 1
        close = matching(clean, open_index)
        if close != -1:
            blocks.append((open_index, close))
    return blocks


def statements(body, offset):
    """The (index, text) of each statement of a module body: a binding that may span several lines."""
    found, start, depth = [], None, 0
    index = 0
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if start is None and stripped:
            start = offset + index + (len(line) - len(line.lstrip()))
            text = ""
        if start is not None:
            text += line
            depth += sum(line.count(c) for c in "{(") - sum(line.count(c) for c in "})")
            if depth <= 0:
                found.append((start, text.strip()))
                start, depth = None, 0
        index += len(line)
    if start is not None:
        found.append((start, text.strip()))
    return found


def strip_generics(text):
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"<[^<>]*>", "", text)
    return text


def wiring_problems(statement):
    """What makes a binding [statement] more than wiring, as short phrases."""
    callee = re.match(r"\w+", statement)
    if not callee or callee.group() not in BINDINGS:
        return [f"`{statement.splitlines()[0][:50]}` is not a binding (single, factory, viewModel, singleOf, ...)"]
    text = strip_generics(statement)
    text = re.sub(r"\{\s*\(?[\w\s,:?]*\)?\s*->", "{", text)   # the parameters of a definition: { (id: String) -> ... }
    text = text.replace("->", " ").replace("::", " ")
    problems = []
    if '"' in text or "'" in text:
        problems.append("a literal (a string): a name or a setting belongs in the factory or in `KoinQualifier`")
    if NUMBER.search(text):
        problems.append("a number: a setting belongs in the factory")
    if text.count("{") > 1:
        problems.append("a block inside the binding (a builder or a DSL): move it into a factory the binding calls")
    if CONTROL_FLOW.search(text):
        problems.append("logic (if, when, val, ...): move it into a factory")
    if OPERATORS.search(text):
        problems.append("an operator: move the expression into a factory")
    for i, char in enumerate(text):
        if char == ")" and re.match(r"\s*\.\s*\w", text[i + 1:]):
            opener = text.rfind("(", 0, i)
            depth = 0
            for j in range(i, -1, -1):
                depth += (text[j] == ")") - (text[j] == "(")
                if depth == 0:
                    opener = j
                    break
            name = re.search(r"(\w+)\s*$", text[:opener])
            if not name or name.group(1) not in GET_CALLS:
                problems.append("chained calls (`a(...).b(...)`, or a value read from the context): move the chain into a factory")
                break
    return problems


def koin_rules(path, clean):
    """module-in-object, koin-wiring-only, koin-qualifier and koin-start for one file that is not a test."""
    found = []
    for open_index, close_index in module_blocks(clean):
        line = line_of(clean, open_index)
        if not in_di_folder(path):
            found.append(Violation(path, line, "module-in-object", "a Koin module is declared in the `di` folder, in "
                                   "`KoinModules` or an object that it uses"))
        elif not any(re.search(r"\bobject\b", h) for h in enclosing_headers(clean, open_index)):
            found.append(Violation(path, line, "module-in-object", "a Koin module is declared in an object (`KoinModules`, "
                                   "or a feature object it uses), never at the top level"))
        body = clean[open_index + 1:close_index]
        for index, statement in statements(body, open_index + 1):
            for problem in wiring_problems(statement):
                found.append(Violation(path, line_of(clean, index), "koin-wiring-only", f"a Koin module only wires, but this has {problem}"))
    if path.name != "KoinQualifier.kt":
        for match in re.finditer(r"\bnamed\s*\(\s*\"", clean):
            found.append(Violation(path, line_of(clean, match.start()), "koin-qualifier",
                                   "a qualifier is a constant of `KoinQualifier`, not a string literal"))
    if not in_di_folder(path):
        for match in re.finditer(r"\bmodules\s*\(([^)]*)\)", clean):
            if "KoinModules" not in match.group(1):
                found.append(Violation(path, line_of(clean, match.start()), "koin-start",
                                       "Koin is started with `modules(KoinModules.modules)`"))
    return found


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
            found.append(Violation(path, 1, "acronym-naming", f"file name `{path.name}`: write `{lower_acronyms(part)}` "
                                   "(an acronym is an ordinary word in a camel case name)"))
    seen = set()
    for pattern in DECLARATIONS:
        for match in pattern.finditer(clean):
            name, line = match.group(1), line_of(clean, match.start(1))
            if (name, line) in seen or not acronym_problem(name):
                continue
            before = clean[clean.rfind("\n", 0, match.start()) + 1:match.start()]
            if re.search(r"\boverride\b", before):
                continue
            nearby = raw_lines[max(line - 2, 0):line]
            if any("AcronymNaming" in text for text in nearby):
                continue
            seen.add((name, line))
            found.append(Violation(path, line, "acronym-naming", f"`{name}`: an acronym is an ordinary word in a camel case "
                                   f"name, e.g. `{lower_acronyms(name)}` (docs/app-conventions.md#naming)"))
    return found


def check(root):
    """Every violation of the app at [root], as Violations with paths relative to it."""
    root = Path(root)
    found, uses_koin, has_modules = [], False, False
    for path in kotlin_files(root):
        raw = path.read_text(errors="replace")
        clean = sanitize(raw)
        relative = path.relative_to(root)
        part = []
        if "org.koin" in raw:
            uses_koin = True
        if path.name == "KoinModules.kt":
            has_modules = True
        for match in re.finditer(r"\bAndroidViewModel\b", clean):
            part.append(Violation(relative, line_of(clean, match.start()), "no-android-view-model",
                                  "`AndroidViewModel` is banned: extend `ViewModel` and take the dependencies as constructor parameters"))
        part += acronym_rule(relative, raw, clean)
        if not is_test(relative):
            part += file_rules(relative, clean)
            part += koin_rules(relative, clean)
        found += part
    if not uses_koin:
        found.append(Violation(Path("."), 1, "koin-required", "the app does not use Koin: every app does (docs/new-app.md)"))
    elif not has_modules:
        found.append(Violation(Path("."), 1, "koin-required", "no KoinModules.kt: all the Koin modules live in `object KoinModules`"))
    return sorted(found, key=lambda v: (str(v.path), v.line, v.rule))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    violations = check(root)
    on_github = os.environ.get("GITHUB_ACTIONS") == "true"
    for v in violations:
        if on_github:
            print(f"::error file={v.path},line={v.line},title={v.rule}::{v.message}")
        else:
            print(v)
    if violations:
        print(f"\n{len(violations)} violation(s) of the conventions (docs/conventions-check.md)")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
