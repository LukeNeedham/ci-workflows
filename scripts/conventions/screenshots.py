#!/usr/bin/env python3
"""SHOT-1..2 and the screenshot package of an app: where it is, what it may hold and its order.txt (docs/screenshots.md).
The render, README and sync scripts read the package through the helpers here too.

Every screenshot owns its data, and nothing is shared: not between pages, not between the screenshots of one page,
not with the general previews or the app. So a file of the package holds nothing at the top level but private
`@Preview` composables without parameters, each with its mock data inside its own body. Anything else (a top-level
`val`, an object, a helper function, a public or `internal` declaration) is a way to share, and is a violation.

The package also has an `order.txt` next to its Kotlin files: the screenshots in the order the README shows them, one name
per line (the composable name without the trailing `Screenshot`; blank lines are ignored). **No comments**: the file says
all it needs to, so a line with a `#` is a violation. Every screenshot is listed once, and nothing else. CI numbers the images by their position: `01-HomePage.png`, `02-…`.
"""

import re
from pathlib import Path

RULES = {
    "SHOT-1": "A file of the screenshot package holds only private @Preview composables with their own data",
    "SHOT-2": "The screenshot package has an order.txt that lists every screenshot once",
}

ORDER_FILE = "order.txt"
SUFFIX = "Screenshot"
PREVIEW_NAME = re.compile(r"^private fun (\w+)\(\s*\)", re.M)
PREVIEW_FUNCTION = re.compile(r"private fun \w+\(\s*\)\s*\{?\s*$")
ANNOTATION_ONLY = re.compile(r"@\w+(\.\w+)*(\([^)]*\))?\s*$")


def package_files(app_dir):
    """The Kotlin files of the screenshot package of the app at [app_dir]: those in a `screenshot` folder under app/src."""
    src = Path(app_dir) / "app" / "src"
    return sorted(p for p in src.rglob("*.kt") if p.parent.name == "screenshot" and "build" not in p.relative_to(src).parts)


def package_folders(app_dir):
    """The `screenshot` folders under app/src (outside the build output), whether or not they hold Kotlin files."""
    src = Path(app_dir) / "app" / "src"
    return sorted(p for p in src.rglob("screenshot") if p.is_dir() and "build" not in p.relative_to(src).parts)


def manual_screenshots(app_dir):
    """Whether readme.yml has opted out of the generated screenshots (`screenshots: manual`). Read without a YAML
    parser, since this runs in the app's build job; scripts/generate_readme.py validates the file properly."""
    path = Path(app_dir) / "readme.yml"
    return path.is_file() and re.search(r"""(?m)^screenshots:[ \t]*["']?manual["']?[ \t]*(#.*)?$""", path.read_text()) is not None


def setup_problems(app_dir):
    """What an app that has a readme.yml still needs for its screenshots, as sentences: none for an app that opted out
    with `screenshots: manual` and has no package (its README generator checks the committed images)."""
    if manual_screenshots(app_dir):
        return ["`screenshots: manual` but the app has a screenshot package: remove one of them"] if package_folders(app_dir) else []
    if not package_folders(app_dir):
        return ["no screenshot package (or, for an app that cannot render previews, `screenshots: manual`)"]
    if not package_files(app_dir):
        return ["the screenshot package has no Kotlin files"]
    return order_problems(app_dir)


def package_dir(app_dir):
    """The folder of the screenshot package, or None when the app has none (or Kotlin files in several)."""
    folders = {p.parent for p in package_files(app_dir)}
    return folders.pop() if len(folders) == 1 else None


def preview_names(app_dir):
    """The screenshots of the package, by name (the composable name without the trailing `Screenshot`)."""
    names = []
    for path in package_files(app_dir):
        names += [n.removesuffix(SUFFIX) for n in PREVIEW_NAME.findall(path.read_text())]
    return names


def read_order(text):
    """The names of an order.txt [text], in order: one per line, blank lines ignored."""
    lines = (line.strip() for line in text.splitlines())
    return [line for line in lines if line]


def order_problems(app_dir):
    """What is wrong with the order of the screenshots of the app, as a list of sentences."""
    folder = package_dir(app_dir)
    if folder is None:
        return [f"the screenshot package must be one folder of Kotlin files (with a {ORDER_FILE} next to them)"]
    path = folder / ORDER_FILE
    if not path.is_file():
        return [f"{path.relative_to(app_dir)} is missing: list the screenshots in the order the README shows them, "
                f"one name per line (docs/screenshots.md)"]
    order, previews = read_order(path.read_text()), preview_names(app_dir)
    comments = [line for line in order if "#" in line]
    if comments:
        return [f"{ORDER_FILE} has no comments (`{line}`): it is one screenshot name per line and nothing else" for line in comments]
    if not previews:
        return [f"the screenshot package has no screenshot: every app has at least one (a private @Preview composable "
                f"named like HomePageScreenshot, listed in {ORDER_FILE})"]
    found = [f"`{n}` is listed twice in {ORDER_FILE}" for n in sorted({n for n in order if order.count(n) > 1})]
    found += [f"`{n}` in {ORDER_FILE} is not a screenshot of the package (its composable is `{n}{SUFFIX}`)"
              for n in dict.fromkeys(order) if n not in previews]
    found += [f"`{n}{SUFFIX}` is not in {ORDER_FILE}: add `{n}` where it belongs in the order" for n in previews if n not in order]
    return found


def problems(text):
    """The (line number, line) of every top-level declaration in [text] that is not a private @Preview composable."""
    found = []
    annotations = []
    in_comment = False
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if in_comment:
            in_comment = "*/" not in line
            continue
        if line.lstrip().startswith("/*"):
            in_comment = "*/" not in line
            continue
        if line.startswith("//") or line[0] in " \t" or line.startswith(("package ", "import ")):
            continue
        if line[0] in "})":
            annotations = []
            continue
        if ANNOTATION_ONLY.match(line):
            annotations.append(line.split("(")[0].strip())
            continue
        if "@Preview" not in annotations or not PREVIEW_FUNCTION.match(line):
            found.append((number, line.strip()))
        annotations = []
    return found


def check(ctx):
    for f in ctx.files:
        if f.is_screenshot:
            for line, text in problems(f.raw):
                ctx.add(f, line, "SHOT-1", f"`{text}` is shared or not a screenshot: a file of the screenshot package holds "
                                           f"only private @Preview composables with their own data inside")
    package = [f for f in ctx.files if f.is_screenshot]
    if package and (ctx.app_dir / "readme.yml").is_file():
        for problem in order_problems(ctx.app_dir):
            ctx.add(package[0], 1, "SHOT-2", problem)
