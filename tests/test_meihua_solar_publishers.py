"""Full publisher identity, rollover and scope are not physical accuracy gates."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.meihua_solar_publishers import (
    EXPECTED_REFERENCE_SHA256,
    compare_label,
    parse_annual_response,
    read_naoj_reference,
)

FOLDER = Path(__file__).parent / "fixtures/meihua_naoj_solar_v1"
LITERALS = json.loads((FOLDER / "literal-seven-conflicts.json").read_bytes())
IDENTITIES = json.loads((FOLDER / "term-identities24.json").read_bytes())
ROWS, RECEIPT = read_naoj_reference(FOLDER)
BY_KEY = {(r["year"], r["term"]): r for r in ROWS}


@pytest.mark.parametrize("year", range(1900, 2101))
def test_each_required_year_retains_all24_source_identities(year):
    expected = json.loads((FOLDER / f"naoj-{year}-default-query.json").read_bytes())
    rows = [r for r in ROWS if r["year"] == year]
    assert len(rows) == 24
    for row, identity, literal in zip(rows, IDENTITIES, expected["rows"]):
        assert all(row[k] == identity[k] for k in ["index", "longitude"])
        assert row["term"] == identity["canonical_name"]
        assert row["source_name"] == identity["source_name"]
        assert row["raw_date_label"] == literal[0]
        assert row["raw_clock_label"] == literal[1]
        assert row["source"]["standard_time"] == "UT+8h"
        assert row["source"]["UTC_epoch_authenticated"] is False
        assert row["source"]["rounding_rule_authenticated"] is False
        assert row["label_normalization"]["actual_error_interval_seconds"] is None
    assert RECEIPT["annual_queries"] == 201 and RECEIPT["solar_terms"] == 4824


@pytest.mark.parametrize("literal", LITERALS, ids=lambda r: str(r["year"]))
def test_seven_known_disagreements_keep_independent_literal_labels(literal):
    row = BY_KEY[literal["year"], literal["term"]]
    assert row["raw_date_label"] == literal["raw_date_label"]
    assert row["raw_clock_label"] == literal["raw_clock_label"]
    assert (
        row["label_normalization"]["nominal_display_datetime"]
        == literal["nominal_display_datetime"]
    )
    assert row["source_midnight_label"] is (literal["year"] in {1979, 2084})


@pytest.mark.parametrize("literal", LITERALS, ids=lambda r: str(r["year"]))
def test_equal_labels_do_not_become_authenticated_UTC_instants(literal):
    row = BY_KEY[literal["year"], literal["term"]]
    actual = {
        "name": literal["term"],
        "datetime_with_offset": literal["nominal_display_datetime"] + "+08:00",
        "ephemeris_model": "synthetic_test_input_not_physical_reference",
        "solar_model_details": {"civil_time_method": "test_only"},
    }
    hko = {
        "published_date": literal["original_hko_date_label"],
        "comparison_status": "synthetic_test_input",
    }
    output = compare_label(row, actual, hko)
    assert output["computed_date_equals_NAOJ_normalized_label"] is True
    assert output["nominal_NAOJ_label_minus_computed_seconds"] == 0
    assert output["actual_event_date_certified_from_minute_label"] is False
    assert output["same_time_conversion_authenticated"] is False
    assert output["label_difference_is_instant_error"] is False
    assert output["actual_error_interval_seconds"] is None
    assert output["HKO_published_date_label"] == literal["original_hko_date_label"]
    assert output["NAOJ"]["raw_date_label"] == literal["raw_date_label"]


def test_1979_end_of_day_label_is_not_a_new_measured_midnight_event():
    row = BY_KEY[1979, "大寒"]
    original = deepcopy(row)
    actual = {"name": "大寒", "datetime_with_offset": "1979-01-20T23:59:54+08:00"}
    hko = {
        "published_date": "1979-01-21",
        "comparison_status": "published_date_disagreement",
    }
    result = compare_label(row, actual, hko)
    assert result["NAOJ"]["raw_date_label"] == "1979/01/20"
    assert result["NAOJ"]["raw_clock_label"] == "24:00"
    assert (
        result["NAOJ"]["label_normalization"]["nominal_display_datetime"]
        == "1979-01-21T00:00:00"
    )
    assert result["computed_date_equals_NAOJ_normalized_label"] is False
    assert result["HKO_date_equals_NAOJ_normalized_label"] is True
    assert result["nominal_NAOJ_label_minus_computed_seconds"] == 6
    assert result["source_midnight_requires_extra_care"] is True
    assert row == original


@pytest.mark.parametrize(
    "change", ["year", "offset", "delta_t", "method", "url", "rows"]
)
def test_wrong_query_identity_cannot_be_repaired_by_source_hash_alone(change):
    year = 1912
    receipt = json.loads((FOLDER / f"naoj-{year}-default-query.json").read_bytes())
    raw = (FOLDER / f"naoj-{year}-default.html").read_bytes()
    if change == "year":
        receipt["parameters"][0][1] = "1913"
    elif change == "offset":
        receipt["parameters"][1][1] = "9"
    elif change == "delta_t":
        receipt["parameters"][7][1] = "99"
    elif change == "method":
        receipt["method"] = "GET"
    elif change == "url":
        receipt["url"] = "https://example.invalid/"
    else:
        receipt["rows"] = receipt["rows"][:-1]
    with pytest.raises(ValueError):
        parse_annual_response(raw, receipt, year)


def test_server_fallback_to_another_year_is_rejected():
    raw = (FOLDER / "naoj-1912-default.html").read_bytes().replace(b"1912", b"1913")
    receipt = json.loads((FOLDER / "naoj-1912-default-query.json").read_bytes())
    receipt["response_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="Returned year"):
        parse_annual_response(raw, receipt, 1912)


def test_a_recommitted_subset_still_cannot_shrink_the_required_cohort(tmp_path):
    folder = tmp_path / "subset"
    shutil.copytree(FOLDER, folder)
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for name in list(manifest["files"]):
        if name.startswith("naoj-1900-default"):
            del manifest["files"][name]
    raw = json.dumps(manifest).encode()
    (folder / "manifest.json").write_bytes(raw)
    with pytest.raises(ValueError, match="All201"):
        read_naoj_reference(folder, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_changed_primary_bytes_do_not_receive_an_old_reference_receipt(tmp_path):
    folder = tmp_path / "tamper"
    shutil.copytree(FOLDER, folder)
    p = folder / "naoj-1912-default.html"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Frozen reference"):
        read_naoj_reference(folder)


def test_an_actual_naive_clock_cannot_be_silently_read_as_UTC():
    row = BY_KEY[1912, "小雪"]
    with pytest.raises(ValueError, match="requires its offset"):
        compare_label(
            row,
            {"name": "小雪", "datetime_with_offset": "1912-11-22T23:48:00"},
            {"comparison_status": "test"},
        )


def test_a_wrong_manifest_commitment_is_not_a_reference():
    with pytest.raises(ValueError, match="prior commitment"):
        read_naoj_reference(FOLDER, expected_sha256="0" * 64)
    assert (
        EXPECTED_REFERENCE_SHA256
        == "d5692771ab8b96cb56df322a40ac1ea2afb4f4930ee8bc14bfb2878bcb69c233"
    )
