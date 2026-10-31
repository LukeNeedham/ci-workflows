import contextlib
import io
import json
import unittest

import _paths  # noqa: F401
import automerge as a
import sync_apps
from fakes import FakeGh


def pr(**changes):
    base = {
        "state": "open",
        "title": f"{a.TITLE_TAG} Sync from ci-workflows",
        "head": {"ref": a.SYNC_BRANCH, "sha": "b" * 40, "repo": {"full_name": "o/r"}},
    }
    return {**base, **changes}


def run(answers, sha="a" * 40):
    out = io.StringIO()
    with FakeGh(answers) as gh, contextlib.redirect_stdout(out):
        code = a.merge("o/r", 5, sha)
    return code, gh.calls, out.getvalue()


def merges(calls):
    return [c for c in calls if c[:2] == ["pr", "merge"]]


class SkipReasonTest(unittest.TestCase):
    def test_the_sync_pr_may_be_merged(self):
        self.assertIsNone(a.skip_reason(pr(), "o/r"))

    def test_a_closed_pr_is_left_alone(self):
        self.assertIn("closed", a.skip_reason(pr(state="closed"), "o/r"))

    def test_a_pr_without_the_tag_is_left_alone(self):
        self.assertIn(a.TITLE_TAG, a.skip_reason(pr(title="Sync from ci-workflows"), "o/r"))

    def test_another_branch_is_left_alone_whatever_the_title(self):
        other = {"ref": "claude/x", "sha": "b" * 40, "repo": {"full_name": "o/r"}}
        self.assertIn("claude/x", a.skip_reason(pr(head=other), "o/r"))

    def test_a_fork_is_left_alone(self):
        fork = {"ref": a.SYNC_BRANCH, "sha": "b" * 40, "repo": {"full_name": "x/r"}}
        self.assertIn("not in this repo", a.skip_reason(pr(head=fork), "o/r"))

    def test_a_deleted_fork_is_left_alone(self):
        gone = {"ref": a.SYNC_BRANCH, "sha": "b" * 40, "repo": None}
        self.assertIn("not in this repo", a.skip_reason(pr(head=gone), "o/r"))


class MergeTest(unittest.TestCase):
    def answers(self, status="ahead", **changes):
        return {
            "api repos/o/r/pulls/5": (0, json.dumps(pr(**changes))),
            "api repos/o/r/compare": (0, status + "\n"),
        }

    def test_the_pr_is_merged_with_a_merge_commit_pinned_to_the_head_it_checked(self):
        code, calls, _ = run(self.answers())
        self.assertEqual(0, code)
        self.assertEqual(1, len(merges(calls)))
        call = merges(calls)[0]
        self.assertIn("--merge", call)
        self.assertEqual("b" * 40, call[call.index("--match-head-commit") + 1])

    def test_commits_that_ci_added_since_the_run_started_do_not_stop_it(self):
        self.assertEqual(1, len(merges(run(self.answers("ahead"))[1])))
        self.assertEqual(1, len(merges(run(self.answers("identical"))[1])))

    def test_a_branch_that_was_replaced_is_not_merged(self):
        for status in ("diverged", "behind"):
            code, calls, out = run(self.answers(status))
            self.assertEqual(0, code)
            self.assertEqual([], merges(calls))
            self.assertIn("changed", out)

    def test_a_pr_that_does_not_qualify_is_not_merged_and_is_not_a_failure(self):
        code, calls, _ = run(self.answers(title="Something else"))
        self.assertEqual(0, code)
        self.assertEqual([], merges(calls))

    def test_a_failed_merge_fails_the_step(self):
        answers = {**self.answers(), "pr merge": (1, "")}
        self.assertEqual(1, run(answers)[0])

    def test_a_pr_that_cannot_be_read_fails_the_step(self):
        self.assertEqual(1, run({"api repos/o/r/pulls/5": (1, "")})[0])


class SyncAgreementTest(unittest.TestCase):
    def test_the_sync_pushes_the_branch_that_the_merge_expects(self):
        self.assertEqual(a.SYNC_BRANCH, sync_apps.BRANCH)

    def test_the_sync_titles_its_pr_with_the_tag_that_the_merge_expects(self):
        self.assertTrue(sync_apps.PR_TITLE.startswith(a.TITLE_TAG))


if __name__ == "__main__":
    unittest.main()
