"""A failed upstream check cannot replace the maintained fingerprint catalog."""

import hashlib
import json

import pytest

from scripts import build_ephemeris_manifest as builder


def test_one_bad_blob_preserves_the_existing_manifest(tmp_path, monkeypatch):
    payloads = {"a.se1": b"SW-a-reference", "b.se1": b"SW-b-reference"}
    rows = [
        {
            "type": "blob",
            "path": "ephe/" + name,
            "size": len(data),
            "sha": hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest(),
        }
        for name, data in payloads.items()
    ]

    def download(url):
        if "/git/trees/" in url:
            return json.dumps({"truncated": False, "tree": rows}).encode()
        return payloads["a.se1"] if url.endswith("a.se1") else b"SW-corrupt"

    monkeypatch.setattr(builder, "download", download)
    output = tmp_path / "catalog.json"
    output.write_bytes(b"existing edition")
    with pytest.raises(ValueError, match="No manifest written"):
        builder.build("a" * 40, tmp_path / "cache", output)
    assert output.read_bytes() == b"existing edition"
    assert (tmp_path / "cache/a.se1").read_bytes() == payloads["a.se1"]
    assert not (tmp_path / "cache/b.se1").exists()


def test_mutable_branch_name_is_not_an_edition_identifier(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "download", lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError, match="full upstream commit"):
        builder.build("master", tmp_path / "cache", tmp_path / "catalog.json")
