"""DI-1..6: Koin is in every app, its modules live in `object KoinModules` and only wire (docs/new-app.md, docs/app-shell.md)."""

import re

from . import scan as k
from .violation import Violation

RULES = {
    "DI-1": "The app uses Koin and has a KoinModules.kt",
    "DI-2": "KoinModules.kt and KoinQualifier.kt hold only their object, in a `di` package, and are named so",
    "DI-3": "A Koin module is declared in an object of a file in a `di` folder, never at the top level",
    "DI-4": "A Koin binding only wires: get(), androidContext(), runtime parameters and names, no literals, blocks, operators or chains",
    "DI-5": "A Koin qualifier is a constant of KoinQualifier, never a string literal",
    "DI-6": "Koin is started with KoinModules",
}

DECLARATION_START = re.compile(
    r"^(?:(?:public|private|internal|protected|data|sealed|enum|abstract|open|inline|annotation|expect|actual|suspend|"
    r"operator|lateinit|const|override|fun|val|var|object|class|interface|typealias|companion)\b)")
BINDINGS = {"single", "factory", "scoped", "viewModel", "singleOf", "factoryOf", "scopedOf", "viewModelOf"}
GET_CALLS = {"get", "getOrNull"}
CONTROL_FLOW = re.compile(r"\b(if|else|when|for|while|return|try|catch|throw|object|fun|val|var)\b")
OPERATORS = re.compile(r"&&|\|\||\?:|==|!=|<=|>=|\?\.|!!|[+*/%!]|(?<![-=])-(?!>)")
NUMBER = re.compile(r"(?<![\w.])\d")


def matching(text, open_index):
    """The index of the bracket that closes the one at [open_index], or -1."""
    close = k.balanced(text, open_index)
    return -1 if close == len(text) else close


def in_di_folder(path):
    return path.parent.name == "di"


def package_of(clean):
    match = re.search(r"^\s*package\s+([\w.]+)", clean, re.M)
    return match.group(1) if match else ""


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
                found.append(Violation(path, line, "DI-2",
                                       f"{name}.kt holds the `object {name}` and nothing else: no other top-level declaration "
                                       f"(a qualifier name goes in `object KoinQualifier`, any other object in a file of its own)"))
            if not package_of(clean).endswith(".di"):
                found.append(Violation(path, 1, "DI-2", f"{name} is in the package `<app package>.di`"))
        elif declared:
            found.append(Violation(path, k.line_of(clean, declared.start()), "DI-2",
                                   f"`object {name}` is the only thing in a file named {name}.kt"))
    wrong = re.search(r"\bobject\s+(KoinModule|KoinQualifiers)\b", clean)
    if wrong:
        right = "KoinModules" if wrong.group(1) == "KoinModule" else "KoinQualifier"
        found.append(Violation(path, k.line_of(clean, wrong.start()), "DI-2",
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
        line = k.line_of(clean, open_index)
        if not in_di_folder(path):
            found.append(Violation(path, line, "DI-3", "a Koin module is declared in the `di` folder, in "
                                   "`KoinModules` or an object that it uses"))
        elif not any(re.search(r"\bobject\b", h) for h in enclosing_headers(clean, open_index)):
            found.append(Violation(path, line, "DI-3", "a Koin module is declared in an object (`KoinModules`, "
                                   "or a feature object it uses), never at the top level"))
        body = clean[open_index + 1:close_index]
        for index, statement in statements(body, open_index + 1):
            for problem in wiring_problems(statement):
                found.append(Violation(path, k.line_of(clean, index), "DI-4", f"a Koin module only wires, but this has {problem}"))
    if path.name != "KoinQualifier.kt":
        for match in re.finditer(r"\bnamed\s*\(\s*\"", clean):
            found.append(Violation(path, k.line_of(clean, match.start()), "DI-5",
                                   "a qualifier is a constant of `KoinQualifier`, not a string literal"))
    if not in_di_folder(path):
        for match in re.finditer(r"\bmodules\s*\(([^)]*)\)", clean):
            if "KoinModules" not in match.group(1):
                found.append(Violation(path, k.line_of(clean, match.start()), "DI-6",
                                       "Koin is started with `modules(KoinModules.modules)`"))
    return found


def check(ctx):
    uses_koin, has_modules = False, False
    for f in ctx.all_files:
        if "org.koin" in f.raw:
            uses_koin = True
        if f.rel.name == "KoinModules.kt":
            has_modules = True
        if not f.is_test:
            ctx.violations += file_rules(f.rel, f.clean) + koin_rules(f.rel, f.clean)
    if not uses_koin:
        ctx.add_path(".", 1, "DI-1", "the app does not use Koin: every app does (docs/new-app.md)")
    elif not has_modules:
        ctx.add_path(".", 1, "DI-1", "no KoinModules.kt: all the Koin modules live in `object KoinModules`")
