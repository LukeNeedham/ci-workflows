import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import screenshots_wanted as w
from check_screenshot_package import package_files


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

    def test_an_app_without_a_package_renders_nothing_and_keeps_its_hand_committed_screenshots(self):
        why = w.skip_reason(self.app("name: A\n", ["other/HomePage.kt"]))
        self.assertIn("No screenshot package", why)
        self.assertIn("committed by hand", why)

    def test_there_is_no_option_to_go_without_screenshots(self):
        # readme.yml is not read at all: a leftover `screenshots: false` changes nothing
        self.assertIsNone(w.skip_reason(self.app("name: A\nscreenshots: false\n", ["screenshot/HomePage.kt"])))

    def test_the_package_is_a_screenshot_folder_outside_the_build_output(self):
        app = self.app(None, ["screenshot/A.kt", "deeper/screenshot/B.kt", "screenshots/C.kt"])
        build = app / "app" / "src" / "build" / "screenshot"
        build.mkdir(parents=True)
        (build / "D.kt").write_text("x")
        self.assertEqual(["A.kt", "B.kt"], sorted(p.name for p in package_files(app)))


if __name__ == "__main__":
    unittest.main()
