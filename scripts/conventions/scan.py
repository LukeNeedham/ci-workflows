"""A small Kotlin scanner for the conventions check (check_conventions.py): just enough of the language to find the top-level declarations of a file.

It is not a parser. [blank] turns comments and the inside of strings into spaces (keeping every offset and line), and
[parse] reads the declarations at the top level of a file, with their modifiers, annotations and text, from what is
left. Offsets into the cleaned text are offsets into the original, so a line number is the same in both.
"""

import re
from dataclasses import dataclass, field

OPENERS = {"{": "}", "(": ")", "[": "]"}
CLOSERS = set(OPENERS.values())
CHAR_LITERAL = re.compile(r"'(?:\\u[0-9a-fA-F]{4}|\\.|[^\\'])'")
MODIFIERS = (
    "public|private|internal|protected|abstract|open|sealed|data|enum|annotation|inline|value|fun|suspend|operator|"
    "infix|tailrec|external|const|lateinit|override|expect|actual|final|noinline|crossinline|vararg"
)
DECLARATION = re.compile(
    r"^[ \t]*(?P<ann>(?:@[\w.:]+(?:\s*\(\s*\))?\s*)*)(?P<mods>(?:\b(?:" + MODIFIERS + r")\s+)*)"
    r"\b(?P<kw>fun|class|interface|object|val|var|typealias)\b(?P<rest>[^\n]*)",
    re.M,
)
ANNOTATION = re.compile(r"@([\w.:]+)")
TYPE_KINDS = ("class", "interface", "object")


def blank(text):
    """[text] with the comments and the inside of the strings and character literals replaced by spaces (newlines are
    kept, and so is every offset). The quotes stay, so a string is still there to be seen."""
    return _scan(text)[0]


def comment_spans(text):
    """The (start, end) of every comment in [text]."""
    return _scan(text)[1]


