"""Tests for new_app.py. Run: python3 -m unittest discover -s tests"""

import base64
import json
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import new_app as n
import sync_apps

COMMON = "0.8.0"
APPS = '[\n  {"name": "AppHub", "repo": "LukeNeedham/AppHub"},\n  {"name": "Krillion wrapper", "repo": "LukeNeedham/krillion-wrapper"}\n]\n'


class Always(list):
    """An answer that is itself a list, to be returned whole every time (a plain list is a sequence of answers)."""


class FakeGithub:
    """A `call` that answers from a table of (method, path) and records what it was asked. An answer that is an Exception
    is raised; a list is taken one at a time, so that a second call can answer differently."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        answer = self.answers.get((method, path), {})
        if isinstance(answer, list) and not isinstance(answer, Always):
            answer = answer.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def made(self, method):
        return [c for c in self.calls if c[0] == method]


def missing(path):
    return RuntimeError(f"GET {path} returned 404: Not Found")


def fake_keystore(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"keystore")


class Names(unittest.TestCase):
    def test_a_normal_name_passes(self):
        for name in ("LyricTutor", "Stickerboard", "LT-Companion", "my_app2", "Ab"):
            self.assertEqual(name, n.check_name(name))

    def test_a_bad_name_says_so(self):
        for name in ("", "A", "1App", "-app", "app-", "my app", "my--app", "a/b", "../x", "app.git", "x" * 51, "App\n", "é"):
            with self.assertRaises(ValueError, msg=repr(name)):
                n.check_name(name)

    def test_the_package_is_the_lower_case_letters_and_digits_of_the_name(self):
        self.assertEqual("com.lukeneedham.lyrictutor", n.package_name("LyricTutor"))
        self.assertEqual("com.lukeneedham.ltcompanion", n.package_name("LT-Companion"))
        self.assertEqual("com.lukeneedham.myapp2", n.package_name("my_app2"))


class AppsJson(unittest.TestCase):
    def test_the_app_is_added_as_the_last_entry_in_the_layout_of_the_file(self):
        new = n.add_to_apps_json(APPS, "LyricTutor", "LukeNeedham/LyricTutor")

        self.assertEqual(
            '[\n  {"name": "AppHub", "repo": "LukeNeedham/AppHub"},\n  {"name": "Krillion wrapper", "repo": "LukeNeedham/krillion-wrapper"},\n'
            '  {"name": "LyricTutor", "repo": "LukeNeedham/LyricTutor"}\n]\n', new)
        self.assertEqual({"name": "LyricTutor", "repo": "LukeNeedham/LyricTutor"}, json.loads(new)[-1])

    def test_the_real_file_stays_valid_and_gains_exactly_one_entry(self):
        text = (n.TOOLS / "apps.json").read_text()
        new = n.add_to_apps_json(text, "LyricTutor", "LukeNeedham/LyricTutor")
        self.assertEqual(json.loads(text) + [{"name": "LyricTutor", "repo": "LukeNeedham/LyricTutor"}], json.loads(new))

    def test_an_app_that_is_listed_is_not_added_again(self):
        self.assertIsNone(n.add_to_apps_json(APPS, "AppHub", "LukeNeedham/AppHub"))
        self.assertIsNone(n.add_to_apps_json(APPS, "Other", "lukeneedham/apphub"), "the repo, whatever its case")
        self.assertIsNone(n.add_to_apps_json(APPS, "AppHub", "LukeNeedham/Else"), "the name")

    def test_a_file_with_no_trailing_newline_works(self):
        new = n.add_to_apps_json(APPS.rstrip(), "LyricTutor", "LukeNeedham/LyricTutor")
        self.assertEqual(3, len(json.loads(new)))


class Scaffold(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_a_new_app_gets_the_basic_files(self):
        changed = n.scaffold(self.dir, "LyricTutor", COMMON, keystore=fake_keystore, year=2026)

        for path in (*n.WRAPPER_FILES, "settings.gradle.kts", ".gitignore", "LICENSE", "app/debug.keystore"):
            self.assertTrue((self.dir / path).is_file(), path)
            self.assertIn(path, changed)
        self.assertEqual("Copyright (c) 2026 Luke Needham. All rights reserved.\n", (self.dir / "LICENSE").read_text())

    def test_the_wrapper_is_a_copy_and_gradlew_can_be_run(self):
        n.scaffold(self.dir, "LyricTutor", COMMON, keystore=fake_keystore)

        for path in n.WRAPPER_FILES:
            self.assertEqual((n.TOOLS / path).read_bytes(), (self.dir / path).read_bytes(), path)
        self.assertTrue((self.dir / "gradlew").stat().st_mode & stat.S_IXUSR)

    def test_the_settings_keep_the_repository_rules_add_the_library_and_name_the_project_and_module(self):
        n.scaffold(self.dir, "LyricTutor", COMMON, keystore=fake_keystore)
        settings = (self.dir / "settings.gradle.kts").read_text()
        source = (n.TOOLS / "settings.gradle.kts").read_text()

        self.assertIn('rootProject.name = "LyricTutor"', settings)
        self.assertIn('include(":app")', settings)
        self.assertNotIn(":common", settings)
        self.assertNotIn("ci-workflows\"", settings.replace("lukeneedham.github.io/ci-workflows/maven", ""))
        self.assertIn("includeGroupByRegex", settings)
        # The library's repository is asked only for its own group, and only in the dependency repositories
        library = 'maven("https://lukeneedham.github.io/ci-workflows/maven") {\n            content { includeGroup("com.lukeneedham") }'
        self.assertEqual(1, settings.count(library))
        self.assertGreater(settings.index(library), settings.index("dependencyResolutionManagement"))
        # Everything else is this repo's own, so a change of its rules reaches the new apps
        self.assertEqual(
            source.replace('rootProject.name = "ci-workflows"', 'rootProject.name = "LyricTutor"').replace('include(":common")', 'include(":app")'),
            settings.replace(n.MAVEN_REPOSITORY, "", 1))

    def test_the_gitignore_does_not_ignore_the_keystore(self):
        n.scaffold(self.dir, "LyricTutor", COMMON, keystore=fake_keystore)
        lines = (self.dir / ".gitignore").read_text().splitlines()

        self.assertEqual([".gradle/", "build/", ".kotlin/", "local.properties", ".idea/"], lines)
        self.assertFalse(any("keystore" in line for line in lines))

    def test_what_the_app_has_is_never_overwritten(self):
        (self.dir / "LICENSE").write_text("MIT License\n")
        (self.dir / "app").mkdir()
        (self.dir / "app" / "debug.keystore").write_bytes(b"mine")

        changed = n.scaffold(self.dir, "LyricTutor", COMMON, keystore=lambda p: self.fail("the keystore is there"))

        self.assertNotIn("LICENSE", changed)
        self.assertNotIn("app/debug.keystore", changed)
        self.assertEqual("MIT License\n", (self.dir / "LICENSE").read_text())
        self.assertEqual(b"mine", (self.dir / "app" / "debug.keystore").read_bytes())

    def test_a_second_run_changes_nothing(self):
        n.scaffold(self.dir, "LyricTutor", COMMON, keystore=fake_keystore)
        self.assertEqual([], n.scaffold(self.dir, "LyricTutor", COMMON, keystore=lambda p: self.fail("the keystore is there")))

    @unittest.skipUnless(shutil.which("keytool"), "needs a JDK")
    def test_the_real_keystore_opens_with_the_standard_debug_credentials(self):
        path = self.dir / "app" / "debug.keystore"
        n.make_debug_keystore(path)

        listing = subprocess.run(
            ["keytool", "-list", "-keystore", str(path), "-storepass", "android", "-alias", "androiddebugkey"],
            capture_output=True, text=True)
        self.assertEqual(0, listing.returncode, listing.stderr)
        self.assertIn("androiddebugkey", listing.stdout)

    def test_the_first_sync_and_the_scaffold_are_both_in_the_first_commit(self):
        changed = n.set_up_app(self.dir, "LyricTutor", COMMON, keystore=fake_keystore)

        self.assertIn("CLAUDE.md", changed)
        self.assertIn(".github/workflows/trigger_on_pull_request.yml", changed)
        self.assertIn(".claude/skills/lukeneedham-conventions/SKILL.md", changed)
        self.assertIn("settings.gradle.kts", changed)
        self.assertIn("app/debug.keystore", changed)
        # What the sync would make is already there, so its next run opens no PR
        self.assertEqual([], sync_apps.sync_app(self.dir))


class PushFirstCommit(unittest.TestCase):
    """The real clone, commit and push, against a bare repo on disk standing in for GitHub."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name) / "remote"
        self.bare = self.base / "LukeNeedham" / "LyricTutor.git"
        seed = Path(self._tmp.name) / "seed"
        seed.mkdir()
        self.run_git(seed, "init", "--quiet", "-b", "main")
        (seed / "README.md").write_text("# LyricTutor\n")
        self.run_git(seed, "add", "-A")
        self.run_git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "Initial commit")
        self.bare.parent.mkdir(parents=True)
        self.run_git(seed, "clone", "--quiet", "--bare", str(seed), str(self.bare))
        self.run_git(self.bare, "config", "receive.denyCurrentBranch", "ignore")
        self.work = Path(self._tmp.name) / "work"
        self.work.mkdir()
        saved = n.os.environ.get("SYNC_GIT_BASE")
        n.os.environ["SYNC_GIT_BASE"] = str(self.base)
        self.addCleanup(lambda: n.os.environ.pop("SYNC_GIT_BASE") if saved is None else n.os.environ.__setitem__("SYNC_GIT_BASE", saved))

    @staticmethod
    def run_git(directory, *args):
        return subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True, text=True).stdout

    def test_the_first_commit_lands_on_main_with_the_project_and_the_readme_kept(self):
        changed = n.push_first_commit("LukeNeedham/LyricTutor", "LyricTutor", None, str(self.work), COMMON, keystore=fake_keystore)

        self.assertIn("app/debug.keystore", changed)
        log = self.run_git(self.bare, "log", "--format=%s", "main").splitlines()
        self.assertEqual([n.COMMIT_MESSAGE, "Initial commit"], log)
        self.assertNotIn("[skip ci]", log[0], "there is a project now: the push starts its main build")
        files = self.run_git(self.bare, "ls-tree", "-r", "--name-only", "main").splitlines()
        for path in ("README.md", "CLAUDE.md", "LICENSE", "settings.gradle.kts", "gradlew", "app/debug.keystore",
                     ".github/workflows/trigger_on_pull_request.yml", ".claude/skills/lukeneedham-conventions/SKILL.md"):
            self.assertIn(path, files)
        mode = self.run_git(self.bare, "ls-tree", "main", "gradlew").split()[0]
        self.assertEqual("100755", mode, "gradlew stays executable in git")

    def test_a_second_run_pushes_nothing(self):
        n.push_first_commit("LukeNeedham/LyricTutor", "LyricTutor", None, str(self.work), COMMON, keystore=fake_keystore)
        before = self.run_git(self.bare, "rev-parse", "main")
        second_work = Path(self._tmp.name) / "work2"
        second_work.mkdir()

        changed = n.push_first_commit("LukeNeedham/LyricTutor", "LyricTutor", None, str(second_work), COMMON, keystore=fake_keystore)

        self.assertEqual([], changed)
        self.assertEqual(before, self.run_git(self.bare, "rev-parse", "main"))


