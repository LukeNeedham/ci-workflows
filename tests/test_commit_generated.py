import subprocess
import tempfile
import unittest
import json
from types import SimpleNamespace
from pathlib import Path

import _paths  # noqa: F401
import commit_generated as c


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def args(**kwargs):
    return SimpleNamespace(**{"paths": ["docs/screenshots"], "what": "The screenshots", "source": "the page previews",
                              "regenerate": "scripts/render_screenshots.py", "message": "Regenerate the screenshots", **kwargs})


class CommitGeneratedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        git(base, "init", "--bare", "-b", "main", str(self.remote))
        self.app = base / "app"
        git(base, "clone", "-q", str(self.remote), str(self.app))
        git(self.app, "config", "user.name", "t")
        git(self.app, "config", "user.email", "t@t")
        (self.app / "docs" / "screenshots").mkdir(parents=True)
        (self.app / "docs" / "screenshots" / "Home.png").write_text("one")
        git(self.app, "add", "-A")
        git(self.app, "commit", "-qm", "first")
        git(self.app, "push", "-q", "origin", "HEAD:refs/heads/feature")
        git(self.app, "checkout", "-q", "-B", "feature", "origin/feature")
        event = Path(self.tmp.name) / "event.json"
        event.write_text(json.dumps({"pull_request": {"head": {"repo": {"full_name": "o/app"}}}}))
        self.pr = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event), "GITHUB_REPOSITORY": "o/app",
                   "GITHUB_HEAD_REF": "feature", "GITHUB_ACTOR": "luke"}

    def tearDown(self):
        self.tmp.cleanup()

    def commits(self):
        return int(git(self.remote, "rev-list", "--count", "feature"))

    def test_nothing_changed_commits_nothing(self):
        self.assertEqual(0, c.run(args(), self.pr, cwd=self.app))
        self.assertEqual(1, self.commits())

    def test_a_change_is_committed_to_the_branch_of_the_pr(self):
        (self.app / "docs" / "screenshots" / "Home.png").write_text("two")
        (self.app / "docs" / "screenshots" / "New.png").write_text("new")
        self.assertEqual(0, c.run(args(), self.pr, cwd=self.app))
        self.assertEqual(2, self.commits())
        self.assertEqual("Regenerate the screenshots", git(self.remote, "log", "-1", "--format=%s", "feature"))
        self.assertEqual("github-actions[bot]", git(self.remote, "log", "-1", "--format=%an", "feature"))

    def test_a_deleted_file_is_committed_too(self):
        (self.app / "docs" / "screenshots" / "Home.png").unlink()
        self.assertEqual(0, c.run(args(), self.pr, cwd=self.app))
        self.assertEqual("", git(self.remote, "ls-tree", "-r", "--name-only", "feature"))

    def test_a_run_that_cannot_commit_fails_with_how_to_regenerate(self):
        (self.app / "docs" / "screenshots" / "Home.png").write_text("two")
        for env in ({**self.pr, "GITHUB_EVENT_NAME": "push"}, {**self.pr, "GITHUB_REPOSITORY": "o/other"},
                    {**self.pr, "GITHUB_ACTOR": "dependabot[bot]"}, {**self.pr, "GITHUB_HEAD_REF": ""}):
            self.assertEqual(1, c.run(args(), env, cwd=self.app), env)
            self.assertEqual(1, self.commits())

    def test_the_three_kinds_name_what_they_generate(self):
        self.assertEqual(["app-icon", "readme", "screenshots"], sorted(c.KINDS))
        for kind in c.KINDS.values():
            self.assertTrue(kind.paths and kind.what and kind.source and kind.regenerate and kind.message)

    def test_a_path_that_never_existed_is_no_change(self):
        self.assertEqual(0, c.run(args(paths=["nothing/here.png"]), self.pr, cwd=self.app))

    def test_a_push_that_races_with_another_job_is_retried_on_top_of_it(self):
        other = Path(self.tmp.name) / "other"
        git(self.tmp.name, "clone", "-q", "-b", "feature", str(self.remote), str(other))
        git(other, "config", "user.name", "o")
        git(other, "config", "user.email", "o@o")
        (other / "README.md").write_text("from the other job")
        git(other, "add", "-A")
        git(other, "commit", "-qm", "other")
        git(other, "push", "-q", "origin", "feature")
        (self.app / "docs" / "screenshots" / "Home.png").write_text("two")
        self.assertEqual(0, c.run(args(), self.pr, cwd=self.app))
        self.assertEqual(3, self.commits())

    def test_two_races_in_a_row_are_retried_too(self):
        (self.app / "docs" / "screenshots" / "Home.png").write_text("two")
        other = Path(self.tmp.name) / "other"
        git(self.tmp.name, "clone", "-q", "-b", "feature", str(self.remote), str(other))
        git(other, "config", "user.name", "o")
        git(other, "config", "user.email", "o@o")
        # A hook on the remote that lets another job get in before the first push is accepted, then a second time
        hook = self.remote / "hooks" / "pre-receive"
        counter = Path(self.tmp.name) / "count"
        hook.write_text(f"#!/bin/sh\nn=$(cat {counter} 2>/dev/null || echo 0)\necho $((n+1)) > {counter}\n"
                        f"if [ \"$n\" -lt 2 ]; then echo racing >&2; exit 1; fi\n")
        hook.chmod(0o755)
        self.assertEqual(0, c.run(args(), self.pr, cwd=self.app))
        self.assertEqual("3", counter.read_text().strip())


if __name__ == "__main__":
    unittest.main()
