"""TOP-1: the only functions at the top level of a file are extension functions and composables (docs/app-conventions.md)."""

import re

RULES = {
    "TOP-1": "A function is a member of a class or an object: only extensions, composables, expect/actual/external functions and main are top-level",
}


def is_extension(d):
    """Whether the function [d] has a receiver: `fun List<Day>.currentIndex()`, `fun <T> T.also2()`, `fun (() -> Unit).run2()`."""
    text = d.text
    rest = re.sub(r"^fun\b\s*", "", text)
    previous = None
    while previous != rest[:200]:  # the generics: `<T : Comparable<T>>`
        previous = rest[:200]
        rest = re.sub(r"^<[^<>]*(?:<[^<>]*>[^<>]*)*>\s*", "", rest)
    if rest.startswith("("):  # a function type as the receiver
        return True
    header = rest[:rest.find("(")] if "(" in rest else rest
    return "." in re.sub(r"<[^<>]*(?:<[^<>]*>[^<>]*)*>", "", header)


def is_platform_function(d):
    """Whether the function [d] has to be at the top level: the platform or the language looks it up there. An `expect` or
    `actual` function of a Kotlin Multiplatform app, an `external` one (a bridge to JavaScript or native code) and `main`."""
    return bool(d.mods & {"expect", "actual", "external"}) or d.name == "main"


def check_top_level_functions(ctx):
    for f in ctx.files:
        for d in f.decls:
            if d.kind != "fun" or d.is_composable or is_extension(d) or is_platform_function(d):
                continue
            ctx.at(f, d, "TOP-1", f"`{d.name}` is a top-level function: put it in an `object` or the class it serves, or make it an "
                                  f"extension function of the type it works on (only extensions, composables, expect/actual/external functions and main are top-level)")


def check(ctx):
    check_top_level_functions(ctx)
