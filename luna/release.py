"""Owner-managed release labels for Luna.

A release is named pojo.N, where N is a positive integer. The number only
advances when a new version is deliberately published, not per source commit.
"""
import re

VERSION = "pojo.2"
PATTERN = re.compile(r"pojo\.([1-9][0-9]*)\Z")


def next_version(current=VERSION):
    """Compute the next available label without publishing it."""
    match = PATTERN.fullmatch(current)
    if not match:
        raise ValueError("Luna release labels must look like pojo.1 or pojo.2")
    return "pojo." + str(int(match.group(1)) + 1)
