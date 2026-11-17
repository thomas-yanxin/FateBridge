"""Exact Decimal oracle, leap-boundary regressions and retained unknowns."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_tt_utc_exact_v1"
ORACLE_PATH = FIXTURE / "oracle.json.gz"
ORACLE = json.loads(gzip.decompress(ORACLE_PATH.read_bytes()))
PRIMARY = json.loads(
    (ROOT / "tests/fixtures/historical-utc-domain-reference-v1.json").read_text()
)


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


def test_every_modern_oracle_datetime_is_exact_to_its_independently_rounded_microsecond():
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    count = 0
    for row in ORACLE["rows"]:
        if row["status"] != "normal":
            continue
        actual = datetime_from_tt(row["jd_tt"], exact_epoch=True)
        assert datetime_from_tt(TTInstant.from_float(row["jd_tt"])) == actual
        delta = actual - epoch
        micros = (
            delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        )
        assert micros == row["expected_epoch_microseconds"], row["id"]
        count += 1
    assert count == 3930


def test_original243_rejections_keep_true_insertions_separate_from_rounding():
    rows = [r for r in ORACLE["rows"] if r["status"] == "unrepresentable_utc_label"]
    assert len(rows) == 243
    rescued = {r["id"]: r for r in PRIMARY["atomic_rescued_ordinary_rows"]}
    assert len(rescued) == 1
    for row in rows:
        point = TTInstant.from_float(row["jd_tt"])
        if row["id"] in rescued:
            expected = rescued[row["id"]]
            assert expected["ERFA_clock_second"] < 60
            assert datetime_from_tt(point).isoformat() == expected["expected_UTC"]
            assert (
                datetime_from_tt(row["jd_tt"], exact_epoch=True).isoformat()
                == expected["expected_UTC"]
            )
        else:
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                datetime_from_tt(row["jd_tt"], exact_epoch=True)
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                datetime_from_tt(point)
