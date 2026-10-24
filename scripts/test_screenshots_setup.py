import unittest
from pathlib import Path

import sync_apps as s

SCRIPTS = Path(__file__).resolve().parent


class ScreenshotsSetupTest(unittest.TestCase):
    def test_the_template_is_filled_with_the_apps_namespace_and_renders_the_right_previews(self):
        template = (SCRIPTS / "screenshots" / "PageScreenshotTest.kt.template").read_text()
        self.assertTrue(template.startswith("package {{PACKAGE}}"))
        self.assertIn('scanPackageTrees("{{PACKAGE}}")', template)
        self.assertIn('"PageContentScreenshot"', template)
        # The general previews are never rendered
        self.assertNotIn("PageContentPreview", template)

    def test_the_init_script_fills_the_template_and_the_script_hands_it_over(self):
        init = (SCRIPTS / "screenshots" / "screenshots.init.gradle").read_text()
        self.assertIn("replace('{{PACKAGE}}'", init)
        self.assertIn("screenshots.template", init)
        sh = (SCRIPTS / "render_screenshots.sh").read_text()
        for name in ("screenshots.init.gradle", "PageScreenshotTest.kt.template", "-Pscreenshots.template"):
            self.assertIn(name, sh)

    def test_the_block_tells_claude_about_the_screenshot_composables(self):
        block = s.claude_block()
        self.assertIn("XPageContentScreenshot", block)
        self.assertIn("AppScreenshotMockData", block)


if __name__ == "__main__":
    unittest.main()
