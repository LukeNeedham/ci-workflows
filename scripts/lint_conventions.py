#!/usr/bin/env python3
"""Checks an app's Kotlin sources against the page, ViewModel, UiState and preview rules (docs/lint.md).

    python3 lint_conventions.py [APP_DIR]

Run by the `conventions` job of android_pr.yml in every app. It reads the sources with no Gradle and no JDK, prints an
error annotation for each violation (file, line, rule id) and a summary, and exits 1 if there is any. A violation is
silenced where it really is the exception with a comment on its line or the line above, and a reason is required:

    // lint:ignore PRV-7: only wraps a platform view, there is nothing to show
"""

import argparse
import bisect
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
import check_screenshot_package as shots  # noqa: E402
import kotlin_scan as k  # noqa: E402

RULES = {
    "PAGE-1": "XPage, XPageContent, XViewModel and XUiState are each in their own file, named after them",
    "PAGE-2": "Every XPage has an XPageContent in its package, and the reverse",
    "PAGE-3": "XPage is public, XPageContent is internal",
    "PAGE-4": "No XScreen, XScreenContent, XView or XContent for a page, no XPageViewModel or XScreenViewModel",
    "PAGE-5": "XPage calls XPageContent once and draws no UI of its own, with no preview",
    "PAGE-6": "XPageContent is stateless: no ViewModel, Koin, Flow, repository or navigator, and it takes the XUiState",
    "VM-1": "A ViewModel is requested only in XPage, and only as XViewModel",
    "VM-2": "A ViewModel is requested by one page only",
    "VM-3": "No ViewModel is scoped to the activity, a navigation graph or a parent",
    "VM-4": "A ViewModel is never a Koin single, factory or scoped definition",
    "VM-5": "A ViewModel holds no other ViewModel",
    "VM-6": "A ViewModel is named XViewModel and belongs to an XPage in its package",
    "VM-7": "A ViewModel declares no SharedFlow: one-off events go through a Channel",
    "UI-1": "An XUiState belongs to an XPage in its package",
    "UI-2": "An XUiState is immutable",
    "UI-3": "An XUiState holds no Flow or Channel",
    "PRV-1": "Every XPageContent has a private @Preview named Preview in its file",
    "PRV-2": "A preview is private and named Preview or Preview<Variant>, once per file",
    "PRV-3": "A preview is in the file of the composable it previews",
    "PRV-4": "A preview is wrapped in AppTheme",
    "PRV-5": "A preview needs no ViewModel, Koin, Flow collection or network",
    "PRV-6": "Only the screenshot package has screenshots, and every preview in it ends in Screenshot",
    "PRV-7": "A composable of 10 lines or more has a preview in its file",
    "CMP-1": "One public composable per file, named after the file",
    "SHOT-1": "A file of the screenshot package holds only private @Preview composables with their own data",
    "SHOT-2": "The screenshot package has an order.txt that lists every screenshot once",
    "IGNORE-1": "A lint:ignore names a rule of this list and gives a reason",
}

