"""Semantic cycle-card compression must preserve every calculation fact."""

import json
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.result_delivery import _json, bound_response
from fatebridge.core.human_design_cycle_summary import (
    FORMAT,
    compact_cycle_summary,
    cycle_contact_facts,
)
from fatebridge.core.human_design_cycles import (
    _cycle_summary_facts,
    cycle_summary,
    summary_conventions,
)
from fatebridge.validation.human_design import verify_human_design_reading
from tests.support.human_design_current import complete_run

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=2)
def current_cycle_run(mode):
    with tempfile.TemporaryDirectory() as empty, pytest.MonkeyPatch.context() as env:
        env.setenv("SE_EPHE_PATH", str(ROOT / "ephe") if mode == "files" else empty)
        env.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return complete_run(
            birth_year=1980,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=0,
            birth_timezone="UTC",
            cycle_reference_datetime="2029-07-01T00:00:00Z",
        )


def rich_current_run(mode="files", *, card=False):
    result = deepcopy(current_cycle_run(mode))
    context = result["cycle_context"]
    context.pop("summary_format", None)
    context.pop("summary_conventions", None)
    result["cycle_summary"] = _cycle_summary_facts(context, result["profile"])
    if card:
        card = {
            k: result[k]
            for k in (
                "birth_utc",
                "profile",
                "cycle_summary",
                "validation",
                "run_metadata",
            )
        }
        card["calculation_policy"] = {
            k: result["calculation_policy"][k]
            for k in ("position_frame", "ephemeris_model")
        }
        return card
    return result


def converted(value):
    p = deepcopy(value)
    context = p["cycle_context"]
    context["summary_format"] = FORMAT
    context["summary_conventions"] = summary_conventions(
        context["source_evidence"], context["reference_ordering"]
    )
    p["cycle_summary"] = cycle_summary(context, p["profile"])
    return p


@pytest.mark.parametrize("mode", ["files", "empty"])
def test_current_card_keeps_business_facts_within8192(mode):
    p = rich_current_run(mode, card=True)
    before = deepcopy(p)
    rich = p["cycle_summary"]
    p["cycle_summary"] = compact_cycle_summary(rich)
    result = bound_response(p, 8192)
    assert len(_json(result)) <= 8192
    assert result["cycle_summary"] == p["cycle_summary"]
    if "result_delivery" in result:
        assert all(
            path.startswith("run_metadata.")
            for path in result["result_delivery"]["deferred_fields"]
        )
    assert {
        k: v for k, v in result.items() if k not in {"run_metadata", "result_delivery"}
    } == {k: v for k, v in p.items() if k != "run_metadata"}
    assert cycle_contact_facts(rich) == cycle_contact_facts(result["cycle_summary"])
    assert before["cycle_summary"] == rich


@pytest.mark.parametrize("mode", ["files", "empty"])
def test_current_full_format_verifies_and_preserves_rich_contact_facts(mode):
    current = deepcopy(current_cycle_run(mode))
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("native verifier call"),
    ):
        assert (
            verify_human_design_reading(current)["status"]
            == "verified_fixed_template_reading"
        )
    rich_context = deepcopy(current["cycle_context"])
    rich_context.pop("summary_format")
    rich = _cycle_summary_facts(rich_context, current["profile"])
    assert cycle_contact_facts(rich) == cycle_contact_facts(current["cycle_summary"])


@pytest.mark.parametrize(
    "label,future",
    [
        ("inserted_UTC_leap_second", True),
        ("unrepresentable_historical_fractional_UTC_adjustment", False),
    ],
)
def test_label_exceptions_are_explicit_and_never_replaced_by_defaults(label, future):
    rich = rich_current_run()["cycle_summary"]
    event = rich["bodies"][0]["contacts"][0]
    event["utc_label_status"] = label
    event["future_leap_seconds_assumed_unchanged"] = future
    event["utc_label"] = None
    compact = compact_cycle_summary(rich)
    assert compact["bodies"][0]["contacts"][0]["utc_label_status"] == label
    assert cycle_contact_facts(rich) == cycle_contact_facts(compact)


