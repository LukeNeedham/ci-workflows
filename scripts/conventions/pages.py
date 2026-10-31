"""PAGE-1..6: the four files of a page, their names, visibility and what `XPage` and `XPageContent` may hold."""

import re

from . import scan as k
from .roles import PAGE, PAGE_CONTENT, UI_STATE, ROLE_FILE, is_viewmodel, page_of, role

RULES = {
    "PAGE-1": "XPage, XPageContent, XViewModel and XUiState are each in their own file, named after them",
    "PAGE-2": "Every XPage has an XPageContent in its package, and the reverse",
    "PAGE-3": "XPage is public, XPageContent is internal",
    "PAGE-4": "No XScreen, XScreenContent, XView or XContent for a page, no XPageViewModel or XScreenViewModel",
    "PAGE-5": "XPage calls XPageContent once and draws no UI of its own, with no preview",
    "PAGE-6": "XPageContent is stateless: no ViewModel, Koin, Flow, repository or navigator, and it takes the XUiState",
}

FORBIDDEN_PAGE_IMPORTS = ("androidx.compose.foundation", "androidx.compose.material")
# What XPageContent never touches: (pattern, what it is)
STATEFUL = [
    (r"(?i)\b\w*viewmodel\w*\b", "a ViewModel"),
    (r"(?i)\b\w*koin\w*\b", "Koin"),
    (r"\b\w*Flow\b|\bcollectAs\w*\b", "a Flow"),
    (r"\b(?:NavController|NavHostController|NavBackStack|Navigator|backStack)\b", "the navigation"),
    (r"\b\w*Repository\b", "a repository"),
]


def check_files(ctx):
    for f in ctx.files:
        if f.is_screenshot:
            continue
        owner = None
        for d in f.decls:
            if role(d) and d.name != f.stem:
                ctx.at(f, d, "PAGE-1", f"`{d.name}` is in {f.rel.name}: each of XPage, XPageContent, XViewModel and "
                                        f"XUiState is in its own file, named after it (`{d.name}.kt`)")
            elif role(d):
                owner = d
        if owner:
            for d in f.decls:
                if d is not owner and not d.is_private and not d.is_preview:  # a public preview is PRV-2's
                    ctx.at(f, d, "PAGE-1", f"`{d.name}` is in {f.rel.name}, the file of `{owner.name}`, which holds only "
                                            f"what its name says: move it to its own file (or make it private)")
        elif ROLE_FILE.match(f.stem) and not any(d.name == f.stem for d in f.decls):
            ctx.add(f, 1, "PAGE-1", f"{f.rel.name} does not declare `{f.stem}`: a file named after a page, ViewModel or "
                                     f"state holds that one declaration")


def check_pairs(ctx):
    for (package, x), (f, d) in ctx.by_role[PAGE].items():
        if (package, x) not in ctx.by_role[PAGE_CONTENT]:
            ctx.at(f, d, "PAGE-2", f"`{d.name}` has no `{x}PageContent` in the package `{package}`")
    for (package, x), (f, d) in ctx.by_role[PAGE_CONTENT].items():
        if (package, x) not in ctx.by_role[PAGE]:
            ctx.at(f, d, "PAGE-2", f"`{d.name}` has no `{x}Page` in the package `{package}`")


def check_visibility(ctx):
    for f, d in ctx.by_role[PAGE].values():
        if d.mods & {"private", "internal", "protected"}:
            ctx.at(f, d, "PAGE-3", f"`{d.name}` is public: the navigation calls it")
    for f, d in ctx.by_role[PAGE_CONTENT].values():
        if "internal" not in d.mods:
            ctx.at(f, d, "PAGE-3", f"`{d.name}` is `internal` (not public, not private): the screenshots of the app use it")


def check_names(ctx):
    for f in ctx.files:
        if f.is_screenshot:
            continue
        for d in f.decls:
            if d.is_composable and not role(d):
                n = d.name
                x = None
                if n.endswith("ScreenContent") or (n.endswith("Screen") and len(n) > len("Screen")):
                    ctx.at(f, d, "PAGE-4", f"`{n}`: a page is an `XPage` and an `XPageContent`, never a `Screen`")
                elif n.endswith("View") and len(n) > 4:
                    x = n[:-4]
                elif n.endswith("Content") and len(n) > len("Content"):
                    x = n[:-7]
                if x and x in ctx.known:
                    ctx.at(f, d, "PAGE-4", f"`{n}` is the content of the page `{x}`: name it `{x}PageContent`")
            elif is_viewmodel(d) and re.search(r"(Page|Screen)ViewModel$", d.name):
                suffix = re.search(r"(Page|Screen)ViewModel$", d.name).group()
                ctx.at(f, d, "PAGE-4", f"`{d.name}`: the ViewModel of `{d.name[:-len(suffix)]}Page` is "
                                        f"`{d.name[:-len(suffix)]}ViewModel`")


def check_page_body(ctx):
    for f, d in ctx.by_role[PAGE].values():
        x = page_of(d)
        calls = len(re.findall(rf"\b{x}PageContent\s*\(", d.text))
        if calls != 1:
            ctx.at(f, d, "PAGE-5", f"`{d.name}` calls `{x}PageContent` {calls} times: it calls it exactly once and "
                                    f"draws nothing itself")
        if any(p.is_preview for p in f.decls):
            ctx.at(f, d, "PAGE-5", f"`{f.rel.name}` has a @Preview: `{d.name}` needs Koin and a ViewModel, so only "
                                    f"`{x}PageContent` has previews")
        ui = [(line, name) for line, name in f.imports if name.startswith(FORBIDDEN_PAGE_IMPORTS)]
        if ui:
            shown = ", ".join(f"`{name}`" for _, name in ui[:3]) + (f" and {len(ui) - 3} more" if len(ui) > 3 else "")
            ctx.add(f, ui[0][0], "PAGE-5", f"`{d.name}` draws no UI of its own, so it does not import {shown}: "
                                            f"that belongs in `{x}PageContent`")


def check_page_content(ctx):
    for f, d in ctx.by_role[PAGE_CONTENT].values():
        x = page_of(d)
        for pattern, what in STATEFUL:
            m = re.search(pattern, d.text)
            if m:
                ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "PAGE-6",
                         f"`{d.name}` is stateless but touches {what} (`{m.group().strip()}`): that goes up into `{x}Page`",
                         d.first_line)
        if (f.package, x) in ctx.by_role[UI_STATE] and not re.search(rf"\b{x}UiState\b", d.params):
            ctx.at(f, d, "PAGE-6", f"`{d.name}` takes the `{x}UiState` as its state")


def check(ctx):
    for rule in (check_files, check_pairs, check_visibility, check_names, check_page_body, check_page_content):
        rule(ctx)
