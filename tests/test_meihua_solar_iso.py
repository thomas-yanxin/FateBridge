"""Exact signed microsecond offsets and ISO aliases at reference-date borders."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.meihua_solar_reference import (
    compare_solar_term_date,
    parse_solar_reference_datetime,
)
from fatebridge.validation.meihua_solar_publishers import compare_label

FOLDER = Path(__file__).parent / "fixtures/meihua_solar_iso_v1"
MANIFEST_SHA256 = "c1289b17148893d2607a5aa70f9f8742f03cd840a6ae62190e58928ddb3e02e9"
raw = (FOLDER / "manifest.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
for name, digest in json.loads(raw)["files"].items():
    if str(name).endswith((".py", ".py.txt")):
        continue
    assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest
CASES = json.loads((FOLDER / "exact-cases201.json").read_bytes())
UNKNOWN = json.loads((FOLDER / "unknown5.json").read_bytes())


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_hko_reference_uses_the_integer_offset_instant_and_keeps_raw_label(case):
    # Expected labels were constructed from integers before the core fix.
    expected = datetime.fromisoformat(case["expected_fixed_UTC8_datetime"])
    output = compare_solar_term_date(
        {"name": case["term"], "datetime_with_offset": case["label"]},
        fact_path="supplied_term",
    )
    assert output["computed_datetime_at_reference_offset"] == expected.isoformat()
    assert output["computed_date"] == case["expected_date"]
    assert output["actual_datetime_with_offset"] == case["label"]
    decoded = parse_solar_reference_datetime(case["label"])
    assert decoded.astimezone(timezone(timedelta(hours=8))) == expected
    if "offset_microseconds" in case:
        assert decoded.utcoffset() == timedelta(
            microseconds=case["offset_microseconds"]
        )
    if expected.year == 1900 or expected.year == 2101:
        assert output["comparison_status"] == "outside_published_year_range"
    else:
        assert output["published_date"] is not None


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_secondary_auditor_consumes_the_same_exact_offset_without_certification(case):
    expected = datetime.fromisoformat(case["expected_fixed_UTC8_datetime"])
    # A synthetic label is an arithmetic control, never a new NAOJ observation.
    reference = {
        "year": expected.year,
        "index": 0,
        "term": case["term"],
        "label_normalization": {
            "nominal_display_datetime": expected.replace(tzinfo=None).isoformat()
        },
        "source_midnight_label": expected.time().isoformat().startswith("00:00:00"),
        "kind": "independent_integer_arithmetic_control_not_real_publisher_data",
    }
    actual = {"name": case["term"], "datetime_with_offset": case["label"]}
    hko = {"published_date": None, "comparison_status": "synthetic_control"}
    output = compare_label(reference, actual, hko)
    assert output["computed_datetime_at_fixed_UTC8"] == expected.isoformat()
    assert output["computed_date_equals_NAOJ_normalized_label"] is True
    assert output["nominal_NAOJ_label_minus_computed_seconds"] == 0
    assert output["label_difference_is_instant_error"] is False
    assert output["actual_event_date_certified_from_minute_label"] is False
    assert output["actual_error_interval_seconds"] is None


@pytest.mark.parametrize("label", UNKNOWN)
def test_absent_offset_or_invalid_time_is_not_guessed(label):
    output = compare_solar_term_date(
        {"name": "小雪", "datetime_with_offset": label}, fact_path="unknown_control"
    )
    assert output["comparison_status"] == "actual_instant_unavailable"
    assert output["computed_date"] is None
