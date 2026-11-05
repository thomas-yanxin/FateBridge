"""Multiple cycle contacts, source failures, independent facts and replay guards."""

import ast
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.human_design import chart_at_tt
from fatebridge.core.human_design_cycles import calculate_cycle_context, cycle_summary
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_cycle_reference import independent_cycle_checks
from tests.ephemeris_case_runtime import native_ephemeris_files
from tests.ephemeris_context import moshier_ephemeris

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1980,
    birth_month=1,
    birth_day=1,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
)


def test_station_refinement_recovers_two_contacts_hidden_inside_one_grid_cell(
    monkeypatch,
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 10.0)

    def read(t):
        if t < 8:
            phase, speed = 359.91 * t / 8, 359.91 / 8
        else:
            phase, speed = 360.01 - 0.1 * (t - 9) ** 2, -0.2 * (t - 9)
        return [t, (20 + phase) % 360, speed, 258]

    result = cycles.derive_body_contacts("Saturn", 0.0, read)
    assert result["status"] == "sampled_search_completed"
    assert result["observed_station_count"] == 1
    assert [r["motion"] for r in result["contacts"]] == ["direct", "retrograde"]
    assert [r["jd_tt"] for r in result["contacts"]] == pytest.approx(
        [9 - math.sqrt(0.1), 9 + math.sqrt(0.1)], abs=2e-9
    )
    # Both original endpoints are below the target. A sign-only coarse scan
    # would return no contact; day-based deduplication would lose the second.
    assert read(8)[1] < 20 and read(10)[1] < 20


def test_natal_revisit_before_a_completed_revolution_is_not_a_return(monkeypatch):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 10.0)
    result = cycles.derive_body_contacts(
        "Saturn", 0.0, lambda t: [t, (100 + math.sin(t)) % 360, math.cos(t), 258]
    )
    assert result["contacts"] == []


@pytest.mark.parametrize(
    "value",
    [
        "2029-07-01",
        "2029-07-01T00:00:00",
        "not-a-date",
        "2029-02-30T00:00:00Z",
        "1700-01-01T00:00:00Z",
        "1960-01-01T00:00:00Z",
    ],
)
def test_reference_requires_a_valid_aware_post_birth_instant(value):
    with pytest.raises(ValueError):
        SPEC.request_model(**INPUT, cycle_reference_datetime=value)


def test_equivalent_offsets_mean_the_same_reference_epoch():
    assert cycles.reference_epoch(
        "2029-07-01T08:00:00+08:00"
    ) == cycles.reference_epoch("2029-07-01T00:00:00Z")


