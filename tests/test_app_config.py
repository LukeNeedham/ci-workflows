"""Tests for app_config.py. Run: python3 -m unittest discover -s tests"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import app_config as c

TOOLS = Path(__file__).resolve().parent.parent
SKILL_FILE = ".claude/skills/lukeneedham-conventions/SKILL.md"


def run(repo="LukeNeedham/Demo", event="pull_request", action="synchronize", base="main", files=(), push_files=()):
    return c.run(repo, event, action, base, list(files), list(push_files))[0]


class Settings(unittest.TestCase):
    def test_every_app_gets_the_standard_settings(self):
        out = run()
        self.assertEqual("app/build/outputs/apk/debug/app-debug.apk", out["apk-path"])
        self.assertEqual("assembleDebug", out["gradle-task"])
        self.assertEqual("17", out["java-version"])
        self.assertEqual("temurin", out["java-distribution"])
        self.assertEqual("Europe/Amsterdam", out["timezone"])
        self.assertEqual("assembleRelease", out["release-gradle-task"])
        self.assertEqual("app/build/outputs/apk/release/app-release.apk", out["release-apk-path"])

    def test_the_comment_id_and_the_release_asset_come_from_the_repo_name(self):
        out = run(repo="LukeNeedham/LT-Companion")
        self.assertEqual("lt-companion-app-link", out["comment-header"])
        self.assertEqual("LT-Companion.apk", out["asset-name"])

    def test_the_outputs_are_what_the_action_declares(self):
        text = (TOOLS / ".github/actions/app-config/action.yml").read_text()
        outputs = text.split("\noutputs:\n")[1].split("\nruns:\n")[0]
        self.assertEqual(set(re.findall(r"(?m)^  ([a-z-]+):$", outputs)), set(run()))


class Jobs(unittest.TestCase):
    def jobs(self, **kwargs):
        out = run(**kwargs)
        return out["generate"], out["cleanup"]

    def test_an_open_pr_and_a_manual_run_build_and_generate(self):
        self.assertEqual(("true", "false"), self.jobs(event="pull_request", action="synchronize"))
        self.assertEqual(("true", "false"), self.jobs(event="workflow_dispatch", action=""))

    def test_a_closed_pr_cleans_up_and_generates_nothing(self):
        self.assertEqual(("false", "true"), self.jobs(event="pull_request", action="closed"))

    def test_a_skipped_run_does_neither(self):
        self.assertEqual(("false", "false"), self.jobs(event="pull_request", action="opened", base="develop"))
        self.assertEqual(("false", "false"), self.jobs(event="pull_request", action="closed", base="develop"))


class Skipping(unittest.TestCase):
    def skip(self, **kwargs):
        out = run(**kwargs)
        return "true" if out["generate"] == "false" and out["cleanup"] == "false" else "false"

    def test_a_pr_that_changes_only_the_skill_is_skipped(self):
        self.assertEqual("true", self.skip(files=[SKILL_FILE, ".claude/skills/other/notes.md"]))

    def test_a_pr_that_changes_only_docs_and_markdown_is_skipped(self):
        self.assertEqual("true", self.skip(files=["docs/setup.md", "README.md", "CLAUDE.md", "app/NOTES.md", "docs/a.png"]))

    def test_markdown_in_a_src_folder_builds(self):
        self.assertEqual("false", self.skip(files=["README.md", "app/src/main/assets/help.md"]))

    def test_a_non_markdown_file_outside_docs_builds(self):
        self.assertEqual("false", self.skip(files=["README.md", "gradle/libs.versions.toml"]))

    def test_one_other_file_in_the_pr_builds_it(self):
        self.assertEqual("false", self.skip(files=[SKILL_FILE, "app/src/Main.kt"]))

    def test_a_push_of_only_generated_files_is_skipped_even_in_a_pr_with_code(self):
        pushed = ["docs/screenshots/01-HomePage.png", "README.md", "app-icon.png", "app/src/debug/kotlin/x/screenshot/README.md"]
        self.assertEqual("true", self.skip(files=["app/src/Main.kt", *pushed], push_files=pushed))

    def test_one_other_file_in_the_push_builds_it(self):
        self.assertEqual("false", self.skip(files=["app/src/Main.kt"], push_files=["README.md", "app/src/Main.kt"]))

    def test_a_push_that_cannot_be_listed_builds(self):
        self.assertEqual("false", self.skip(files=["app/src/Main.kt", "README.md"], push_files=[]))

    def test_only_a_synchronize_is_skipped_for_its_push(self):
        self.assertEqual("false", self.skip(action="opened", files=["app/src/Main.kt", "README.md"], push_files=["README.md"]))

    def test_other_readmes_and_images_are_not_generated(self):
        for f in ["docs/README.md", "app/README.md", "docs/other.png", "docs/screenshotsx/a.png", "app-icon.png.bak"]:
            self.assertEqual("false", self.skip(files=["app/src/Main.kt", f], push_files=[f]), f)

    def test_claude_settings_and_claude_md_are_not_android_sources(self):
        self.assertEqual("true", self.skip(files=[".claude/settings.json"]))
        self.assertEqual("true", self.skip(files=["CLAUDE.md"]))

    def test_a_pr_with_no_known_files_builds(self):
        self.assertEqual("false", self.skip(files=[]))

    def test_a_closing_pr_is_not_skipped_for_its_files(self):
        self.assertEqual("false", self.skip(action="closed", files=[SKILL_FILE]))

    def test_only_prs_into_main_are_built(self):
        self.assertEqual("false", self.skip(base="main", files=["app/Main.kt"]))
        for base in ("master", "develop", "release/1.0"):
            self.assertEqual("true", self.skip(base=base, files=["app/Main.kt"]), base)
            self.assertEqual("true", self.skip(base=base, action="closed"), base)

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
        self.assertIn("generate=false", lines)
        self.assertIn("cleanup=false", lines)
        self.assertIn("apk-path=app/build/outputs/apk/debug/app-debug.apk", lines)


class Workflows(unittest.TestCase):
    def test_the_shared_workflows_take_no_settings_as_inputs(self):
        # Every app is built the same way; an input of that name would be a per-app setting again
        for name in ("android_pr", "android_main_build", "android_release"):
            text = (TOOLS / ".github" / "workflows" / f"{name}.yml").read_text().split("\njobs:\n")[0]
            for key in list(c.SETTINGS) + ["comment-header", "asset-name", "branches"]:
                self.assertNotRegex(text, rf"(?m)^      {re.escape(key)}:", f"{name} {key}")

    def test_the_release_workflow_checks_its_setup_before_it_tags_anything(self):
        text = (TOOLS / ".github/workflows/android_release.yml").read_text()
        for secret in ("RELEASE_KEYSTORE_BASE64", "RELEASE_KEYSTORE_PASSWORD", "RELEASE_KEY_ALIAS", "RELEASE_KEY_PASSWORD"):
            self.assertRegex(text, rf"(?m)^      {secret}:\n(.*\n)*?        required: false", secret)
        self.assertLess(text.index("Check the app is set up for releases"), text.index("Tag this commit"))


class AppsFile(unittest.TestCase):
    apps = json.loads((TOOLS / "apps.json").read_text())

    def test_an_entry_is_just_a_name_and_a_repo(self):
        # Nothing is configured per app: every app is built the same way
        self.assertTrue(self.apps)
        for entry in self.apps:
            self.assertEqual({"name", "repo"}, set(entry), entry)
            self.assertRegex(entry["repo"], r"^[\w.-]+/[\w.-]+$")
            self.assertTrue(entry["name"])
        # Names are compared exactly, so two entries must not differ only by case
        self.assertEqual(len(self.apps), len({a["repo"].lower() for a in self.apps}))


if __name__ == "__main__":
    unittest.main()
