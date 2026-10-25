"""Tests for sync_apps.py. Run: python3 -m unittest discover -s tests"""

import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import sync_apps as s

TOOLS = s.TOOLS


class SyncApp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative, text):
        path = self.dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_a_new_app_gets_the_skill_the_callers_and_the_block(self):
        changed = s.sync_app(self.dir)

        self.assertIn(".claude/skills/lukeneedham-conventions/SKILL.md", changed)
        for name in s.CALLERS:
            self.assertTrue((self.dir / ".github" / "workflows" / name).is_file(), name)
        claude = (self.dir / "CLAUDE.md").read_text()
        self.assertIn(s.BLOCK_BEGIN, claude)
        self.assertTrue(claude.startswith("# Instructions for Claude"))

    def test_a_second_run_changes_nothing(self):
        s.sync_app(self.dir)
        self.assertEqual([], s.sync_app(self.dir))

    def test_the_callers_are_copied_byte_for_byte_over_whatever_the_app_has(self):
        self.write(".github/workflows/trigger_on_pull_request.yml", "name: Old\nwith:\n  apk-path: old.apk\n")

        changed = s.sync_callers(self.dir)

        self.assertIn(".github/workflows/trigger_on_pull_request.yml", changed)
        for name in s.CALLERS:
            self.assertEqual((TOOLS / "callers" / name).read_bytes(), (self.dir / ".github/workflows" / name).read_bytes(), name)

    def test_the_callers_hold_no_settings(self):
        for path in sorted((TOOLS / "callers").glob("*.yml")):
            for line in path.read_text().splitlines():
                self.assertNotRegex(line, r"^\s*#?\s*(apk-path|gradle-task|java-version|java-distribution|timezone|comment-header|asset-name):", path.name)
            self.assertNotRegex(path.read_text(), r"(?m)^\s*branches:", path.name)

    def test_a_caller_has_one_comment_saying_where_it_is_copied_from(self):
        for name in s.CALLERS:
            comments = [l for l in (TOOLS / "callers" / name).read_text().splitlines() if "#" in l]
            self.assertEqual(
                [f"# Copied from LukeNeedham/ci-workflows (callers/{name}). Do not edit it here: change it there."],
                comments, name)

    def test_every_app_gets_every_caller_including_the_release_one(self):
        s.sync_callers(self.dir)
        for name in ("trigger_on_pull_request.yml", "build_main.yml", "delete_prereleases.yml", "release.yml"):
            self.assertTrue((self.dir / ".github/workflows" / name).is_file(), name)
        self.assertEqual(sorted(p.name for p in (TOOLS / "callers").glob("*.yml")), sorted(s.CALLERS))

    def test_the_skill_is_mirrored_and_stray_files_go(self):
        self.write(".claude/skills/lukeneedham-conventions/SKILL.md", "old")
        self.write(".claude/skills/lukeneedham-conventions/stray.md", "x")

        changed = s.sync_skill(self.dir)

        self.assertIn(".claude/skills/lukeneedham-conventions/stray.md", changed)
        self.assertFalse((self.dir / ".claude/skills/lukeneedham-conventions/stray.md").exists())
        source = (TOOLS / "skills/lukeneedham-conventions/SKILL.md").read_text()
        self.assertEqual(source, (self.dir / ".claude/skills/lukeneedham-conventions/SKILL.md").read_text())

    def test_the_old_copy_it_by_hand_line_becomes_the_block(self):
        self.write("CLAUDE.md", """# Instructions for Claude

- Before starting work, check that `.claude/skills/lukeneedham-conventions` matches
  `skills/lukeneedham-conventions` on `main` of `LukeNeedham/ci-workflows`; if not, copy it over and
  include that in this work's PR. See that repo's `docs/skill.md`.
- Another rule.
""")

        s.sync_claude_md(self.dir)

        text = (self.dir / "CLAUDE.md").read_text()
        self.assertNotIn("Before starting work", text)
        self.assertIn(s.BLOCK_BEGIN, text)
        self.assertIn("- Another rule.", text)

    def test_the_old_instruction_goes_even_when_the_block_is_already_there(self):
        old = ("Before starting work, check that `.claude/skills/lukeneedham-conventions` matches `skills/lukeneedham-conventions`"
               " on `main` of `LukeNeedham/ci-workflows`; if not, copy it over and include that in this work's PR."
               " See that repo's `docs/skill.md`.\n")
        self.write("CLAUDE.md", "# Instructions\n\n- Rule.\n\n" + old + "\n" + s.BLOCK_BEGIN + "\nstale\n" + s.BLOCK_END + "\n")

        s.sync_claude_md(self.dir)

        text = (self.dir / "CLAUDE.md").read_text()
        self.assertNotIn("Before starting work", text)
        self.assertEqual(1, text.count(s.BLOCK_BEGIN))
        self.assertIn("- Rule.\n\n" + s.BLOCK_BEGIN, text)
        self.assertEqual([], s.sync_claude_md(self.dir))

    def test_an_existing_block_is_replaced_not_added_again(self):
        self.write("CLAUDE.md", "# Instructions\n\n" + s.BLOCK_BEGIN + "\nstale\n" + s.BLOCK_END + "\n\n- Rule.\n")

        s.sync_claude_md(self.dir)

        text = (self.dir / "CLAUDE.md").read_text()
        self.assertEqual(1, text.count(s.BLOCK_BEGIN))
        self.assertNotIn("stale", text)
        self.assertIn("- Rule.", text)

    def test_the_block_tells_claude_the_readme_standard(self):
        s.sync_claude_md(self.dir)
        self.assertIn("docs/readme-template.yml", (self.dir / "CLAUDE.md").read_text())

    def test_the_readme_source_is_reported_but_nothing_is_written(self):
        self.assertEqual("readme.yml is missing", s.readme_note(self.dir))
        self.write("readme.yml", "name: Demo\n")
        self.assertIn("readme.yml is invalid", s.readme_note(self.dir))
        self.write("readme.yml", (TOOLS / "docs/readme-template.yml").read_text())
        self.assertIn("no screenshots", s.readme_note(self.dir))
        self.write("docs/screenshots/Home.png", "png")
        self.assertIn("no LICENSE file", s.readme_note(self.dir))
        self.write("LICENSE", "MIT License\n")
        # The app has a readme.yml, so it is held to the screenshot rules: its package is missing
        self.assertIn("no screenshot package", s.readme_note(self.dir))
        self.write("app/src/debug/kotlin/x/screenshot/HomePage.kt",
                   "package x.screenshot\n\n@Preview\n@Composable\nprivate fun HomePageScreenshot() {\n}\n")
        self.assertIn("order.txt is missing", s.readme_note(self.dir))
        self.write("app/src/debug/kotlin/x/screenshot/order.txt", "HomePage\n")
        self.assertEqual("", s.readme_note(self.dir))
        # An app that opted out has no package to report
        (self.dir / "app/src/debug/kotlin/x/screenshot/order.txt").unlink()
        (self.dir / "app/src/debug/kotlin/x/screenshot/HomePage.kt").unlink()
        (self.dir / "app/src/debug/kotlin/x/screenshot").rmdir()
        self.write("readme.yml", (TOOLS / "docs/readme-template.yml").read_text() + "\nscreenshots: manual\n")
        self.assertEqual("", s.readme_note(self.dir))
        s.sync_app(self.dir)
        self.assertFalse((self.dir / "README.md").exists())

class Api(unittest.TestCase):
    def test_a_request_with_a_body_declares_json(self):
        from unittest import mock
        seen = {}

        def fake_open(request):
            seen.update(request.headers)
            raise RuntimeError("stop")

        with mock.patch("urllib.request.urlopen", fake_open):
            with self.assertRaises(RuntimeError):
                s.api("t", "POST", "/repos/o/r/pulls", {"title": "x"})
        self.assertEqual("application/json", seen["Content-type"])
        self.assertEqual("Bearer t", seen["Authorization"])


if __name__ == "__main__":
    unittest.main()
