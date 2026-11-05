"""Reduced clock fractions retain their actual unit, original scope and failures."""

import json
from datetime import timezone
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_cycles import reference_epoch
from fatebridge.core.human_design_reference_clock import reference_datetime
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURE = Path(__file__).parents[1] / "data/human_design/reference_fraction"
PLAN = json.loads((FIXTURE / "plan.json").read_text())
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")
BASIC = dict(
    birth_year=1980,
    birth_month=9,
    birth_day=9,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.mark.parametrize(
    "case,fact",
    list(zip(PLAN["cases"], REFERENCE["cases"], strict=True)),
    ids=[c["id"] for c in PLAN["cases"]],
)
def test_all_original_local_clock_labels_expand_to_independent_utc_and_same_tt(
    case, fact
):
    label, tt = reference_epoch(case["input"])
    canonical, expected_tt = reference_epoch(fact["utc_label"])
    assert label == canonical == case["expected_utc_label"]
    assert tt == expected_tt


def forbidden(*args, **kwargs):
    raise AssertionError("Pure clock parser/replay called a native producer")


def test_independent126labels_parse_without_native_calls(monkeypatch):
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    for c in PLAN["cases"]:
        assert (
            reference_datetime(c["input"]).astimezone(timezone.utc).isoformat()
            == c["expected_utc_label"]
        )
    assert reference_datetime("1980-09-09T12.5").tzinfo is None


@pytest.mark.parametrize(
    "value",
    [
        "1980-09-09T12.0000001Z",
        "1980-09-09T12:30,0000001Z",
        "1980-09-09T12:30:00.0000001Z",
        "1980-09-09T12.5+00:00:00.0000001",
    ],
)
def test_original_six_digit_limit_remains_a_rejection(value):
    with pytest.raises(ValueError, match="最多6位"):
        reference_epoch(value)
    with pytest.raises(ValueError, match="最多6位"):
        reference_datetime(value)


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "text,canonical,birth_minute",
    [
        ("1980-09-09T12.5Z", "1980-09-09T12:30:00+00:00", 15),
        ("1980-09-09T12:15.5Z", "1980-09-09T12:15:30+00:00", 15),
        ("1980-09-09T12.123600Z", "1980-09-09T12:07:24.960000+00:00", 0),
    ],
)
def test_complete_actual_reference_matches_expanded_input_on_both_backends(
    empty, text, canonical, birth_minute, monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "SE_EPHE_PATH",
        str(tmp_path if empty else Path(__file__).resolve().parents[2] / "ephe"),
    )
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    values = []
    for label in [text, canonical]:
        value = execute_tool(
            SPEC,
            SPEC.request_model(
                **{
                    **BASIC,
                    "birth_minute": birth_minute,
                    "cycle_reference_datetime": label,
                }
            ),
        )
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            check["gate_activation_context_status"] == "verified_all_current_contexts"
        )
        assert value["cycle_context"]["reference_utc"] == canonical
        assert value["cycle_context"]["reference_ordering"]["relation"] == "after"
        assert value["cycle_summary"]["sixth_line"]["current_phase"] is None
        assert value["calculation_policy"]["ephemeris_model"] == (
            "moshier" if empty else "swieph"
        )
        value.pop("run_metadata")
        value["clock_evidence"].pop("cycle_reference_datetime")
        values.append(value)
    assert _same_value(*values)


def test_every_original_fact_also_passes_the_python310_complete_form_path(monkeypatch):
    import fatebridge.core.human_design_reference_clock as module
    from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset

    def python310_subset(value):
        if module._REDUCED_FRACTION.fullmatch(value):
            raise ValueError("Python3.10does not accept this reduced representation")
        return datetime_fromisoformat_preserving_offset(value)

    monkeypatch.setattr(
        module, "datetime_fromisoformat_preserving_offset", python310_subset
    )
    for case in PLAN["cases"]:
        assert (
            module.reference_datetime(case["input"])
            .astimezone(timezone.utc)
            .isoformat()
            == case["expected_utc_label"]
        )
    for value in [
        "2020-02-30T12.5Z",
        "2020W542T12.5Z",
        "2020-12-29T24.5Z",
        "2020-12-29T1261.5Z",
    ]:
        with pytest.raises(ValueError):
            module.reference_datetime(value)
