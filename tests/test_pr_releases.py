import io
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _paths  # noqa: F401
import pr_releases as p
from fakes import FakeGh


class Outputs:
    """Captures the step outputs of the code inside."""

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "out"
        self.saved = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = str(self.path)
        return self

    def __exit__(self, *exc):
        text = self.path.read_text() if self.path.exists() else ""
        self.values = dict(line.split("=", 1) for line in text.splitlines())
        if self.saved is None:
            os.environ.pop("GITHUB_OUTPUT")
        else:
            os.environ["GITHUB_OUTPUT"] = self.saved
        self.dir.cleanup()



class TagSchemeTest(unittest.TestCase):
    def test_a_branch_becomes_part_of_a_tag(self):
        self.assertEqual("claude-fix_bug-1.2", p.clean_branch("Claude/Fix_Bug#1.2"))

    def test_the_tag_has_the_run_and_the_attempt(self):
        self.assertEqual("claude-x-77-2", p.release_tag("claude/x", 77, 2))

    def test_the_cleanup_recognises_exactly_the_tags_that_the_build_makes(self):
        tag = p.release_tag("claude/x", 77, 1)
        self.assertTrue(p.is_build_tag(tag, "claude/x"))
        self.assertFalse(p.is_build_tag(tag, "claude/y"))
        # Another branch whose name starts with this one, and things that only look like a run
        self.assertFalse(p.is_build_tag("claude-x-main-3-1", "claude/x"))
        self.assertFalse(p.is_build_tag("claude-x-77-1-extra", "claude/x"))
        self.assertFalse(p.is_build_tag("claude-x-77", "claude/x"))
        self.assertFalse(p.is_build_tag("v1.0.0", "claude/x"))


class StepsTest(unittest.TestCase):
    def test_meta_has_the_time_the_apk_name_and_the_tag(self):
        with Outputs() as out:
            self.assertEqual(0, p.meta("Europe/Amsterdam", "app/build/outputs/apk/debug/app-debug.apk", "claude/x", "77", "1"))
        self.assertRegex(out.values["time"], r"^\d\d/\d\d/\d{4} \d\d:\d\d:\d\d$")
        self.assertEqual("app-debug.apk", out.values["apk-name"])
        self.assertEqual("claude-x-77-1", out.values["tag"])

    def test_stale_finds_the_previous_apk_in_the_sticky_comment(self):
        body = "### Build\n- **APK:** [Download](https://github.com/o/r/releases/download/b-1-1/app-debug.apk)\n"
        with FakeGh({"api --paginate repos/o/r/issues/5/comments": (0, body)}) as gh, Outputs() as out:
            p.stale("o/r", "5", "app-link", "Europe/Amsterdam", "0123456789abcdef")
        self.assertEqual("0123456", out.values["short-sha"])
        self.assertEqual("https://github.com/o/r/releases/download/b-1-1/app-debug.apk", out.values["old-url"])
        jq = gh.calls[0][-1]
        self.assertIn("Sticky Pull Request Commentapp-link ", jq)

    def test_stale_has_no_link_when_there_is_no_comment_or_the_call_fails(self):
        for answer in ((0, ""), (1, "boom")):
            with FakeGh({"api": answer}), Outputs() as out:
                p.stale("o/r", "5", "h", "UTC", "abcdef0")
            self.assertEqual("", out.values["old-url"])

    def test_superseded_only_when_the_head_of_the_pr_moved(self):
        for current, expected in (("newer", "true"), ("same", None), ("", None)):
            with FakeGh({"api repos/o/r/pulls/5": (0, current + "\n")}), Outputs() as out:
                p.superseded("o/r", "5", "same")
            self.assertEqual(expected, out.values.get("superseded"), current)
        with FakeGh({"api": (1, "")}), Outputs() as out:
            p.superseded("o/r", "5", "same")
        self.assertNotIn("superseded", out.values)


class CleanupTest(unittest.TestCase):
    RELEASES = ('[{"tagName":"claude-x-1-1","isPrerelease":true},{"tagName":"claude-x-2-1","isPrerelease":true},'
                '{"tagName":"claude-x-3-1","isPrerelease":false},{"tagName":"claude-x-main-4-1","isPrerelease":true},'
                '{"tagName":"other-5-1","isPrerelease":true},{"tagName":"0.3.0","isPrerelease":false}]')

    def test_it_deletes_the_prereleases_of_the_branch_and_nothing_else(self):
        with FakeGh({"release list": (0, self.RELEASES)}) as gh:
            self.assertEqual(0, p.cleanup("claude/x"))
        deleted = [c[2] for c in gh.calls if c[:2] == ["release", "delete"]]
        self.assertEqual(["claude-x-1-1", "claude-x-2-1"], deleted)
        self.assertTrue(all("--cleanup-tag" in c and "--yes" in c for c in gh.calls if c[:2] == ["release", "delete"]))

    def test_it_says_when_there_is_nothing_to_delete(self):
        buffer = io.StringIO()
        with FakeGh({"release list": (0, "[]")}) as gh, redirect_stdout(buffer):
            self.assertEqual(0, p.cleanup("claude/x"))
        self.assertIn("No PR build releases found for branch 'claude/x'", buffer.getvalue())
        self.assertEqual(1, len(gh.calls))

    def test_a_failing_gh_fails_the_step(self):
        with FakeGh({"release list": (1, "")}):
            self.assertEqual(1, p.cleanup("claude/x"))
        with FakeGh({"release list": (0, self.RELEASES), "release delete": (3, "")}):
            self.assertEqual(3, p.cleanup("claude/x"))


if __name__ == "__main__":
    unittest.main()
