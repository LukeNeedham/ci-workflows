import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
import sync_apps as s

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ACTIONS = ROOT / ".github" / "actions"


class ScreenshotsSetupTest(unittest.TestCase):
    def test_the_test_is_plain_code_that_takes_the_namespace_of_the_app_from_a_system_property(self):
        test = (SCRIPTS / "screenshots" / "test" / "PageScreenshotTest.kt").read_text()
        self.assertTrue(test.startswith("package com.lukeneedham.screenshots"))
        self.assertNotIn("{{", test)
        # Only the screenshot package of the app is scanned, whatever the names, so the general previews are not rendered
        self.assertIn('scanPackageTrees("${System.getProperty("screenshots.package")}.screenshot")', test)
        self.assertNotIn("Preview()", test)
        self.assertIn("require(names.distinct()", test)
        # Every screenshot is rendered in inspection mode, as in Android Studio, so no screenshot wraps itself for it
        self.assertIn("LocalInspectionMode provides true", test)
        self.assertFalse(list((SCRIPTS / "screenshots").glob("*.template")))

    def test_the_init_script_sets_the_namespace_and_the_script_hands_over_the_test(self):
        init = (SCRIPTS / "screenshots" / "screenshots.init.gradle").read_text()
        # read once after evaluation, as a plain value: a task that reads the project when it runs breaks the configuration cache
        self.assertIn("def screenshotsPackage = android.namespace", init)
        self.assertIn("systemProperty 'screenshots.package', screenshotsPackage", init)
        self.assertNotIn("doFirst", init)
        self.assertIn("screenshots.sources", init)
        # The app's own unit tests are left out of the run
        self.assertIn("setSrcDirs(own)", init)
        # ... also by excluding every file outside the test of ci-workflows from the unit test compile tasks, whatever the
        # Kotlin plugin does with the source sets (the app's src/test/kotlin was compiled without it)
        self.assertIn("compile.*UnitTest(Kotlin|JavaWithJavac)", init)
        self.assertIn("!element.file.toPath().startsWith(testSources.toPath())", init)
        # Gradle must always run the test: skipping it as up to date would render nothing
        self.assertIn("outputs.upToDateWhen { false }", init)
        self.assertIn("outputs.cacheIf { false }", init)
        self.assertIn("exceptionFormat 'full'", init)  # a failing preview says why in the CI log
        test = (SCRIPTS / "screenshots" / "test" / "PageScreenshotTest.kt").read_text()
        self.assertIn('captureRoboImage("build/screenshots/', test)
        render = (SCRIPTS / "render_screenshots.py").read_text()
        for name in ("screenshots.init.gradle", "-Pscreenshots.sources", "problems"):
            self.assertIn(name, render)

    def test_each_action_runs_scripts_that_exist(self):
        for action in ("app-icon", "screenshots", "readme"):
            text = (ACTIONS / action / "action.yml").read_text()
            self.assertIn("using: composite", text, action)
            used = {name for name in re.findall(r"\$CI_SCRIPTS/([\w.]+\.py)", text)}
            self.assertTrue(used, action)
            for script in used:
                self.assertTrue((SCRIPTS / script).is_file(), f"{action} runs scripts/{script}, which does not exist")

    def test_the_block_tells_claude_about_the_screenshot_package(self):
        block = " ".join(s.claude_block().split())
        self.assertIn("package `screenshot`", block)
        self.assertIn("nothing is shared", block)
        self.assertIn("never `XScreen`", block)
        self.assertNotIn("AppScreenshotMockData", block)

    def test_the_block_names_the_viewmodel_and_does_not_imply_a_screenshot_per_page(self):
        block = " ".join(s.claude_block().split())
        self.assertIn("`XViewModel`", block)
        self.assertIn("`Route.X`", block)
        self.assertIn("a page can have several, or none", block)
        self.assertNotIn("one file per page", block)


if __name__ == "__main__":
    unittest.main()
