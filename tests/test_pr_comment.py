import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent / "actions" / "pr-comment"))
import pr_comment  # noqa: E402

APK = "https://github.com/o/r/releases/download/branch-208-1/composeApp-debug.apk"
RUN = "https://github.com/o/r/actions/runs/1"


class PrCommentTest(unittest.TestCase):
    def test_find_previous_url_in_success_comment(self):
        body = f"App apk at:\n{APK}\n\n* **Triggered by:** PR Commit `abc`\n<!-- Sticky Pull Request Commentexample-app-link -->"
        self.assertEqual(pr_comment.find_previous_url(body), APK)

    def test_find_previous_url_in_stale_comment(self):
        message = pr_comment.build_message("in-progress", "abc", RUN, "t", previous_url=APK)
        self.assertEqual(pr_comment.find_previous_url(message), APK)

    def test_find_previous_url_none(self):
        self.assertIsNone(pr_comment.find_previous_url("⏳ **New build in progress**"))
        self.assertIsNone(pr_comment.find_previous_url(""))

    def test_find_comment_body_uses_marker(self):
        bodies = ["unrelated", "hello <!-- Sticky Pull Request Commentexample-app-link -->"]
        self.assertEqual(pr_comment.find_comment_body(bodies, "example-app-link"), bodies[1])
        self.assertEqual(pr_comment.find_comment_body(bodies, "other"), "")

    def test_success_message(self):
        msg = pr_comment.build_message("success", "abc", RUN, "09/10/2026 12:00:00", apk_url=APK)
        self.assertIn(APK, msg)
        self.assertIn("`abc`", msg)
        self.assertIn("**Built at:** 09/10/2026 12:00:00", msg)
        self.assertNotIn("stale", msg)

    def test_in_progress_keeps_old_link_as_stale(self):
        msg = pr_comment.build_message("in-progress", "abc", RUN, "t", previous_url=APK)
        self.assertIn("New build in progress", msg)
        self.assertIn(f"stale, does not include this commit): {APK}", msg)

    def test_in_progress_without_previous_build(self):
        msg = pr_comment.build_message("in-progress", "abc", RUN, "t")
        self.assertNotIn("stale", msg)

    def test_failed_and_cancelled(self):
        self.assertIn("Build failed", pr_comment.build_message("failed", "abc", RUN, "t", previous_url=APK))
        self.assertIn("Build cancelled", pr_comment.build_message("cancelled", "abc", RUN, "t"))

    def test_unknown_state(self):
        with self.assertRaises(ValueError):
            pr_comment.build_message("bogus", "abc", RUN, "t")

    def test_format_time_uses_timezone(self):
        now = datetime(2026, 10, 9, 10, 32, 43, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(pr_comment.format_time("Europe/Amsterdam", now.astimezone(ZoneInfo("Europe/Amsterdam"))), "09/10/2026 12:32:43")


if __name__ == "__main__":
    unittest.main()
