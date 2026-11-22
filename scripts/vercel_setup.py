#!/usr/bin/env python3
"""Sets up a website on Vercel (docs/next-js-app.md): the project, connected to the GitHub repo so that every pull request gets a
preview and `main` is deployed, and Deployment Protection off for previews, so that a preview opens without a login (web_preview.py
fails a PR whose preview asks for one).

Every step can be repeated: a project that is there is carried on with, and a setting that is right is left alone. The project is
the one that is already connected to the repo, whatever its name (PersonalWebsite is `personal-website` there); only when there is
none is one created, named after the repo.

    VERCEL_TOKEN=... python3 vercel_setup.py LukeNeedham/PersonalWebsite [--project NAME] [--team ID] [--dry-run]

Environment: VERCEL_TOKEN (needed), VERCEL_TEAM_ID (optional: the team the project belongs to; a personal account has none).
The Vercel GitHub app must be installed for the repo (a one-time step of the account on https://vercel.com/account/login-connections
or the project's Git settings): Vercel refuses to connect a repo it cannot see, and the error says so.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.vercel.com"
GET_PROJECT = "/v9/projects/{id}"
CREATE_PROJECT = "/v11/projects"
UPDATE_PROJECT = "/v9/projects/{id}"
# The characters of a Vercel project name: lower case letters, digits, '.', '_' and '-', at most 100, and never '---'
MAX_NAME = 100


class VercelError(RuntimeError):
    """A call that failed, with the status and the answer of Vercel in the message."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


def project_name(repo_name):
    """The name of the Vercel project for a repo: lower case, with what the name cannot have (anything but letters, digits, '.',
    '_' and '-') changed to '-', and no run of three dashes."""
    name = re.sub(r"[^a-z0-9._-]", "-", repo_name.lower())
    name = re.sub(r"-{3,}", "--", name)[:MAX_NAME]
    if not name.strip("-._"):
        raise ValueError(f"No project name can be made from {repo_name!r}")
    return name


