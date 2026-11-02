"""Semantic cycle-card compression must preserve every calculation fact."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.result_delivery import _json, bound_response
from fatebridge.core.human_design_cycle_summary import (
    FORMAT,
    compact_cycle_summary,
    cycle_contact_facts,
)
from fatebridge.core.human_design_cycles import cycle_summary, summary_conventions
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-cycle-summary-v1"


def load(name):
    return json.loads(gzip.decompress((BASE / "evidence" / name).read_bytes()))


def converted(value):
    p = deepcopy(value)
    context = p["cycle_context"]
    context["summary_format"] = FORMAT
    context["summary_conventions"] = summary_conventions(
        context["source_evidence"], context["reference_ordering"]
    )
    p["cycle_summary"] = cycle_summary(context, p["profile"])
    p["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in p.items() if k != "run_metadata"}
    )
    return p


def test_original_failing_card_cases_and_numeric_implementation_are_unchanged():
    from scripts.historical_source_identity import HistoricalSources

    originals = HistoricalSources(ROOT)
    plan = json.loads((BASE / "evidence/plan.json").read_text())
    for name in (
        "tests/test_human_design_transports.py",
        "src/fatebridge/core/human_design.py",
        "src/fatebridge/core/human_design_cycle_history.py",
        "src/fatebridge/application/result_delivery.py",
        "src/fatebridge/services/replay_metadata.py",
    ):
        if name == "tests/test_human_design_transports.py":
            original = ROOT / (
                "tests/fixtures/architecture_refactor_v1/frozen-tests/"
                "test_human_design_transports.py.txt"
            )
            assert (
                hashlib.sha256(original.read_bytes()).hexdigest()
                == plan["source_before"][name]
            )
        else:
            assert originals.matches(ROOT / name, plan["source_before"][name])


@pytest.mark.parametrize("mode", ["files", "empty"])
def test_saved_real_card_fits_original8192_without_extra_deferral(mode):
    p = load(f"before-{mode}-card-full.json.gz")
    before = deepcopy(p)
    rich = p["cycle_summary"]
    p["cycle_summary"] = compact_cycle_summary(rich)
    result = bound_response(p, 8192)
    assert len(_json(result)) <= 8192
    assert result["cycle_summary"] == p["cycle_summary"]
    if "result_delivery" in result:
        assert result["result_delivery"]["deferred_fields"] == ["run_metadata.runtime"]
    assert cycle_contact_facts(rich) == cycle_contact_facts(result["cycle_summary"])
    assert before["cycle_summary"] == rich


@pytest.mark.parametrize("mode", ["files", "empty"])
def test_both_full_formats_verify_without_native_recalculation(mode):
    old = load(f"before-{mode}-full.json.gz")
    new = converted(old)
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("native verifier call"),
    ):
        assert (
            verify_human_design_reading(old)["status"]
            == "verified_fixed_template_reading"
        )
        assert (
            verify_human_design_reading(new)["status"]
            == "verified_fixed_template_reading"
        )
    assert old["cycle_context"]["bodies"] == new["cycle_context"]["bodies"]
    assert (
        old["cycle_context"]["source_evidence"]
        == new["cycle_context"]["source_evidence"]
    )
    assert cycle_contact_facts(old["cycle_summary"]) == cycle_contact_facts(
        new["cycle_summary"]
    )
    details = new["cycle_context"]["summary_conventions"]
    assert (
        details["reference_contact_ordering"]
        == old["cycle_summary"]["reference_contact_ordering"]
    )
    for key in ("arithmetic_scope", "numerical_scope", "scope"):
        assert details[key] == old["cycle_summary"][key]
    assert new["cycle_context"]["ruleset"]["version"] == "1.6.0"
    assert new["profile_evidence"]["ruleset"]["version"] == "1.39.0"


@pytest.mark.parametrize(
    "label,future",
    [
        ("inserted_UTC_leap_second", True),
        ("unrepresentable_historical_fractional_UTC_adjustment", False),
    ],
)
def test_label_exceptions_are_explicit_and_never_replaced_by_defaults(label, future):
    rich = load("before-files-full.json.gz")["cycle_summary"]
    event = rich["bodies"][0]["contacts"][0]
    event["utc_label_status"] = label
    event["future_leap_seconds_assumed_unchanged"] = future
    event["utc_label"] = None
    compact = compact_cycle_summary(rich)
    assert compact["bodies"][0]["contacts"][0]["utc_label_status"] == label
    assert cycle_contact_facts(rich) == cycle_contact_facts(compact)


def test_real_native_speed_and_segment_disagreement_survives_compaction():
    path = (
        ROOT
        / "docs/validation/human-design-cycle-solar-stations-v1/evidence/public-after-final-output.json.gz"
    )
    rich = json.loads(gzip.decompress(path.read_bytes()))["cycle_summary"]
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
    s = compact_cycle_summary(load("before-files-full.json.gz")["cycle_summary"])
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
    p = converted(load("before-files-full.json.gz"))
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
    p["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in p.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(p)["status"] == "rejected"


def test_unobserved_motion_stays_unknown_instead_of_inheriting_agreement():
    rich = load("before-files-full.json.gz")["cycle_summary"]
    rich["bodies"][0]["contacts"][0]["motion_evidence"] = None
    compact = compact_cycle_summary(rich)
    assert compact["bodies"][0]["contacts"][0]["segment_phase_trend"] is None
    assert cycle_contact_facts(compact)[0]["contacts"][0]["motion_evidence"] is None
    assert cycle_contact_facts(compact) == cycle_contact_facts(rich)


def test_missing_format_cannot_turn_compact_defaults_into_implicit_rich_facts():
    compact = compact_cycle_summary(load("before-files-full.json.gz")["cycle_summary"])
    compact.pop("summary_format")
    with pytest.raises(ValueError, match="format declaration"):
        cycle_contact_facts(compact)


def test_integer_zero_is_not_a_known_false_leap_status():
    rich = load("before-files-full.json.gz")["cycle_summary"]
    rich["bodies"][0]["contacts"][0]["future_leap_seconds_assumed_unchanged"] = 0
    compact = compact_cycle_summary(rich)
    event = compact["bodies"][0]["contacts"][0]
    assert type(event["future_leap_seconds_assumed_unchanged"]) is int
    with pytest.raises(ValueError, match="leap-second status"):
        cycle_contact_facts(compact)
