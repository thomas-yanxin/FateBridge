"""Completed solar models can choose different months at the same instant."""

import gzip
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.liuyao_calendar_models import SCOPE, month_model_comparison
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from tests.fixtures.liuyao_v31_compat import without_v31_readout

REFERENCE = Path(__file__).parent / "fixtures/liuyao_model_boundary_v27"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]
CURRENT_BEFORE_PATH = (
    REFERENCE.parent
    / "architecture_refactor_v1/sixyao-model-boundary-before-v9.json.gz"
)
assert hashlib.sha256(CURRENT_BEFORE_PATH.read_bytes()).hexdigest() == (
    "66668785ab29013a911a4633ecbb37f237301d5c1b4eee876e83229e7ffb0101"
)
CURRENT_BEFORE = {
    row["id"]: row["output"]
    for row in json.loads(gzip.decompress(CURRENT_BEFORE_PATH.read_bytes()))["rows"]
}

ROOT = "liuyao_evidence.calendar_conventions.month_model_comparison"
ADDED_DETAILS = {
    "selected_crossing_jd_tt",
    "native_choice_probe_jd_tt",
    "native_choice_probe_datetime_utc",
    "selected_minus_native_seconds_tt",
}


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
    value = comparison(result)
    assert value["coverage_complete"] is True
    assert value["primary_context_consistent"] is True
    assert value["compared_month_boundaries"] == 36
    assert value["calculation_month_branch"] == case["selected_month_branch"]
    assert value["native_month_branch"] == case["native_month_branch"]
    assert value["month_changed"] is case["month_changed"]
    assert value["native_models"] == ["moshier"]
    assert value["selected_models"] == ["fatebridge_analytic_solar_v1"]
    assert value["missing_native_probes"] == []
    assert value["status"] == (
        "month_differs_between_completed_paths"
        if case["month_changed"]
        else "same_month_in_completed_paths"
    )
    active = value["active_boundary_differences"]
    assert len(active) == int(case["month_changed"])
    if active:
        fact = active[0]
        assert fact["name"] == case["term"]
        assert (
            fact["selected"]["datetime_utc"]
            == comparison(CURRENT_BEFORE[case["id"]])["active_boundary_differences"][0][
                "selected"
            ]["datetime_utc"]
        )
        assert (
            fact["native"]["datetime_utc"]
            == comparison(CURRENT_BEFORE[case["id"]])["active_boundary_differences"][0][
                "native"
            ]["datetime_utc"]
        )
        assert fact["native"]["role"] == "completed_native_choice_probe"
        assert fact["native"]["native_retflags"] == [4]
        assert fact["selected_has_passed"] is not fact["native_has_passed"]
        assert (
            fact["selected_minus_native_seconds_tt"]
            == (fact["selected"]["julian_day_tt"] - fact["native"]["julian_day_tt"])
            * 86400
        )


def test_engineered_inputs_and_previous_source_outputs_remain_frozen():
    for name in ["freeze.json", "baseline-freeze.json"]:
        for file, digest in json.loads((REFERENCE / name).read_text())[
            "files_sha256"
        ].items():
            assert hashlib.sha256((REFERENCE / file).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_complete_current_model_comparison_matches_pre_repair_source(case):
    assert build_sixyao_result(**case["input"]) == CURRENT_BEFORE[case["id"]]


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_actual_native_probe_and_selected_months_are_kept_distinct(case):
    result = build_sixyao_result(**case["input"])
    assert_comparison(result, case)
    if case["month_changed"]:
        assert f"本次采用{case['selected_month_branch']}月" in result["snapshot_text"]
        assert (
            f"原生选择路径为{case['native_month_branch']}月" in result["snapshot_text"]
        )
        assert SCOPE in result["snapshot_text"]
    else:
        assert case["term"] == "谷雨"
        assert "同次交气模型比较：" not in result["snapshot_text"]


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_complete_primary_business_output_is_unchanged_except_declared_readout(case):
    historical = json.loads(
        (REFERENCE / ("baseline-" + case["id"] + ".json")).read_text()
    )
    assert (
        historical["liuyao_evidence"]["conditional_analysis"]["ruleset_version"]
        == "2.17.0"
    )
    before = deepcopy(CURRENT_BEFORE[case["id"]])
    assert (
        before["liuyao_evidence"]["conditional_analysis"]["ruleset_version"] == "2.20.0"
    )
    before = without_v31_readout(before)
    before["liuyao_evidence"]["calendar_conventions"].pop("month_model_comparison")
    after = build_sixyao_result(**case["input"])
    after = without_v31_readout(after)
    after["liuyao_evidence"]["calendar_conventions"].pop("month_model_comparison")

    def strip_added_probe_fields(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "solar_model_details":
                    assert ADDED_DETAILS <= set(child)
                    for name in ADDED_DETAILS:
                        child.pop(name)
                else:
                    strip_added_probe_fields(child)
        elif isinstance(value, list):
            for child in value:
                strip_added_probe_fields(child)

    strip_added_probe_fields(after)
    strip_added_probe_fields(before)
    lines = after["snapshot_text"].splitlines()
    added = [
        line for line in lines if line.startswith("同次交气模型比较：") or line == SCOPE
    ]
    assert len(added) == (2 if case["month_changed"] else 0)
    after["snapshot_text"] = "\n".join(line for line in lines if line not in added)
    before["snapshot_text"] = "\n".join(
        line for line in before["snapshot_text"].splitlines() if line not in added
    )
    assert after == before


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
    assert result["liuyao_evidence"]["calendar_conventions"]["month_branch"] == "辰"
    assert (
        result["calendar_context"]["current_solar_term"]["ephemeris_model"] == "moshier"
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


@pytest.mark.parametrize("case", CASES[:2], ids=lambda x: x["id"])
@pytest.mark.parametrize(
    "side", ["before_both", "at_selected", "at_native", "after_both"]
)
def test_completed_path_boundaries_are_inclusive_at_the_actual_instant(case, side):
    boundary = comparison(CURRENT_BEFORE[case["id"]])["active_boundary_differences"][0]
    selected = datetime.fromisoformat(boundary["selected"]["datetime_utc"])
    native = datetime.fromisoformat(boundary["native"]["datetime_utc"])
    instant = {
        "before_both": min(selected, native) - timedelta(microseconds=1),
        "at_selected": selected,
        "at_native": native,
        "after_both": max(selected, native) + timedelta(microseconds=1),
    }[side]
    payload = {
        **case["input"],
        "date": instant.date().isoformat(),
        "time": instant.time().isoformat(),
    }
    value = comparison(build_sixyao_result(**payload))
    assert value["month_changed"] is ((instant >= selected) != (instant >= native))


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
