"""Full-span reference integrity and counterexamples to false TT acceptance."""

import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.validation import fengshui_solar_terms as audit

FOLDER = Path(__file__).parent / "data/fengshui_all_terms_v1"


@pytest.fixture(scope="module")
def reference():
    return audit.load_solar_terms_reference(FOLDER)


def test_full_declared_range_contains_both_jie_and_qi_without_dropping_endpoints(
    reference,
):
    assert len(reference["rows"]) == 10104
    assert reference["rows"][0]["year"] == 1784
    assert reference["rows"][-1]["year"] == 2204
    assert {r["term"] for r in reference["rows"]} == set(audit.TERMS)
    assert sum(r["term_index"] % 2 == 0 for r in reference["rows"]) == 5052
    assert sum(r["term_index"] % 2 == 1 for r in reference["rows"]) == 5052


def test_existing421_lichun_reference_is_preserved_and_independently_reproduced(
    reference,
):
    previous = json.loads(
        (FOLDER.parent / "fengshui_lichun_tt/reference.json").read_text()
    )
    current = [r for r in reference["rows"] if r["term"] == "立春"]
    assert len(current) == len(previous["rows"]) == 421
    for old, new in zip(previous["rows"], current, strict=True):
        assert old["year"] == new["year"]
        assert abs(old["jd_tt"] - new["jd_tt"]) * 86400 <= 0.001


@pytest.mark.parametrize("name", sorted(audit.CAPTURE_HASHES))
def test_changed_or_self_rehashed_capture_cannot_replace_the_frozen_reference(
    tmp_path, name
):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    (folder / name).write_text("{}")
    with pytest.raises(ValueError, match="capture changed"):
        audit.load_solar_terms_reference(folder)
    hashes = json.loads((folder / "hashes.json").read_text())
    hashes[name] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(hashes))
    with pytest.raises(ValueError, match="capture manifest"):
        audit.load_solar_terms_reference(folder)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_year",
        "missing_qi",
        "duplicate",
        "reorder",
        "relabel_term",
        "wrong_longitude",
        "nan",
        "boolean_epoch",
        "outside_month",
        "loose_reference_bracket",
        "loose_gate",
        "shorter_protocol",
        "different_collector",
        "different_dependency",
    ],
)
def test_incomplete_or_relabelled_protocol_cannot_be_accepted(reference, mutation):
    value = deepcopy(reference)
    if mutation == "missing_year":
        del value["rows"][:24]
    elif mutation == "missing_qi":
        value["rows"] = [r for r in value["rows"] if r["term_index"] % 2 == 0]
    elif mutation == "duplicate":
        value["rows"][1] = deepcopy(value["rows"][0])
    elif mutation == "reorder":
        value["rows"][0], value["rows"][1] = value["rows"][1], value["rows"][0]
    elif mutation == "relabel_term":
        value["rows"][1]["term"] = "小寒"
    elif mutation == "wrong_longitude":
        value["rows"][1]["longitude_degrees"] = 285
    elif mutation == "nan":
        value["rows"][1]["jd_tt"] = float("nan")
    elif mutation == "boolean_epoch":
        value["rows"][1]["jd_tt"] = True
    elif mutation == "outside_month":
        value["rows"][1]["jd_tt"] += 365
    elif mutation == "loose_reference_bracket":
        value["rows"][1]["bracket_width_seconds"] = 1.0
    elif mutation == "loose_gate":
        value["protocol"]["numeric_implementation_tolerance_seconds"] = 3.0
    elif mutation == "shorter_protocol":
        value["protocol"]["years"] = [1800, 2200]
    elif mutation == "different_collector":
        value["collector_sha256"] = "changed"
    else:
        value["versions"]["skyfield"] = "unverified"
    with pytest.raises(ValueError):
        audit.validate_solar_terms_reference(value)


@pytest.fixture
def actual_resolution(reference, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    row = next(r for r in reference["rows"] if (r["year"], r["term"]) == (2026, "夏至"))
    return row, audit.solar_term_resolution(2026, "夏至", "UTC")


def test_actual_named_root_and_serialized_civil_output_both_meet_gate(
    actual_resolution,
):
    row, resolution = actual_resolution
    checked = audit.compare_resolution(row, resolution)
    assert checked["within_tolerance"] is True
    assert abs(checked["selected_root_difference_seconds_tt"]) <= 1.0
    assert abs(checked["civil_roundtrip_difference_seconds_tt"]) <= 1.0
    assert resolution["ephemeris_model"] == "fatebridge_de440_solar_v1"


@pytest.mark.parametrize(
    "mutation",
    [
        "civil",
        "raw_root",
        "missing_root",
        "approximate",
        "no_model",
        "no_tt",
        "unknown_provider",
    ],
)
def test_real_result_mutations_cannot_hide_behind_other_correct_fields(
    actual_resolution, mutation
):
    row, value = deepcopy(actual_resolution)
    if mutation == "civil":
        value["moment"] = (
            datetime.fromisoformat(value["moment"]) + timedelta(seconds=2)
        ).isoformat()
    elif mutation == "raw_root":
        value["solar_model_details"]["selected_crossing_jd_tt"] += 2 / 86400
    elif mutation == "missing_root":
        del value["solar_model_details"]["selected_crossing_jd_tt"]
    elif mutation == "approximate":
        value["approximate"] = True
    elif mutation == "no_model":
        value["ephemeris_model"] = None
    elif mutation == "no_tt":
        value["time_basis"]["root_time_scale"] = None
    else:
        value["provider"] = "unverified_or_linear"
    assert audit.compare_resolution(row, value)["within_tolerance"] is False


def test_simplified_date_hypotheses_are_not_promoted_by_more_astronomy(reference):
    assert "not absolute observed UTC" in reference["protocol"]["scope"]
    assert "original-book date-table selection" in reference["protocol"]["scope"]
