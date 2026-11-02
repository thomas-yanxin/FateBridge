"""Retain source-level scope and independently verify the frozen records."""

import hashlib
import json
import shutil
import struct
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.audit_astrodice_de441_reference import audit

FIXTURE = Path(__file__).parent / "fixtures/astrodice-de441-records-v1"


def test_frozen_records_replay_exactly_with_an_independent_basis_and_calendar():
    manifest = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "96f8c9b6a8b2fde8f5f11b43316928fc2694fb90ab89c7d438bc7d4ef5aa9d30"
    )
    for name, expected in json.loads(manifest.read_text())["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    result = audit(FIXTURE)
    assert result == json.loads((FIXTURE / "independent-exact-replay.json").read_text())
    assert result["rational_components_exactly_equal"] == 420
    assert not result["tt_calendar_acceptance"]
    assert not result["apparent_position_acceptance"]
    assert not result["full_goal_complete"]
    for index in range(7):
        native = json.loads((FIXTURE / f"native-first-{index:02}.json").read_text())
        assert native["status"] == "geometric_lines_satisfied"
        assert not native["apparent_position_or_rate_acceptance"]


def test_changed_reference_velocity_is_rejected_by_raw_coefficient_replay(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "data")
    p = tmp_path / "data/geometric-reference.json"
    reference = json.loads(p.read_text())
    values = reference["rows"][0]["states_at_exact_tdb_au_and_au_per_day"]["Mercury"]
    values[3] = str(Fraction(values[3]) + Fraction(1, 10**12))
    p.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match="coefficient evaluation differs"):
        audit(p.parent)


def test_rehashing_a_modified_excerpt_does_not_preserve_original_source_bytes(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "data")
    root = tmp_path / "data"
    kernel = root / "diagnostic-kernels/case-00.eph"
    raw = bytearray(kernel.read_bytes())
    old = struct.unpack_from("<d", raw, 2 * 8144 + 16)[0]
    struct.pack_into("<d", raw, 2 * 8144 + 16, old + 1)
    kernel.write_bytes(raw)
    p = root / "geometric-reference.json"
    reference = json.loads(p.read_text())
    reference["rows"][0]["kernel_sha256"] = hashlib.sha256(raw).hexdigest()
    p.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match="original constants/coefficients"):
        audit(root)


def test_partial_source_study_cannot_be_relabelled_as_full_astrodice_holdouts(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "data")
    p = tmp_path / "data/geometric-reference.json"
    reference = json.loads(p.read_text())
    reference["rows"][3]["role"] = "full_astrodice_holdout"
    p.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match="identity or role"):
        audit(p.parent)
