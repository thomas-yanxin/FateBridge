"""A minute label and a selected subset cannot become a one-second certificate."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.validation.meihua_solar_seconds import (
    parse_naoj_minute_label,
    read_solar_tt_reference,
)

REFERENCE = Path(__file__).parent / "fixtures/meihua_solar_seconds_v1"
CASES = json.loads((REFERENCE / "clock-cases.json").read_text())


def test_frozen_independent_data_and_manual_labels_are_preserved():
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    assert manifest["clock_cases_frozen_before_parser_implementation"]
    assert not manifest["expected_values_from_production"]
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES["valid"])
def test_valid_labels_retain_raw_notation_without_precision_or_utc_inference(case):
    result = parse_naoj_minute_label(case["date"], case["clock"])
    assert result["nominal_display_datetime"] == case["nominal"]
    assert result["end_of_day_24_00"] is case["endofday"]
    assert result["raw_date_label"] == case["date"]
    assert result["raw_clock_label"] == case["clock"]
    assert not result["one_second_precision_testable_from_this_label"]
    assert not result["is_authenticated_UTC_instant"]
    assert not result["rounding_rule_authenticated"]
    assert result["actual_error_interval_seconds"] is None


@pytest.mark.parametrize("date_label,clock_label", CASES["invalid"])
def test_malformed_or_unrepresentable_labels_are_not_silently_rounded(
    date_label, clock_label
):
    with pytest.raises(ValueError):
        parse_naoj_minute_label(date_label, clock_label)


def test_end_of_day_and_next_midnight_share_only_a_nominal_display_value():
    first = parse_naoj_minute_label("1979/01/20", "24:00")
    second = parse_naoj_minute_label("1979/01/21", "00:00")
    assert first["nominal_display_datetime"] == second["nominal_display_datetime"]
    assert first != second
    assert not first["is_authenticated_UTC_instant"]


@pytest.mark.parametrize("name", ["reference-2000b.json", "reference-2000a.json"])
def test_both_independent_implementation_references_keep_all_required_terms(name):
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    result = read_solar_tt_reference(
        REFERENCE / name, expected_sha256=manifest["files"][name]
    )
    assert len(result) == (9624 if name == "reference-2000b.json" else 4824)
    assert all(
        (year, index) in result for year in range(1900, 2101) for index in range(24)
    )


@pytest.mark.parametrize(
    "fault",
    ["drop", "duplicate", "wrong_longitude", "nonfinite", "bool_epoch", "bool_id"],
)
def test_cohort_corruption_stops_before_any_production_comparison(tmp_path, fault):
    data = json.loads((REFERENCE / "reference-2000a.json").read_text())
    if fault == "drop":
        data["rows"].pop()
    elif fault == "duplicate":
        data["rows"].append(data["rows"][0])
    elif fault == "wrong_longitude":
        data["rows"][0]["longitude"] = 0
    elif fault == "nonfinite":
        data["rows"][0]["jd_tt"] = float("nan")
    elif fault == "bool_epoch":
        data["rows"][0]["jd_tt"] = True
    else:
        data["rows"][0]["year"] = True
    path = tmp_path / "changed-reference.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_solar_tt_reference(
            path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )


def test_changed_reference_bytes_cannot_keep_an_old_commitment(tmp_path):
    data = (REFERENCE / "reference-2000a.json").read_bytes()
    path = tmp_path / "reference.json"
    path.write_bytes(data + b" ")
    with pytest.raises(ValueError, match="recorded commitment"):
        read_solar_tt_reference(path, expected_sha256=hashlib.sha256(data).hexdigest())


def test_duplicate_json_keys_are_rejected_even_with_a_matching_file_hash(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text('{"production_imports":true,"production_imports":false,"rows":[]}')
    with pytest.raises(ValueError, match="Duplicate JSON keys"):
        read_solar_tt_reference(
            path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("value", [None, False, "A" * 64, "0" * 63])
def test_unusable_commitment_is_not_an_authenticated_reference(value):
    with pytest.raises(ValueError, match="recorded lowercase"):
        read_solar_tt_reference(
            REFERENCE / "reference-2000a.json", expected_sha256=value
        )
