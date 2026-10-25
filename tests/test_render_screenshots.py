import os
import stat
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import render_screenshots as r

GOOD = """package x.screenshot

@Preview
@Composable
private fun HomePageScreenshot() {
    val state = 1
}
"""


class RenderScreenshotsTest(unittest.TestCase):
    def app(self, source, order="HomePage\n", gradlew="mkdir -p app/build/screenshots && echo png > app/build/screenshots/HomePage.png\necho \"$@\" > gradle-args.txt\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Path(tmp.name)
        if source is not None:
            path = app / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot" / "HomePage.kt"
            path.parent.mkdir(parents=True)
            path.write_text(source)
            if order is not None:
                (path.parent / "order.txt").write_text(order)
        script = app / "gradlew"
        script.write_text("#!/usr/bin/env bash\n" + gradlew)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return app

    def test_a_valid_package_is_rendered_with_the_init_script_and_the_template(self):
        app = self.app(GOOD)
        (app / "docs" / "screenshots").mkdir(parents=True)
        (app / "docs" / "screenshots" / "Removed.png").write_text("stale")
        self.assertEqual(0, r.render(app, ["--no-daemon"]))
        args = (app / "gradle-args.txt").read_text()
        for expected in ("testDebugUnitTest", "*PageScreenshotTest", "--init-script", "screenshots.init.gradle",
                         "-Pscreenshots.template=", "PageScreenshotTest.kt.template", "--no-daemon"):
            self.assertIn(expected, args)
        # The rendered set replaces the committed one as a whole: the stale image is gone
        self.assertEqual(["01-HomePage.png"], [p.name for p in (app / "docs" / "screenshots").glob("*.png")])

    def test_a_package_that_shares_something_is_refused_before_gradle_runs(self):
        app = self.app(GOOD + "\nprivate val shared = 1\n")
        self.assertEqual(1, r.render(app, []))
        self.assertFalse((app / "gradle-args.txt").exists())

    def test_no_package_is_refused(self):
        self.assertEqual(1, r.render(self.app(None), []))

    def test_an_app_that_opted_out_of_the_generated_screenshots_cannot_also_have_a_package(self):
        app = self.app(GOOD)
        (app / "readme.yml").write_text("name: A\nscreenshots: manual\n")
        self.assertEqual(1, r.render(app, []))
        self.assertFalse((app / "gradle-args.txt").exists())

    def test_an_empty_package_a_missing_order_file_and_a_package_without_screenshots_are_refused(self):
        empty = self.app(None)
        (empty / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot").mkdir(parents=True)
        no_kotlin = self.app(None)
        (no_kotlin / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot").mkdir(parents=True)
        (no_kotlin / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot" / "order.txt").write_text("HomePage\n")
        no_order = self.app(GOOD, order=None)
        no_previews = self.app("package x.screenshot\n\n// nothing here\n", order="")
        for app in (empty, no_kotlin, no_order, no_previews):
            self.assertEqual(1, r.render(app, []))
            self.assertFalse((app / "gradle-args.txt").exists())

    def test_a_failing_gradle_run_fails(self):
        self.assertEqual(3, r.render(self.app(GOOD, gradlew="exit 3\n"), []))

    def test_a_run_that_rendered_nothing_fails(self):
        self.assertEqual(1, r.render(self.app(GOOD, gradlew="mkdir -p app/build/screenshots\n"), []))

    def test_the_committed_screenshots_stay_unless_the_new_ones_are_rendered(self):
        for gradlew in ("exit 3\n", "mkdir -p app/build/screenshots\n"):
            app = self.app(GOOD, gradlew=gradlew)
            (app / "docs" / "screenshots").mkdir(parents=True)
            (app / "docs" / "screenshots" / "Kept.png").write_text("committed")
            self.assertNotEqual(0, r.render(app, []))
            self.assertEqual("committed", (app / "docs" / "screenshots" / "Kept.png").read_text(), gradlew)

    def test_images_left_in_the_build_folder_by_an_earlier_run_do_not_count(self):
        app = self.app(GOOD, gradlew="exit 0\n")
        (app / "app" / "build" / "screenshots").mkdir(parents=True)
        (app / "app" / "build" / "screenshots" / "Old.png").write_text("old")
        self.assertEqual(1, r.render(app, []))


    def test_the_images_are_numbered_by_their_position_in_the_order_file(self):
        two = GOOD + "\n@Preview\n@Composable\nprivate fun SettingsPageScreenshot() {\n    val state = 1\n}\n"
        gradlew = ("mkdir -p app/build/screenshots && echo a > app/build/screenshots/HomePage.png "
                   "&& echo b > app/build/screenshots/SettingsPage.png\n")
        app = self.app(two, order="# the order of the README\nSettingsPage\n\nHomePage  # first look\n", gradlew=gradlew)
        self.assertEqual(0, r.render(app, []))
        shots = app / "docs" / "screenshots"
        self.assertEqual(["01-SettingsPage.png", "02-HomePage.png"], sorted(p.name for p in shots.glob("*.png")))
        self.assertEqual("b", (shots / "01-SettingsPage.png").read_text().strip())

    def test_the_number_has_the_width_of_the_list(self):
        self.assertEqual({"A": "01-A.png", "B": "02-B.png"}, r.numbered(["A", "B"]))
        self.assertEqual("007-X.png", r.numbered(list("ABCDEF") + ["X"] + ["Y"] * 100)["X"])

    def test_the_order_file_is_required_and_has_to_match_the_package(self):
        for order, expected in ((None, "order.txt is missing"), ("", "`HomePageScreenshot` is not in order.txt"),
                                ("HomePage\nGone\n", "`Gone` in order.txt is not a screenshot"),
                                ("HomePage\nHomePage\n", "`HomePage` is listed twice")):
            app = self.app(GOOD, order=order)
            self.assertEqual(1, r.render(app, []), order)
            self.assertFalse((app / "gradle-args.txt").exists(), order)

    def test_a_listed_screenshot_that_was_not_rendered_fails_and_keeps_the_committed_ones(self):
        app = self.app(GOOD, gradlew="mkdir -p app/build/screenshots && echo a > app/build/screenshots/Other.png\n")
        (app / "docs" / "screenshots").mkdir(parents=True)
        (app / "docs" / "screenshots" / "Kept.png").write_text("committed")
        self.assertEqual(1, r.render(app, []))
        self.assertEqual("committed", (app / "docs" / "screenshots" / "Kept.png").read_text())


if __name__ == "__main__":
    unittest.main()
