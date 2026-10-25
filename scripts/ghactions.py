"""Small helpers for scripts that run in GitHub Actions: step outputs, the environment file and error annotations.

Outside Actions (no GITHUB_OUTPUT or GITHUB_ENV) they print instead, so a script can be run by hand.
"""

import os


def _append(variable, name, value):
    line = f"{name}={value}"
    path = os.environ.get(variable)
    if path:
        with open(path, "a") as f:
            f.write(line + "\n")
    else:
        print(line)


def output(name, value):
    """Sets the output [name] of the running step."""
    _append("GITHUB_OUTPUT", name, value)


def export_env(name, value):
    """Sets the environment variable [name] for the steps that follow."""
    _append("GITHUB_ENV", name, value)


def error(message, title=None):
    """Prints an error annotation. It does not fail the step: return a non-zero exit code for that."""
    print(f"::error title={title}::{message}" if title else f"::error::{message}")
