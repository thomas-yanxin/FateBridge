"""Source access must preserve fixed identities and observable failures."""

from __future__ import annotations

import hashlib
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from scripts.numerology import retrieve_canping_source_images as retrieval


class Response(io.BytesIO):
    code = 200
    url = "https://www.digital.archives.go.jp/returned-image"
    headers = {"Content-Type": "image/jpeg"}


def small_region() -> dict:
    return {
        "pdf_page": 96,
        "region": [2950, 0, 2950, 2200],
        "url": "https://www.digital.archives.go.jp/fixed-image",
        "expected_sha256": hashlib.sha256(b"fixed bytes").hexdigest(),
    }


def test_all_registered_regions_keep_frozen_source_and_duplicate_provenance():
    rows = retrieval.registered_regions()
    assert len(rows) == 112
    assert len({r["pdf_page"] for r in rows}) == 28
    assert all(r["canvas_dimensions"] == [5900, 4400] for r in rows)
    assert all(r["url"].endswith("/full/0/native.jpg") for r in rows)
    assert any(len(r["witness_fixture_ids"]) > 1 for r in rows)
    selected = next(
        r
        for r in rows
        if r["pdf_page"] == 96 and r["region"][0] == 2950 and r["region"][1] == 0
    )
    # Identity from the pre-request p096-q1 native image, not a fetched output.
    assert (
        selected["expected_sha256"]
        == "a6e8ce98c97e5a5f57b78a352ee015d2b5fedf8e91c09a474215cfa16d76f735"
    )


def test_modified_collation_rejected_before_any_request(tmp_path, monkeypatch):
    path = tmp_path / "collation.json"
    path.write_bytes(retrieval.COLLATION.read_bytes() + b"\n")
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="identity changed"):
        retrieval.registered_regions(path)


def test_plan_is_offline_and_selects_exact_page(monkeypatch, capsys):
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: pytest.fail("network"))
    assert retrieval.main(["--page", "96", "--plan"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert len(plan["regions"]) == 4
    assert {r["pdf_page"] for r in plan["regions"]} == {96}


def test_unregistered_page_is_not_guessed(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: pytest.fail("network"))
    output = tmp_path / "new-output"
    with pytest.raises(SystemExit) as exc:
        retrieval.main(["--page", "1", "--fetch", "--output", str(output)])
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "body,verified", [(b"fixed bytes", True), (b"changed bytes", False)]
)
def test_actual_response_hash_decides_identity(tmp_path, monkeypatch, body, verified):
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: Response(body))
    row = retrieval.retrieve_region(small_region(), tmp_path, 1)
    assert row["http_status"] == 200
    assert row["hash_verified"] is verified
    assert (tmp_path / row["body_path"]).read_bytes() == body
    assert row["body_path"].endswith(".jpg" if verified else ".unverified.bin")
    assert row["expected_sha256"] == small_region()["expected_sha256"]


def test_http_failure_body_and_status_are_preserved(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError(
            small_region()["url"], 400, "Bad Request", {}, io.BytesIO(b"bad image")
        )

    monkeypatch.setattr(retrieval, "urlopen", fail)
    row = retrieval.retrieve_region(small_region(), tmp_path, 1)
    assert row["http_status"] == 400 and row["hash_verified"] is False
    assert (tmp_path / row["body_path"]).read_bytes() == b"bad image"


def test_network_failure_is_not_retried_or_marked_verified(tmp_path, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise URLError("offline")

    monkeypatch.setattr(retrieval, "urlopen", fail)
    row = retrieval.retrieve_region(small_region(), tmp_path, 1)
    assert len(calls) == 1
    assert row["http_status"] is None and row["hash_verified"] is False
    assert row["error"] == "URLError"
    assert list(tmp_path.iterdir()) == []


def test_excess_response_is_retained_as_truncated_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "MAX_RESPONSE_BYTES", 3)
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: Response(b"fixed bytes"))
    row = retrieval.retrieve_region(small_region(), tmp_path, 1)
    assert row["response_truncated_at_limit"] is True
    assert row["hash_verified"] is False
    assert (tmp_path / row["body_path"]).read_bytes() == b"fixe"


def test_existing_output_directory_is_preserved(tmp_path, monkeypatch):
    marker = tmp_path / "preserve.txt"
    marker.write_text("existing evidence")
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(FileExistsError):
        retrieval.main(["--page", "96", "--fetch", "--output", str(tmp_path)])
    assert marker.read_text() == "existing evidence"


def test_failed_fetch_has_nonzero_exit_and_completed_failure_receipt(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(retrieval, "registered_regions", lambda: [small_region()])
    monkeypatch.setattr(
        retrieval, "urlopen", lambda *a, **k: Response(b"changed bytes")
    )
    output = tmp_path / "fetch"
    assert retrieval.main(["--page", "96", "--fetch", "--output", str(output)]) == 1
    summary = json.loads((output / "summary.json").read_text())
    assert summary["completed"] is True
    assert summary["verified_regions"] == 0 and summary["unverified_regions"] == 1
    assert summary["reading_changes"] == 0
    assert summary["results"][0]["expected_sha256"] == small_region()["expected_sha256"]


def test_recorded_same_image_cannot_overwrite_a_previous_file(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "urlopen", lambda *a, **k: Response(b"fixed bytes"))
    first = retrieval.retrieve_region(small_region(), tmp_path, 1)
    target = tmp_path / first["body_path"]
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        retrieval.retrieve_region(small_region(), tmp_path, 1)
    assert target.read_bytes() == original
