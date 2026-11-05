"""Current model comparisons retain independently adjudicated source phases."""

import gzip
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import erfa
import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.liuyao_calendar_models import SCOPE, month_model_comparison
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_MODEL
from fatebridge.core.moshier_solar import solar_longitude as complete_moshier_longitude
from tests.solar_source_facts import HKO_TERM_LONGITUDES

CASES = json.loads(
    (Path(__file__).parent / "data/liuyao/model_boundary_inputs.json").read_bytes()
)["cases"]

SOURCE = json.loads(
    (
        Path(__file__).parent / "data/liuyao/model_boundary_de440_source.json"
    ).read_bytes()
)
SOURCE_CASES = {row["id"]: row for row in SOURCE["cases"]}

ROOT = "liuyao_evidence.calendar_conventions.month_model_comparison"


@pytest.fixture(autouse=True)
def analytic_environment(monkeypatch, tmp_path_factory):
    empty = tmp_path_factory.getbasetemp() / "model-boundary-empty-ephe"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    # Preserve the frozen former-default analytic/native comparison controls.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def comparison(result):
    return result["liuyao_evidence"]["calendar_conventions"]["month_model_comparison"]


def assert_comparison(result, case):
    source = SOURCE_CASES[case["id"]]
    value = comparison(result)
    assert value["coverage_complete"] is True
    assert value["primary_context_consistent"] is True
    assert value["compared_month_boundaries"] == 36
    assert value["calculation_month_branch"] == case["selected_month_branch"]
    assert value["native_month_branch"] == source["current_month_branch_from_reference"]
    assert (
        value["month_changed"]
        is source["current_month_changed_between_completed_paths"]
    )
    assert value["native_models"] == [COMPLETE_MOSHIER_MODEL]
    assert value["selected_models"] == ["fatebridge_analytic_solar_v1"]
    assert value["missing_native_probes"] == []
    assert value["status"] == (
        "month_differs_between_completed_paths"
        if source["current_month_changed_between_completed_paths"]
        else "same_month_in_completed_paths"
    )
    # Check actual completed roots even when both paths now give the same month.
    for record in (value["native_previous_boundary"], value["native_next_boundary"]):
        assert record["role"] == "completed_native_choice_probe"
        assert record["native_retflags"] == []
        high = record["julian_day_tt"]
        low = math.nextafter(high, -math.inf)
        target = HKO_TERM_LONGITUDES[record["name"]]
        assert math.remainder(complete_moshier_longitude(low) - target, 360) < 0
        assert math.remainder(complete_moshier_longitude(high) - target, 360) >= 0
    active = value["active_boundary_differences"]
    assert len(active) == int(source["current_month_changed_between_completed_paths"])
    if active:
        fact = active[0]
        assert fact["name"] == case["term"]
        assert fact["native"]["role"] == "completed_native_choice_probe"
        assert fact["native"]["native_retflags"] == []
        for record in (fact["selected"], fact["native"]):
            if record["ephemeris_model"] != COMPLETE_MOSHIER_MODEL:
                continue
            hi = record["julian_day_tt"]
            lo = math.nextafter(hi, -math.inf)
            target = HKO_TERM_LONGITUDES[fact["name"]]
            left = complete_moshier_longitude(lo)
            right = complete_moshier_longitude(hi)
            assert math.remainder(left - target, 360) < 0
            assert math.remainder(right - target, 360) >= 0
        assert fact["selected_has_passed"] is not fact["native_has_passed"]
        assert (
            fact["selected_minus_native_seconds_tt"]
            == (fact["selected"]["julian_day_tt"] - fact["native"]["julian_day_tt"])
            * 86400
        )


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_current_completed_months_match_the_independent_source_phase(case):
    result = build_sixyao_result(**case["input"])
    assert_comparison(result, case)
    if SOURCE_CASES[case["id"]]["current_month_changed_between_completed_paths"]:
        assert f"本次采用{case['selected_month_branch']}月" in result["snapshot_text"]
        assert (
            f"原生选择路径为{case['native_month_branch']}月" in result["snapshot_text"]
        )
        assert SCOPE in result["snapshot_text"]
    else:
        assert "同次交气模型比较：" not in result["snapshot_text"]


def test_explicit_native_does_not_start_an_alternate_analytic_calculation(monkeypatch):
    import fatebridge.core.analytic_solar as solar

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")

    def unexpected(*args, **kwargs):
        raise AssertionError("Native result must not manufacture another model")

    monkeypatch.setattr(solar, "solar_longitude", unexpected)
    result = build_sixyao_result(**CASES[0]["input"])
    assert (
        "month_model_comparison"
        not in result["liuyao_evidence"]["calendar_conventions"]
    )
    assert (
        result["liuyao_evidence"]["calendar_conventions"]["month_branch"]
        == SOURCE_CASES[CASES[0]["id"]]["current_month_branch_from_reference"]
    )
    assert (
        result["calendar_context"]["current_solar_term"]["ephemeris_model"]
        == COMPLETE_MOSHIER_MODEL
    )