class CreateRepo(unittest.TestCase):
    def github(self, extra=None):
        answers = {
            ("GET", "/user"): {"login": "LukeNeedham"},
            ("GET", "/repos/LukeNeedham/LyricTutor"): missing("/repos/LukeNeedham/LyricTutor"),
            ("POST", "/user/repos"): {"default_branch": "main"},
        }
        answers.update(extra or {})
        return FakeGithub(answers)

    def test_the_repo_is_created_with_a_readme_so_that_main_exists(self):
        call = self.github()

        repo = n.create_repo(call, "LyricTutor", private=True)

        self.assertEqual("LukeNeedham/LyricTutor", repo)
        (_, _, body), = call.made("POST")
        self.assertEqual({"name": "LyricTutor", "private": True, "auto_init": True, "description": "LyricTutor, an Android app"}, body)

    def test_a_repo_is_public_unless_private_is_asked_for(self):
        call = self.github()
        n.create_repo(call, "LyricTutor", private=False)
        self.assertIs(False, call.made("POST")[0][2]["private"])

    def test_another_default_branch_is_renamed_to_main(self):
        call = self.github({("POST", "/user/repos"): {"default_branch": "master"}})

        n.create_repo(call, "LyricTutor", private=False)

        self.assertIn(("POST", "/repos/LukeNeedham/LyricTutor/branches/master/rename", {"new_name": "main"}), call.calls)

    def test_main_is_not_renamed(self):
        call = self.github()
        n.create_repo(call, "LyricTutor", private=False)
        self.assertEqual([], [c for c in call.calls if "rename" in c[1]])

    def test_a_repo_that_exists_is_an_error(self):
        call = self.github({("GET", "/repos/LukeNeedham/LyricTutor"): {"name": "LyricTutor"}})

        with self.assertRaisesRegex(RuntimeError, "already exists"):
            n.create_repo(call, "LyricTutor", private=False)
        self.assertEqual([], call.made("POST"))

    def test_resume_carries_on_with_the_repo_that_exists_and_creates_nothing(self):
        call = self.github({("GET", "/repos/LukeNeedham/LyricTutor"): {"name": "LyricTutor"}})

        repo = n.create_repo(call, "LyricTutor", private=False, resume=True)

        self.assertEqual("LukeNeedham/LyricTutor", repo)
        self.assertEqual([], call.made("POST"))

    def test_a_token_of_another_account_is_refused_before_anything_is_made(self):
        call = self.github({("GET", "/user"): {"login": "someone-else"}})

        with self.assertRaisesRegex(RuntimeError, "someone-else"):
            n.create_repo(call, "LyricTutor", private=False)
        self.assertEqual([], call.made("POST"))

    def test_an_error_other_than_not_found_is_not_taken_for_a_free_name(self):
        call = self.github({("GET", "/repos/LukeNeedham/LyricTutor"): RuntimeError("GET /repos/x returned 500: oops")})

        with self.assertRaisesRegex(RuntimeError, "500"):
            n.create_repo(call, "LyricTutor", private=False)
        self.assertEqual([], call.made("POST"))


