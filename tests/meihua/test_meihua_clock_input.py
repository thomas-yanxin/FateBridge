"""Supplied components, nominal defaults and observed accuracy are different facts."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_tool
from fatebridge.application.meihua_clock_binding import require_meihua_clock_binding
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.tool_catalog import CATALOG
from tests.support.meihua_clock_input_reference import FOLDER, assert_clock_input, cases

CASES = cases()
SPEC = next(s for s in CATALOG if s.key == "meihua_analysis")
TOPICS = MeihuaAnalysisRequest.model_json_schema()["properties"][
    "interpretation_topic"
]["enum"]


def test_all_sixteen_states_and_source_principles_precede_implementation():
    protocol = json.loads((FOLDER / "protocol.json").read_bytes())
    assert protocol["frozen_before_production_edits"]
    assert not protocol["expected_values_from_FateBridge"]
    assert protocol["clock_range_candidates_from_omission_prohibited"]
    assert protocol["no_retroactive_weather_case_exclusion"]
    assert protocol["new_real_world_observations"] == 0


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("topic", TOPICS)
def test_all_declared_component_states_on_every_published_chapter(case, topic):
    out = calculate_meihua_analysis(**case["arguments"], interpretation_topic=topic)
    assert "error" not in out
    assert_clock_input(out, case, "direct_service_optional_components")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_bound_request_components_and_full_guard_match_independent_truth(case):
    request = MeihuaAnalysisRequest(**case["arguments"])
    out = execute_tool(SPEC, request)
    assert "error" not in out
    assert_clock_input(out, case, "bound_request_model_fields_set")
    require_meihua_clock_binding(out, request)


@pytest.mark.parametrize("minute", [True, False, -1, 60, 1.0, 1.5, "1", {}, []])
def test_invalid_or_coerced_minutes_never_reach_calendar(minute, monkeypatch):
    import fatebridge.services.divination as service

    args = {**CASES[0]["arguments"], "analysis_minute": minute}
    with pytest.raises(ValidationError):
        MeihuaAnalysisRequest(**args)
    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("Invalid minute reached calendar")

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    out = service.calculate_meihua_analysis(**args)
    assert out["error_code"] == "validation_error" and not out["retryable"]
    assert out["issues"][0]["path"] == "analysis_minute" and not called


def test_omission_null_and_known_zero_have_honest_replay_identity():
    args = CASES[0]["arguments"]
    variants = [{}, {"analysis_minute": None}, {"analysis_minute": 0}]
    rows = [execute_tool(SPEC, MeihuaAnalysisRequest(**args, **v)) for v in variants]
    assert (
        rows[0]["run_metadata"]["input_sha256"]
        == rows[1]["run_metadata"]["input_sha256"]
    )
    assert (
        rows[0]["run_metadata"]["input_sha256"]
        != rows[2]["run_metadata"]["input_sha256"]
    )
    assert rows[0]["meihua"]["seed"] == rows[2]["meihua"]["seed"]
    assert (
        rows[0]["analysis_context"]["civil_instant_utc"]
        == rows[2]["analysis_context"]["civil_instant_utc"]
    )
    assert (
        "supplied_civil_hour"
        in rows[0]["meihua"]["calendar_policy"]["civil_clock_resolution"][
            "clock_label_precision"
        ]
    )
    assert (
        "supplied_civil_minute"
        in rows[2]["meihua"]["calendar_policy"]["civil_clock_resolution"][
            "clock_label_precision"
        ]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "known_minute",
        "defaults",
        "bool_default",
        "interval",
        "stability",
        "accuracy",
        "provenance",
        "nominal",
        "missing_notice",
        "duplicate_notice",
        "trace",
        "scope",
        "scope_basis",
        "classical_precision",
        "extra_accuracy_claim",
        "changed_statement",
    ],
)
def test_forged_precision_or_request_binding_fails_before_projection(mutation):
    request = MeihuaAnalysisRequest(**CASES[0]["arguments"])
    good = execute_tool(SPEC, request)
    out = deepcopy({k: v for k, v in good.items() if k != "run_metadata"})
    clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
    receipt = clock["input_components"]
    if mutation == "known_minute":
        receipt["supplied_components"].append("minute")
    elif mutation == "defaults":
        receipt["calculation_defaults"]["minute"] = 1
    elif mutation == "bool_default":
        receipt["calculation_defaults"]["minute"] = False
    elif mutation == "interval":
        receipt["uncertainty_interval"] = {"seconds": 60}
    elif mutation == "stability":
        receipt["calendar_stability"] = "stable"
    elif mutation == "accuracy":
        receipt["observed_precision_certified"] = True
    elif mutation == "provenance":
        receipt["provenance"] = "guessed_components"
    elif mutation == "nominal":
        receipt["nominal_civil_datetime"] = "2000-01-06T09:01:00+08:00"
    elif mutation in {"missing_notice", "duplicate_notice"}:
        text = out["summary"]
        text = (
            text.replace(receipt["statement"] + " ", "", 1)
            if mutation == "missing_notice"
            else receipt["statement"] + " " + text
        )
        out["summary"] = out["interpretation"]["comprehensive_judgement"] = text
    elif mutation == "trace":
        out["meihua"]["rule_trace"][-1] = {
            **out["meihua"]["rule_trace"][-1],
            "result": {},
        }
    elif mutation == "scope":
        out["interpretation"]["evidence_scope"]["clock_input"][
            "calendar_stability"
        ] = "stable"
    elif mutation == "scope_basis":
        out["interpretation"]["evidence_scope"]["clock_input"][
            "calendar_basis"
        ] = "all_instants"
    elif mutation == "classical_precision":
        receipt["original_text_uniquely_prescribes_this_precision"] = True
    elif mutation == "extra_accuracy_claim":
        receipt["unverified_accuracy"] = "perfect"
    else:
        old = receipt["statement"]
        receipt["statement"] = "记录精度已核实"
        out["summary"] = out["interpretation"]["comprehensive_judgement"] = out[
            "summary"
        ].replace(old, receipt["statement"], 1)
    with pytest.raises(ValueError):
        require_meihua_clock_binding(out, request)
    forged = replace(SPEC, bind=lambda request: (lambda: out, (), {}))
    failure = execute_tool(forged, request)
    assert failure["status_code"] == 500 and failure["error_code"] == "internal_error"


def test_internal_presence_flags_are_not_published_user_parameters():
    assert "_clock_supplied_components" not in MeihuaAnalysisRequest.model_fields
    with pytest.raises(ValidationError):
        MeihuaAnalysisRequest(
            **CASES[0]["arguments"], _clock_supplied_components=["minute"]
        )
