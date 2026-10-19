"""Choose the CI test scope from the complete push or pull-request diff.

Unknown paths or an unavailable diff always select the full suite. Example JSON
and validation fixtures stay in that suite even though they live under docs/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Sequence

ROOT_DOCUMENTS = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"}
ARCHIVE_SUFFIXES = {".json", ".log", ".txt", ".xml", ".csv"}


def documentation_only(paths: Sequence[str]) -> bool:
    if not paths:
        return False
    for name in paths:
        path = PurePosixPath(name)
        if name in ROOT_DOCUMENTS:
            continue
        if (
            len(path.parts) < 2
            or path.parts[0] != "docs"
            or path.name == "AGENTS.md"
            or path.parts[1] in {"examples", "validation"}
        ):
            return False
        if path.suffix == ".md":
            continue
        if path.parts[1] in {"audits", "research"} and path.suffix in ARCHIVE_SUFFIXES:
            continue
        return False
    return True


def changed_paths(base: str, head: str, event: str) -> list[str] | None:
    # Only full object IDs from the event are accepted as revision arguments.
    if event not in {"push", "pull_request"} or not all(
        re.fullmatch(r"[0-9a-f]{40}", ref) and ref != "0" * 40 for ref in (base, head)
    ):
        return None
    try:
        for ref in (base, head):
            found = subprocess.run(
                ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
                capture_output=True,
            )
            if found.returncode:
                # A force-push's old tip may no longer be in the checkout.
                subprocess.run(
                    ["git", "fetch", "--no-tags", "--depth=1", "origin", ref],
                    check=True,
                    capture_output=True,
                )
        # GitHub PRs compare the merge-base; pushes compare their complete
        # before/after trees, including every commit in a multi-commit push.
        separator = "..." if event == "pull_request" else ".."
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--no-renames",
                "-z",
                base + separator + head,
            ],
            check=True,
            capture_output=True,
        )
        return [os.fsdecode(name) for name in result.stdout.split(b"\0") if name]
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Diff unavailable; running the full suite: {error}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    paths = changed_paths(args.base, args.head, args.event)
    full_tests = not documentation_only(paths or [])
    print(json.dumps({"full_tests": full_tests, "changed_files": paths}))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"full_tests={str(full_tests).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