class RegisterApp(unittest.TestCase):
    PATH = f"/repos/{n.COMMON_REPO}/contents/apps.json"

    def file(self, text, sha="abc"):
        return {"content": base64.b64encode(text.encode()).decode(), "sha": sha}

    def test_it_commits_the_new_file_to_main_with_the_sha_it_read(self):
        call = FakeGithub({("GET", f"{self.PATH}?ref=main"): self.file(APPS, "s1")})

        added = n.register_app(call, "LyricTutor", "LukeNeedham/LyricTutor")

        self.assertTrue(added)
        (_, path, body), = call.made("PUT")
        self.assertEqual(self.PATH, path)
        self.assertEqual({"message", "content", "sha", "branch"}, set(body))
        self.assertEqual(("s1", "main", "Add LyricTutor to apps.json"), (body["sha"], body["branch"], body["message"]))
        committed = json.loads(base64.b64decode(body["content"]))
        self.assertEqual({"name": "LyricTutor", "repo": "LukeNeedham/LyricTutor"}, committed[-1])
        self.assertEqual(3, len(committed), "only the one entry is added")

    def test_an_app_that_is_listed_makes_no_commit(self):
        call = FakeGithub({("GET", f"{self.PATH}?ref=main"): self.file(APPS)})

        self.assertFalse(n.register_app(call, "AppHub", "LukeNeedham/AppHub"))
        self.assertEqual([], call.made("PUT"))

    def test_a_commit_that_landed_in_between_is_retried_on_top_of_it(self):
        newer = APPS.replace("\n]\n", ',\n  {"name": "Other", "repo": "LukeNeedham/Other"}\n]\n')
        call = FakeGithub({
            ("GET", f"{self.PATH}?ref=main"): [self.file(APPS, "old"), self.file(newer, "new")],
            ("PUT", self.PATH): [RuntimeError(f"PUT {self.PATH} returned 409: conflict"), {}],
        })

        self.assertTrue(n.register_app(call, "LyricTutor", "LukeNeedham/LyricTutor"))

        puts = call.made("PUT")
        self.assertEqual(["old", "new"], [p[2]["sha"] for p in puts])
        self.assertEqual(["AppHub", "Krillion wrapper", "Other", "LyricTutor"], [a["name"] for a in json.loads(base64.b64decode(puts[1][2]["content"]))])

    def test_another_error_is_not_retried(self):
        call = FakeGithub({
            ("GET", f"{self.PATH}?ref=main"): self.file(APPS),
            ("PUT", self.PATH): RuntimeError(f"PUT {self.PATH} returned 403: protected branch"),
        })

        with self.assertRaisesRegex(RuntimeError, "403"):
            n.register_app(call, "LyricTutor", "LukeNeedham/LyricTutor")
        self.assertEqual(1, len(call.made("PUT")))


