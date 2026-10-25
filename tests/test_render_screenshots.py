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
    def app(self, source, gradlew="mkdir -p app/build/screenshots && echo png > app/build/screenshots/HomePage.png\necho \"$@\" > gradle-args.txt\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Path(tmp.name)
        if source is not None:
            path = app / "app" / "src" / "debug" / "kotlin" / "x" / "screenshot" / "HomePage.kt"
            path.parent.mkdir(parents=True)
            path.write_text(source)
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
        self.assertEqual(["HomePage.png"], [p.name for p in (app / "docs" / "screenshots").glob("*.png")])

    def test_a_package_that_shares_something_is_refused_before_gradle_runs(self):
        app = self.app(GOOD + "\nprivate val shared = 1\n")
        self.assertEqual(1, r.render(app, []))
        self.assertFalse((app / "gradle-args.txt").exists())

    def test_no_package_is_refused(self):
        self.assertEqual(1, r.render(self.app(None), []))

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


if __name__ == "__main__":
    unittest.main()
