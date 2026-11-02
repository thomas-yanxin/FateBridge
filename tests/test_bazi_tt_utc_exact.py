"""Exact Decimal oracle, leap-boundary regressions and retained unknowns."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.time_scales import datetime_from_tt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_tt_utc_exact_v1"
ORACLE_PATH = FIXTURE / "oracle.json.gz"
ORACLE = json.loads(gzip.decompress(ORACLE_PATH.read_bytes()))


def load_audit(name):
    path = ROOT / "docs/validation" / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(path.read_bytes()))


def test_oracle_keeps_all_inputs_and_original_before_failures():
    assert (
        hashlib.sha256(ORACLE_PATH.read_bytes()).hexdigest()
        == ORACLE_PATH.with_suffix(".sha256").read_text().strip()
    )
    assert ORACLE["row_count"] == 6391
    assert ORACLE["counts"] == {
        "normal": 3930,
        "unrepresentable_utc_label": 243,
        "pre_atomic_policy_unadjudicated": 2218,
    }
    before = load_audit("bazi-tt-utc-exact-before-v1.json.gz")
    assert before["counts"]["normal_microsecond_mismatches"] == 3900
    assert before["counts"]["normal_unexpected_error"] == 14
    assert before["counts"]["unrepresentable_not_correctly_rejected"] == 14
    assert before["maximum_absolute_microsecond_error"] == 20
    assert before["registered_exact_atomic_conversion_gate_passed"] is False


def test_every_modern_oracle_datetime_is_exact_to_its_independently_rounded_microsecond():
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    count = 0
    for row in ORACLE["rows"]:
        if row["status"] != "normal":
            continue
        actual = datetime_from_tt(row["jd_tt"], exact_epoch=True)
        delta = actual - epoch
        micros = (
            delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        )
        assert micros == row["expected_epoch_microseconds"], row["id"]
        count += 1
    assert count == 3930


def test_all_unrepresentable_leap_and_rounded_labels_are_rejected():
    rows = [r for r in ORACLE["rows"] if r["status"] == "unrepresentable_utc_label"]
    assert len(rows) == 243
    for row in rows:
        with pytest.raises(ValueError, match="UTC leap second not representable"):
            datetime_from_tt(row["jd_tt"], exact_epoch=True)


def test_all2218_unadjudicated_historical_outputs_are_unchanged_not_counted_as_truth():
    before = load_audit("bazi-tt-utc-exact-before-v1.json.gz")
    after = load_audit("bazi-tt-utc-explicit-exact-v2-v1.json.gz")
    assert before["row_count"] == after["row_count"] == 6391
    keys = [
        "actual_datetime_utc",
        "actual_epoch_microseconds",
        "error_type",
        "message",
        "expected_leap_label_rejection",
    ]
    count = 0
    for old, new in zip(before["rows"], after["rows"], strict=True):
        assert old["id"] == new["id"]
        if old["status"] == "pre_atomic_policy_unadjudicated":
            assert {k: old.get(k) for k in keys} == {k: new.get(k) for k in keys}
            count += 1
    assert count == 2218
    assert after["registered_exact_atomic_conversion_gate_passed"] is True
    assert after["historical_truth_certified"] is False
    assert after["future_offsets_physically_certified"] is False


def test_default_scalar_contract_does_not_erase_its_exact_point_conflicts():
    default = load_audit("bazi-tt-utc-default-v2-v1.json.gz")
    assert default["exact_epoch_requested"] is False
    assert default["row_count"] == 6391
    assert default["counts"]["normal_exact_microsecond_matches"] == 3903
    assert default["counts"]["normal_microsecond_mismatches"] == 13
    assert default["counts"]["normal_unexpected_error"] == 14
    assert default["counts"]["unrepresentable_not_correctly_rejected"] == 14
    assert default["registered_exact_atomic_conversion_gate_passed"] is False
    assert default["maximum_absolute_microsecond_error"] == 20
    exact = load_audit("bazi-tt-utc-explicit-exact-v2-v1.json.gz")
    assert exact["exact_epoch_requested"] is True
    assert exact["registered_exact_atomic_conversion_gate_passed"] is True
    assert exact["full_goal_complete"] is default["full_goal_complete"] is False
