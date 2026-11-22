#!/usr/bin/env python3
"""The preview of a pull request of a Next.js website (web_pr.yml): finds the URL of the Vercel preview deployment, checks
that it opens without a login, and writes the body of the PR comment that links to it.

Vercel builds every PR through its GitHub integration and reports the deployment to GitHub (a deployment of the
environment "Preview", with a status that has the URL). This reads that, so CI needs no Vercel token.

    python3 web_preview.py --repo R --pr N --sha SHA --body-file comment.md [--timeout SECONDS]

Sets the step outputs `url` and `public` ("true" or "false"), and writes the comment to --body-file. The comment holds the
URL as `<!-- preview-url: URL -->` on a line of its own, so that AppHub can read it from the PR (docs/next-js-app.md).
Uses GH_TOKEN for the GitHub API. Exits 1 when there is no preview, and 2 when the preview asks for a login.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghactions import error, output

# The comment of the PR is one per PR (a sticky comment with this header), updated by each push
HEADER = "web-preview-link"
URL_MARKER = "preview-url"
# What a protected Vercel preview answers: 401, or a redirect to the login of Vercel
LOGIN_HOSTS = ("vercel.com/sso", "vercel.com/login")


def api(path):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def is_preview_deployment(deployment):
    """Whether [deployment] is one of Vercel's previews: the environment is "Preview", or "Preview – <project>" in a monorepo."""
    return str(deployment.get("environment", "")).lower().startswith("preview")


def preview_url(deployments, statuses_of):
    """The URL and state of the preview of the newest preview deployment in [deployments] (newest first), or (None, state).
    [statuses_of] gets a deployment and returns its statuses, newest first. A deployment whose newest status has no
    URL yet is still being built: its state ("pending", "in_progress", "queued"... or "failure", "error") is returned."""
    state = None
    for deployment in deployments:
        if not is_preview_deployment(deployment):
            continue
        statuses = statuses_of(deployment)
        if not statuses:
            state = state or "pending"
            continue
        newest = statuses[0]
        if newest.get("state") == "success":
            return newest.get("environment_url") or newest.get("target_url"), "success"
        return None, newest.get("state", "pending")
    return None, state or "missing"


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def asks_for_login(status, location):
    """Whether an anonymous request that got [status] and the redirect [location] was refused for want of a login."""
    if status in (401, 403):
        return True
    return 300 <= status < 400 and any(host in (location or "") for host in LOGIN_HOSTS)


def is_public(url):
    """Whether [url] opens for someone who is not logged in to Vercel."""
    opener = urllib.request.build_opener(NoRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": "ci-workflows-preview-check"})
    try:
        with opener.open(request, timeout=30) as response:
            status, location = response.status, response.headers.get("Location")
    except urllib.error.HTTPError as e:
        status, location = e.code, e.headers.get("Location")
    return not asks_for_login(status, location)


def comment_body(url, sha, public):
    commit = sha[:7]
    if not public:
        return (
            f"### 🔒 Preview needs a login\n\n"
            f"- **Commit:** `{commit}`\n- **Preview:** {url}\n\n"
            f"Vercel asks for a login to open this preview. Turn off *Deployment Protection* for previews in the project's "
            f"settings on Vercel (`docs/next-js-app.md`).\n\n<!-- {URL_MARKER}: {url} -->\n"
        )
    return f"### 🌐 Preview\n\n- **Commit:** `{commit}`\n- **Preview:** {url}\n\n<!-- {URL_MARKER}: {url} -->\n"


def waiting_body(sha, state):
    return f"### ⏳ Preview not ready\n\n- **Commit:** `{sha[:7]}`\n- **Vercel:** {state}\n"


def find(repo, sha, timeout, interval=10, clock=time.monotonic, sleep=time.sleep, get=api):
    """Waits for the preview of [sha] and returns (url, state). The url is None when it did not succeed within [timeout]
    seconds, and the state says why."""
    deadline = clock() + timeout
    while True:
        deployments = get(f"/repos/{repo}/deployments?sha={sha}&per_page=20")
        url, state = preview_url(deployments, lambda d: get(f"/repos/{repo}/deployments/{d['id']}/statuses?per_page=5"))
        if url or state in ("failure", "error", "inactive") or clock() >= deadline:
            return url, state
        sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for Vercel to finish the preview")
    args = parser.parse_args()

    url, state = find(args.repo, args.sha, args.timeout)
    if not url:
        Path(args.body_file).write_text(waiting_body(args.sha, state))
        error(f"No preview deployment of {args.sha[:7]} succeeded on Vercel (state: {state}). Is the repo connected to a Vercel project?",
              "No preview")
        sys.exit(1)

    public = is_public(url)
    output("url", url)
    output("public", "true" if public else "false")
    Path(args.body_file).write_text(comment_body(url, args.sha, public))
    if not public:
        error(f"{url} asks for a login. Turn off Deployment Protection for previews in the Vercel project (docs/next-js-app.md).",
              "Preview is not public")
        sys.exit(2)


if __name__ == "__main__":
    main()
