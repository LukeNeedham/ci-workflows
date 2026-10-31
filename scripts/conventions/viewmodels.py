"""VM-1..8 and UI-1..3: only a page requests its own ViewModel, and what a ViewModel and a UiState may hold."""

import re
from collections import defaultdict

from . import scan as k
from .roles import PAGE, UI_STATE, is_viewmodel, page_of, role

RULES = {
    "VM-1": "A ViewModel is requested only in XPage, and only as XViewModel",
    "VM-2": "A ViewModel is requested by one page only",
    "VM-3": "No ViewModel is scoped to the activity, a navigation graph or a parent",
    "VM-4": "A ViewModel is never a Koin single, factory or scoped definition",
    "VM-5": "A ViewModel holds no other ViewModel",
    "VM-6": "A ViewModel is named XViewModel and belongs to an XPage in its package",
    "VM-8": "No AndroidViewModel: a ViewModel extends ViewModel and takes its dependencies as constructor parameters",
    "VM-7": "A ViewModel declares no SharedFlow: one-off events go through a Channel",
    "UI-1": "An XUiState belongs to an XPage in its package",
    "UI-2": "An XUiState is immutable",
    "UI-3": "An XUiState holds no Flow or Channel",
}

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


def lookups(ctx, f):
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


def check_lookups(ctx):
    requests = defaultdict(list)  # ViewModel -> [(file, line, requester)]
    for f in ctx.files:
        reported = set()
        for m, name, type_name, args, enclosing in lookups(ctx, f):
            line = k.line_of(f.clean, m.start())
            short = type_name.split(".")[-1] if type_name else None
            scoped = name in SCOPED_LOOKUPS or OWNER_WORDS.search(args)
            if scoped:
                reported.add(line)
                ctx.add(f, line, "VM-3", f"`{name}` shares a ViewModel between pages (scoped to the activity, a navigation "
                                          f"graph or a parent): each page has its own, and state pages share goes in a repository")
            page = enclosing if enclosing is not None and role(enclosing) == PAGE else None
            if page is None:
                ctx.add(f, line, "VM-1", f"`{name}` requests a ViewModel outside an `XPage`: only the page gets its ViewModel")
            elif short is None:
                ctx.add(f, line, "VM-1", f"`{name}` in `{page.name}` needs its type: `{name}<{page_of(page)}ViewModel>()`")
            elif short != f"{page_of(page)}ViewModel":
                ctx.add(f, line, "VM-1", f"`{page.name}` requests `{short}`: its ViewModel is `{page_of(page)}ViewModel`")
            if short:
                requests[short].append((f, line, page.name if page else f"{f.path}"))
        for m in OWNER_STANDALONE.finditer(f.clean):
            line = k.line_of(f.clean, m.start())
            if line not in reported:
                ctx.add(f, line, "VM-3", f"`{m.group().strip(' =')}` hands a ViewModel to another owner than its page")
    for type_name, sites in requests.items():
        requesters = sorted({who for _, _, who in sites})
        if len(requesters) > 1:
            for f, line, _ in sites:
                ctx.add(f, line, "VM-2", f"`{type_name}` is requested by {', '.join(f'`{r}`' for r in requesters)}: a ViewModel "
                                          f"belongs to one page, so give each its own and share state in a repository")


def check_definitions(ctx):
    for f in ctx.files:
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
                ctx.add(f, k.line_of(f.clean, m.start()), "VM-4",
                         f"`{m.group()}` defines `{hit.group()}` as one shared instance: a ViewModel is a `viewModel` or "
                         f"`viewModelOf` definition, created for its page")


def check_viewmodels(ctx):
    for f in ctx.files:
        if f.is_screenshot:
            continue
        for d in f.decls:
            if not is_viewmodel(d):
                continue
            inherited = set(re.findall(r"\b[A-Z]?\w*ViewModel\b", d.supertypes))
            others = set(re.findall(r"\b[A-Z]\w*ViewModel\b", d.text)) - inherited - {d.name, "ViewModel", "AndroidViewModel"}
            for other in sorted(others):
                ctx.at(f, d, "VM-5", f"`{d.name}` holds `{other}`: a ViewModel never holds or calls another, so share "
                                      f"state through a repository")
            m = re.search(r"\b\w*SharedFlow\b|\basSharedFlow\b", d.text)
            if m:
                ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "VM-7",
                         f"`{d.name}` uses `{m.group()}`: a one-off event goes through a `Channel` exposed with "
                         f"`receiveAsFlow()`, so it is never lost or doubled", d.first_line)
            if d.mods & {"abstract", "sealed"} or d.kind != "class":
                continue
            if re.search(r"(Page|Screen)ViewModel$", d.name):
                continue  # PAGE-4
            if not role(d):
                ctx.at(f, d, "VM-6", f"`{d.name}` is a ViewModel: name it `XViewModel`, for the page `XPage`")
            elif not ctx.has(PAGE, f, page_of(d)):
                ctx.at(f, d, "VM-6", f"`{d.name}` has no `{page_of(d)}Page` in the package `{f.package}`: a ViewModel "
                                      f"belongs to the page it is named after")


def check_ui_states(ctx):
    for f, d in ctx.by_role[UI_STATE].values():
        x = page_of(d)
        if not ctx.has(PAGE, f, x):
            ctx.at(f, d, "UI-1", f"`{d.name}` has no `{x}Page` in the package `{f.package}`: a state belongs to the page "
                                  f"it is named after")
        m = re.search(r"\bvar\s+\w+|\b(?:Mutable\w+|mutable\w+Of|ArrayList|HashMap|HashSet|LinkedHashMap)\b", d.text)
        if m:
            ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "UI-2",
                     f"`{d.name}` is immutable (`{m.group().strip()}`): `val`s and read-only collections, changed with `copy`", d.first_line)
        m = re.search(r"\b\w*Flow\b|\bChannel\b", d.text)
        if m:
            ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "UI-3",
                     f"`{d.name}` is plain data but holds `{m.group()}`: flows and channels belong in the ViewModel", d.first_line)


def check_android_view_model(ctx):
    for f in ctx.all_files:
        for m in re.finditer(r"\bAndroidViewModel\b", f.clean):
            ctx.add(f, k.line_of(f.clean, m.start()), "VM-8",
                    "`AndroidViewModel` is banned: extend `ViewModel` and take the dependencies as constructor parameters")


def check(ctx):
    check_android_view_model(ctx)
    for rule in (check_lookups, check_definitions, check_viewmodels, check_ui_states):
        rule(ctx)
