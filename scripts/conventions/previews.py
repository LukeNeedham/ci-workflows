"""PRV-1..7 and CMP-1: every public or `internal` composable has a preview in its file, and what a preview may hold."""

import re
from collections import Counter

from . import scan as k
from .pages import STATEFUL
from .roles import PAGE_CONTENT, SHEET_CONTENT, role, sheet_role

RULES = {
    "PRV-1": "Every XPageContent and XSheetContent has a private @Preview named Preview in its file",
    "PRV-2": "A preview is private and named Preview or Preview<Variant>, once per file",
    "PRV-3": "A preview is in the file of the composable it previews",
    "PRV-4": "A preview is wrapped in AppTheme",
    "PRV-5": "A preview needs no ViewModel, Koin, Flow collection or network",
    "PRV-6": "Only the screenshot package has screenshots, and every preview in it ends in Screenshot",
    "PRV-7": "Every public or internal composable has a preview in its file",
    "CMP-1": "One public composable per file, named after the file",
}

SHELL_COMPOSABLES = {"Root", "AppNavigation", "Router", "AppTheme"}
PREVIEW_FORBIDDEN = [(p, w) for p, w in STATEFUL if w in ("a ViewModel", "Koin")] + [
    (r"\bcollectAs\w*\b|\.collect\b", "a Flow collection"),
]


def returns_value(d):
    """Whether the function [d] returns something (`remember…`, a state holder): there is nothing in it to preview."""
    open_paren = d.text.find("(")
    if open_paren < 0:
        return False
    close = k.balanced(d.text, open_paren)
    return re.match(r"\s*:\s*\w", d.text[close + 1:]) is not None


def check_previews(ctx):
    for f in ctx.files:
        previews = [d for d in f.decls if d.is_preview]
        composables = [d for d in f.decls if d.is_composable and not d.is_preview]
        counts = Counter(d.name for d in previews)
        for d in previews:
            if f.is_screenshot:
                if not d.name.endswith("Screenshot"):
                    ctx.at(f, d, "PRV-6", f"`{d.name}` is a screenshot of the package: its name ends in `Screenshot`")
            else:
                check_general_preview(ctx, f, d, composables, counts)
            if not re.search(r"\bAppTheme\s*[({]", d.text):
                ctx.at(f, d, "PRV-4", f"`{d.name}` is wrapped in `AppTheme {{ … }}`, like the app")
            for pattern, what in PREVIEW_FORBIDDEN:
                m = re.search(pattern, d.text)
                if m:
                    ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "PRV-5",
                             f"`{d.name}` uses {what} (`{m.group().strip()}`): a preview takes fake state and needs none", d.first_line)
            if re.search(r"https?://", d.raw) and "LocalAsyncImagePreviewHandler" not in d.text:
                ctx.at(f, d, "PRV-5", f"`{d.name}` has a URL but not Coil's `LocalAsyncImagePreviewHandler`: a preview "
                                       f"never depends on the network")
        for d in composables:
            if (role(d) == PAGE_CONTENT or sheet_role(d) == SHEET_CONTENT) and not any(
                    p.name == "Preview" and p.is_private for p in previews):
                ctx.at(f, d, "PRV-1", f"`{d.name}` has no `private fun Preview()` with `@Preview` in {f.rel.name}")


def check_general_preview(ctx, f, d, composables, counts):
    if not d.is_private:
        ctx.at(f, d, "PRV-2", f"`{d.name}` must be `private`, so the same name in every file never clashes")
    if d.name != "Preview" and not re.fullmatch(r"Preview[A-Z]\w*", d.name):
        ctx.at(f, d, "PRV-2", f"`{d.name}` is named `Preview`, or `Preview` and a differentiator (`PreviewEmpty`)")
    if counts[d.name] > 1:
        ctx.at(f, d, "PRV-2", f"`{d.name}` is declared more than once in {f.rel.name}")
    if d.name.endswith("Screenshot"):
        ctx.at(f, d, "PRV-6", f"`{d.name}` is a screenshot: it belongs in the `screenshot` package")
    names = [c.name for c in composables]
    if not names:
        ctx.at(f, d, "PRV-3", f"`{d.name}` previews nothing in {f.rel.name}: a preview is in the file of its composable")
    elif not any(re.search(rf"\b{n}\s*[({{]", d.text) for n in names):
        ctx.at(f, d, "PRV-3", f"`{d.name}` does not show a composable of {f.rel.name} ({', '.join(f'`{n}`' for n in names)}): "
                               f"a preview is in the file of its composable")


def check_composables(ctx):
    for f in ctx.files:
        if f.is_screenshot:
            continue
        plain = [d for d in f.decls if d.is_composable and not d.is_preview and not role(d)]
        public = [d for d in plain if not d.is_private]
        if len(public) > 1:
            names = ", ".join(f"`{d.name}`" for d in public)
            for d in public[1:]:
                ctx.at(f, d, "CMP-1", f"{f.rel.name} has {len(public)} public composables ({names}): one composable per "
                                       f"file (make a helper `private`)")
        elif public and public[0].name != f.stem:
            ctx.at(f, public[0], "CMP-1", f"`{public[0].name}` is in {f.rel.name}: name the file after the composable")
        if any(d.is_preview for d in f.decls):
            continue
        for d in public:
            if returns_value(d) or d.name in SHELL_COMPOSABLES:
                continue  # nothing to show
            ctx.at(f, d, "PRV-7", f"`{d.name}` has no `@Preview` in {f.rel.name}: every public or `internal` composable has one, "
                                   f"mocked where it needs the camera, a video or Koin (a page has none, its content has)")


def check(ctx):
    check_previews(ctx)
    check_composables(ctx)
