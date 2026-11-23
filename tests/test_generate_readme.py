import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

import _paths  # noqa: F401
import generate_readme as g

TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "readme-template.yml"
BUILD = 'android {\n    compileSdk = 36\n    defaultConfig {\n        minSdk = 26 // why\n    }\n}\n'
SHOTS = ["docs/screenshots/HomePage.png", "docs/screenshots/PullRequestPage.png"]


class app:
    """A folder with the files that the README needs from the project: a screenshot and a LICENSE."""

    def __init__(self, screenshots=True, license="MIT License\n"):
        self.screenshots, self.license = screenshots, license

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        if self.screenshots:
            (folder / "docs" / "screenshots").mkdir(parents=True)
            (folder / "docs" / "screenshots" / "HomePage.png").write_bytes(b"png")
        if self.license is not None:
            (folder / "LICENSE").write_text(self.license)
        return folder

    def __exit__(self, *exc):
        self.tmp.cleanup()


def data():
    return yaml.safe_load(TEMPLATE.read_text())


def facts(**kwargs):
    return g.Facts(**{"min_sdk": 26, "compile_sdk": 36, "screenshots": SHOTS, "license": "MIT", **kwargs})


def render(d=None, **kwargs):
    return g.render(d or data(), "LukeNeedham/Demo", facts(**kwargs))