def test_real_native_speed_and_segment_disagreement_survives_compaction():
    inputs = json.loads(
        (
            Path(__file__).parents[1] / "data/human_design/regression-inputs.json"
        ).read_text()
    )
    run = complete_run(**inputs["cycle_coordinate_extrema"])
    context = deepcopy(run["cycle_context"])
    context.pop("summary_format", None)
    rich = _cycle_summary_facts(context, run["profile"])
    compact = compact_cycle_summary(rich)
    assert cycle_contact_facts(rich) == cycle_contact_facts(compact)
    events = [
        c
        for b in compact["bodies"]
        for c in b["contacts"]
        if c.get("segment_phase_trend") == "increasing" and c["motion"] == "retrograde"
    ]
    assert len(events) == 1
    facts = [
        c
        for b in cycle_contact_facts(compact)
        for c in b["contacts"]
        if c["jd_tt"] == events[0]["jd_tt"]
    ]
    assert (
        facts[0]["motion_evidence"]["native_speed_agrees_with_segment_trend"] is False
    )


@pytest.mark.parametrize(
    "fault", ["missing_defaults", "false_physical", "reverse_mapping", "unknown_format"]
)
def test_decoder_rejects_missing_or_forged_conventions(fault):
    s = compact_cycle_summary(rich_current_run()["cycle_summary"])
    if fault == "missing_defaults":
        s.pop("contact_defaults")
    elif fault == "false_physical":
        s["motion_evidence_defaults"][
            "instantaneous_coordinate_derivative_certified"
        ] = True
    elif fault == "reverse_mapping":
        s["motion_evidence_defaults"]["segment_phase_trend_from_motion"][
            "direct"
        ] = "decreasing"
    else:
        s["summary_format"] = "unknown"
    with pytest.raises(ValueError):
        cycle_contact_facts(s)


@pytest.mark.parametrize(
    "fault",
    [
        "default_status",
        "future_flag",
        "direction",
        "physical",
        "details",
        "remove_format",
        "unknown_format",
    ],
)
def test_rehashed_full_result_cannot_forge_compact_facts(fault):
    p = converted(rich_current_run())
    s = p["cycle_summary"]
    if fault == "default_status":
        s["contact_defaults"]["utc_label_status"] = "physically_certified"
    elif fault == "future_flag":
        s["contact_defaults"]["future_leap_seconds_assumed_unchanged"] = True
    elif fault == "direction":
        s["bodies"][0]["contacts"][0]["segment_phase_trend"] = "decreasing"
    elif fault == "physical":
        s["motion_evidence_defaults"][
            "instantaneous_coordinate_derivative_certified"
        ] = True
    elif fault == "details":
        p["cycle_context"]["summary_conventions"]["reference_contact_ordering"][
            "physical_accuracy_certified"
        ] = True
    elif fault == "remove_format":
        p["cycle_context"].pop("summary_format")
    else:
        p["cycle_context"]["summary_format"] = "unknown"
    assert verify_human_design_reading(p)["status"] == "rejected"


def test_unobserved_motion_stays_unknown_instead_of_inheriting_agreement():
    rich = rich_current_run()["cycle_summary"]
    rich["bodies"][0]["contacts"][0]["motion_evidence"] = None
    compact = compact_cycle_summary(rich)
    assert compact["bodies"][0]["contacts"][0]["segment_phase_trend"] is None
    assert cycle_contact_facts(compact)[0]["contacts"][0]["motion_evidence"] is None
    assert cycle_contact_facts(compact) == cycle_contact_facts(rich)


def test_missing_format_cannot_turn_compact_defaults_into_implicit_rich_facts():
    compact = compact_cycle_summary(rich_current_run()["cycle_summary"])
    compact.pop("summary_format")
    with pytest.raises(ValueError, match="format declaration"):
        cycle_contact_facts(compact)


def test_integer_zero_is_not_a_known_false_leap_status():
    rich = rich_current_run()["cycle_summary"]
    rich["bodies"][0]["contacts"][0]["future_leap_seconds_assumed_unchanged"] = 0
    compact = compact_cycle_summary(rich)
    event = compact["bodies"][0]["contacts"][0]
    assert type(event["future_leap_seconds_assumed_unchanged"]) is int
    with pytest.raises(ValueError, match="leap-second status"):
        cycle_contact_facts(compact)
