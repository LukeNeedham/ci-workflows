import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

import generate_readme as g

TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "readme-template.yml"


def data():
    return yaml.safe_load(TEMPLATE.read_text())


class GenerateReadmeTest(unittest.TestCase):
    def test_the_template_is_valid(self):
        self.assertEqual([], g.problems(data()))
        self.assertEqual([], g.problems(data(), ["docs/screenshots/Home.png"]))

    def test_the_layout_is_the_standard_one(self):
        text = g.render(data(), "LukeNeedham/Demo")
        headings = [l[3:] for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(["Description", "Getting started as a user", "Getting started as a developer",
                          "Project structure", "Contributing", "License"], headings)
        self.assertLess(text.index("app-icon.png"), text.index("# Demo App"))
        self.assertIn("git clone https://github.com/LukeNeedham/Demo.git", text)
        self.assertIn("Requires Android 8.0 (API 26) or newer.", text)
        self.assertIn("2. Open the app", text)
        self.assertIn("Edit readme.yml", text)

    def test_optional_parts_appear_between_the_right_sections(self):
        d = data()
        d["sections"] = [{"title": "Privacy", "body": "None."}]
        d["developer"] = {"notes": "Create local.properties."}
        text = g.render(d, "LukeNeedham/Demo", ["docs/screenshots/Home.png", "docs/screenshots/PullRequest.png"])
        self.assertIn('<img src="docs/screenshots/PullRequest.png" width="240" alt="Pull Request">', text)
        order = [text.index(s) for s in ("## Description", "## Screenshots", "## Getting started as a user",
                                         "Create local.properties.", "## Project structure", "## Privacy", "## Contributing")]
        self.assertEqual(sorted(order), order)

    def test_a_closed_app_links_no_license_file_and_install_can_be_replaced(self):
        d = data()
        d["license"] = "All rights reserved"
        d["user"]["install"] = "Get the APK from a PR."
        text = g.render(d, "LukeNeedham/Demo")
        self.assertNotIn("LICENSE", text)
        self.assertTrue(text.rstrip().endswith("All rights reserved."))
        self.assertIn("1. Get the APK from a PR.", text)
        self.assertNotIn("apphub", text.lower().replace("app-icon", ""))
        self.assertIn("See [LICENSE](LICENSE).", g.render(data(), "LukeNeedham/Demo"))

    def test_screenshots_are_required_unless_the_app_opts_out(self):
        self.assertTrue(any("no screenshots" in f for f in g.problems(data(), [])))
        d = data()
        d["screenshots"] = False
        self.assertEqual([], g.problems(d, []))
        self.assertNotIn("Screenshots", g.render(d, "LukeNeedham/Demo", ["docs/screenshots/Home.png"]))
        d["screenshots"] = [{"path": "a.png"}]
        self.assertTrue(any("can only be `false`" in f for f in g.problems(d, ["x.png"])))

    def test_problems_name_what_is_missing(self):
        found = g.problems({"name": "X", "extra": 1, "user": {}})
        text = "\n".join(found)
        for expected in ("unknown field `extra`", "`tagline` is required", "`structure` must be", "`user.min-android`"):
            self.assertIn(expected, text)

    def test_writing_and_check_mode(self):
        script = str(Path(g.__file__))
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run([sys.executable, script, tmp, "--repo", "LukeNeedham/Demo", *a], capture_output=True, text=True)
            (Path(tmp) / "readme.yml").write_text(TEMPLATE.read_text())
            self.assertEqual(1, run().returncode)  # no screenshots yet
            (Path(tmp) / "docs" / "screenshots").mkdir(parents=True)
            (Path(tmp) / "docs" / "screenshots" / "Home.png").write_bytes(b"png")
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            shots = ["docs/screenshots/Home.png"]
            self.assertEqual(g.render(data(), "LukeNeedham/Demo", shots), (Path(tmp) / "README.md").read_text())
            self.assertEqual(0, run("--check").returncode)
            (Path(tmp) / "README.md").write_text("edited by hand\n")
            self.assertEqual(1, run("--check").returncode)
            self.assertEqual(0, run().returncode)
            self.assertEqual(0, run("--check").returncode)


if __name__ == "__main__":
    unittest.main()
