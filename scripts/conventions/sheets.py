"""SHEET-1..5: a bottom sheet is an `XSheet` that puts a stateless `XSheetContent` (own file, own preview) in it."""

import re

from . import scan as k
from .pages import STATEFUL
from .roles import SHEET, SHEET_CONTENT, sheet_role

RULES = {
    "SHEET-1": "Every XSheet has an XSheetContent in its package and calls it",
    "SHEET-2": "Every XSheetContent has an XSheet in its package",
    "SHEET-3": "A bottom sheet (ModalBottomSheet, BottomSheetScaffold…) is only used inside an XSheet composable",
    "SHEET-4": "XSheetContent knows nothing of the sheet around it: no sheet, sheet state or sheet layout",
    "SHEET-5": "XSheetContent is stateless: no ViewModel, Koin, Flow, repository or navigator",
}

SHEET_PRIMITIVE = re.compile(
    r"(?<![\w.])(ModalBottomSheet|ModalBottomSheetLayout|BottomSheetScaffold|BottomSheetDialog|ModalBottomSheetDialog|"
    r"BottomSheetDialogFragment)\b\s*[({:<]"
)
# What XSheetContent leaves to its sheet: the sheet itself, its state and the shared layout that wraps a sheet
SHEET_PARTS = re.compile(
    r"\b(?:ModalBottomSheet\w*|BottomSheet\w*|SheetState|rememberModalBottomSheetState|rememberStandardBottomSheetState|"
    r"SheetLayout|SheetDefaults|SheetValue)\b"
)


def check_sheets(ctx):
    for (package, x), (f, d) in ctx.sheets[SHEET].items():
        content = ctx.sheets[SHEET_CONTENT].get((package, x))
        if content is None:
            ctx.at(f, d, "SHEET-1", f"`{d.name}` has no `{x}SheetContent` in the package `{package}`: a sheet only draws "
                                     f"the sheet, and puts `{x}SheetContent` (its own file, with its own preview) in it")
        elif not re.search(rf"\b{x}SheetContent\s*\(", d.text):
            ctx.at(f, d, "SHEET-1", f"`{d.name}` does not call `{x}SheetContent`: the sheet delegates its content to it")
    for (package, x), (f, d) in ctx.sheets[SHEET_CONTENT].items():
        if (package, x) not in ctx.sheets[SHEET]:
            ctx.at(f, d, "SHEET-2", f"`{d.name}` has no `{x}Sheet` in the package `{package}`: the content of a sheet is "
                                     f"shown by the sheet that goes with it")
        for pattern, what in STATEFUL:
            m = re.search(pattern, d.text)
            if m:
                ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "SHEET-5",
                         f"`{d.name}` is stateless but touches {what} (`{m.group().strip()}`): that goes up into the "
                         f"page that shows `{x}Sheet`", d.first_line)
        m = SHEET_PARTS.search(d.text)
        if m:
            ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "SHEET-4",
                     f"`{d.name}` uses `{m.group()}`: the content of a sheet does not know about the sheet around it "
                     f"(`{x}Sheet` does that)", d.first_line)
    for f in ctx.files:
        if f.is_screenshot:
            continue
        has_sheet = any(sheet_role(d) == SHEET for d in f.decls)
        for d in f.decls:
            if sheet_role(d):
                continue  # XSheet draws the sheet; XSheetContent is SHEET-4's
            m = SHEET_PRIMITIVE.search(d.text)
            if not m or d.kind != "fun":
                continue
            if d.is_private and not d.is_preview and has_sheet:
                continue  # a helper of the XSheet of this file
            ctx.add(f, k.line_of(f.clean, d.keyword + m.start()), "SHEET-3",
                     f"`{d.name}` uses `{m.group(1)}`: a bottom sheet is only drawn inside an `XSheet` composable "
                     f"(`XSheet.kt`), which the page calls and which puts `XSheetContent` in it", d.first_line)


def check(ctx):
    check_sheets(ctx)