def test_omission_never_reads_now_or_runs_the_cycle_sampler(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("optional cycles should not run")

    monkeypatch.setattr(cycles, "derive_body_contacts", forbidden)
    result = calculate_human_design(**INPUT)
    assert result["cycle_context"] == {"status": "not_requested"}
    assert result["cycle_summary"]["sixth_line"]["current_phase"] is None


def test_empty_installation_preserves_planets_and_reports_missing_chiron():
    with moshier_ephemeris():
        result = calculate_human_design(
            **INPUT, cycle_reference_datetime="2029-07-01T00:00:00Z"
        )
        rows = result["cycle_context"]["bodies"]
        assert result["cycle_context"]["status"] == "partial"
        assert [len(r["contacts"]) for r in rows] == [1, 3, 0]
        assert rows[2]["status"] == "unavailable"
        assert rows[2]["failure"]["reason"] == "native_ephemeris_unavailable"
        assert rows[2]["natal_longitude"] is None
        assert all(r["native_return_flag_model"] == "moshier" for r in rows[:2])


def test_three_real_retrograde_contacts_and_reference_relation_keep_natal_unchanged(
    native_ephemeris_files,
):
    chart = chart_at_tt(2444239.5)
    saved = copy.deepcopy(chart)
    context = calculate_cycle_context(
        chart, "2029-07-01T00:00:00Z", require_swiss_files=False
    )
    assert chart == saved
    assert [len(r["contacts"]) for r in context["bodies"]] == [1, 3, 3]
    chiron = context["bodies"][2]
    assert chiron["body_orbit_source"] == "swiss_main_asteroid_file"
    assert [r["motion"] for r in chiron["contacts"]] == [
        "direct",
        "retrograde",
        "direct",
    ]
    summary = cycle_summary(context, "6/3")
    assert summary["bodies"][2]["reference_relation"] == "between_observed_contacts"
    assert summary["sixth_line"]["applicable"] is True
    assert summary["sixth_line"]["current_phase"] is None
    assert all(r["future_leap_seconds_assumed_unchanged"] for r in chiron["contacts"])
    assert all(
        abs(r["residual_degrees"]) <= 1e-7 and r["bracket_width_seconds"] <= 0.0002
        for row in context["bodies"]
        for r in row["contacts"]
    )


@pytest.mark.parametrize(
    "failure", ["native_ephemeris_unavailable", "native_model_changed_within_search"]
)
def test_interrupted_search_keeps_observed_contacts_but_does_not_claim_completion(
    monkeypatch, failure
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 30.0)

    def read(t):
        if t > 25:
            if failure == "native_ephemeris_unavailable":
                raise cycles.CycleUnavailable(failure, t)
            return [t, (15 * t) % 360, 15.0, 260]
        return [t, (15 * t) % 360, 15.0, 258]

    result = cycles.derive_body_contacts("Saturn", 0.0, read)
    assert result["status"] == "partial" and len(result["contacts"]) == 1
    assert result["failure"]["reason"] == failure


@pytest.fixture(scope="module")
def complete_run():
    return execute_tool(
        SPEC,
        SPEC.request_model(**INPUT, cycle_reference_datetime="2029-07-01T00:00:00Z"),
    )


def test_full_cycle_trace_replays_every_consumed_native_position(complete_run):
    report = verify_human_design_reading(complete_run)
    assert report["status"] == "verified_fixed_template_reading"
    assert report["checked_cycle_evaluation_count"] > 35000


def test_large_cycle_result_pages_reconstruct_the_same_run_without_recalculation(
    complete_run, tmp_path, monkeypatch
):
    from fatebridge.application import result_delivery as delivery

    store = delivery.ResultStore(tmp_path / "private-cycles")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    bounded = delivery.bound_response(complete_run, 8192)
    reference = bounded["result_delivery"]

    def forbidden(*args, **kwargs):
        raise AssertionError("pages must not calculate positions again")

    monkeypatch.setattr(cycles, "_native_reader", forbidden)
    parts, offset = [], 0
    while True:
        page = store.page(reference["result_id"], offset)
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    text = "".join(parts)
    assert hashlib.sha256(text.encode()).hexdigest() == page["sha256"]
    reconstructed = json.loads(text)
    assert reconstructed == complete_run
    assert (
        reconstructed["run_metadata"]["run_id"]
        == complete_run["run_metadata"]["run_id"]
    )
    assert (
        verify_human_design_reading(reconstructed)["status"]
        == "verified_fixed_template_reading"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "contact",
        "motion",
        "missing_witness",
        "duplicate_witness",
        "flags",
        "longitude",
        "body_set",
        "origin",
        "reference",
        "completeness",
        "phase",
        "source",
    ],
)
def test_rehashing_cannot_hide_forged_cycle_search_or_age_assignment(complete_run, bad):
    run = copy.deepcopy(complete_run)
    context, summary = run["cycle_context"], run["cycle_summary"]
    first = context["bodies"][0]
    if bad == "contact":
        context["bodies"][1]["contacts"].pop()
    elif bad == "motion":
        first["contacts"][0]["motion"] = "retrograde"
    elif bad == "missing_witness":
        first["evaluation_witnesses"].pop(4)
    elif bad == "duplicate_witness":
        first["evaluation_witnesses"].append(first["evaluation_witnesses"][0])
    elif bad == "flags":
        first["evaluation_witnesses"][1][3] |= 2048
    elif bad == "longitude":
        first["natal_longitude"] += 1
    elif bad == "body_set":
        context["bodies"].pop()
    elif bad == "origin":
        context["origin"] = "design"
    elif bad == "reference":
        context["reference_jd_tt"] += 1
    elif bad == "completeness":
        context["continuous_completeness_certified"] = True
    elif bad == "source":
        context["ruleset"]["source_catalog_sha256"] = "0" * 64
    else:
        summary["sixth_line"]["current_phase"] = "after_50th_birthday"
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(run)["status"] == "rejected"


def test_independent_plan_sources_and_generator_do_not_import_the_engine():
    plan = json.loads(
        (ROOT / "tests/fixtures/human-design-cycles-plan.json").read_text()
    )
    source = ROOT / "scripts/gen_human_design_cycles_reference.py"
    ref = json.loads(
        (ROOT / "tests/fixtures/human-design-cycles-reference.json").read_text()
    )
    assert plan["same_epoch_tolerance_arcseconds"] == 2
    assert plan["root_angular_residual_tolerance_arcseconds"] == 4
    assert plan["event_time_difference_seconds_acceptance"] is None
    assert hashlib.sha256(source.read_bytes()).hexdigest() == ref["generator_sha256"]
    imports = [
        n.module or ""
        for n in ast.walk(ast.parse(source.read_text()))
        if isinstance(n, ast.ImportFrom)
    ]
    assert all(not n.startswith(("fatebridge", "swisseph", "tests")) for n in imports)
    assert sum(len(r["contacts"]) for r in ref["records"]) == 25


def test_independent_reference_retains_fixed_angular_tolerances_and_all_outcomes(
    native_ephemeris_files,
):
    report = independent_cycle_checks(ROOT)
    assert report["cases_checked"] == 9
    assert report["bounded_acceptance_passed"] == all(
        r["bounded_case_passed"] for r in report["rows"]
    )
    assert report["timing_accuracy_certified"] is False
    assert report["continuous_completeness_certified"] is False
    assert all(
        r["contact_count_matches"] and r["motion_sequence_matches"]
        for r in report["rows"]
    )


def test_chiron_spk_adapter_is_checked_against_six_frozen_horizons_positions():
    fixture = json.loads(
        (ROOT / "tests/fixtures/human-design-cycles-horizons.json").read_text()
    )
    assert (
        fixture["reference_sha256"]
        == hashlib.sha256(
            (ROOT / "tests/fixtures/human-design-cycles-reference.json").read_bytes()
        ).hexdigest()
    )
    assert (
        fixture["generator_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts/check_human_design_cycle_horizons.py").read_bytes()
        ).hexdigest()
    )
    assert (
        hashlib.sha256(fixture["raw_response_utf8"].encode()).hexdigest()
        == fixture["raw_response_sha256"]
    )
    assert len(fixture["rows"]) == 6
    assert all(row["error_arcseconds"] <= 2 for row in fixture["rows"])
