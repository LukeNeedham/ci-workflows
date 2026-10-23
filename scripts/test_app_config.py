"""Tests for app_config.py. Run: python3 -m unittest discover -s scripts"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import app_config as c

TOOLS = c.TOOLS
APPS = json.loads((TOOLS / "apps.json").read_text())
SKILL_FILE = ".claude/skills/lukeneedham-conventions/SKILL.md"


def run(repo="LukeNeedham/Demo", event="pull_request", action="synchronize", base="main", files=(), apps=()):
    return c.run(repo, event, action, base, list(files), list(apps))[0]


class Settings(unittest.TestCase):
    def test_an_app_that_sets_nothing_gets_the_defaults(self):
        out = run(apps=[{"name": "Demo", "repo": "LukeNeedham/Demo"}])
        self.assertEqual("app/build/outputs/apk/debug/app-debug.apk", out["apk-path"])
        self.assertEqual("assembleDebug", out["gradle-task"])
        self.assertEqual("17", out["java-version"])
        self.assertEqual("zulu", out["java-distribution"])
        self.assertEqual("Europe/Amsterdam", out["timezone"])
        self.assertEqual("assembleRelease", out["release-gradle-task"])
        self.assertEqual("", out["asset-name"])

    def test_the_comment_id_is_derived_from_the_repo_name(self):
        self.assertEqual("demo-app-link", run(apps=[{"name": "Demo", "repo": "LukeNeedham/Demo"}])["comment-header"])

    def test_what_the_entry_sets_wins_over_the_default(self):
        out = run(apps=[{"name": "Demo", "repo": "LukeNeedham/Demo", "apk-path": "x/y.apk", "java-version": 21, "comment-header": "mine"}])
        self.assertEqual("x/y.apk", out["apk-path"])
        self.assertEqual("21", out["java-version"])
        self.assertEqual("mine", out["comment-header"])

    def test_the_repo_is_found_whatever_its_case(self):
        out = run(repo="lukeneedham/DEMO", apps=[{"name": "Demo", "repo": "LukeNeedham/Demo", "apk-path": "x.apk"}])
        self.assertEqual("x.apk", out["apk-path"])

    def test_an_unknown_repo_gets_the_defaults_and_a_warning(self):
        out, log = c.run("LukeNeedham/Nope", "pull_request", "opened", "main", [], APPS)
        self.assertEqual("app/build/outputs/apk/debug/app-debug.apk", out["apk-path"])
        self.assertEqual("false", out["skip"])
        self.assertTrue(any(line.startswith("::warning::") for line in log))


class Skipping(unittest.TestCase):
    demo = [{"name": "Demo", "repo": "LukeNeedham/Demo"}]

    def skip(self, **kwargs):
        return run(apps=kwargs.pop("apps", self.demo), **kwargs)["skip"]

    def test_a_pr_that_changes_only_the_skill_is_skipped(self):
        self.assertEqual("true", self.skip(files=[SKILL_FILE, ".claude/skills/other/notes.md"]))

    def test_one_other_file_in_the_pr_builds_it(self):
        self.assertEqual("false", self.skip(files=[SKILL_FILE, "app/src/Main.kt"]))

    def test_other_files_under_claude_still_build(self):
        self.assertEqual("false", self.skip(files=[".claude/settings.json"]))
        self.assertEqual("false", self.skip(files=["CLAUDE.md"]))

    def test_a_pr_with_no_known_files_builds(self):
        self.assertEqual("false", self.skip(files=[]))

    def test_a_closing_pr_is_not_skipped_for_its_files(self):
        self.assertEqual("false", self.skip(action="closed", files=[SKILL_FILE]))

    def test_a_pr_into_another_branch_is_skipped_when_open_and_when_closed(self):
        self.assertEqual("true", self.skip(base="develop", files=["app/Main.kt"]))
        self.assertEqual("true", self.skip(base="develop", action="closed"))

    def test_the_branches_of_the_entry_are_used(self):
        apps = [{"name": "Demo", "repo": "LukeNeedham/Demo", "branches": ["master", "release/*"]}]
        self.assertEqual("false", self.skip(apps=apps, base="master", files=["a"]))
        self.assertEqual("false", self.skip(apps=apps, base="release/1.2", files=["a"]))
        self.assertEqual("true", self.skip(apps=apps, base="main", files=["a"]))

    def test_a_manual_run_is_never_skipped(self):
        self.assertEqual("false", self.skip(event="workflow_dispatch", base="", files=[SKILL_FILE]))


class Cli(unittest.TestCase):
    def test_it_writes_the_outputs_to_github_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = Path(tmp, "files.txt")
            files.write_text(SKILL_FILE + "\n")
            out = Path(tmp, "out.txt")
            subprocess.run(
                [sys.executable, str(TOOLS / "scripts" / "app_config.py"), "--repo", "LukeNeedham/FlagTutor",
                 "--event", "pull_request", "--action", "opened", "--base", "main", "--files", str(files)],
                env={**os.environ, "GITHUB_OUTPUT": str(out)}, check=True, capture_output=True,
            )
            lines = out.read_text().splitlines()
        self.assertIn("skip=true", lines)
        self.assertIn("apk-path=composeApp/build/outputs/apk/debug/composeApp-debug.apk", lines)


class Workflows(unittest.TestCase):
    def test_the_shared_workflows_take_no_settings_as_inputs(self):
        # Settings come from apps.json only; an input of that name would be a second source of truth
        import re
        for name in ("android_pr", "android_main_build", "android_release"):
            text = (TOOLS / ".github" / "workflows" / f"{name}.yml").read_text()
            for key in list(c.DEFAULTS) + [c.COMMENT_HEADER]:
                self.assertNotRegex(text, rf"(?m)^      {re.escape(key)}:", f"{name} {key}")


class AppsFile(unittest.TestCase):
    def test_every_entry_uses_only_known_keys(self):
        for entry in APPS:
            self.assertLessEqual(set(entry), c.ENTRY_KEYS, entry["name"])

    def test_branches_and_callers_are_lists_of_strings(self):
        for entry in APPS:
            for key in ("branches", "callers"):
                if key in entry:
                    self.assertTrue(entry[key] and all(isinstance(v, str) for v in entry[key]), f"{entry['name']} {key}")

    def test_every_other_setting_is_a_string(self):
        for entry in APPS:
            for key in list(c.DEFAULTS) + [c.COMMENT_HEADER]:
                if key in entry:
                    self.assertIsInstance(entry[key], str, f"{entry['name']} {key}")

    def test_every_caller_an_entry_names_has_an_example(self):
        for entry in APPS:
            for name in entry.get("callers", []):
                self.assertTrue((TOOLS / "examples" / name).is_file(), f"{entry['name']} {name}")

    def test_the_defaults_are_the_standard_app_layout(self):
        self.assertEqual("app/build/outputs/apk/debug/app-debug.apk", c.DEFAULTS["apk-path"])


if __name__ == "__main__":
    unittest.main()