SKIP_DIRS = {"build", ".gradle", ".git", ".idea", "node_modules"}
MIN_PREVIEW_LINES = 10
PAGE_CONTENT, PAGE, VIEW_MODEL, UI_STATE = "PageContent", "Page", "ViewModel", "UiState"
SUFFIX_OF_ROLE = {PAGE_CONTENT: "PageContent", PAGE: "Page", VIEW_MODEL: "ViewModel", UI_STATE: "UiState"}
ROLE_FILE = re.compile(r".+(PageContent|Page|ViewModel|UiState)$")
FORBIDDEN_PAGE_IMPORTS = ("androidx.compose.foundation", "androidx.compose.material")
# What XPageContent never touches: (pattern, what it is)
STATEFUL = [
    (r"(?i)\b\w*viewmodel\w*\b", "a ViewModel"),
    (r"(?i)\b\w*koin\w*\b", "Koin"),
    (r"\b\w*Flow\b|\bcollectAs\w*\b", "a Flow"),
    (r"\b(?:NavController|NavHostController|NavBackStack|Navigator|backStack)\b", "the navigation"),
    (r"\b\w*Repository\b", "a repository"),
]
PREVIEW_FORBIDDEN = [(p, w) for p, w in STATEFUL if w in ("a ViewModel", "Koin")] + [
    (r"\bcollectAs\w*\b|\.collect\b", "a Flow collection"),
]
LOOKUPS = (
    "koinViewModel|koinNavViewModel|koinActivityViewModel|getViewModel|hiltViewModel|sharedKoinViewModel|sharedViewModel|"
    "activityViewModels|activityViewModel|viewModels|viewModel"
)
LOOKUP = re.compile(r"(?<!\w)(" + LOOKUPS + r")\s*(?:<\s*([\w.]+)\s*>)?\s*([({])")
LAMBDA_LOOKUPS = {"koinViewModel", "koinNavViewModel", "koinActivityViewModel", "sharedKoinViewModel", "getViewModel"}
LOCAL_FUNCTION = re.compile(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.<>?]+\.)?(\w+)\s*\(")
SCOPED_LOOKUPS = {"activityViewModel", "activityViewModels", "koinActivityViewModel", "sharedViewModel", "sharedKoinViewModel"}
OWNER_WORDS = re.compile(r"Owner|Entry|Activity|activity|NavGraph|BackStack|backStack")
OWNER_STANDALONE = re.compile(r"\bviewModelStoreOwner\s*=|\bLocalViewModelStoreOwner\b|\bownerProducer\b")
DEFINITION = re.compile(r"(?<![\w.])(single|singleOf|factory|factoryOf|scoped|scopedOf)\b")
DECLARED_TYPE = re.compile(r":\s*([\w.]+)\s*(?:=|by)\s*$")
FUN_BEFORE = re.compile(r"\bfun\s*(?:<[^>]*>\s*)?(?:[\w.<>?]+\.)?$")
PACKAGE = re.compile(r"^\s*package\s+([\w.]+)", re.M)
IMPORT = re.compile(r"^\s*import\s+([\w.*]+)", re.M)
IGNORE = re.compile(r"//\s*lint:ignore\s+([A-Z]+-\d+)\s*(?::\s*(\S.*))?")


@dataclass
class Violation:
    path: str
    line: int
    rule: str
    message: str
    anchor: int = 0  # the first line a lint:ignore may sit above

    def __post_init__(self):
        self.anchor = self.anchor or self.line


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
        self.starts = [d.start for d in self.decls]

    def in_comment(self, offset):
        return any(a <= offset < b for a, b in self.comments)

    def decl_at(self, offset):
        i = bisect.bisect_right(self.starts, offset) - 1
        return self.decls[i] if i >= 0 and offset < self.decls[i].end else None


def source_files(app_dir):
    """The Kotlin files of the app, relative to [app_dir]: those of every source set but the test ones."""
    found = []
    for folder, dirs, names in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if not name.endswith(".kt"):
                continue
            rel = (Path(folder) / name).relative_to(app_dir)
            parts = rel.parts
            if "src" not in parts[:-1]:
                continue
            source_set = parts[parts.index("src") + 1] if parts.index("src") + 1 < len(parts) - 1 else ""
            if "test" not in source_set.lower():
                found.append(rel)
    return sorted(found)


def role(d):
    """Which of the four files of a page the declaration [d] is, or None."""
    if d.is_composable and not d.is_preview:
        if d.name.endswith("PageContent") and len(d.name) > len("PageContent"):
            return PAGE_CONTENT
        if d.name.endswith("Page") and len(d.name) > len("Page"):
            return PAGE
    if d.kind == "class" and d.name.endswith("ViewModel") and len(d.name) > len("ViewModel"):
        return VIEW_MODEL
    if d.is_type and d.name.endswith("UiState") and len(d.name) > len("UiState"):
        return UI_STATE
    return None


def page_of(d):
    """The X of an XPage, XPageContent, XViewModel or XUiState."""
    return d.name[:-len(SUFFIX_OF_ROLE[role(d)])]


def returns_value(d):
    """Whether the function [d] returns something (`remember…`, a state holder): there is nothing in it to preview."""
    open_paren = d.text.find("(")
    if open_paren < 0:
        return False
    close = k.balanced(d.text, open_paren)
    return re.match(r"\s*:\s*\w", d.text[close + 1:]) is not None


def is_viewmodel(d):
    return d.kind == "class" and re.search(r"\b\w*ViewModel\b", d.supertypes) is not None


class Lint:
    def __init__(self, app_dir):
        self.app_dir = Path(app_dir)
        self.files = [SourceFile(self.app_dir, rel) for rel in source_files(self.app_dir)]
        self.violations = []
        self.by_role = defaultdict(dict)  # role -> {(package, X): (file, declaration)}
        for f in self.files:
            if f.is_screenshot:
                continue
            for d in f.decls:
                if role(d):
                    self.by_role[role(d)].setdefault((f.package, page_of(d)), (f, d))
        self.known = {x for pairs in self.by_role.values() for (_, x) in pairs}

    def add(self, f, line, rule, message, anchor=None):
        self.violations.append(Violation(f.path, line, rule, message, anchor or line))

    def at(self, f, d, rule, message):
        self.add(f, d.line, rule, message, d.first_line)

    def has(self, kind, f, x):
        return (f.package, x) in self.by_role[kind]

    # ---- pages ----

    def check_files(self):
        for f in self.files:
            if f.is_screenshot:
                continue
            owner = None
            for d in f.decls:
                if role(d) and d.name != f.stem:
                    self.at(f, d, "PAGE-1", f"`{d.name}` is in {f.rel.name}: each of XPage, XPageContent, XViewModel and "
                                            f"XUiState is in its own file, named after it (`{d.name}.kt`)")
                elif role(d):
                    owner = d
            if owner:
                for d in f.decls:
                    if d is not owner and not d.is_private and not d.is_preview:  # a public preview is PRV-2's
                        self.at(f, d, "PAGE-1", f"`{d.name}` is in {f.rel.name}, the file of `{owner.name}`, which holds only "
                                                f"what its name says: move it to its own file (or make it private)")
            elif ROLE_FILE.match(f.stem) and not any(d.name == f.stem for d in f.decls):
                self.add(f, 1, "PAGE-1", f"{f.rel.name} does not declare `{f.stem}`: a file named after a page, ViewModel or "
                                         f"state holds that one declaration")

    def check_pairs(self):
        for (package, x), (f, d) in self.by_role[PAGE].items():
            if (package, x) not in self.by_role[PAGE_CONTENT]:
                self.at(f, d, "PAGE-2", f"`{d.name}` has no `{x}PageContent` in the package `{package}`")
        for (package, x), (f, d) in self.by_role[PAGE_CONTENT].items():
            if (package, x) not in self.by_role[PAGE]:
                self.at(f, d, "PAGE-2", f"`{d.name}` has no `{x}Page` in the package `{package}`")

    def check_visibility(self):
        for f, d in self.by_role[PAGE].values():
            if d.mods & {"private", "internal", "protected"}:
                self.at(f, d, "PAGE-3", f"`{d.name}` is public: the navigation calls it")
        for f, d in self.by_role[PAGE_CONTENT].values():
            if "internal" not in d.mods:
                self.at(f, d, "PAGE-3", f"`{d.name}` is `internal` (not public, not private): the screenshots of the app use it")

    def check_names(self):
        for f in self.files:
            if f.is_screenshot:
                continue
            for d in f.decls:
                if d.is_composable and not role(d):
                    n = d.name
                    x = None
                    if n.endswith("ScreenContent") or (n.endswith("Screen") and len(n) > len("Screen")):
                        self.at(f, d, "PAGE-4", f"`{n}`: a page is an `XPage` and an `XPageContent`, never a `Screen`")
                    elif n.endswith("View") and len(n) > 4:
                        x = n[:-4]
                    elif n.endswith("Content") and len(n) > len("Content"):
                        x = n[:-7]
                    if x and x in self.known:
                        self.at(f, d, "PAGE-4", f"`{n}` is the content of the page `{x}`: name it `{x}PageContent`")
                elif is_viewmodel(d) and re.search(r"(Page|Screen)ViewModel$", d.name):
                    suffix = re.search(r"(Page|Screen)ViewModel$", d.name).group()
                    self.at(f, d, "PAGE-4", f"`{d.name}`: the ViewModel of `{d.name[:-len(suffix)]}Page` is "
                                            f"`{d.name[:-len(suffix)]}ViewModel`")

    def check_page_body(self):
        for f, d in self.by_role[PAGE].values():
            x = page_of(d)
            calls = len(re.findall(rf"\b{x}PageContent\s*\(", d.text))
            if calls != 1:
                self.at(f, d, "PAGE-5", f"`{d.name}` calls `{x}PageContent` {calls} times: it calls it exactly once and "
                                        f"draws nothing itself")
            if any(p.is_preview for p in f.decls):
                self.at(f, d, "PAGE-5", f"`{f.rel.name}` has a @Preview: `{d.name}` needs Koin and a ViewModel, so only "
                                        f"`{x}PageContent` has previews")
            ui = [(line, name) for line, name in f.imports if name.startswith(FORBIDDEN_PAGE_IMPORTS)]
            if ui:
                shown = ", ".join(f"`{name}`" for _, name in ui[:3]) + (f" and {len(ui) - 3} more" if len(ui) > 3 else "")
                self.add(f, ui[0][0], "PAGE-5", f"`{d.name}` draws no UI of its own, so it does not import {shown}: "
                                                f"that belongs in `{x}PageContent`")

    def check_page_content(self):
        for f, d in self.by_role[PAGE_CONTENT].values():
            x = page_of(d)
            for pattern, what in STATEFUL:
                m = re.search(pattern, d.text)
                if m:
                    self.add(f, k.line_of(f.clean, d.keyword + m.start()), "PAGE-6",
                             f"`{d.name}` is stateless but touches {what} (`{m.group().strip()}`): that goes up into `{x}Page`",
                             d.first_line)
            if (f.package, x) in self.by_role[UI_STATE] and not re.search(rf"\b{x}UiState\b", d.params):
                self.at(f, d, "PAGE-6", f"`{d.name}` takes the `{x}UiState` as its state")

    # ---- ViewModels ----

    def lookups(self, f):
        """(call, name, type, arguments, enclosing declaration) of every request for a ViewModel in [f]."""
        found = []
        own = set(LOCAL_FUNCTION.findall(f.clean))  # a function of this file that happens to be called like a lookup
        for m in LOOKUP.finditer(f.clean):
            if FUN_BEFORE.search(f.clean[max(0, m.start() - 60):m.start()]) or m.group(1) in own:
                continue
            paren = m.end() - 1
            if m.group(3) == "{" and m.group(1) not in LAMBDA_LOOKUPS:
                continue  # viewModel<T> { … }: a definition of the Koin module
            close = k.balanced(f.clean, paren)
            if m.group(1) == "viewModel" and f.clean[close + 1:].lstrip().startswith("{"):
                continue  # viewModel(qualifier) { … }: a definition of the Koin module
            type_name = m.group(2)
            if not type_name:
                declared = DECLARED_TYPE.search(f.clean[max(0, m.start() - 80):m.start()])
                type_name = declared.group(1) if declared else None
            found.append((m, m.group(1), type_name, f.clean[paren + 1:close], f.decl_at(m.start())))
        return found

    def check_lookups(self):
        requests = defaultdict(list)  # ViewModel -> [(file, line, requester)]
        for f in self.files:
            reported = set()
            for m, name, type_name, args, enclosing in self.lookups(f):
                line = k.line_of(f.clean, m.start())
                short = type_name.split(".")[-1] if type_name else None
                scoped = name in SCOPED_LOOKUPS or OWNER_WORDS.search(args)
                if scoped:
                    reported.add(line)
                    self.add(f, line, "VM-3", f"`{name}` shares a ViewModel between pages (scoped to the activity, a navigation "
                                              f"graph or a parent): each page has its own, and state pages share goes in a repository")
                page = enclosing if enclosing is not None and role(enclosing) == PAGE else None
                if page is None:
                    self.add(f, line, "VM-1", f"`{name}` requests a ViewModel outside an `XPage`: only the page gets its ViewModel")
                elif short is None:
                    self.add(f, line, "VM-1", f"`{name}` in `{page.name}` needs its type: `{name}<{page_of(page)}ViewModel>()`")
                elif short != f"{page_of(page)}ViewModel":
                    self.add(f, line, "VM-1", f"`{page.name}` requests `{short}`: its ViewModel is `{page_of(page)}ViewModel`")
                if short:
                    requests[short].append((f, line, page.name if page else f"{f.path}"))
            for m in OWNER_STANDALONE.finditer(f.clean):
                line = k.line_of(f.clean, m.start())
                if line not in reported:
                    self.add(f, line, "VM-3", f"`{m.group().strip(' =')}` hands a ViewModel to another owner than its page")
        for type_name, sites in requests.items():
            requesters = sorted({who for _, _, who in sites})
            if len(requesters) > 1:
                for f, line, _ in sites:
                    self.add(f, line, "VM-2", f"`{type_name}` is requested by {', '.join(f'`{r}`' for r in requesters)}: a ViewModel "
                                              f"belongs to one page, so give each its own and share state in a repository")

    def check_definitions(self):
        for f in self.files:
            for m in DEFINITION.finditer(f.clean):
                if FUN_BEFORE.search(f.clean[max(0, m.start() - 60):m.start()]):
                    continue
                i, scope = m.end(), ""
                for _ in range(3):  # <T>, (args) and { … }
                    while i < len(f.clean) and f.clean[i] in " \t\n":
                        i += 1
                    if i < len(f.clean) and f.clean[i] == "<":
                        j = f.clean.find(">", i)
                    elif i < len(f.clean) and f.clean[i] in "({":
                        j = k.balanced(f.clean, i)
                    else:
                        break
                    scope += f.clean[i:j + 1]
                    i = j + 1
                hit = re.search(r"\b[A-Z]\w*ViewModel\b", scope)
                if hit:
                    self.add(f, k.line_of(f.clean, m.start()), "VM-4",
                             f"`{m.group()}` defines `{hit.group()}` as one shared instance: a ViewModel is a `viewModel` or "
                             f"`viewModelOf` definition, created for its page")

    def check_viewmodels(self):
        for f in self.files:
            if f.is_screenshot:
                continue
            for d in f.decls:
                if not is_viewmodel(d):
                    continue
                inherited = set(re.findall(r"\b[A-Z]?\w*ViewModel\b", d.supertypes))
                others = set(re.findall(r"\b[A-Z]\w*ViewModel\b", d.text)) - inherited - {d.name, "ViewModel", "AndroidViewModel"}
                for other in sorted(others):
                    self.at(f, d, "VM-5", f"`{d.name}` holds `{other}`: a ViewModel never holds or calls another, so share "
                                          f"state through a repository")
                m = re.search(r"\b\w*SharedFlow\b|\basSharedFlow\b", d.text)
                if m:
                    self.add(f, k.line_of(f.clean, d.keyword + m.start()), "VM-7",
                             f"`{d.name}` uses `{m.group()}`: a one-off event goes through a `Channel` exposed with "
                             f"`receiveAsFlow()`, so it is never lost or doubled", d.first_line)
                if d.mods & {"abstract", "sealed"} or d.kind != "class":
                    continue
                if re.search(r"(Page|Screen)ViewModel$", d.name):
                    continue  # PAGE-4
                if not role(d):
                    self.at(f, d, "VM-6", f"`{d.name}` is a ViewModel: name it `XViewModel`, for the page `XPage`")
                elif not self.has(PAGE, f, page_of(d)):
                    self.at(f, d, "VM-6", f"`{d.name}` has no `{page_of(d)}Page` in the package `{f.package}`: a ViewModel "
                                          f"belongs to the page it is named after")

    def check_ui_states(self):
        for f, d in self.by_role[UI_STATE].values():
            x = page_of(d)
            if not self.has(PAGE, f, x):
                self.at(f, d, "UI-1", f"`{d.name}` has no `{x}Page` in the package `{f.package}`: a state belongs to the page "
                                      f"it is named after")
            m = re.search(r"\bvar\s+\w+|\b(?:Mutable\w+|mutable\w+Of|ArrayList|HashMap|HashSet|LinkedHashMap)\b", d.text)
            if m:
                self.add(f, k.line_of(f.clean, d.keyword + m.start()), "UI-2",
                         f"`{d.name}` is immutable (`{m.group().strip()}`): `val`s and read-only collections, changed with `copy`", d.first_line)
            m = re.search(r"\b\w*Flow\b|\bChannel\b", d.text)
            if m:
                self.add(f, k.line_of(f.clean, d.keyword + m.start()), "UI-3",
                         f"`{d.name}` is plain data but holds `{m.group()}`: flows and channels belong in the ViewModel", d.first_line)

    # ---- previews and composables ----

    def check_previews(self):
        for f in self.files:
            previews = [d for d in f.decls if d.is_preview]
            composables = [d for d in f.decls if d.is_composable and not d.is_preview]
            counts = Counter(d.name for d in previews)
            for d in previews:
                if f.is_screenshot:
                    if not d.name.endswith("Screenshot"):
                        self.at(f, d, "PRV-6", f"`{d.name}` is a screenshot of the package: its name ends in `Screenshot`")
                else:
                    self.check_general_preview(f, d, composables, counts)
                if not re.search(r"\bAppTheme\s*[({]", d.text):
                    self.at(f, d, "PRV-4", f"`{d.name}` is wrapped in `AppTheme {{ … }}`, like the app")
                for pattern, what in PREVIEW_FORBIDDEN:
                    m = re.search(pattern, d.text)
                    if m:
                        self.add(f, k.line_of(f.clean, d.keyword + m.start()), "PRV-5",
                                 f"`{d.name}` uses {what} (`{m.group().strip()}`): a preview takes fake state and needs none", d.first_line)
                if re.search(r"https?://", d.raw) and "LocalAsyncImagePreviewHandler" not in d.text:
                    self.at(f, d, "PRV-5", f"`{d.name}` has a URL but not Coil's `LocalAsyncImagePreviewHandler`: a preview "
                                           f"never depends on the network")
            for d in composables:
                if role(d) == PAGE_CONTENT and not any(p.name == "Preview" and p.is_private for p in previews):
                    self.at(f, d, "PRV-1", f"`{d.name}` has no `private fun Preview()` with `@Preview` in {f.rel.name}")

    def check_general_preview(self, f, d, composables, counts):
        if not d.is_private:
            self.at(f, d, "PRV-2", f"`{d.name}` must be `private`, so the same name in every file never clashes")
        if d.name != "Preview" and not re.fullmatch(r"Preview[A-Z]\w*", d.name):
            self.at(f, d, "PRV-2", f"`{d.name}` is named `Preview`, or `Preview` and a differentiator (`PreviewEmpty`)")
        if counts[d.name] > 1:
            self.at(f, d, "PRV-2", f"`{d.name}` is declared more than once in {f.rel.name}")
        if d.name.endswith("Screenshot"):
            self.at(f, d, "PRV-6", f"`{d.name}` is a screenshot: it belongs in the `screenshot` package")
        names = [c.name for c in composables]
        if not names:
            self.at(f, d, "PRV-3", f"`{d.name}` previews nothing in {f.rel.name}: a preview is in the file of its composable")
        elif not any(re.search(rf"\b{n}\s*[({{]", d.text) for n in names):
            self.at(f, d, "PRV-3", f"`{d.name}` does not show a composable of {f.rel.name} ({', '.join(f'`{n}`' for n in names)}): "
                                   f"a preview is in the file of its composable")

    def check_composables(self):
        for f in self.files:
            if f.is_screenshot:
                continue
            plain = [d for d in f.decls if d.is_composable and not d.is_preview and not role(d)]
            public = [d for d in plain if not d.is_private]
            if len(public) > 1:
                names = ", ".join(f"`{d.name}`" for d in public)
                for d in public[1:]:
                    self.at(f, d, "CMP-1", f"{f.rel.name} has {len(public)} public composables ({names}): one composable per "
                                           f"file (make a helper `private`)")
            elif public and public[0].name != f.stem:
                self.at(f, public[0], "CMP-1", f"`{public[0].name}` is in {f.rel.name}: name the file after the composable")
            if any(d.is_preview for d in f.decls):
                continue
            for d in public:
                lines = sum(1 for line in d.text.splitlines() if line.strip())
                if lines >= MIN_PREVIEW_LINES and not returns_value(d) and not re.search(r"(?i)koin|ViewModel|NavDisplay|NavHost|NavBackStack|NavController|collectAs", d.text):
                    self.at(f, d, "PRV-7", f"`{d.name}` is {lines} lines and has no `@Preview` in {f.rel.name}: every composable "
                                           f"but a trivial one has one (a composable that needs Koin or navigation has none)")

    # ---- screenshots ----

    def check_screenshots(self):
        for f in self.files:
            if f.is_screenshot:
                for line, text in shots.problems(f.raw):
                    self.add(f, line, "SHOT-1", f"`{text}` is shared or not a screenshot: a file of the screenshot package holds "
                                                f"only private @Preview composables with their own data inside")
        if any(f.is_screenshot for f in self.files) and (self.app_dir / "readme.yml").is_file():
            package_files = [f for f in self.files if f.is_screenshot]
            for problem in shots.order_problems(self.app_dir):
                self.add(package_files[0], 1, "SHOT-2", problem)

    # ---- the comments that silence a rule ----

    def apply_ignores(self):
        kept = []
        ignores = defaultdict(set)  # path -> {(rule, line)}
        for f in self.files:
            for m in IGNORE.finditer(f.raw):
                if not f.in_comment(m.start()):
                    continue
                line = k.line_of(f.raw, m.start())
                if m.group(1) not in RULES or m.group(1) == "IGNORE-1":
                    self.add(f, line, "IGNORE-1", f"`{m.group(1)}` is not a rule that can be ignored (docs/lint.md lists them)")
                elif not m.group(2):
                    self.add(f, line, "IGNORE-1", f"lint:ignore {m.group(1)} gives no reason: `// lint:ignore {m.group(1)}: why`")
                else:
                    ignores[f.path].add((m.group(1), line))
        for v in self.violations:
            if not any((v.rule, n) in ignores[v.path] for n in range(v.anchor - 1, v.line + 1)):
                kept.append(v)
        return kept

    def run(self):
        for check in (self.check_files, self.check_pairs, self.check_visibility, self.check_names, self.check_page_body,
                      self.check_page_content, self.check_lookups, self.check_definitions, self.check_viewmodels,
                      self.check_ui_states, self.check_previews, self.check_composables, self.check_screenshots):
            check()
        unique = {(v.path, v.line, v.rule, v.message): v for v in self.violations}
        self.violations = list(unique.values())
        return sorted(self.apply_ignores(), key=lambda v: (v.path, v.line, v.rule))


def lint(app_dir):
    """The violations in the app at [app_dir], sorted."""
    return Lint(app_dir).run()


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
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("app_dir", nargs="?", default=".")
    args = parser.parse_args(argv)
    linter = Lint(args.app_dir)
    violations = linter.run()
    for v in violations:
        print(f"::error file={escape(v.path, True)},line={v.line},title={v.rule}::{escape(v.message)}")
        print(f"{v.path}:{v.line}: [{v.rule}] {v.message}")
    text = summary(violations, len(linter.files))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a") as out:
            out.write(text)
    print(f"\n{len(violations)} violations in {len(linter.files)} Kotlin files." if violations
          else f"Conventions: no violations in {len(linter.files)} Kotlin files.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
