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


def data():
    return yaml.safe_load(TEMPLATE.read_text())


def render(d=None, **kwargs):
    return g.render(d or data(), "LukeNeedham/Demo", 26, kwargs.pop("screenshots", SHOTS), kwargs.pop("compile_sdk", 36))


class GenerateReadmeTest(unittest.TestCase):
    def test_the_template_is_valid(self):
        self.assertEqual([], g.problems(data()))
        self.assertEqual([], g.problems(data(), ["docs/screenshots/HomePage.png"]))

    def test_the_layout_is_the_standard_one(self):
        text = render()
        headings = [l[3:] for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(["Description", "Screenshots", "Getting started as a user", "Getting started as a developer",
                          "Contributing", "License"], headings)
        self.assertLess(text.index("app-icon.png"), text.index("# Demo App"))
        self.assertIn("git clone https://github.com/LukeNeedham/Demo.git", text)
        self.assertIn("Edit readme.yml", text)

    def test_the_minimum_android_version_and_platform_come_from_the_project(self):
        text = render()
        self.assertIn("Requires Android 8.0 (API 26) or newer.", text)
        self.assertIn("Android SDK (platform 36)", text)
        self.assertIn("Requires Android API 99 or newer.", g.render(data(), "LukeNeedham/Demo", 99, SHOTS))
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

    def test_a_closed_app_links_no_license_file_and_install_can_be_replaced(self):
        d = data()
        d["license"] = "All rights reserved"
        d["user"] = {"install": "Get the APK from a PR."}
        text = render(d)
        self.assertNotIn("LICENSE", text)
        self.assertTrue(text.rstrip().endswith("All rights reserved."))
        self.assertIn("1. Get the APK from a PR.", text)
        self.assertNotIn("apphub", text.lower().replace("app-icon", ""))
        self.assertIn("See [LICENSE](LICENSE).", render())

    def test_screenshots_are_required_unless_the_app_opts_out(self):
        self.assertTrue(any("no screenshots" in f for f in g.problems(data(), [])))
        d = data()
        d["screenshots"] = False
        self.assertEqual([], g.problems(d, []))
        self.assertNotIn("Screenshots", render(d))
        d["screenshots"] = [{"path": "a.png"}]
        self.assertTrue(any("can only be `false`" in f for f in g.problems(d, ["x.png"])))

    def test_problems_name_what_is_missing(self):
        text = "\n".join(g.problems({"name": "X", "extra": 1}))
        for expected in ("unknown field `extra`", "`tagline` is required", "`description` is required", "`license` is required"):
            self.assertIn(expected, text)


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
            self.assertEqual(1, run().returncode)  # no screenshots yet
            (app / "docs" / "screenshots").mkdir(parents=True)
            (app / "docs" / "screenshots" / "HomePage.png").write_bytes(b"png")
            self.assertIn("minimum Android version", run().stderr)  # no build file to read the minimum Android version from
            (app / "app").mkdir()
            (app / "app" / "build.gradle.kts").write_text(BUILD)
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(g.render(data(), "LukeNeedham/Demo", 26, ["docs/screenshots/HomePage.png"], 36), (app / "README.md").read_text())
            self.assertEqual(0, run("--check").returncode)
            (app / "README.md").write_text("edited by hand\n")
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(0, run("--check").returncode)


if __name__ == "__main__":
    unittest.main()