class GenerateReadmeTest(unittest.TestCase):
    def test_the_template_is_valid(self):
        self.assertEqual([], g.problems(data()))
        with app() as folder:
            self.assertEqual([], g.problems(data(), folder))

    def test_the_layout_is_the_standard_one(self):
        text = render()
        headings = [l[3:] for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(["Description", "Screenshots", "Getting started as a user", "Getting started as a developer",
                          "Contributing", "License"], headings)
        self.assertLess(text.index("app-icon.png"), text.index("# Demo App"))
        self.assertIn("git clone https://github.com/LukeNeedham/Demo.git", text)
        self.assertIn("Edit readme.yml", text)
        self.assertIn("JDK 17", text)

    def test_the_minimum_android_version_and_platform_come_from_the_project(self):
        text = render()
        self.assertIn("Requires Android 8.0 (API 26) or newer.", text)
        self.assertIn("Android SDK (platform 36)", text)
        self.assertIn("Requires Android API 99 or newer.", render(min_sdk=99))
        self.assertIn("the Android SDK, for example", render(compile_sdk=None))

    def test_the_architecture_is_not_in_the_readme_data_but_pointed_to(self):
        text = render()
        self.assertNotIn("Project structure", text)
        self.assertIn("shared architecture and conventions", text)
        self.assertIn("`Page` and a `PageContent`", text)
        for field in ("structure", "architecture"):
            d = data()
            d[field] = "x"
            self.assertIn(f"unknown field `{field}`", "\n".join(g.problems(d)))
        d = data()
        d["user"] = {"min-android": "8.0"}
        self.assertIn("unknown field `user.min-android`", "\n".join(g.problems(d)))

    def test_the_developer_section_has_only_what_is_specific_to_the_app(self):
        d = data()
        d["developer"] = {"notes": "Create local.properties."}
        text = render(d)
        self.assertLess(text.index("shared architecture and conventions"), text.index("Create local.properties."))
        self.assertLess(text.index("Create local.properties."), text.index("## Contributing"))
        d["developer"] = {"notes": "x", "structure": ["y"]}
        self.assertIn("`developer` can only have `notes`", "\n".join(g.problems(d)))

    def test_optional_parts_appear_between_the_right_sections(self):
        d = data()
        d["sections"] = [{"title": "Privacy", "body": "None."}]
        d["developer"] = {"notes": "Create local.properties."}
        text = render(d)
        self.assertIn('<img src="docs/screenshots/PullRequestPage.png" width="240" alt="Pull Request Page">', text)
        order = [text.index(s) for s in ("## Description", "## Screenshots", "## Getting started as a user",
                                         "Create local.properties.", "## Privacy", "## Contributing")]
        self.assertEqual(sorted(order), order)

    def test_the_install_step_can_be_replaced(self):
        d = data()
        d["user"] = {"install": "Get the APK from a PR."}
        text = render(d)
        self.assertIn("1. Get the APK from a PR.", text)
        self.assertNotIn("apphub", text.lower().replace("app-icon", ""))

    def test_the_license_is_the_one_of_the_license_file_and_always_linked(self):
        self.assertTrue(render(license="MIT").rstrip().endswith("MIT. See [LICENSE](LICENSE)."))
        self.assertTrue(render(license="All rights reserved").rstrip().endswith("All rights reserved. See [LICENSE](LICENSE)."))

    def test_the_license_is_no_field_of_the_data(self):
        d = data()
        d["license"] = "MIT"
        self.assertIn("`license` is not a field", "\n".join(g.problems(d)))

    def test_the_license_file_is_required_and_named_by_its_wording(self):
        with app(license=None) as folder:
            self.assertIn("no LICENSE file", "\n".join(g.problems(data(), folder)))
        with app(license="  \n") as folder:
            self.assertIn("no LICENSE file", "\n".join(g.problems(data(), folder)))
        cases = {
            "MIT License\n\nCopyright (c) 2025 Someone\n": "MIT",
            "Apache License\n Version 2.0, January 2004": "Apache 2.0",
            "                    GNU GENERAL PUBLIC LICENSE\n                       Version 3, 29 June 2007": "GPL 3.0",
            "Copyright (c) 2026 Luke Needham. All rights reserved.\n": "All rights reserved",
            "Some custom terms\nand more": "Some custom terms",
        }
        for text, name in cases.items():
            self.assertEqual(name, g.license_name(text), text)

    def test_links_sit_under_the_tagline_and_the_stores_are_offered_to_install_from(self):
        d = data()
        d["links"] = {"play-store": "https://play.google.com/x", "f-droid": "https://f-droid.org/y",
                      "web": "https://demo.example.com", "other": [{"title": "Privacy", "url": "https://example.com/p"}]}
        self.assertEqual([], g.problems(d))
        text = render(d)
        line = "[Google Play](https://play.google.com/x) · [F-Droid](https://f-droid.org/y) · [Web app](https://demo.example.com) · [Privacy](https://example.com/p)"
        self.assertIn(line, text)
        self.assertLess(text.index("# Demo App"), text.index(line))
        self.assertLess(text.index(line), text.index("## Description"))
        self.assertIn("1. Install it from [Google Play](https://play.google.com/x) or [F-Droid](https://f-droid.org/y), or get the latest build",
                      text)
        self.assertNotIn("·", render())

    def test_bad_links_are_reported(self):
        for links, expected in (({"play-store": "http://plain.example.com"}, "`links.play-store` must be an https URL"),
                                ({"steam": "https://x.com"}, "unknown field `links.steam`"),
                                ({"other": [{"title": "x"}]}, "`links.other[0]` needs"), ("https://x.com", "`links` must be a mapping")):
            d = data()
            d["links"] = links
            self.assertIn(expected, "\n".join(g.problems(d)))

    def test_free_text_cannot_add_a_section(self):
        d = data()
        d["description"] = "Text.\n\n## Features\n\n- a\n\n```\n# a comment in code\n```\n\n### Fine"
        found = "\n".join(g.problems(d))
        self.assertIn("`description` has the heading `## Features`", found)
        self.assertNotIn("a comment in code", found)
        self.assertNotIn("Fine", found)
        d["description"] = "Text."
        d["developer"] = {"notes": "# Notes"}
        d["sections"] = [{"title": "Privacy", "body": "## Inner"}]
        found = "\n".join(g.problems(d))
        self.assertIn("`developer.notes` has the heading", found)
        self.assertIn("`sections[0].body` has the heading", found)

    def test_every_app_has_screenshots_and_there_is_no_option_to_go_without(self):
        with app(screenshots=False) as folder:
            self.assertTrue(any("no screenshots" in f for f in g.problems(data(), folder)))
        with app() as folder:
            self.assertEqual([], g.problems(data(), folder))

    def test_screenshots_can_be_opted_out_of_with_manual_and_only_that(self):
        d = data()
        d["screenshots"] = "manual"
        self.assertEqual([], g.problems(d))
        with app() as folder:
            self.assertEqual([], g.problems(d, folder))
        with app(screenshots=False) as folder:
            self.assertIn("It says `screenshots: manual`, so commit one", "\n".join(g.problems(d, folder)))
            (folder / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot").mkdir(parents=True)
            self.assertIn("`screenshots: manual` but the app has a screenshot package", "\n".join(g.problems(d, folder)))
        for value in (False, True, "auto", ["a.png"]):
            d["screenshots"] = value
            self.assertIn("`screenshots` can only be `manual`", "\n".join(g.problems(d)))

    def test_the_screenshots_section_lists_every_image_of_the_folder(self):
        text = render()
        self.assertEqual(2, text.count("<img src=\"docs/screenshots/"))

    def test_the_number_in_the_image_name_orders_the_images_and_is_not_in_the_alt_text(self):
        self.assertEqual("Pull Request Page", g.alt_text("docs/screenshots/02-PullRequestPage.png"))
        text = render(screenshots=("docs/screenshots/01-HomePage.png", "docs/screenshots/02-SettingsPage.png"))
        self.assertLess(text.index("01-HomePage.png"), text.index("02-SettingsPage.png"))
        self.assertIn('alt="Home Page"', text)

    def test_problems_name_what_is_missing(self):
        text = "\n".join(g.problems({"name": "X", "extra": 1}))
        for expected in ("unknown field `extra`", "`tagline` is required", "`description` is required"):
            self.assertIn(expected, text)


WEB_TEMPLATE = TEMPLATE.parent / "readme-template-web.yml"
PACKAGE = '{"scripts": {"dev": "next dev", "build": "next build", "lint": "eslint .", "format": "prettier --write .", "test": "vitest run"}, "engines": {"node": "24.x"}}'


class website:
    """A folder with the files that the README of a website needs from the project: package.json, a lockfile and a LICENSE."""

    def __init__(self, lockfile="yarn.lock", package=PACKAGE, license="MIT License\n"):
        self.lockfile, self.package, self.license = lockfile, package, license

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        if self.package is not None:
            (folder / "package.json").write_text(self.package)
        if self.lockfile:
            (folder / self.lockfile).write_text("")
        if self.license is not None:
            (folder / "LICENSE").write_text(self.license)
        return folder

    def __exit__(self, *exc):
        self.tmp.cleanup()


def web_data():
    return yaml.safe_load(WEB_TEMPLATE.read_text())


class WebsiteReadmeTest(unittest.TestCase):
    def render(self, d=None, **folder):
        with website(**folder) as path:
            return g.render_web(d or web_data(), "LukeNeedham/Demo", g.web_facts(path))

    def test_the_template_is_valid(self):
        self.assertEqual([], g.problems(web_data(), stack="next-js"))
        with website() as folder:
            self.assertEqual([], g.problems(web_data(), folder, "next-js"))

    def test_the_layout_has_no_icon_screenshots_or_install_steps(self):
        text = self.render()
        headings = [l[3:] for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(["Description", "Getting started as a developer", "Contributing", "License"], headings)
        for left_out in ("app-icon", "Screenshots", "Android", "AppHub", "Getting started as a user"):
            self.assertNotIn(left_out, text)
        self.assertTrue(text.startswith("<!-- Generated from readme.yml"))
        self.assertIn("# Demo Site\n\nOne line", text)
        self.assertTrue(text.rstrip().endswith("MIT. See [LICENSE](LICENSE)."))

    def test_the_commands_come_from_the_package_manager_and_the_scripts_of_the_project(self):
        text = self.render()
        self.assertIn("Requirements: Node.js 24 and yarn.", text)
        for line in ("git clone https://github.com/LukeNeedham/Demo.git", "cd Demo", "yarn install", "yarn dev ", "yarn lint ",
                     "yarn format ", "yarn test ", "yarn build "):
            self.assertIn(line, text)
        self.assertNotIn("yarn typecheck", text, "the project has no such script")
        npm = self.render(lockfile="package-lock.json")
        self.assertIn("npm install", npm)
        self.assertIn("npm run build", npm)
        self.assertIn("Requirements: Node.js and pnpm.", self.render(lockfile="pnpm-lock.yaml", package='{"scripts": {}}'))

    def test_a_website_has_its_own_fields(self):
        d = web_data()
        d["screenshots"] = "manual"
        d["user"] = {"steps": ["x"]}
        found = "\n".join(g.problems(d, stack="next-js"))
        self.assertIn("unknown field `screenshots` (a website has no screenshots", found)
        self.assertIn("unknown field `user`", found)
        d = web_data()
        d["links"] = {"play-store": "https://play.google.com/x"}
        self.assertIn("unknown field `links.play-store` (only `other`)", "\n".join(g.problems(d, stack="next-js")))
        d["links"] = {"web": "https://demo.example.com"}
        self.assertIn("`links.web` is not a field: the production address is the `productionUrl`", "\n".join(g.problems(d, stack="next-js")))

    def test_links_notes_and_sections(self):
        d = web_data()
        d["links"] = {"other": [{"title": "Design", "url": "https://example.com/d"}]}
        d["developer"] = {"notes": "Copy `.env.example`."}
        d["sections"] = [{"title": "Credits", "body": "Photos by someone."}]
        self.assertEqual([], g.problems(d, stack="next-js"))
        text = self.render(d)
        self.assertIn("[Design](https://example.com/d)", text)
        self.assertNotIn("Website](", text, "the site has no productionUrl")
        order = [text.index(s) for s in ("## Description", "## Getting started as a developer", "Copy `.env.example`.", "## Credits", "## Contributing")]
        self.assertEqual(sorted(order), order)

    def test_the_production_link_is_the_production_url_of_the_site_in_apps_json(self):
        with tempfile.TemporaryDirectory() as tmp, website() as folder:
            apps = Path(tmp) / "apps.json"
            apps.write_text('[{"name": "Demo", "repo": "LukeNeedham/Demo", "stack": "next-js", "productionUrl": "https://demo.example.com"},'
                            ' {"name": "Other", "repo": "LukeNeedham/Other", "stack": "next-js"}]')
            self.assertEqual("https://demo.example.com", g.production_url("lukeneedham/demo", apps))
            self.assertEqual("", g.production_url("LukeNeedham/Other", apps), "listed, but with no productionUrl")
            self.assertEqual("", g.production_url("LukeNeedham/Unlisted", apps))
            d = web_data()
            d["links"] = {"other": [{"title": "Design", "url": "https://example.com/d"}]}
            text = g.render_web(d, "LukeNeedham/Demo", g.web_facts(folder, "LukeNeedham/Demo", apps))
            self.assertIn("[Website](https://demo.example.com) · [Design](https://example.com/d)\n\n## Description", text)
            self.assertLess(text.index("# Demo Site"), text.index("[Website]"))

    def test_every_website_of_apps_json_with_a_production_url_gets_it_in_its_readme(self):
        apps = json.loads(g.APPS_FILE.read_text())
        for app in apps:
            if app["stack"] == "next-js" and "productionUrl" in app:
                self.assertEqual(app["productionUrl"], g.production_url(app["repo"]))

    def test_the_project_must_have_a_package_json_a_lockfile_and_a_license(self):
        for kwargs, expected in (({"package": None}, "no package.json"), ({"lockfile": None}, "no lockfile"), ({"license": None}, "no LICENSE file")):
            with website(**kwargs) as folder:
                self.assertIn(expected, "\n".join(g.problems(web_data(), folder, "next-js")))

    def test_the_command_line_renders_and_checks_a_website(self):
        script = str(Path(g.__file__))
        with website() as folder:
            run = lambda *a: subprocess.run([sys.executable, script, str(folder), "--repo", "LukeNeedham/Demo", "--stack", "next-js", *a],
                                            capture_output=True, text=True)
            (folder / "readme.yml").write_text(WEB_TEMPLATE.read_text())
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(self.render(), (folder / "README.md").read_text())
            self.assertEqual(0, run("--check").returncode)
            (folder / "README.md").write_text("edited by hand\n")
            self.assertEqual(1, run("--check").returncode)

    def test_the_default_stack_is_still_the_android_app(self):
        with website() as folder:
            (folder / "readme.yml").write_text(WEB_TEMPLATE.read_text())
            result = subprocess.run([sys.executable, str(Path(g.__file__)), str(folder), "--repo", "LukeNeedham/Demo"], capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertIn("screenshots", result.stderr)


class SdkLevelsTest(unittest.TestCase):
    def levels(self, build, catalog=None):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "app").mkdir()
            (app / "app" / "build.gradle.kts").write_text(build)
            if catalog is not None:
                (app / "gradle").mkdir()
                (app / "gradle" / "libs.versions.toml").write_text(catalog)
            return g.sdk_levels(app)

    def test_literals_with_comments(self):
        self.assertEqual((26, 36), self.levels(BUILD))

    def test_other_ways_to_write_it(self):
        self.assertEqual((24, 35), self.levels("android {\n compileSdk { version = release(35) }\n defaultConfig { minSdkVersion(24) }\n}\n"))

    def test_a_commented_out_value_is_ignored(self):
        self.assertEqual((26, 36), self.levels("// minSdk = 21\n" + BUILD))

    def test_from_the_version_catalog(self):
        build = "android {\n compileSdk = libs.versions.compileSdk.get().toInt()\n defaultConfig { minSdk = libs.versions.min.sdk.get().toInt() }\n}\n"
        self.assertEqual((23, 36), self.levels(build, '[versions]\ncompileSdk = "36"\nmin-sdk = "23"\n'))

    def test_an_unreadable_min_sdk_is_an_error_not_a_guess(self):
        with self.assertRaises(g.SdkError):
            self.levels("android {\n compileSdk = 36\n}\n")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(g.SdkError):
            g.sdk_levels(Path(tmp))

    def test_an_unreadable_compile_sdk_is_just_missing(self):
        self.assertEqual((26, None), self.levels("android {\n defaultConfig { minSdk = 26 }\n}\n"))


class CommandLineTest(unittest.TestCase):
    def test_writing_and_check_mode(self):
        script = str(Path(g.__file__))
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            run = lambda *a: subprocess.run([sys.executable, script, tmp, "--repo", "LukeNeedham/Demo", *a], capture_output=True, text=True)
            (app / "readme.yml").write_text(TEMPLATE.read_text())
            self.assertEqual(1, run().returncode)  # no screenshots and no LICENSE yet
            (app / "docs" / "screenshots").mkdir(parents=True)
            (app / "docs" / "screenshots" / "HomePage.png").write_bytes(b"png")
            (app / "LICENSE").write_text("MIT License\n")
            self.assertIn("minimum Android version", run().stderr)  # no build file to read the minimum Android version from
            (app / "app").mkdir()
            (app / "app" / "build.gradle.kts").write_text(BUILD)
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(g.render(data(), "LukeNeedham/Demo", facts(screenshots=("docs/screenshots/HomePage.png",))), (app / "README.md").read_text())
            self.assertEqual(0, run("--check").returncode)
            (app / "README.md").write_text("edited by hand\n")
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(0, run("--check").returncode)


if __name__ == "__main__":
    unittest.main()