def _scan(text):
    out = list(text)
    comments = []
    n = len(text)

    def erase(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    def string_end(i):
        """The index just past the string whose opening quote is at [i]."""
        if text.startswith('"""', i):
            end = text.find('"""', i + 3)
            if end < 0:
                return n
            while text.startswith('"', end + 3):  # """a"""" ends at the last three quotes
                end += 1
            return end + 3
        j = i + 1
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
            elif c == '"':
                return j + 1
            elif text.startswith("${", j):
                j = template_end(j + 2)
            else:
                j += 1
        return n

    def template_end(j):
        """The index just past the `}` of a string template whose code starts at [j]."""
        depth = 1
        while j < n and depth:
            c = text[j]
            if c == '"':
                j = string_end(j)
                continue
            depth += (c == "{") - (c == "}")
            j += 1
        return j

    i = 0
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            erase(i, end)
            comments.append((i, end))
            i = end
        elif text.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            erase(i, j)
            comments.append((i, j))
            i = j
        elif c == '"':
            end = string_end(i)
            quote = 3 if text.startswith('"""', i) else 1
            erase(i + quote, max(i + quote, end - quote))
            i = end
        elif c == "'":
            m = CHAR_LITERAL.match(text, i)
            if m:
                erase(i + 1, m.end() - 1)
                i = m.end()
            else:
                i += 1
        else:
            i += 1
    return "".join(out), comments


def skeleton(clean):
    """[clean] with everything inside brackets blanked: only the top level of the file is left, positions unchanged."""
    out = list(clean)
    depth = 0
    for i, c in enumerate(clean):
        if c in OPENERS:
            depth += 1
        elif c in CLOSERS:
            depth = max(0, depth - 1)
        elif depth and c != "\n":
            out[i] = " "
    return "".join(out)


def balanced(text, i):
    """The index of the bracket that closes the one at [i] in [text] (len(text) when it never closes)."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] in OPENERS:
            depth += 1
        elif text[j] in CLOSERS:
            depth -= 1
            if depth == 0:
                return j
    return len(text)


def line_of(text, offset):
    """The 1-based line of [offset] in [text]."""
    return text.count("\n", 0, offset) + 1


@dataclass
class Declaration:
    kind: str  # fun, class, interface, object, val, var or typealias
    name: str
    mods: set
    annotations: list
    start: int  # first character (the first annotation, if any)
    keyword: int  # the keyword
    end: int  # where the next declaration starts
    line: int  # of the keyword
    first_line: int  # of the first annotation
    text: str = ""  # cleaned text from the keyword to the end
    params: str = ""  # the cleaned text between the parentheses after the name ("" for none)
    supertypes: str = ""  # the cleaned text of a class's supertypes
    raw: str = field(default="", repr=False)  # the original text, from the keyword to the end

    def has(self, annotation):
        return annotation in self.annotations

    @property
    def is_private(self):
        return "private" in self.mods

    @property
    def is_composable(self):
        return self.kind == "fun" and "Composable" in self.annotations

    @property
    def is_preview(self):
        return self.kind == "fun" and any(a.startswith("Preview") for a in self.annotations)

    @property
    def is_type(self):
        return self.kind in TYPE_KINDS


def _name_and_params(kind, clean, flat, keyword, end):
    """(name, params, supertypes) of the declaration whose keyword starts at [keyword]."""
    rest_start = keyword + len(kind)
    header_end = flat.find("{", rest_start, end)
    header_end = end if header_end < 0 else header_end
    header = flat[rest_start:header_end]
    params, supertypes = "", ""
    if kind == "fun":
        before_paren = header.split("(", 1)[0]
        words = re.findall(r"\w+", before_paren)
        paren = flat.find("(", rest_start, header_end)
        if paren >= 0:
            params = clean[paren + 1:balanced(clean, paren)]
        return (words[-1] if words else ""), params, supertypes
    if kind in ("val", "var", "typealias"):
        words = re.findall(r"\w+", re.split(r"[:=]", header, maxsplit=1)[0])
        return (words[-1] if words else ""), params, supertypes
    m = re.match(r"\s*(\w+)", header)
    if not m:
        return "", params, supertypes
    name, i = m.group(1), m.end()
    if header[i:].lstrip().startswith("<"):  # type parameters: skip to the matching >
        i += header[i:].index("<")
        depth = 0
        while i < len(header):
            depth += (header[i] == "<") - (header[i] == ">")
            i += 1
            if depth == 0:
                break
    constructor = re.match(r"\s*(?:(?:private|internal|protected|public)\s+)?(?:constructor\s*)?\(", header[i:])
    if constructor and kind == "class":
        paren = rest_start + i + constructor.end() - 1
        close = balanced(clean, paren)
        params = clean[paren + 1:close]
        i = close + 1 - rest_start
    tail = header[i:]
    colon = tail.find(":")
    if colon >= 0:
        supertypes = clean[rest_start + i + colon + 1:header_end]
    return name, params, supertypes


def parse(raw):
    """(cleaned text, top-level declarations) of the Kotlin source [raw]."""
    clean = blank(raw)
    flat = skeleton(clean)
    matches = list(DECLARATION.finditer(flat))
    declarations = []
    for index, m in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        kind, keyword = m.group("kw"), m.start("kw")
        name, params, supertypes = _name_and_params(kind, clean, flat, keyword, end)
        declarations.append(Declaration(
            kind=kind,
            name=name,
            mods=set(m.group("mods").split()),
            annotations=[a.split(":")[-1].split(".")[-1] for a in ANNOTATION.findall(m.group("ann"))],
            start=m.start("ann") if m.group("ann") else keyword,
            keyword=keyword,
            end=end,
            line=line_of(clean, keyword),
            first_line=line_of(clean, m.start("ann") if m.group("ann") else keyword),
            text=clean[keyword:end],
            params=params,
            supertypes=supertypes,
            raw=raw[keyword:end],
        ))
    return clean, declarations
