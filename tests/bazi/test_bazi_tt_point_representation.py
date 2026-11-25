"""The same rounded JD cannot stand for two different boundary intentions."""

import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.time_scales import datetime_from_tt, leap_table
from fatebridge.core.astro.tt_epoch import TTInstant
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files as native_ephemeris_files,
)

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = json.loads(
    (ROOT / "tests/fixtures/historical-utc-domain-reference-v1.json").read_text()
)


def test_all_atomic_policy_starts_retain_the_original_utc_midnight_losslessly() -> None:
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


def test_twopart_input_is_not_silently_added_at_large_jd() -> None:
    point = TTInstant.from_parts(2457754.5, 0.001)
    assert point.days == Fraction(2457754.5) + Fraction(0.001)
    assert point.days != Fraction(point.as_float())
    assert datetime_from_tt(point) != datetime_from_tt(
        TTInstant.from_float(point.as_float())
    )


@pytest.mark.usefixtures("native_ephemeris_files")
def test_pre_atomic_parts_keep_the_existing_exact_entry_precision() -> None:
    for row in PRIMARY["preUTC_native_reference"]["rows"]:
        actual = datetime_from_tt(TTInstant.from_parts(*row["TT_parts"]))
        assert actual.isoformat() == row["prior_exact_entry_UTC"]
        native = datetime.fromisoformat(row["native_UTC_carrier"])
        assert abs((actual - native).total_seconds()) <= 0.0002


def test_naive_utc_and_floating_atomic_offset_are_not_invented_or_rounded() -> None:
    with pytest.raises(
        ValueError, match="UTC calendar normalization requires an aware datetime"
    ):
        TTInstant.from_utc(datetime(2000, 1, 1), tai_minus_utc_seconds=32)
    with pytest.raises(TypeError, match="exact integer or Fraction"):
        TTInstant.from_utc(
            datetime(2000, 1, 1, tzinfo=timezone.utc), tai_minus_utc_seconds=32.0
        )
    with pytest.raises(TypeError, match="exact Fraction"):
        TTInstant(2457754.5)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf")])
def test_nonfinite_and_boolean_points_are_rejected(value) -> None:
    with pytest.raises(ValueError, match="finite and numeric"):
        TTInstant.from_float(value)


def test_explicit_exact_type_cannot_enable_nominal_scalar_aliases() -> None:
    point = TTInstant.from_float(2457754.5)
    with pytest.raises(ValueError, match="nominal scalar boundary"):
        datetime_from_tt(point, exact_epoch=False)
