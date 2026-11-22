"""Tests for web_preview.py and next_js_project.py. Run: python3 -m unittest discover -s tests"""

import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import next_js_project as n
import web_preview as w


def deployment(id, environment="Preview"):
    return {"id": id, "environment": environment}


class PreviewUrl(unittest.TestCase):
    def test_the_url_of_the_newest_preview_that_succeeded(self):
        statuses = {1: [{"state": "success", "environment_url": "https://a.vercel.app"}]}
        self.assertEqual(("https://a.vercel.app", "success"), w.preview_url([deployment(1)], lambda d: statuses[d["id"]]))

    def test_nothing_is_a_preview_when_there_is_no_deployment_of_the_commit(self):
        self.assertEqual((None, "missing"), w.preview_url([], lambda d: self.fail("read")))

    def test_the_first_deployment_of_a_project_is_its_production_one_and_is_the_preview_of_the_first_pr(self):
        # Vercel makes the first deployment of a project production, whatever its branch (seen on the first PR of MatthewPersonalWebsite)
        statuses = [{"state": "success", "environment_url": "https://first.vercel.app"}]
        self.assertEqual(("https://first.vercel.app", "success"), w.preview_url([deployment(1, "Production")], lambda d: statuses))

    def test_a_preview_is_preferred_to_a_production_deployment_of_the_same_commit(self):
        statuses = {1: [{"state": "success", "environment_url": "https://prod"}], 2: [{"state": "success", "environment_url": "https://preview"}]}
        found = w.preview_url([deployment(1, "Production"), deployment(2)], lambda d: statuses[d["id"]])
        self.assertEqual(("https://preview", "success"), found)

    def test_a_production_deployment_still_being_built_says_so(self):
        self.assertEqual((None, "in_progress"), w.preview_url([deployment(1, "Production")], lambda d: [{"state": "in_progress"}]))

    def test_a_preview_of_a_monorepo_project_counts(self):
        statuses = [{"state": "success", "target_url": "https://b.vercel.app"}]
        self.assertEqual(("https://b.vercel.app", "success"), w.preview_url([deployment(1, "Preview – site")], lambda d: statuses))

    def test_a_deployment_still_being_built_says_so(self):
        self.assertEqual((None, "in_progress"), w.preview_url([deployment(1)], lambda d: [{"state": "in_progress"}]))
        self.assertEqual((None, "pending"), w.preview_url([deployment(1)], lambda d: []))

    def test_a_failed_build_says_so(self):
        self.assertEqual((None, "failure"), w.preview_url([deployment(1)], lambda d: [{"state": "failure"}]))

    def test_the_newest_deployment_decides_not_an_older_success(self):
        statuses = {2: [{"state": "failure"}], 1: [{"state": "success", "environment_url": "https://old"}]}
        self.assertEqual((None, "failure"), w.preview_url([deployment(2), deployment(1)], lambda d: statuses[d["id"]]))


class Find(unittest.TestCase):
    def run_find(self, answers, timeout=30):
        """find() with the API answering [answers] in turn, and a clock that moves 10 seconds a sleep."""
        now = [0]
        calls = []

        def get(path):
            calls.append(path)
            if "/statuses" in path:
                return answers[min(len([c for c in calls if "/statuses" in c]) - 1, len(answers) - 1)]
            return [deployment(7)]

        result = w.find("o/r", "abc", timeout, interval=10, clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s), get=get)
        return result, now[0]

    def test_it_waits_until_the_preview_is_ready(self):
        result, waited = self.run_find([[{"state": "in_progress"}], [{"state": "success", "environment_url": "https://x"}]])
        self.assertEqual(("https://x", "success"), result)
        self.assertEqual(10, waited)

    def test_it_stops_at_once_on_a_failed_build(self):
        result, waited = self.run_find([[{"state": "failure"}]])
        self.assertEqual((None, "failure"), result)
        self.assertEqual(0, waited)

    def test_it_gives_up_at_the_timeout(self):
        result, waited = self.run_find([[{"state": "in_progress"}]], timeout=25)
        self.assertEqual((None, "in_progress"), result)
        self.assertGreaterEqual(waited, 25)


class Login(unittest.TestCase):
    def test_a_refusal_or_a_redirect_to_vercel_is_a_login(self):
        self.assertTrue(w.asks_for_login(401, None))
        self.assertTrue(w.asks_for_login(403, None))
        self.assertTrue(w.asks_for_login(307, "https://vercel.com/sso-api?url=x"))

    def test_a_page_or_an_ordinary_redirect_is_public(self):
        self.assertFalse(w.asks_for_login(200, None))
        self.assertFalse(w.asks_for_login(308, "https://example.com/about/"))
        self.assertFalse(w.asks_for_login(404, None))


class Comment(unittest.TestCase):
    def test_the_url_is_on_a_line_of_its_own_for_apphub(self):
        body = w.comment_body("https://a.vercel.app", "0123456789", True)
        self.assertIn("\n<!-- preview-url: https://a.vercel.app -->\n", body)
        self.assertIn("`0123456", body)
        self.assertNotIn("login", body)

    def test_a_protected_preview_says_what_to_change(self):
        body = w.comment_body("https://a.vercel.app", "0123456789", False)
        self.assertIn("Deployment Protection", body)
        self.assertIn("<!-- preview-url: https://a.vercel.app -->", body)


class WriteComment(unittest.TestCase):
    def test_the_comment_is_written_and_the_workflow_is_told_by_an_output(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            saved = os.environ.get("GITHUB_OUTPUT")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                w.write_comment(Path(d) / "comment.md", "hello")
            finally:
                os.environ.pop("GITHUB_OUTPUT") if saved is None else os.environ.__setitem__("GITHUB_OUTPUT", saved)
            self.assertEqual("hello", (Path(d) / "comment.md").read_text())
            self.assertEqual("comment=true\n", out.read_text())

    def test_the_workflow_does_not_test_the_file_with_hashfiles(self):
        # hashFiles() only sees the workspace, and the comment is in the runner's temp folder: such a test is always false
        workflow = (Path(w.__file__).resolve().parent.parent / ".github/workflows/web_pr.yml").read_text()
        self.assertNotIn("hashFiles", workflow)
        self.assertIn("steps.preview.outputs.comment == 'true'", workflow)


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_the_package_manager_comes_from_the_lockfile(self):
        for lockfile, expected in (("yarn.lock", "yarn"), ("pnpm-lock.yaml", "pnpm"), ("package-lock.json", "npm")):
            with self.subTest(lockfile):
                folder = self.dir / lockfile
                folder.mkdir()
                (folder / lockfile).write_text("")
                self.assertEqual(expected, n.detect(folder)[0])

    def test_no_lockfile_is_no_manager(self):
        self.assertIsNone(n.detect(self.dir))

    def test_the_install_never_changes_the_lockfile(self):
        for _, _, install, _ in n.MANAGERS:
            self.assertRegex(install, r"frozen-lockfile|npm ci")

    def test_a_test_script_is_found(self):
        (self.dir / "package.json").write_text(json.dumps({"scripts": {"lint": "x", "test": "y"}}))
        self.assertTrue(n.has_script(self.dir, "test"))
        (self.dir / "package.json").write_text(json.dumps({"scripts": {"lint": "x"}}))
        self.assertFalse(n.has_script(self.dir, "test"))


if __name__ == "__main__":
    unittest.main()
