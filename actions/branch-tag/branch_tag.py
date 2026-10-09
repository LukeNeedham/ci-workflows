"""Release tag scheme shared by the PR build and cleanup workflows.

Builds tag as `<clean-branch>-<run_number>-<run_attempt>`. Cleanup finds a branch's releases by the
same scheme, so both sides must use this module.
"""
import argparse
import json
import re
import sys


def clean_branch(raw):
    """Replace slashes/special characters with dashes and lowercase."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", raw).lower()


def release_tag(branch, run_number, run_attempt):
    return f"{clean_branch(branch)}-{run_number}-{run_attempt}"


def matches(tag, branch):
    """True if `tag` was produced by `release_tag` for `branch` (any run)."""
    prefix = clean_branch(branch) + "-"
    return tag.startswith(prefix) and re.fullmatch(r"\d+-\d+", tag[len(prefix):]) is not None


def select_tags(releases, branch):
    """Tags of the pre-releases (only) that belong to `branch`."""
    return [
        r["tagName"]
        for r in releases
        if r.get("isPrerelease") and matches(r["tagName"], branch)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tag = sub.add_parser("tag", help="print the release tag for this run")
    tag.add_argument("--branch", required=True)
    tag.add_argument("--run-number", required=True)
    tag.add_argument("--run-attempt", required=True)

    select = sub.add_parser("select", help="read `gh release list --json tagName,isPrerelease` on stdin, print the branch's tags")
    select.add_argument("--branch", required=True)

    args = parser.parse_args(argv)
    if args.command == "tag":
        print(release_tag(args.branch, args.run_number, args.run_attempt))
    else:
        for t in select_tags(json.load(sys.stdin), args.branch):
            print(t)


if __name__ == "__main__":
    main()
