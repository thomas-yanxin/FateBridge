"""The same rounded JD cannot stand for two different boundary intentions."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.historical_utc import HistoricalUTCAdjustment
from fatebridge.core.astro.time_scales import datetime_from_tt, leap_table
from fatebridge.core.astro.tt_epoch import TTInstant

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads(
    gzip.decompress(
        (ROOT / "tests/data/bazi_tt_utc_exact_v1/oracle.json.gz").read_bytes()
    )
)


def test_explicit_float_points_preserve_all_original_adjudicated_answers():
    normal = rejected = 0
    for row in ORACLE["rows"]:
        point = TTInstant.from_float(row["jd_tt"])
        if row["status"] == "normal":
            actual = datetime_from_tt(point)
            assert actual.isoformat() == row["expected_datetime_utc"], row["id"]
            normal += 1
        elif row["status"] == "unrepresentable_utc_label":
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                datetime_from_tt(point)
            rejected += 1
    assert (normal, rejected) == (3930, 243)


def test_all_atomic_policy_starts_retain_the_original_utc_midnight_losslessly():
    entries = leap_table()["entries"]
    assert len(entries) == 28
    for entry in entries:
        civil = datetime.fromisoformat(entry["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        offset = entry["tai_minus_utc_seconds"]
        for microseconds in (0, 1, 17, 999999):
            actual_civil = civil + timedelta(microseconds=microseconds)
            point = TTInstant.from_utc(actual_civil, tai_minus_utc_seconds=offset)
            assert datetime_from_tt(point) == actual_civil


def test_twopart_input_is_not_silently_added_at_large_jd():
    point = TTInstant.from_parts(2457754.5, 0.001)
    assert point.days == Fraction(2457754.5) + Fraction(0.001)
    assert point.days != Fraction(point.as_float())
    assert datetime_from_tt(point) != datetime_from_tt(
        TTInstant.from_float(point.as_float())
    )


def test_pre_atomic_policy_parts_cannot_silently_lose_their_precision():
    with pytest.raises(HistoricalUTCAdjustment, match="exact two-part TT"):
        datetime_from_tt(TTInstant.from_parts(2430000.5, 0.001))


def test_naive_utc_and_floating_atomic_offset_are_not_invented_or_rounded():
    with pytest.raises(ValueError, match="timezone-aware"):
        TTInstant.from_utc(datetime(2000, 1, 1), tai_minus_utc_seconds=32)
    with pytest.raises(TypeError, match="exact integer or Fraction"):
        TTInstant.from_utc(
            datetime(2000, 1, 1, tzinfo=timezone.utc), tai_minus_utc_seconds=32.0
        )
    with pytest.raises(TypeError, match="exact Fraction"):
        TTInstant(2457754.5)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf")])
def test_nonfinite_and_boolean_points_are_rejected(value):
    with pytest.raises(ValueError, match="finite and numeric"):
        TTInstant.from_float(value)


def test_explicit_exact_type_cannot_enable_nominal_scalar_aliases():
    point = TTInstant.from_float(2457754.5)
    with pytest.raises(ValueError, match="nominal scalar boundary"):
        datetime_from_tt(point, exact_epoch=False)
