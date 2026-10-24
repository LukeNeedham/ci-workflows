import unittest
from pathlib import Path

import _paths  # noqa: F401
import sync_apps as s

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ACTIONS = ROOT / ".github" / "actions"


class ScreenshotsSetupTest(unittest.TestCase):
    def test_the_template_is_filled_with_the_apps_namespace_and_renders_the_right_previews(self):
        template = (SCRIPTS / "screenshots" / "PageScreenshotTest.kt.template").read_text()
        self.assertTrue(template.startswith("package {{PACKAGE}}"))
        # Only the screenshot package of the app is scanned, whatever the names, so the general previews are not rendered
        self.assertIn('scanPackageTrees("{{PACKAGE}}.screenshot")', template)
        self.assertNotIn("PageContentPreview", template)
        self.assertIn("require(names.distinct()", template)

    def test_the_init_script_fills_the_template_and_the_script_hands_it_over(self):
        init = (SCRIPTS / "screenshots" / "screenshots.init.gradle").read_text()
        self.assertIn("replace('{{PACKAGE}}'", init)
        self.assertIn("screenshots.template", init)
        render = (SCRIPTS / "render_screenshots.py").read_text()
        for name in ("screenshots.init.gradle", "PageScreenshotTest.kt.template", "-Pscreenshots.template", "problems"):
            self.assertIn(name, render)

    def test_each_action_runs_scripts_that_exist(self):
        for action in ("app-icon", "screenshots", "readme"):
            text = (ACTIONS / action / "action.yml").read_text()
            self.assertIn("using: composite", text, action)
            used = {name for name in __import__("re").findall(r"scripts/([\w.]+\.py)", text)}
            self.assertTrue(used, action)
            for script in used:
                self.assertTrue((SCRIPTS / script).is_file(), f"{action} runs scripts/{script}, which does not exist")

    def test_the_block_tells_claude_about_the_screenshot_package(self):
        block = " ".join(s.claude_block().split())
        self.assertIn("package `screenshot`", block)
        self.assertIn("nothing is shared between screenshots", block)
        self.assertIn("docs/pages.md", block)
        self.assertIn("never `XScreen`", block)
        self.assertNotIn("AppScreenshotMockData", block)

    def test_the_block_names_the_viewmodel_and_does_not_imply_a_screenshot_per_page(self):
        block = " ".join(s.claude_block().split())
        self.assertIn("`XViewModel`", block)
        self.assertIn("a page can have several, or none", block)
        self.assertNotIn("one file per page", block)


if __name__ == "__main__":
    unittest.main()
