"""Tests for was_built.py. Run: python3 -m unittest discover -s tests"""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import _paths  # noqa: F401
import app_config
import was_built as w

ROOT = Path(__file__).resolve().parent.parent
SHA = "243904d2ebcb766666145731082d54a273eb61f7"


def comment(heading, sha=SHA, marker=True):
    body = f"### {heading}\n\n- **Commit:** [`{sha[:7]}`](https://github.com/o/app/commit/{sha})\n- **Run:** [#68](https://x)\n"
    return body + ("<!-- Sticky Pull Request Commentapp-app-link -->" if marker else "")


def gh_answering(bodies, code=0):
    """A `gh` that answers the list of comments of the PR with [bodies], as the jq of was_built.py prints them (one JSON string a line)."""
    calls = []

    def runner(args):
        calls.append(args)
        return SimpleNamespace(returncode=code, stdout="".join(json.dumps(b) + "\n" for b in bodies), stderr="denied" if code else "")

    runner.calls = calls
    return runner


class WasBuilt(unittest.TestCase):

    def test_a_build_that_succeeded_failed_or_is_running_built_the_commit(self):
        for heading in ("✅ Build succeeded", "❌ Build failed", "⏳ Build in progress"):
            self.assertEqual("true", w.was_built("o/app", "12", SHA, gh_answering([comment(heading)])), heading)

    def test_a_cancelled_build_did_not(self):
        self.assertEqual("false", w.was_built("o/app", "12", SHA, gh_answering([comment("🚫 Build cancelled")])))

    def test_a_comment_about_another_commit_says_nothing_of_this_one(self):
        # The incident: the last build was of the commit before, the pushed one never had a run
        other = "0a237eb4b1b90cdc9ac47cc56ad3db508b1a6eda"
        self.assertEqual("false", w.was_built("o/app", "12", SHA, gh_answering([comment("✅ Build succeeded", sha=other)])))

    def test_no_build_comment_means_not_built(self):
        self.assertEqual("false", w.was_built("o/app", "12", SHA, gh_answering([])))

    def test_the_short_sha_of_the_comment_matches_the_full_sha(self):
        self.assertTrue(w.build_comment_says_built(comment("✅ Build succeeded"), SHA))
        self.assertFalse(w.build_comment_says_built(comment("✅ Build succeeded"), "243904e" + SHA[7:]))

    def test_a_comment_that_cannot_be_read_is_unknown_so_that_the_push_is_built(self):
        self.assertEqual("unknown", w.was_built("o/app", "12", SHA, gh_answering([], code=1)))

    def test_it_asks_for_the_sticky_comment_of_the_app_on_the_pr(self):
        runner = gh_answering([comment("✅ Build succeeded")])
        w.was_built("LukeNeedham/Demo", "12", SHA, runner)
        args = " ".join(runner.calls[0])
        self.assertIn("repos/LukeNeedham/Demo/issues/12/comments", args)
        self.assertIn("Sticky Pull Request Commentdemo-app-link ", args)

    def test_the_marker_is_the_one_that_the_build_comment_is_written_with(self):
        # pr_releases.py reads the same comment by the same marker: they must not drift apart
        self.assertEqual("demo-app-link", app_config.settings("LukeNeedham/Demo")["comment-header"])


class Wiring(unittest.TestCase):
    """The action and the script agree: the action passes what the script reads, and an unknown answer builds."""

    def test_the_action_asks_was_built_and_passes_the_answer_to_the_config(self):
        action = (ROOT / ".github" / "actions" / "app-config" / "action.yml").read_text()
        self.assertIn("scripts/was_built.py", action)
        self.assertIn("steps.built.outputs.built", action)
        self.assertIn("--before-built", action)

    def test_without_an_answer_a_push_of_generated_files_is_built(self):
        out = app_config.run("o/app", "pull_request", "synchronize", "main", ["app/src/Main.kt", "README.md"], ["README.md"], False)[0]
        self.assertEqual("true", out["generate"])

    def test_the_command_line_builds_unless_it_is_told_that_the_commit_was_built(self):
        import subprocess, sys, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pushed = Path(tmp) / "pushed.txt"
            pushed.write_text("README.md\n")
            changed = Path(tmp) / "changed.txt"
            changed.write_text("README.md\napp/src/Main.kt\n")
            base = [sys.executable, str(ROOT / "scripts" / "app_config.py"), "--repo", "o/app", "--event", "pull_request",
                    "--action", "synchronize", "--base", "main", "--files", str(changed), "--push-files", str(pushed)]
            for flag, generate in ((["--before-built", "true"], "false"), (["--before-built", "false"], "true"), ([], "true")):
                out = subprocess.run([*base, *flag], capture_output=True, text=True, check=True).stdout
                self.assertIn(f"generate={generate}", out, flag)


if __name__ == "__main__":
    unittest.main()