class CreateApp(unittest.TestCase):
    """The order of the steps, and what is reported. The push is a stub: it is tested with the files above."""

    def run_it(self, pushed=("a", "b"), listed=False, **kwargs):
        events = []
        answers = {
            ("GET", "/user"): {"login": "LukeNeedham"},
            ("GET", "/repos/LukeNeedham/LyricTutor"): missing("x"),
            ("POST", "/user/repos"): {"default_branch": "main"},
            ("GET", f"/repos/{n.COMMON_REPO}/releases?per_page=100"): Always([{"tag_name": "common-0.8.0"}, {"tag_name": "v1", "draft": False}]),
            ("GET", f"/repos/{n.COMMON_REPO}/tags?per_page=100"): Always([{"name": "common-0.7.0"}]),
            ("GET", f"/repos/{n.COMMON_REPO}/contents/apps.json?ref=main"): {
                "content": base64.b64encode((APPS if not listed else APPS.replace("AppHub", "LyricTutor")).encode()).decode(), "sha": "s"},
        }
        call = FakeGithub(answers)

        def make_caller(token):
            def with_token(method, path, body=None):
                events.append((method, path, token))
                return call(method, path, body)
            return with_token

        def push(repo, name, token, work, common_version):
            events.append(("push", repo, token, common_version))
            return list(pushed)

        secrets = []
        original = sync_apps.sync_secret
        sync_apps.sync_secret = lambda app, token, commit, dry_run: secrets.append((app["repo"], token, commit)) or (" set" if commit else "")
        self.addCleanup(setattr, sync_apps, "sync_secret", original)
        lines = n.create_app("LyricTutor", push=push, make_caller=make_caller, **kwargs)
        return lines, events, secrets

    def test_the_steps_run_in_order_and_the_app_is_listed_last(self):
        lines, events, secrets = self.run_it(create_token="create", sync_token="sync", commit_token="commit")

        kinds = [(e[0], e[1]) for e in events]
        self.assertLess(kinds.index(("POST", "/user/repos")), kinds.index(("push", "LukeNeedham/LyricTutor")))
        self.assertLess(kinds.index(("push", "LukeNeedham/LyricTutor")), kinds.index(("PUT", f"/repos/{n.COMMON_REPO}/contents/apps.json")))
        self.assertEqual([("LukeNeedham/LyricTutor", "sync", "commit")], secrets)
        self.assertEqual(
            ["repo https://github.com/LukeNeedham/LyricTutor (public)", "shared library common 0.8.0", "first commit on main: 2 files",
             "secret GENERATED_COMMIT_TOKEN set", "apps.json: LyricTutor added"], lines)

    def test_the_newest_library_version_of_the_releases_and_the_tags_goes_to_the_push(self):
        _, events, _ = self.run_it(create_token="t")
        self.assertEqual(["0.8.0"], [e[3] for e in events if e[0] == "push"])

    def test_the_repo_is_made_with_the_create_token_and_the_rest_with_the_sync_token(self):
        _, events, _ = self.run_it(create_token="create", sync_token="sync", commit_token="c")

        self.assertEqual({"create"}, {e[2] for e in events if e[:2] == ("POST", "/user/repos")})
        self.assertEqual({"sync"}, {e[2] for e in events if e[0] == "push" or e[0] == "PUT"})

    def test_one_token_does_everything_when_only_one_is_given(self):
        for kwargs in ({"create_token": "t"}, {"sync_token": "t"}):
            _, events, _ = self.run_it(**kwargs)
            self.assertEqual({"t"}, {e[2] for e in events}, kwargs)

    def test_no_token_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "No token"):
            n.create_app("LyricTutor")

    def test_a_bad_name_is_refused_before_anything_is_called(self):
        with self.assertRaises(ValueError):
            n.create_app("bad name", create_token="t")

    def test_a_repo_that_is_set_up_and_listed_reports_that_nothing_was_left_to_do(self):
        lines, _, _ = self.run_it(pushed=(), listed=True, create_token="t")

        self.assertEqual("first commit: nothing to add, already done", lines[2])
        self.assertEqual("apps.json: LyricTutor was already listed", lines[4])

    def test_a_missing_commit_token_is_said_not_hidden(self):
        lines, _, _ = self.run_it(create_token="t")
        self.assertIn("secret GENERATED_COMMIT_TOKEN not set (no token for it)", lines)

    def test_a_token_that_may_not_create_repos_gets_the_hint(self):
        call = FakeGithub({
            ("GET", "/user"): {"login": "LukeNeedham"},
            ("GET", "/repos/LukeNeedham/LyricTutor"): missing("x"),
            ("POST", "/user/repos"): RuntimeError("POST /user/repos returned 403: Resource not accessible by personal access token"),
        })

        with self.assertRaisesRegex(RuntimeError, "Create it first.*resume"):
            n.create_app("LyricTutor", create_token="t", make_caller=lambda token: call)

    def test_a_private_repo_is_reported_as_private(self):
        lines, _, _ = self.run_it(create_token="t", private=True)
        self.assertEqual("repo https://github.com/LukeNeedham/LyricTutor (private)", lines[0])