def make_call(token, team=None):
    """`call(method, path, body=None)` of the Vercel API: returns (status, json). It does not raise for an HTTP error."""

    def call(method, path, body=None):
        query = "?" + urllib.parse.urlencode({"teamId": team}) if team else ""
        request = urllib.request.Request(
            f"{API}{path}{query}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {token}", **({"Content-Type": "application/json"} if body is not None else {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": {"message": raw[:300]}}

    return call


def error_of(status, answer):
    """The message and the code of an error answer of Vercel: {"error": {"code": ..., "message": ...}}."""
    error = (answer or {}).get("error") if isinstance(answer, dict) else None
    if not isinstance(error, dict):
        return f"status {status}", None
    return f"{error.get('message', 'status ' + str(status))} ({error.get('code', status)})", error.get("code")


def fail(what, status, answer):
    message, code = error_of(status, answer)
    hint = ""
    if status in (401, 403):
        hint = " VERCEL_TOKEN is missing, wrong, or may not use this team (VERCEL_TEAM_ID)."
    elif "github" in message.lower() or "install" in (code or "").lower() or "repo" in (code or "").lower():
        hint = " Install the Vercel GitHub app for this repo (https://github.com/apps/vercel) and run again."
    raise VercelError(f"{what}: {message}.{hint}", status, code)


def linked_repo(project):
    """`owner/name` of the repo a project is connected to, or None. A project says it as link: {type, org, repo}."""
    link = project.get("link") or {}
    if link.get("org") and link.get("repo"):
        return f"{link['org']}/{link['repo']}"
    return link.get("repo") or None


def find_linked_project(call, repo, max_pages=5):
    """The project that is already connected to the GitHub repo [repo] (owner/name), whatever it is called, or None. Reads the
    projects the token can see, a page of 100 at a time."""
    path = "/v9/projects?limit=100"
    for _ in range(max_pages):
        status, answer = call("GET", path)
        if status != 200:
            fail("Listing the Vercel projects", status, answer)
        for found in answer.get("projects") or []:
            connected = linked_repo(found)
            if connected and connected.lower() == repo.lower():
                return found
        after = (answer.get("pagination") or {}).get("next")
        if not after:
            return None
        path = f"/v9/projects?limit=100&until={after}"
    return None


def ensure_project(call, name, repo):
    """The Vercel project [name], connected to the GitHub repo [repo] (owner/name). Creates it when there is none.
    Returns (project, created). A project of this name that is connected to another repo is an error: it is not this site's."""
    status, project = call("GET", GET_PROJECT.format(id=urllib.parse.quote(name)))
    if status == 200:
        connected = linked_repo(project)
        if connected and connected.lower() != repo.lower():
            raise VercelError(f"The Vercel project {name} is connected to {connected}, not {repo}. Use another --project name.")
        if not connected:
            raise VercelError(f"The Vercel project {name} exists and is connected to no repo. Connect it to {repo} in its Git settings, or use another --project name.")
        return project, False
    if status != 404:
        fail(f"Reading the Vercel project {name}", status, project)
    status, created = call("POST", CREATE_PROJECT, {
        "name": name,
        "framework": "nextjs",
        "gitRepository": {"type": "github", "repo": repo},
    })
    if status not in (200, 201):
        fail(f"Creating the Vercel project {name}", status, created)
    return created, True


def previews_are_public(project):
    """Whether the project asks for no login to open a preview: it has no Vercel Authentication (`ssoProtection`)."""
    return not project.get("ssoProtection")


def open_previews(call, project):
    """Turns Deployment Protection off (`ssoProtection: null`), so that a preview opens without a login. Returns whether it changed.
    The answer is read again: a setting that the plan does not allow would otherwise look done."""
    if previews_are_public(project):
        return False
    status, answer = call("PATCH", UPDATE_PROJECT.format(id=project["id"]), {"ssoProtection": None})
    if status != 200:
        fail(f"Turning Deployment Protection off for {project.get('name')}", status, answer)
    status, again = call("GET", GET_PROJECT.format(id=project["id"]))
    if status != 200 or not previews_are_public(again):
        raise VercelError(
            f"Vercel accepted the change but {project.get('name')} still has Deployment Protection on "
            f"(ssoProtection: {(again or {}).get('ssoProtection')}). Turn it off in the project's settings.")
    return True


def target_name(call, repo):
    """The name of the project to set up for [repo]: the one already connected to it, else the one a new project would get."""
    linked = find_linked_project(call, repo)
    return linked["name"] if linked else project_name(repo.split("/")[1])


def set_up(call, repo, project=None):
    """Sets up the website [repo] on Vercel. Returns the lines to report, one per step."""
    name = project or target_name(call, repo)
    found, created = ensure_project(call, name, repo)
    lines = [f"vercel project {found.get('name', name)} " + (f"created and connected to {repo}" if created else f"already connected to {repo}")]
    changed = open_previews(call, found)
    lines.append("vercel previews: Deployment Protection " + ("turned off" if changed else "was off already"))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", help="the GitHub repo of the website, owner/name")
    parser.add_argument("--project", help="the name of the Vercel project (default: the repo's name, lower case)")
    parser.add_argument("--team", default=os.environ.get("VERCEL_TEAM_ID"), help="the team id, if the project belongs to a team")
    parser.add_argument("--dry-run", action="store_true", help="read the project and say what would change; change nothing")
    args = parser.parse_args()
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print("::error::VERCEL_TOKEN is not set. See docs/next-js-app.md.")
        sys.exit(1)
    print(f"::add-mask::{token}")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print(f"::error::{args.repo!r} is not owner/name")
        sys.exit(1)
    call = make_call(token, args.team)
    try:
        if args.dry_run:
            name = args.project or target_name(call, args.repo)
            status, found = call("GET", GET_PROJECT.format(id=urllib.parse.quote(name)))
            print(f"vercel project {name}: " + (
                "not there, would be created" if status == 404 else
                f"connected to {linked_repo(found)}, previews {'public' if previews_are_public(found) else 'ask for a login'}"
                if status == 200 else f"status {status}"))
            return
        print("\n".join(set_up(call, args.repo, args.project)))
    except (VercelError, ValueError) as e:
        print(f"::error::{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
