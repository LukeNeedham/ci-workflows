import unittest
from pathlib import Path

import check_readme as c

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "readme-template.md").read_text()


class CheckReadmeTest(unittest.TestCase):
    def test_the_template_follows_the_format(self):
        self.assertEqual([], c.problems(TEMPLATE))

    def test_a_bare_readme_fails(self):
        found = c.problems("# Demo\n\nHello\n")
        self.assertTrue(any("icon" in f for f in found))
        self.assertTrue(any("## Description" in f for f in found))

    def test_the_markdown_icon_form_is_accepted(self):
        text = TEMPLATE.replace('<img src="app-icon.png" width="128" alt="<App name> icon">', "![icon](app-icon.png)")
        self.assertEqual([], c.problems(text))

    def test_the_icon_must_come_before_the_title(self):
        text = "# Demo\n\n" + TEMPLATE.split("# <App name>")[0] + TEMPLATE.split("# <App name>", 1)[1]
        self.assertTrue(any("icon" in f for f in c.problems(text)))

    def test_sections_must_be_in_order(self):
        text = TEMPLATE.replace("## License", "## Zzz").replace("## Description", "## License").replace("## Zzz", "## Description")
        self.assertTrue(any("out of order" in f for f in c.problems(text)))

    def test_extra_sections_are_allowed(self):
        self.assertEqual([], c.problems(TEMPLATE.replace("## Contributing", "## Privacy\n\nNone.\n\n## Contributing")))


if __name__ == "__main__":
    unittest.main()
