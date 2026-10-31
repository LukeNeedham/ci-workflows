import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import screenshots_wanted as w
from conventions.screenshots import package_files


class ScreenshotsWantedTest(unittest.TestCase):
    def app(self, readme=None, screenshot_files=()):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Path(tmp.name)
        if readme is not None:
            (app / "readme.yml").write_text(readme)
        for name in screenshot_files:
            path = app / "app" / "src" / "debug" / "kotlin" / "x" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("package x.screenshot\n")
        return app

    def test_an_app_with_a_screenshot_package_has_screenshots_to_render(self):
        self.assertIsNone(w.skip_reason(self.app("name: A\n", ["screenshot/HomePage.kt"])))

    def test_an_app_that_opted_out_without_a_package_renders_nothing_and_keeps_its_hand_committed_screenshots(self):
        app = self.app("name: A\nscreenshots: manual  # a WebView wrapper\n")
        (app / "docs" / "screenshots").mkdir(parents=True)
        (app / "docs" / "screenshots" / "Home.png").write_bytes(b"png")
        why = w.skip_reason(app)
        self.assertIn("screenshots: manual", why)
        self.assertIn("committed by hand", why)

    def test_everything_else_is_left_to_the_render_to_fail(self):
        # No package, no opt-out: even with a committed screenshot, rendering has to fail, so it is not skipped
        app = self.app("name: A\n")
        (app / "docs" / "screenshots").mkdir(parents=True)
        (app / "docs" / "screenshots" / "Home.png").write_bytes(b"png")
        self.assertIsNone(w.skip_reason(app))
        # Opted out but a package exists (even an empty one): the render fails and says to remove one
        for files in ([], ["screenshot/HomePage.kt"]):
            both = self.app("name: A\nscreenshots: manual\n", files)
            (both / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot").mkdir(parents=True, exist_ok=True)
            self.assertIsNone(w.skip_reason(both))
        # Opting out is `screenshots: manual` and nothing else
        self.assertIsNone(w.skip_reason(self.app("name: A\nscreenshots: auto\n")))
        self.assertIsNone(w.skip_reason(self.app("name: A\n# screenshots: manual\n")))

    def test_an_app_without_a_readme_yml_is_not_held_to_the_screenshot_rules_yet(self):
        # Not migrated: only a warning, nothing rendered, so merging the workflows leaves its CI green
        why = w.skip_reason(self.app(None, ["screenshot/HomePage.kt"]))
        self.assertIn("no readme.yml yet", why.lower())

    def test_the_opt_out_is_read_like_the_yaml_reads_it(self):
        for text in ("screenshots: manual\n", 'screenshots: "manual"\n', "screenshots: 'manual'  # a wrapper\n"):
            self.assertIn("manual", w.skip_reason(self.app("name: A\n" + text)), text)
        for text in ("screenshots:\nmanual\n", "screenshots: manually\n", " screenshots: manual\n"):
            self.assertIsNone(w.skip_reason(self.app("name: A\n" + text)), text)

    def test_the_package_is_a_screenshot_folder_outside_the_build_output(self):
        app = self.app(None, ["screenshot/A.kt", "deeper/screenshot/B.kt", "screenshots/C.kt"])
        build = app / "app" / "src" / "build" / "screenshot"
        build.mkdir(parents=True)
        (build / "D.kt").write_text("x")
        self.assertEqual(["A.kt", "B.kt"], sorted(p.name for p in package_files(app)))


if __name__ == "__main__":
    unittest.main()
