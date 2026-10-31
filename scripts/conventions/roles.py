"""Which declaration is which part of a page or of a sheet: the names that the page, ViewModel and preview rules share."""

import re

SHEET_CONTENT, SHEET = "SheetContent", "Sheet"
PAGE_CONTENT, PAGE, VIEW_MODEL, UI_STATE = "PageContent", "Page", "ViewModel", "UiState"
SUFFIX_OF_ROLE = {PAGE_CONTENT: "PageContent", PAGE: "Page", VIEW_MODEL: "ViewModel", UI_STATE: "UiState"}
ROLE_FILE = re.compile(r".+(PageContent|Page|ViewModel|UiState)$")


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


def sheet_role(d):
    """SHEET for an `XSheet` composable, SHEET_CONTENT for an `XSheetContent` one, else None."""
    if d.is_composable and not d.is_preview:
        if d.name.endswith("SheetContent") and len(d.name) > len("SheetContent"):
            return SHEET_CONTENT
        if d.name.endswith("Sheet") and len(d.name) > len("Sheet"):
            return SHEET
    return None


def page_of(d):
    """The X of an XPage, XPageContent, XViewModel or XUiState."""
    return d.name[:-len(SUFFIX_OF_ROLE[role(d)])]


def is_viewmodel(d):
    return d.kind == "class" and re.search(r"\b\w*ViewModel\b", d.supertypes) is not None
