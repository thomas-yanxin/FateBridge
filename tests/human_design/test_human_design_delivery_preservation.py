"""A disappearing delivery must remain missing, never be recalculated."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.human_design.preserve_human_design_deliveries import preserve_delivery


def packet(tmp_path: Path, *, projected=False):
    business = {"type": "fixture_structure", "positions": [1, 2, 3]}
    metadata = {
        "run_id": "synthetic-preservation-fixture",
    }
    payload = {
        **({"type": business["type"]} if projected else business),
        "run_metadata": metadata,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    original = tmp_path / "original.json"
    original.write_text(json.dumps({"payload": payload}))
    return {
        "run_metadata": metadata,
        "result_delivery": {
            "file_path": str(original),
            "total_chars": len(encoded),
            "total_bytes": len(encoded.encode()),
        },
    }, original


def test_atomic_preservation_survives_original_expiry_without_native_replay(tmp_path):
    p, original = packet(tmp_path)
    first = preserve_delivery(tmp_path, p, 3, full_requested=True)
    saved = tmp_path / first["file"]
    assert saved.read_bytes() == original.read_bytes()
    original.unlink()
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Recalculation is forbidden"),
    ):
        second = preserve_delivery(tmp_path, p, 3, full_requested=True)
    assert first == second
    assert first["unprojected_request_result"] is True
    assert first["model_visibility_certified"] is False


def test_missing_both_original_and_preserved_file_is_not_filled_in(tmp_path):
    p, original = packet(tmp_path)
    original.unlink()
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Recalculation is forbidden"),
    ):
        with pytest.raises(FileNotFoundError):
            preserve_delivery(tmp_path, p, 3, full_requested=True)
    assert not (tmp_path / "delivery-3.json").exists()


def test_changed_original_cannot_replace_an_earlier_preserved_receipt(tmp_path):
    p, original = packet(tmp_path)
    saved = preserve_delivery(tmp_path, p, 3, full_requested=True)
    original.write_text("{}")
    with pytest.raises(ValueError, match="differs"):
        preserve_delivery(tmp_path, p, 3, full_requested=True)
    assert (
        hashlib.sha256((tmp_path / saved["file"]).read_bytes()).hexdigest()
        == saved["file_sha256"]
    )


def test_projection_is_preserved_without_becoming_full_business_or_full_visibility(
    tmp_path,
):
    p, _ = packet(tmp_path, projected=True)
    r = preserve_delivery(tmp_path, p, 2, full_requested=False)
    assert (
        r["unprojected_request_result"] is False
        and r["model_visibility_certified"] is False
    )
    # The capture must supply the original request projection; the preserved
    # bytes alone cannot establish whether fields were omitted by that request.
    assert r["full_result_requested"] is False