@pytest.mark.parametrize("bad", [None, True, math.nan, "not a TT epoch"])
def test_missing_or_invalid_native_tt_is_unknown_not_agreement(bad):
    case = CASES[0]
    result = build_sixyao_result(**case["input"])
    terms = [
        term
        for year in range(1971, 1974)
        for term in get_solar_terms_for_year(year, "UTC")
    ]
    index = next(
        i
        for i, term in enumerate(terms)
        if term.moment.year == 1972 and term.name == "立夏"
    )
    details = deepcopy(terms[index].solar_model_details)
    details["native_choice_probe_jd_tt"] = bad
    terms[index] = replace(terms[index], solar_model_details=details)
    value = month_model_comparison(
        datetime.fromisoformat(
            case["input"]["date"] + "T" + case["input"]["time"] + "+00:00"
        ),
        "UTC",
        result["calendar_context"]["bazi_month_boundary"],
        terms=terms,
    )
    assert value["coverage_complete"] is False
    assert value["status"] == "not_compared_incomplete_native_probes"
    assert "month_changed" not in value and "native_month_branch" not in value
    assert value["missing_native_probes"] == ["1972:立夏"]


def test_modifying_returned_probe_data_does_not_change_cached_comparisons():
    original = build_sixyao_result(**CASES[0]["input"])
    changed = get_solar_terms_for_year(1972, "UTC")[8].as_dict()
    changed["solar_model_details"]["native_choice_probe_datetime_utc"] = None
    assert comparison(build_sixyao_result(**CASES[0]["input"])) == comparison(original)


def test_different_primary_boundary_provenance_is_not_a_completed_comparison():
    case = CASES[0]
    result = build_sixyao_result(**case["input"])
    primary = deepcopy(result["calendar_context"]["bazi_month_boundary"])
    primary["start_term"]["solar_model_details"][
        "coefficient_sha256"
    ] = "deliberate simulated prior-source mismatch"
    value = month_model_comparison(
        datetime.fromisoformat(
            case["input"]["date"] + "T" + case["input"]["time"] + "+00:00"
        ),
        "UTC",
        primary,
    )
    assert value["primary_context_consistent"] is False
    assert value["coverage_complete"] is False
    assert value["status"] == "not_compared_primary_boundaries_changed"
    assert value["active_boundary_differences"] == []
    assert "month_changed" not in value and "native_month_branch" not in value


@pytest.mark.local_data
@pytest.mark.parametrize("case", CASES, ids=lambda row: row["id"])
def test_original_inputs_and_stock_counterexamples_keep_independent_de440_phase(case):
    source = SOURCE_CASES[case["id"]]
    assert source["input"] == case["input"]
    assert source["stock_native_month_branch"] == case["native_month_branch"]
    assert source["stock_month_changed"] is case["month_changed"]
    reference_path = Path(__file__).parents[1] / SOURCE["reference_path"]
    raw = reference_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE["reference_original_bytes_sha256"]
    packet = json.loads(gzip.decompress(raw))
    original = next(
        row
        for row in packet["rows"]
        if row["year"] == 1972 and row["index"] == case["term_index"]
    )
    assert source["original_reference_row"] == original
    clock = datetime.fromisoformat(case["input"]["date"] + "T" + case["input"]["time"])
    utc = erfa.dtf2d(
        "UTC",
        clock.year,
        clock.month,
        clock.day,
        clock.hour,
        clock.minute,
        clock.second + clock.microsecond / 1e6,
    )
    expected_tai_minus_utc = 11 if clock.month >= 7 else 10
    assert erfa.dat(clock.year, clock.month, clock.day, 0) == expected_tai_minus_utc
    assert source["tt_minus_utc_seconds"] == expected_tai_minus_utc + 32.184
    tt1, tt2 = erfa.taitt(*erfa.utctai(*utc))
    delta = float(((tt1 - original["jd_tt"]) + tt2) * 86400)
    assert delta == pytest.approx(source["input_minus_reference_seconds"], abs=1e-9)
    assert (delta >= 0) is source["reference_has_passed"]
    expected_month = (
        source["month_branch_after"] if delta >= 0 else source["month_branch_before"]
    )
    assert expected_month == source["current_month_branch_from_reference"]
    assert source["stock_month_matches_reference"] is (case["id"] == "1972-07")
