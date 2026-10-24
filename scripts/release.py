#!/usr/bin/env python3
"""The checks and steps of the release workflow (android_release.yml), run in the app's checkout.

    python3 release.py check-setup
    python3 release.py check-version --version 0.3.0
    python3 release.py restore-key
    python3 release.py check-signed --apk app/build/outputs/apk/release/app-release.apk
    python3 release.py publish --version 0.3.0 --notes "" --apk APK --asset-name Name.apk

The secrets come in the environment: KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS and KEY_PASSWORD (the RELEASE_*
secrets of the workflow). Every failure is an error annotation and a non-zero exit code.
"""

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import error, export_env

GUIDE = "https://github.com/LukeNeedham/ci-workflows/blob/main/docs/setup.md#3-permanent-releases-optional"
SECRETS = {
    "KEYSTORE_BASE64": "RELEASE_KEYSTORE_BASE64",
    "KEYSTORE_PASSWORD": "RELEASE_KEYSTORE_PASSWORD",
    "KEY_ALIAS": "RELEASE_KEY_ALIAS",
    "KEY_PASSWORD": "RELEASE_KEY_PASSWORD",
}


def is_semver(version):
    """major.minor.patch, with no v prefix."""
    return re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is not None


def applies_release_script(root):
    """Whether a Gradle file of the project applies gradle/android-release.gradle."""
    for path in Path(root).rglob("*"):
        if path.is_file() and path.name.endswith((".gradle", ".gradle.kts")):
            if re.search(r"android-release\.gradle", path.read_text(errors="ignore")):
                return True
    return False


def check_setup(env, root="."):
    """Everything an app needs to publish releases, reported in one go before anything is tagged or built."""
    failed = False
    missing = [secret for variable, secret in SECRETS.items() if not env.get(variable)]
    if missing:
        error(f"Missing repo secrets: {' '.join(missing)}. Add them under Settings > Secrets and variables > Actions. "
              f"How: {GUIDE}", title="This repo cannot publish a release yet")
        failed = True
    if not applies_release_script(root):
        error("The app's build.gradle.kts does not apply gradle/android-release.gradle, which sets the version from "
              f"the tag and the release signing. How: {GUIDE}", title="This repo cannot publish a release yet")
        failed = True
    return 1 if failed else 0


def check_version(version, cwd=None):
    if not is_semver(version):
        error(f"Version must look like 0.3.0, got '{version}'")
        return 1
    exists = subprocess.run(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{version}"],
                            capture_output=True, cwd=cwd)
    if exists.returncode == 0:
        error(f"Tag {version} already exists. Pick a new version.")
        return 1
    return 0


def restore_key(env):
    """Writes the keystore from its secret and exports its path for the Gradle build."""
    encoded = env.get("KEYSTORE_BASE64")
    if not encoded:
        error("Secret RELEASE_KEYSTORE_BASE64 is not set")
        return 1
    path = Path(env["RUNNER_TEMP"]) / "release.keystore"
    path.write_bytes(base64.b64decode(encoded))
    export_env("RELEASE_KEYSTORE_FILE", str(path))
    return 0


def newest_apksigner(android_home):
    """The apksigner of the newest build-tools version."""
    def version(path):
        return [int(n) for n in re.findall(r"\d+", path.parent.name)]
    found = sorted(Path(android_home).glob("build-tools/*/apksigner"), key=version)
    return found[-1] if found else None


def check_signed(apk, env):
    if not Path(apk).is_file():
        error(f"Expected it at {apk}. Every app builds its release APK there (module app, ./gradlew assembleRelease).",
              title="The release APK was not built")
        return 1
    apksigner = newest_apksigner(env.get("ANDROID_HOME", ""))
    if apksigner is None:
        error("Cannot find apksigner in the build-tools of ANDROID_HOME")
        return 1
    return subprocess.run([str(apksigner), "verify", "--print-certs", apk]).returncode


def publish(version, notes, apk, asset_name):
    shutil.copy(apk, asset_name)
    notes_args = ["--notes", notes] if notes else ["--generate-notes"]
    return subprocess.run(["gh", "release", "create", version, asset_name, "--title", version, "--latest", *notes_args]).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-setup")
    commands.add_parser("restore-key")
    commands.add_parser("check-version").add_argument("--version", required=True)
    commands.add_parser("check-signed").add_argument("--apk", required=True)
    p = commands.add_parser("publish")
    p.add_argument("--version", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--apk", required=True)
    p.add_argument("--asset-name", required=True)
    a = parser.parse_args()
    if a.command == "check-setup":
        code = check_setup(os.environ)
    elif a.command == "check-version":
        code = check_version(a.version)
    elif a.command == "restore-key":
        code = restore_key(os.environ)
    elif a.command == "check-signed":
        code = check_signed(a.apk, os.environ)
    else:
        code = publish(a.version, a.notes, a.apk, a.asset_name)
    sys.exit(code)


if __name__ == "__main__":
    main()
