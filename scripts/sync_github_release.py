"""Create an idempotent GitHub Release for the commit actually published to PyPI."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def github_api(
    repository: str, path: str, payload: dict[str, object] | None = None
) -> dict[str, object] | None:
    """Only GET 404 is absence; authentication and service errors must stop us."""
    token = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]
    request = Request(
        f"https://api.github.com/repos/{repository}/{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            decoded: object = json.load(response)
    except HTTPError as error:
        if payload is None and error.code == 404:
            return None
        else:
            raise
    if not isinstance(decoded, dict):
        raise ValueError("GitHub API returned a non-object JSON payload")
    return decoded


def sync_release(repository: str, version: str, source_sha: str) -> str:
    """Never move a tag or rewrite an existing published release."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("An exact published commit SHA is required")
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", version):
        raise ValueError("Invalid package version")
    tag = f"v{version}"
    encoded_tag = quote(tag, safe="")
    reference = github_api(repository, f"git/ref/tags/{encoded_tag}")
    if reference is None:
        github_api(
            repository, "git/refs", {"ref": f"refs/tags/{tag}", "sha": source_sha}
        )
    # The commits endpoint resolves both lightweight and annotated tags.
    commit = github_api(repository, f"commits/refs/tags/{encoded_tag}")
    if commit is None or commit["sha"] != source_sha:
        raise ValueError(f"{tag} does not point to published commit {source_sha}")

    release = github_api(repository, f"releases/tags/{encoded_tag}")
    if release is not None:
        if release["draft"]:
            raise ValueError(f"{tag} has a draft release; review it before publishing")
        existing_url = release["html_url"]
        if not isinstance(existing_url, str):
            raise ValueError("GitHub release payload missing html_url")
        return existing_url

    created = github_api(
        repository,
        "releases",
        {
            "tag_name": tag,
            "target_commitish": source_sha,
            "name": f"FateBridge {tag}",
            "body": (
                f"PyPI: https://pypi.org/project/fatebridge/{version}/\n\n"
                f"```bash\nuv pip install fatebridge=={version}\n```\n\n"
                f"Source commit: `{source_sha}`.\n"
            ),
            "generate_release_notes": True,
            # GitHub selects Latest by version/date, so backfills cannot force
            # an older version to replace a newer release as Latest.
            "make_latest": "legacy",
        },
    )
    if created is None or not isinstance(created.get("html_url"), str):
        raise ValueError("GitHub release creation response missing html_url")
    created_url = created["html_url"]
    assert isinstance(created_url, str)
    return created_url


def main() -> int:
    """Parse CLI arguments and ensure the GitHub Release matches the commit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    print(sync_release(args.repo, args.version, args.sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
