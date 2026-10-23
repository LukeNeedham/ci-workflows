"""Tests for sync_apps.py. Run: python3 -m unittest discover -s scripts"""

import tempfile
import unittest
from pathlib import Path

import sync_apps as s

TOOLS = s.TOOLS


def app(**extra):
    return {"name": "Demo", "repo": "LukeNeedham/Demo", **extra}


class ReadAndRender(unittest.TestCase):
    template = (TOOLS / "examples" / "trigger_on_pull_request.yml").read_text()

    def test_the_unchanged_template_reads_its_own_apk_path_and_branch(self):
        inputs, branches = s.read_inputs(self.template)
        self.assertEqual({"apk-path": s.DEFAULT_APK_PATH}, inputs)
        self.assertEqual(["main"], branches)

    def test_rendering_with_the_templates_own_values_changes_nothing(self):
        inputs, branches = s.read_inputs(self.template)
        self.assertEqual(self.template, s.render_caller(self.template, inputs, branches))

    def test_an_app_value_replaces_the_default_and_a_commented_one_is_uncommented(self):
        out = s.render_caller(self.template, {"apk-path": "x/y.apk", "java-version": "'21'", "gradle-task": "assembleDebug"}, [])
        self.assertIn("      apk-path: x/y.apk\n", out)
        self.assertIn("      java-version: '21'\n", out)
        # Equal to the default: stays commented
        self.assertIn("      # gradle-task: assembleDebug\n", out)

    def test_a_trailing_comment_is_kept(self):
        out = s.render_caller(self.template, {"comment-header": "demo-app-link"}, [])
        self.assertIn("      comment-header: demo-app-link # change only if a PR needs several APK comments\n", out)

    def test_branches_are_replaced_and_the_comment_stays_on_the_first(self):
        out = s.render_caller(self.template, {}, ["main", "develop"])
        self.assertIn("      - main   # CONFIGURE: the branch(es) your PRs target\n      - develop\n", out)

    def test_what_an_app_has_is_read_back_after_rendering(self):
        out = s.render_caller(self.template, {"apk-path": "x/y.apk", "timezone": "UTC"}, ["dev"])
        inputs, branches = s.read_inputs(out)
        self.assertEqual({"apk-path": "x/y.apk", "timezone": "UTC"}, inputs)
        self.assertEqual(["dev"], branches)


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
        changed = s.sync_app(app(), self.dir)

        self.assertIn(".claude/skills/lukeneedham-conventions/SKILL.md", changed)
        for name in s.DEFAULT_CALLERS:
            self.assertTrue((self.dir / ".github" / "workflows" / name).is_file(), name)
        pr = (self.dir / ".github/workflows/trigger_on_pull_request.yml").read_text()
        self.assertIn("comment-header: demo-app-link", pr)
        claude = (self.dir / "CLAUDE.md").read_text()
        self.assertIn(s.BLOCK_BEGIN, claude)
        self.assertTrue(claude.startswith("# Instructions for Claude"))

    def test_a_second_run_changes_nothing(self):
        s.sync_app(app(), self.dir)
        self.assertEqual([], s.sync_app(app(), self.dir))

    def test_an_apps_own_settings_survive_and_carry_over_to_the_main_build(self):
        self.write(".github/workflows/trigger_on_pull_request.yml", self_template(apk="app/build/x.apk", header="demo-link"))

        s.sync_app(app(), self.dir)

        pr = (self.dir / ".github/workflows/trigger_on_pull_request.yml").read_text()
        main = (self.dir / ".github/workflows/build_main.yml").read_text()
        self.assertIn("apk-path: app/build/x.apk", pr)
        self.assertIn("comment-header: demo-link", pr)
        self.assertIn("apk-path: app/build/x.apk", main)

    def test_apps_json_inputs_win_over_the_apps_own_file(self):
        self.write(".github/workflows/trigger_on_pull_request.yml", self_template(apk="old.apk", header="h"))

        s.sync_app(app(inputs={"apk-path": "new.apk"}), self.dir)

        self.assertIn("apk-path: new.apk", (self.dir / ".github/workflows/trigger_on_pull_request.yml").read_text())

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

        s.sync_claude_md(app(), self.dir)

        text = (self.dir / "CLAUDE.md").read_text()
        self.assertNotIn("Before starting work", text)
        self.assertIn(s.BLOCK_BEGIN, text)
        self.assertIn("- Another rule.", text)

    def test_an_existing_block_is_replaced_not_added_again(self):
        self.write("CLAUDE.md", "# Instructions\n\n" + s.BLOCK_BEGIN + "\nstale\n" + s.BLOCK_END + "\n\n- Rule.\n")

        s.sync_claude_md(app(), self.dir)

        text = (self.dir / "CLAUDE.md").read_text()
        self.assertEqual(1, text.count(s.BLOCK_BEGIN))
        self.assertNotIn("stale", text)
        self.assertIn("- Rule.", text)

    def test_the_block_tells_claude_the_readme_standard(self):
        s.sync_claude_md(app(), self.dir)
        self.assertIn("docs/readme.md", (self.dir / "CLAUDE.md").read_text())

    def test_the_readme_source_is_reported_but_nothing_is_written(self):
        self.assertEqual("readme.yml is missing", s.readme_note(self.dir))
        self.write("readme.yml", "name: Demo\n")
        self.assertIn("readme.yml is invalid", s.readme_note(self.dir))
        self.write("readme.yml", (TOOLS / "docs/readme-template.yml").read_text())
        self.assertEqual("", s.readme_note(self.dir))
        s.sync_app(app(), self.dir)
        self.assertFalse((self.dir / "README.md").exists())

    def test_an_app_can_opt_out_of_the_skill_and_the_callers(self):
        changed = s.sync_app(app(skill=False, callers=[]), self.dir)
        self.assertEqual([], changed)
        self.assertFalse((self.dir / ".claude").exists())
        self.assertFalse((self.dir / "CLAUDE.md").exists())


def self_template(apk, header):
    text = (TOOLS / "examples" / "trigger_on_pull_request.yml").read_text()
    text = text.replace(s.DEFAULT_APK_PATH, apk)
    return text.replace("# comment-header: example-app-link", f"comment-header: {header}")


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


class AppsFile(unittest.TestCase):
    def test_every_app_has_a_name_and_a_repo(self):
        import json
        apps = json.loads((TOOLS / "apps.json").read_text())
        self.assertTrue(apps)
        for entry in apps:
            self.assertRegex(entry["repo"], r"^[\w.-]+/[\w.-]+$")
            self.assertTrue(entry["name"])
        self.assertEqual(len(apps), len({a["repo"] for a in apps}))

    def test_every_default_caller_has_an_example(self):
        for name in s.DEFAULT_CALLERS:
            self.assertTrue((TOOLS / "examples" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
