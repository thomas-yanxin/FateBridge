"""Civil seconds select an instant, without becoming a Meihua seed number."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services.divination import calculate_meihua_analysis
from tests.meihua.test_meihua_civil_clock import CASES as CLOCKS
from tests.meihua.test_meihua_civil_clock import parameters as clock_parameters
from tests.support.meihua_input_seconds_reference import FOLDER, cases, parameters

CASES = cases()


def test_reference_keeps_all_jie_and_zhongqi_with_shared_dynamics_limit():
    protocol = json.loads((FOLDER / "protocol.json").read_bytes())
    assert protocol["frozen_before_production_edits"]
    assert protocol["shared_DE440_dynamics_not_independent_observations"]
    assert protocol["new_real_world_observations"] == 0
    assert sum(c["same_civil_minute"] for c in CASES) == 42
    assert sum(c["is_jie"] for c in CASES) == 24
    reference = FOLDER.parent / "meihua_solar_seconds_v1/reference-2000a.json"
    assert (
        hashlib.sha256(reference.read_bytes()).hexdigest() == protocol["source_sha256"]
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_both_sides_of_independent_solar_roots_select_actual_month_and_term(case):
    outputs = []
    for side in ["before", "after"]:
        out = calculate_meihua_analysis(**parameters(case[side]))
        assert "error" not in out
        outputs.append(out)
        assert (
            out["calendar_context"]["bazi_month_boundary"]["branch"]
            == case[side + "_month_branch"]
        )
        assert out["analysis_context"]["current_jieqi"] == case[side + "_current_term"]
        clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
        assert clock["local_datetime"] == case[side]
        assert (
            out["calendar_context"]["bazi_month_boundary"]["comparison_datetime"]
            == case[side]
        )
        assert (
            out["analysis_context"]["civil_instant_utc"]
            == datetime.fromisoformat(case[side]).astimezone(timezone.utc).isoformat()
        )
        assert clock["input_second"]["seconds_enter_cast_seed"] is False
        assert clock["input_second"]["input_precision_certifies_accuracy"] is False
        assert (
            clock["input_second"]["original_text_uniquely_prescribes_seconds"] is False
        )
    assert outputs[0]["meihua"]["seed"] == outputs[1]["meihua"]["seed"]
    if case["is_jie"]:
        assert (
            outputs[0]["four_pillars"]["month"] != outputs[1]["four_pillars"]["month"]
        )
        assert (
            outputs[0]["meihua"]["seasonal_strength"]["month_branch"]
            == case["before_month_branch"]
        )
        assert (
            outputs[1]["meihua"]["seasonal_strength"]["month_branch"]
            == case["after_month_branch"]
        )
    else:
        assert (
            outputs[0]["four_pillars"]["month"] == outputs[1]["four_pillars"]["month"]
        )


@pytest.mark.parametrize("second", [True, False, -1, 60, 1.0, 1.5, "1", {}, []])
def test_invalid_or_coerced_seconds_never_reach_calendar(second, monkeypatch):
    import fatebridge.services.divination as service

    args = parameters(CASES[0]["after"])
    args["analysis_second"] = second
    with pytest.raises(ValidationError):
        MeihuaAnalysisRequest(**args)
    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("Invalid second reached the calendar")

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    out = service.calculate_meihua_analysis(**args)
    assert out["error_code"] == "validation_error" and out["retryable"] is False
    assert out["issues"][0]["path"] == "analysis_second" and not called


def test_omitted_null_and_explicit_zero_keep_the_same_instant_and_cast():
    args = parameters(CASES[0]["before"])
    args.pop("analysis_second")
    omitted = calculate_meihua_analysis(**args)
    null = calculate_meihua_analysis(**args, analysis_second=None)
    zero = calculate_meihua_analysis(**args, analysis_second=0)
    assert omitted == null
    assert omitted["meihua"]["seed"] == zero["meihua"]["seed"]
    assert (
        "input_second"
        not in omitted["meihua"]["calendar_policy"]["civil_clock_resolution"]
    )
    clock = zero["meihua"]["calendar_policy"]["civil_clock_resolution"]
    assert clock["input_second"]["value"] == 0
    absent_clock = omitted["meihua"]["calendar_policy"]["civil_clock_resolution"]
    assert absent_clock["input_components"]["omitted_components"] == ["second"]
    assert clock["input_components"]["omitted_components"] == []
    assert absent_clock["input_components"]["calculation_defaults"] == {"second": 0}
    assert clock["input_components"]["calculation_defaults"] == {}
    assert absent_clock["instant_utc"] == clock["instant_utc"]
    # The original v62 function is preserved and separately replayed negative.
    # Current provenance and its declared notice differ; every other complete
    # numerical and chapter field must still be identical.
    for value in [omitted, zero]:
        evidence = value["meihua"]["calendar_policy"]["civil_clock_resolution"].pop(
            "input_components"
        )
        value["interpretation"]["evidence_scope"].pop("clock_input")
        if evidence["omitted_components"]:
            for parent, key in [
                (value, "summary"),
                (value["interpretation"], "comprehensive_judgement"),
                (value["interpretation"], "traditional_judgement"),
            ]:
                if parent.get(key):
                    assert parent[key].startswith(evidence["statement"] + " ")
                    parent[key] = parent[key].removeprefix(evidence["statement"] + " ")
    clock.pop("input_second")
    clock["clock_label_precision"] = omitted["meihua"]["calendar_policy"][
        "civil_clock_resolution"
    ]["clock_label_precision"]
    assert zero == omitted


@pytest.mark.parametrize("second", range(60))
def test_seconds_within_a_regular_minute_never_add_to_seed(second):
    args = dict(
        analysis_year=2025,
        analysis_month=5,
        analysis_day=10,
        analysis_hour=12,
        analysis_minute=34,
        analysis_timezone="UTC",
    )
    base = calculate_meihua_analysis(**args)
    out = calculate_meihua_analysis(**args, analysis_second=second)
    assert out["meihua"]["seed"] == base["meihua"]["seed"]
    assert out["meihua"]["base_hexagram"] == base["meihua"]["base_hexagram"]
    assert (
        out["analysis_context"]["civil_instant_utc"]
        == f"2025-05-10T12:34:{second:02d}+00:00"
    )


@pytest.mark.parametrize("case", CLOCKS["valid"], ids=lambda c: c["id"])
def test_seconds_survive_both_fold_choices_and_non_hour_offsets(case):
    out = calculate_meihua_analysis(**clock_parameters(case), analysis_second=37)
    clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
    expected = datetime.fromisoformat(case["utc"]) + timedelta(seconds=37)
    assert clock["instant_utc"] == expected.isoformat()
    assert clock["fold"] == case["fold"]
    assert clock["resolved_utc_offset"] == case["offset"]


@pytest.mark.parametrize("case", CLOCKS["invalid"], ids=lambda c: c["id"])
def test_adding_seconds_does_not_rescue_gaps_or_invalid_offsets(case):
    out = calculate_meihua_analysis(**clock_parameters(case), analysis_second=37)
    assert out["error_code"] == "validation_error" and out["retryable"] is False


@pytest.mark.parametrize(
    "before,after",
    [
        ("2025-05-10T22:59:59+08:00", "2025-05-10T23:00:00+08:00"),
        ("2025-05-10T23:59:59+08:00", "2025-05-11T00:00:00+08:00"),
    ],
)
def test_known_seconds_do_not_move_civil_day_or_double_hour_early(before, after):
    left = calculate_meihua_analysis(**parameters(before))
    right = calculate_meihua_analysis(**parameters(after))
    assert left["meihua"]["seed"] != right["meihua"]["seed"]
    assert left["analysis_context"]["analysis_datetime"] == datetime.fromisoformat(
        before
    ).strftime("%Y-%m-%d %H:%M:%S")
    assert right["analysis_context"]["analysis_datetime"] == datetime.fromisoformat(
        after
    ).strftime("%Y-%m-%d %H:%M:%S")
