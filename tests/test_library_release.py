import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _paths  # noqa: F401
import library_release as l


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Repo:
    """A local bare remote with a main branch, and a clone of it."""

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        base = Path(self.dir.name)
        self.remote, self.app = base / "remote.git", base / "app"
        git(base, "init", "--bare", "-b", "main", str(self.remote))
        git(base, "clone", "-q", str(self.remote), str(self.app))
        git(self.app, "config", "user.name", "t")
        git(self.app, "config", "user.email", "t@t")
        (self.app / "README.md").write_text("x")
        git(self.app, "add", "-A")
        git(self.app, "commit", "-qm", "first")
        git(self.app, "push", "-q", "origin", "HEAD:main")
        self.sha = git(self.app, "rev-parse", "HEAD")
        return self

    def __exit__(self, *exc):
        self.dir.cleanup()


class LibraryReleaseTest(unittest.TestCase):
    def test_the_version_must_be_major_minor_patch(self):
        self.assertEqual(0, l.check_version("0.7.0"))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(1, l.check_version("0.7"))
        self.assertIn("The version must be major.minor.patch, but it is '0.7'", buffer.getvalue())

    def test_a_missing_gh_pages_branch_is_created_empty_and_the_release_commit_is_checked_out_again(self):
        with Repo() as repo:
            self.assertEqual(0, l.ensure_gh_pages(repo.sha, cwd=repo.app))
            self.assertEqual(".nojekyll", git(repo.remote, "ls-tree", "-r", "--name-only", "gh-pages"))
            self.assertEqual("Start the Maven repository", git(repo.remote, "log", "-1", "--format=%s", "gh-pages"))
            self.assertEqual("github-actions[bot]", git(repo.remote, "log", "-1", "--format=%an", "gh-pages"))
            self.assertEqual(repo.sha, git(repo.app, "rev-parse", "HEAD"))

    def test_an_existing_gh_pages_branch_is_left_alone(self):
        with Repo() as repo:
            l.ensure_gh_pages(repo.sha, cwd=repo.app)
            before = git(repo.remote, "rev-parse", "gh-pages")
            self.assertEqual(0, l.ensure_gh_pages(repo.sha, cwd=repo.app))
            self.assertEqual(before, git(repo.remote, "rev-parse", "gh-pages"))

    def test_a_published_version_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            published = Path(tmp) / "maven" / "com" / "lukeneedham" / "common" / "0.7.0"
            published.mkdir(parents=True)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(1, l.check_unpublished("0.7.0", pages=tmp))
                self.assertEqual(0, l.check_unpublished("0.8.0", pages=tmp))
            self.assertIn("Version 0.7.0 is already published. Pick a new one.", buffer.getvalue())

    def test_the_published_files_are_pushed_to_gh_pages(self):
        with Repo() as repo:
            l.ensure_gh_pages(repo.sha, cwd=repo.app)
            pages = Path(repo.dir.name) / "pages"
            git(repo.dir.name, "clone", "-q", "-b", "gh-pages", str(repo.remote), str(pages))
            (pages / "maven").mkdir()
            (pages / "maven" / "common.pom").write_text("pom")
            self.assertEqual(0, l.push("0.7.0", cwd=pages))
            self.assertEqual("Publish common 0.7.0", git(repo.remote, "log", "-1", "--format=%s", "gh-pages"))
            self.assertIn("maven/common.pom", git(repo.remote, "ls-tree", "-r", "--name-only", "gh-pages"))


if __name__ == "__main__":
    unittest.main()
