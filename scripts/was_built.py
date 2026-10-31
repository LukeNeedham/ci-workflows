#!/usr/bin/env python3
"""Says whether the commit [sha] of a pull request was built by CI, for app_config.py.

A push that changes only generated files is not built: it is CI's own commit, and the code under it was built by its own run. That
holds only if the code under it *was* built. When two pushes land within seconds of each other (a person's, then CI's) the first can
end up without a run, and the second would then be skipped with the first never built. So app_config.py asks here first.

    python3 was_built.py --repo LukeNeedham/AppHub --pr 12 --sha <commit>      prints true, false or unknown

The answer is read from the sticky comment of the PR (`build` job of android_pr_build.yml), which names the commit of the latest build
and how it went: in progress, succeeded or failed all mean it was built, a cancelled build does not. That needs only the permission
`pull-requests` that the callers already have (the Actions API would need `actions: read`). A commit that has no such comment was
not built. `unknown` when GitHub could not be asked: the caller then builds, which is always safe. Needs `gh` and GH_TOKEN.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_config import settings

COMMIT = re.compile(r"\*\*Commit:\*\* \[`([0-9a-f]{7,40})`\]")
CANCELLED = "🚫"


def build_comment_says_built(body, sha):
    """Whether the build comment [body] is about the commit [sha] and says it was built (or is being built)."""
    match = COMMIT.search(body)
    if not match or not sha.startswith(match.group(1)):
        return False
    return CANCELLED not in body


def was_built(repo, pr, sha, runner=None):
    """'true', 'false' or 'unknown'. [runner] runs `gh` (for the tests)."""
    runner = runner or (lambda args: subprocess.run(["gh", *args], capture_output=True, text=True))
    # The sticky comment action embeds this marker in the comment it manages (as pr_releases.py stale does)
    marker = f"Sticky Pull Request Comment{settings(repo)['comment-header']} "
    jq = f".[] | select(.body | contains({json.dumps(marker)})) | .body | @json"
    result = runner(["api", "--paginate", f"repos/{repo}/issues/{pr}/comments", "--jq", jq])
    if result.returncode != 0:
        print(f"::warning::Could not read the comments of the PR to find out whether {sha} was built, so the push is built: "
              f"{result.stderr.strip()}", file=sys.stderr)
        return "unknown"
    bodies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return "true" if any(build_comment_says_built(body, sha) for body in bodies) else "false"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    print(was_built(args.repo, args.pr, args.sha))


if __name__ == "__main__":
    main()