class RenderedApp(unittest.TestCase):
    """The app of templates/new-app, rendered, against the rules of the docs. It cannot be compiled here (no Android SDK), so
    these checks are what stands between a typo in a template and a red first build."""

    PACKAGE = "com.lukeneedham.lyrictutor"

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)
        n.scaffold(cls.dir, "LyricTutor", COMMON, keystore=fake_keystore)
        cls.root = cls.dir / "app" / "src" / "main" / "kotlin" / "com" / "lukeneedham" / "lyrictutor"
        cls.sources = sorted(cls.dir.rglob("*.kt"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def text(self, relative):
        return (self.dir / relative).read_text()

    def ui(self, name):
        return (self.root / "ui" / name).read_text()

    def test_every_template_is_a_tmpl_and_nothing_is_left_of_a_token_or_the_suffix(self):
        templates = n.TOOLS.joinpath(*n.TEMPLATE_DIR)
        self.assertTrue(all(p.name.endswith(n.TEMPLATE_SUFFIX) for p in templates.rglob("*") if p.is_file()))
        for path in self.dir.rglob("*"):
            if path.is_file() and path.suffix not in (".jar", ".keystore") and ".git" not in path.parts:
                self.assertEqual([], n.TOKEN_RE.findall(path.read_text()), path)
                self.assertFalse(path.name.endswith(n.TEMPLATE_SUFFIX), path)
        self.assertEqual([], [p for p in self.dir.rglob("*") if "__" in p.name])

    def test_the_app_is_in_the_files_the_task_names(self):
        for relative in (
            "App.kt", "MainActivity.kt", "di/AppModule.kt",
            "ui/Root.kt", "ui/AppNavigation.kt", "ui/Router.kt", "ui/Route.kt",
            "ui/SettingsPage.kt", "ui/SettingsPageContent.kt", "ui/SettingsViewModel.kt", "ui/SettingsUiState.kt",
            "ui/theme/AppTheme.kt", "ui/theme/AppThemeValues.kt", "ui/theme/ToDebugTheme.kt",
        ):
            self.assertTrue((self.root / relative).is_file(), relative)
        self.assertTrue((self.dir / "app/src/debug/kotlin/com/lukeneedham/lyrictutor/screenshot/SettingsPage.kt").is_file())
        self.assertTrue((self.dir / "app/src/debug/kotlin/com/lukeneedham/lyrictutor/screenshot/order.txt").is_file())
        self.assertTrue((self.dir / "app/src/test/kotlin/com/lukeneedham/lyrictutor/SettingsViewModelTest.kt").is_file())

    def test_every_source_declares_the_package_of_its_folder(self):
        for path in self.sources:
            folder = path.parent.relative_to(self.dir / "app" / "src").parts[2:]  # after main|debug|test, and kotlin
            package = re.search(r"(?m)^package (\S+)$", path.read_text()).group(1)
            self.assertEqual(".".join(folder), package, path)

    def test_the_braces_of_every_source_balance(self):
        for path in self.sources:
            code = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', path.read_text())  # strings
            code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
            code = re.sub(r"//[^\n]*", "", code)
            for opening, closing in ("{}", "()", "[]"):
                self.assertEqual(code.count(opening), code.count(closing), f"{path}: {opening}{closing}")

    def test_the_versions_are_this_repos_and_the_library_is_the_one_asked_for(self):
        catalog = self.text("gradle/libs.versions.toml")
        repo = (n.TOOLS / "gradle" / "libs.versions.toml").read_text()
        for key in ("agp", "kotlin"):
            self.assertIn(re.search(rf'(?m)^{key} = "[^"]+"$', repo).group(0), catalog)
        kotlin = re.search(r'(?m)^kotlin = "([^"]+)"', repo).group(1)
        self.assertIn(f'ksp = "{kotlin}-2.0.4"', catalog)
        self.assertIn(f'common = "{COMMON}"', catalog)

    def test_every_alias_the_build_uses_is_in_the_catalog(self):
        catalog = self.text("gradle/libs.versions.toml")
        libraries, plugins = (
            {m.replace("-", ".") for m in re.findall(r"(?m)^([\w-]+) = ", section)}
            for section in re.split(r"(?m)^\[plugins\]", catalog.split("[libraries]")[1])
        )
        for build in ("build.gradle.kts", "app/build.gradle.kts"):
            for alias in re.findall(r"libs\.plugins\.([\w.]+)", self.text(build)):
                self.assertIn(alias, plugins, f"{build}: libs.plugins.{alias}")
            for alias in re.findall(r"libs\.(?!plugins\.|versions\.)([\w.]+)", self.text(build)):
                self.assertIn(alias, libraries, f"{build}: libs.{alias}")

    def test_the_dependencies_of_the_architecture_are_all_there(self):
        build = self.text("app/build.gradle.kts")
        for needle in (
            "libs.common", "libs.compose.ui)", "libs.compose.foundation", "libs.androidx.activity.compose",
            "libs.androidx.navigation3.runtime", "libs.androidx.navigation3.ui", "libs.androidx.lifecycle.viewmodel.navigation3",
            "libs.koin.android", "libs.koin.compose.viewmodel", "platform(libs.koin.bom)",
            "libs.coil.compose", "libs.coil.network.okhttp",
            "libs.kotlinx.serialization.json", "libs.kotlinx.coroutines.android", "libs.kotlinx.datetime",
            "libs.room.runtime", "libs.room.ktx", "ksp(libs.room.compiler)", "libs.datastore.preferences",
            "libs.ktor.client.okhttp", "libs.ktor.client.core", "libs.media3.exoplayer",
            "libs.junit", "libs.kotlinx.coroutines.test", "libs.plugins.kotlinSerialization", "libs.plugins.composeCompiler",
        ):
            self.assertIn(needle, build)
        self.assertNotIn("material", build.lower(), "no Material: the app has its own theme")

    def test_the_project_follows_the_standard_of_new_app_md(self):
        build = self.text("app/build.gradle.kts")
        self.assertIn(f'namespace = "{self.PACKAGE}"', build)
        self.assertIn(f'applicationId = "{self.PACKAGE}"', build)
        for needle in ("compileSdk = 36", "targetSdk = 36", "minSdk = 23", 'storeFile = file("debug.keystore")', "buildConfig = true",
                       "isMinifyEnabled = true", "isShrinkResources = true", "VERSION_17"):
            self.assertIn(needle, build)
        self.assertIn(self.PACKAGE, self.text("app/proguard-rules.pro"))
        self.assertIn("com.lukeneedham.common.logger.LogEntry", self.text("app/proguard-rules.pro"))

    def test_every_library_api_the_app_imports_exists_in_common(self):
        declarations = "\n".join(p.read_text() for p in (n.TOOLS / "common" / "src").rglob("*.kt"))
        used = {i for path in self.sources for i in re.findall(r"(?m)^import com\.lukeneedham\.common\.([\w.]+)$", path.read_text())}
        self.assertTrue(used)
        for name in used:
            simple = name.split(".")[-1]
            self.assertRegex(declarations, rf"\b(fun|class|object|val|var|interface)\s+(\w+\.)?{simple}\b", f"common.{name}")

    def test_the_shell_is_the_one_of_app_shell_md(self):
        everything = {p.name: p.read_text() for p in self.sources if "/src/main/" in p.as_posix()}
        for text in everything.values():
            for forbidden in ("NavHost(", "entryProvider {", "MaterialTheme", "material3"):
                self.assertNotIn(forbidden, text)
        self.assertEqual(["MainActivity.kt"], [n for n, t in everything.items() if "ComponentActivity()" in t])
        self.assertEqual(["MainActivity.kt"], [name for name, text in everything.items() if "setContent" in text])
        self.assertIn("setContent { Root() }", everything["MainActivity.kt"])
        root = everything["Root.kt"]
        self.assertLess(root.index("AppTheme {"), root.index("ProvideDebugSettings("))
        self.assertLess(root.index("ProvideDebugSettings("), root.index("AppNavigation()"))
        self.assertIn("toDebugTheme()", root)

    def test_the_router_has_a_branch_for_every_route_and_no_else(self):
        route, router = self.ui("Route.kt"), self.ui("Router.kt")
        members = re.findall(r"data (?:object|class) (\w+)", route)
        self.assertEqual(["Settings", "Debug", "Logs", "Crashes"], members)
        for member in members:
            self.assertIn(f"Route.{member} ->", router)
        self.assertNotIn("else ->", router)
        self.assertEqual(1, route.count("sealed interface Route : NavKey"))
        self.assertIn("Route.Settings -> SettingsPage(", router)
        for page in ("DebugPage", "LogsPage", "CrashesPage"):
            self.assertIn(f"{page}(", router)

    def test_the_application_starts_the_library_first_then_koin(self):
        app = (self.root / "App.kt").read_text()
        body = app.split("override fun onCreate() {")[1]
        self.assertLess(body.index("super.onCreate()"), body.index("DebugKit.init("))
        self.assertLess(body.index("DebugKit.init("), body.index("startKoin"))
        self.assertIn("BuildConfig.DEBUG", app)

    def test_the_settings_page_is_the_page_pattern_with_a_file_for_each(self):
        page, content, model, state = (self.ui(f"Settings{x}.kt") for x in ("Page", "PageContent", "ViewModel", "UiState"))
        self.assertIn("fun SettingsPage(onOpenDebug: () -> Unit)", page)
        self.assertIn("koinViewModel<SettingsViewModel>()", page)
        self.assertNotIn("@Preview", page)
        self.assertIn("SettingsPageContent(state = state, onOpenDebug = onOpenDebug)", page)
        self.assertIn("internal fun SettingsPageContent(", content)
        self.assertIn("private fun Preview()", content)
        self.assertEqual(1, content.count("@Preview"))
        self.assertIn("class SettingsViewModel(", model)
        self.assertIn("class SettingsUiState(", state)
        for name, text in (("SettingsPageContent", page), ("SettingsViewModel", content), ("SettingsUiState", content), ("SettingsPage(", model)):
            self.assertNotIn(f"fun {name}" if name[0] != "S" or "(" in name else f"class {name}", text)
        for forbidden in ("koinViewModel", "ViewModel()", "Flow<", "collectAsState"):
            self.assertNotIn(forbidden, content, "the content is stateless: state down, events up")

    def test_the_settings_page_shows_only_the_debug_button_that_opens_the_debug_page(self):
        content = self.ui("SettingsPageContent.kt")
        self.assertIn("DebugButton(onClick = onOpenDebug)", content)
        self.assertIn("Route.Settings -> SettingsPage(onOpenDebug = { navigateTo(Route.Debug) })", self.ui("Router.kt"))
        self.assertIn("Route.Debug -> DebugPage(", self.ui("Router.kt"))

    def test_all_text_of_the_ui_is_in_strings_xml(self):
        content = self.ui("SettingsPageContent.kt")
        self.assertIn("stringResource(R.string.settings_title)", content)
        self.assertNotRegex(content, r'text = "')
        strings = self.text("app/src/main/res/values/strings.xml")
        self.assertIn('<string name="settings_title">', strings)
        self.assertIn('<string name="app_name">LyricTutor</string>', strings)

    def test_the_theme_is_the_apps_own_and_maps_every_debug_colour(self):
        theme, values, mapping = (self.ui(f"theme/{x}.kt") for x in ("AppTheme", "AppThemeValues", "ToDebugTheme"))
        self.assertIn("object AppTheme", theme)
        self.assertIn("fun AppTheme(", theme)
        self.assertIn("val current: AppThemeValues", theme)
        self.assertIn("isSystemInDarkTheme()", theme)
        debug_theme = (n.TOOLS / "common/src/commonMain/kotlin/com/lukeneedham/common/ui/DebugTheme.kt").read_text()
        for field in re.findall(r"(?m)^    val (\w+):", debug_theme):
            self.assertIn(f"{field} = {field}", mapping, f"DebugTheme.{field}")
            self.assertRegex(values, rf"val {field}: ")

    def test_the_screenshot_package_passes_the_checks_of_ci(self):
        import check_screenshot_package as check

        self.assertEqual([], check.setup_problems(self.dir))
        screenshot = self.dir / "app/src/debug/kotlin/com/lukeneedham/lyrictutor/screenshot/SettingsPage.kt"
        self.assertEqual([], check.problems(screenshot.read_text()))
        self.assertEqual(["SettingsPage"], check.preview_names(self.dir))
        self.assertEqual("SettingsPage\n", (screenshot.parent / "order.txt").read_text())

    def test_the_resources_are_well_formed_and_the_manifest_resolves_into_them(self):
        import xml.etree.ElementTree as ET

        for path in (self.dir / "app" / "src" / "main").rglob("*.xml"):
            ET.parse(path)
        manifest = self.text("app/src/main/AndroidManifest.xml")
        self.assertIn('android:name=".App"', manifest)
        self.assertIn('android:name=".MainActivity"', manifest)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertIn("android.permission.INTERNET", manifest)
        self.assertIn('android:theme="@style/Theme.App"', manifest)
        self.assertIn('<style name="Theme.App"', self.text("app/src/main/res/values/themes.xml"))
        icon = self.text("app/src/main/res/mipmap-anydpi/ic_launcher.xml")
        self.assertIn("<adaptive-icon", icon)
        self.assertTrue((self.dir / "app/src/main/res/drawable/ic_launcher_foreground.xml").is_file())
        self.assertIn('name="ic_launcher_background"', self.text("app/src/main/res/values/colors.xml"))

    def test_the_viewmodel_test_and_the_koin_module_agree_on_the_constructor(self):
        self.assertIn("SettingsViewModel(isDebugEnabled = DebugKit.enabled)", self.text("app/src/main/kotlin/com/lukeneedham/lyrictutor/di/AppModule.kt"))
        self.assertIn("class SettingsViewModel(isDebugEnabled: Boolean)", self.ui("SettingsViewModel.kt"))
        self.assertIn("SettingsViewModel(isDebugEnabled = true)", self.text("app/src/test/kotlin/com/lukeneedham/lyrictutor/SettingsViewModelTest.kt"))

    def test_a_second_run_changes_nothing_and_an_existing_file_is_kept(self):
        self.assertEqual([], n.scaffold(self.dir, "LyricTutor", COMMON, keystore=lambda p: self.fail("there")))
        with tempfile.TemporaryDirectory() as other:
            other = Path(other)
            (other / "app").mkdir()
            (other / "app" / "build.gradle.kts").write_text("mine")
            changed = n.scaffold(other, "LyricTutor", COMMON, keystore=fake_keystore)
            self.assertEqual("mine", (other / "app" / "build.gradle.kts").read_text())
            self.assertNotIn("app/build.gradle.kts", changed)

    def test_a_template_with_a_token_that_nothing_fills_is_refused(self):
        with tempfile.TemporaryDirectory() as tools:
            tools = Path(tools)
            template = tools.joinpath(*n.TEMPLATE_DIR)
            template.mkdir(parents=True)
            (template / "a.txt.tmpl").write_text("hello __NOT_A_TOKEN__")
            (tools / "gradle").mkdir()
            (tools / "gradle" / "libs.versions.toml").write_text('agp = "1"\nkotlin = "2"\n')
            with self.assertRaisesRegex(ValueError, "__NOT_A_TOKEN__"):
                n.render_templates(Path(tools) / "out", n.template_values("LyricTutor", COMMON, tools), [], tools)


class CommonVersion(unittest.TestCase):
    def test_the_newest_version_is_taken_by_number_not_by_text(self):
        self.assertEqual("0.10.1", n.latest_common_version(["common-0.8.0", "common-0.10.1", "common-0.9.0", "v3", "common-1.x"]))

    def test_no_release_of_the_library_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "No release"):
            n.latest_common_version(["v1", "main-build"])

    def test_drafts_are_not_taken(self):
        call = FakeGithub({
            ("GET", f"/repos/{n.COMMON_REPO}/releases?per_page=100"): Always([
                {"tag_name": "common-0.9.0", "draft": True}, {"tag_name": "common-0.8.0", "draft": False}]),
            ("GET", f"/repos/{n.COMMON_REPO}/tags?per_page=100"): Always([]),
        })
        self.assertEqual("0.8.0", n.fetch_common_version(call))


class Summary(unittest.TestCase):
    def test_the_next_steps_name_the_repo_the_package_and_what_is_left_to_do(self):
        text = n.next_steps("LyricTutor")

        self.assertIn("https://github.com/LukeNeedham/LyricTutor", text)
        self.assertIn("com.lukeneedham.lyrictutor", text)
        self.assertIn("installations/select_target", text)
        self.assertIn("https://claude.ai/code/new?repo=LukeNeedham%2FLyricTutor", text)


if __name__ == "__main__":
    unittest.main()
