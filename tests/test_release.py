import io
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _paths  # noqa: F401
import release as r
from fakes import FakeGh

SECRETS = {"KEYSTORE_BASE64": "a", "KEYSTORE_PASSWORD": "b", "KEY_ALIAS": "c", "KEY_PASSWORD": "d"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def run(function, *args, **kwargs):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = function(*args, **kwargs)
    return code, buffer.getvalue()


class ReleaseChecksTest(unittest.TestCase):
    def project(self, gradle="plugins { }\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "app").mkdir()
        (root / "app" / "build.gradle.kts").write_text(gradle)
        return root

    def test_the_versions_that_can_be_released(self):
        for good in ("0.3.0", "10.20.30"):
            self.assertTrue(r.is_semver(good), good)
        for bad in ("v0.3.0", "0.3", "0.3.0-beta", "0.3.0\n", ""):
            self.assertFalse(r.is_semver(bad), bad)

    def test_an_app_that_is_set_up_passes(self):
        root = self.project('apply(from = "https://raw.githubusercontent.com/o/r/main/gradle/android-release.gradle")\n')
        self.assertEqual((0, ""), run(r.check_setup, SECRETS, root))

    def test_everything_that_is_missing_is_in_one_report(self):
        code, out = run(r.check_setup, {"KEYSTORE_BASE64": "a", "KEY_ALIAS": ""}, self.project())
        self.assertEqual(1, code)
        self.assertIn("Missing repo secrets: RELEASE_KEYSTORE_PASSWORD RELEASE_KEY_ALIAS RELEASE_KEY_PASSWORD", out)
        self.assertNotIn("RELEASE_KEYSTORE_BASE64", out)
        self.assertIn("does not apply gradle/android-release.gradle", out)
        self.assertEqual(2, out.count("::error title=This repo cannot publish a release yet::"))

    def test_only_the_gradle_script_missing(self):
        code, out = run(r.check_setup, SECRETS, self.project())
        self.assertEqual(1, code)
        self.assertNotIn("Missing repo secrets", out)

    def test_the_version_must_be_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote, app = Path(tmp) / "remote.git", Path(tmp) / "app"
            git(tmp, "init", "--bare", "-b", "main", str(remote))
            git(tmp, "clone", "-q", str(remote), str(app))
            git(app, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
            git(app, "tag", "0.3.0")
            git(app, "push", "-q", "origin", "HEAD:main", "refs/tags/0.3.0")
            code, out = run(r.check_version, "0.3.0", cwd=app)
            self.assertEqual(1, code)
            self.assertIn("Tag 0.3.0 already exists", out)
            self.assertEqual((0, ""), run(r.check_version, "0.4.0", cwd=app))
            code, out = run(r.check_version, "v0.4.0", cwd=app)
            self.assertEqual(1, code)
            self.assertIn("Version must look like 0.3.0, got 'v0.4.0'", out)


class SigningTest(unittest.TestCase):
    def test_the_keystore_is_restored_and_its_path_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "env"
            os.environ["GITHUB_ENV"] = str(env_file)
            try:
                code, _ = run(r.restore_key, {"KEYSTORE_BASE64": "aGVsbG8=\n", "RUNNER_TEMP": tmp})
            finally:
                del os.environ["GITHUB_ENV"]
            self.assertEqual(0, code)
            self.assertEqual(b"hello", (Path(tmp) / "release.keystore").read_bytes())
            self.assertEqual(f"RELEASE_KEYSTORE_FILE={Path(tmp) / 'release.keystore'}\n", env_file.read_text())

    def test_a_missing_secret_fails(self):
        code, out = run(r.restore_key, {"RUNNER_TEMP": "/tmp"})
        self.assertEqual(1, code)
        self.assertIn("RELEASE_KEYSTORE_BASE64 is not set", out)

    def test_the_newest_build_tools_win_by_number_not_by_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version in ("9.0.0", "34.0.0", "35.0.1"):
                tool = Path(tmp) / "build-tools" / version / "apksigner"
                tool.parent.mkdir(parents=True)
                tool.write_text("#!/bin/sh\n")
            self.assertEqual("35.0.1", r.newest_apksigner(tmp).parent.name)
            self.assertIsNone(r.newest_apksigner(Path(tmp) / "nowhere"))

    def test_the_apk_must_exist_and_be_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = Path(tmp) / "build-tools" / "35.0.0" / "apksigner"
            tool.parent.mkdir(parents=True)
            seen = Path(tmp) / "seen"
            tool.write_text(f"#!/bin/sh\necho \"$@\" > {seen}\nexit ${{APKSIGNER_EXIT:-0}}\n")
            tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
            apk = Path(tmp) / "app-release.apk"
            env = {"ANDROID_HOME": tmp}
            code, out = run(r.check_signed, str(apk), env)
            self.assertEqual(1, code)
            self.assertIn("The release APK was not built", out)
            apk.write_text("apk")
            code, out = run(r.check_signed, str(apk), env)
            self.assertEqual(0, code)
            self.assertEqual(f"verify --print-certs {apk}", seen.read_text().strip())
            os.environ["APKSIGNER_EXIT"] = "1"
            try:
                self.assertEqual(1, run(r.check_signed, str(apk), env)[0])
            finally:
                del os.environ["APKSIGNER_EXIT"]


class PublishTest(unittest.TestCase):
    def test_it_publishes_with_the_notes_or_generated_ones(self):
        for notes, expected in (("Fixes it", ["--notes", "Fixes it"]), ("", ["--generate-notes"])):
            with tempfile.TemporaryDirectory() as tmp, FakeGh() as gh:
                cwd = os.getcwd()
                os.chdir(tmp)
                try:
                    (Path(tmp) / "app-release.apk").write_text("apk")
                    self.assertEqual(0, r.publish("0.3.0", notes, "app-release.apk", "Demo.apk"))
                    self.assertTrue((Path(tmp) / "Demo.apk").is_file())
                finally:
                    os.chdir(cwd)
            self.assertEqual(["release", "create", "0.3.0", "Demo.apk", "--title", "0.3.0", "--latest", *expected], gh.calls[0])


if __name__ == "__main__":
    unittest.main()
