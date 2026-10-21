"""Skip published package versions before building or requesting a PyPI token."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


def package_version(path: Path) -> str:
    """Read the static version without importing the package or its dependencies."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and version.strip():
                return version
            break
    raise ValueError("Package must declare a nonempty static __version__ string")


def already_published(version: str) -> bool:
    """Only a missing version (404) permits publishing; other failures stop CI."""
    url = f"https://pypi.org/pypi/fatebridge/{quote(version, safe='')}/json"
    try:
        with urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    files = payload["urls"]
    if not isinstance(files, list):
        raise ValueError("PyPI returned an invalid release file list")
    return bool(files)


def main() -> int:
    version = package_version(Path("src/fatebridge/__init__.py"))
    tag = os.environ.get("RELEASE_TAG", "")
    if tag and tag != f"v{version}":
        raise ValueError(f"Release tag {tag!r} does not match v{version}")
    should_publish = not already_published(version)
    message = (
        f"fatebridge {version}: new version; build and publish"
        if should_publish
        else f"fatebridge {version}: already on PyPI; skip build and publish"
    )
    print(message)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"should_publish={str(should_publish).lower()}\n")
            stream.write(f"version={version}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
