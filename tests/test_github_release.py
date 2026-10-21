"""Release synchronization must preserve the published version's source commit."""

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from scripts import sync_github_release

SHA = "a" * 40
URL = "https://github.com/owner/FateBridge/releases/tag/v0.1.1"


@pytest.fixture
def github(monkeypatch):
    state = {"sha": None, "release": None, "writes": []}

    def api(repository, path, payload=None):
        assert repository == "owner/FateBridge"
        if payload is not None:
            state["writes"].append((path, payload))
            if path == "git/refs":
                assert payload == {"ref": "refs/tags/v0.1.1", "sha": SHA}
                state["sha"] = payload["sha"]
                return {}
            assert path == "releases"
            state["release"] = {"html_url": URL, "draft": False}
            return state["release"]
        if path == "git/ref/tags/v0.1.1":
            return {"ref": "refs/tags/v0.1.1"} if state["sha"] else None
        if path == "commits/refs/tags/v0.1.1":
            return {"sha": state["sha"]}
        assert path == "releases/tags/v0.1.1"
        return state["release"]

    monkeypatch.setattr(sync_github_release, "github_api", api)
    return state


def test_create_release_and_retry_without_mutations(github):
    assert sync_github_release.sync_release("owner/FateBridge", "0.1.1", SHA) == URL
    assert len(github["writes"]) == 2
    payload = github["writes"][1][1]
    assert payload["target_commitish"] == SHA
    assert payload["generate_release_notes"] is True
    assert payload["make_latest"] == "legacy"
    assert "fatebridge==0.1.1" in payload["body"]
    assert SHA in payload["body"]
    assert sync_github_release.sync_release("owner/FateBridge", "0.1.1", SHA) == URL
    assert len(github["writes"]) == 2


def test_existing_tag_without_release_recovers(github):
    github["sha"] = SHA
    assert sync_github_release.sync_release("owner/FateBridge", "0.1.1", SHA) == URL
    assert [path for path, _ in github["writes"]] == ["releases"]


@pytest.mark.parametrize("has_release", [True, False])
def test_conflicting_tag_is_never_moved(github, has_release):
    github["sha"] = "b" * 40
    if has_release:
        github["release"] = {"html_url": URL, "draft": False}
    with pytest.raises(ValueError, match="does not point to published commit"):
        sync_github_release.sync_release("owner/FateBridge", "0.1.1", SHA)
    assert github["writes"] == []


def test_existing_draft_is_not_published_implicitly(github):
    github["sha"] = SHA
    github["release"] = {"html_url": URL, "draft": True}
    with pytest.raises(ValueError, match="draft release"):
        sync_github_release.sync_release("owner/FateBridge", "0.1.1", SHA)
    assert github["writes"] == []


@pytest.mark.parametrize("sha", ["master", "abc123", "", "0" * 39])
def test_release_requires_an_exact_commit(github, sha):
    with pytest.raises(ValueError, match="exact published commit"):
        sync_github_release.sync_release("owner/FateBridge", "0.1.1", sha)
    assert github["writes"] == []


@pytest.mark.parametrize("status", [404, 403, 429, 500])
@pytest.mark.parametrize("payload", [None, {"tag_name": "v0.1.1"}])
def test_only_get_404_is_absence(monkeypatch, status, payload):
    monkeypatch.setenv("GH_TOKEN", "fixture-token")

    def request(req, timeout):
        assert req.full_url == "https://api.github.com/repos/owner/FateBridge/releases"
        assert req.get_header("Authorization") == "Bearer fixture-token"
        assert timeout == 30
        if payload is not None:
            assert json.loads(req.data) == payload
        raise HTTPError(req.full_url, status, "fixture", {}, None)

    monkeypatch.setattr(sync_github_release, "urlopen", request)
    if status == 404 and payload is None:
        assert sync_github_release.github_api("owner/FateBridge", "releases") is None
    else:
        with pytest.raises(HTTPError):
            sync_github_release.github_api("owner/FateBridge", "releases", payload)


def test_github_response_and_network_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(
        sync_github_release, "urlopen", lambda *a, **kw: io.BytesIO(b'{"id": 1}')
    )
    assert sync_github_release.github_api("owner/FateBridge", "releases") == {"id": 1}

    def offline(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(sync_github_release, "urlopen", offline)
    with pytest.raises(URLError):
        sync_github_release.github_api("owner/FateBridge", "releases")
