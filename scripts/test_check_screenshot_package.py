import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "screenshots"))
import check_screenshot_package as c

GOOD = '''package com.lukeneedham.demo.screenshot

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview

/**
 * Rendered by CI to docs/screenshots/HomePage.png.
 */
@OptIn(ExperimentalCoilApi::class)
@Preview
@Composable
private fun HomePageScreenshot() {
    val state = HomeUiState(items = listOf("a"))
    fun helper() = 1
    AppTheme {
        HomePageContent(state = state)
    }
}

// A second screenshot of the page, with data of its own
@Preview
@Composable
private fun HomeEmptyPageScreenshot() {
    AppTheme { HomePageContent(state = HomeUiState()) }
}
'''


class CheckScreenshotPackageTest(unittest.TestCase):
    def test_private_previews_with_their_own_data_pass(self):
        self.assertEqual([], c.problems(GOOD))

    def test_each_way_of_sharing_fails(self):
        for bad in (
            "private val state = HomeUiState()\n",
            "val state = HomeUiState()\n",
            "internal object SharedMockData {\n    val x = 1\n}\n",
            "private fun helper() = 1\n",
            "internal fun helper() = 1\n",
            "class Fake\n",
            "data class Fake(val a: Int)\n",
            "typealias State = HomeUiState\n",
        ):
            self.assertEqual(1, len(c.problems(GOOD + "\n" + bad)), bad)

    def test_a_preview_must_be_private_and_take_no_parameters(self):
        for bad in (
            "@Preview\n@Composable\nfun HomePageScreenshot() {\n}\n",
            "@Preview\n@Composable\ninternal fun HomePageScreenshot() {\n}\n",
            "@Preview\n@Composable\nprivate fun HomePageScreenshot(state: HomeUiState) {\n}\n",
        ):
            self.assertEqual(1, len(c.problems(GOOD + "\n" + bad)), bad)

    def test_a_composable_that_is_not_a_preview_fails(self):
        self.assertEqual(1, len(c.problems(GOOD + "\n@Composable\nprivate fun Helper() {\n}\n")))

    def test_the_line_of_the_problem_is_reported(self):
        self.assertEqual([(3, "val x = 1")], c.problems("package a\n\nval x = 1\n"))


if __name__ == "__main__":
    unittest.main()
