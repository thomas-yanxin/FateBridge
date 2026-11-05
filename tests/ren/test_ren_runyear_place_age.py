"""Actual birthplace clocks and timezone-invariant lunar-year age wiring."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_fault,
)
from tests.support.transports import SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "runyear_place_age", ROOT / "scripts/ren/audit_ren_runyear_place_age.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
CASES = REFERENCE["cases"]


def test_entire_precommitted_cohort_keeps_all_failed_input_probes():
    report = AUDIT.audit()
    assert (
        report["expected_count"]
        == report["compared_count"]
        == report["matched_count"]
        == 28
    )
    assert not report["calculation_errors"]
    assert report["selected_place_age_checks_passed"]
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["classical_acceptance_passed"]
    assert not report["free_text_semantic_acceptance_passed"]
    assert not report["goal_complete"]


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_source_inventory_changes_do_not_create_a_pass(tmp_path, change):
    corpus = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "reference.json"
    if change == "edit":
        d = json.loads(p.read_text())
        d["cases"][18]["expected"]["age"] = 0
        p.write_text(json.dumps(d))
    elif change == "missing":
        p.unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen runyear place/age"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("project", [False, True])
def test_place_inference_errors_and_age_clock_survive_all_three_transports(
    case, project, surface_calls
):
    spec = SPECS["liureng_runyear"]
    fields = ["runyear", "liureng.calendar_policy.civil_instant_utc"]
    params, flags, options = (
        [("response_char_limit", "0")],
        ["--response-char-limit", "0"],
        {},
    )
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, case["input"], params=params, options=options, flags=flags
    )
    bodies = [http.json(), cli, protocol.structured_content]
    expected = case["expected"]
    if "error" in expected:
        assert http.status_code == 400 and code == 1 and protocol.is_error
        for body in bodies:
            assert expected["error"] in body["error"]
            assert "runyear" not in body
        return
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        run = body["runyear"]
        clock = run["birth_civil_clock"]
        age = run["age_calendar"]
        assert clock["timezone"] == expected["timezone"]
        assert clock["instant_utc"] == expected["birth_instant_utc"]
        assert clock["timezone_source"] == expected["timezone_source"]
        assert clock["timezone_assumed"] is expected.get("assumed", False)
        assert run["age"] == expected["age"] and run["ganzhi"] == expected["ganzhi"]
        assert age["timezone"] == clock["timezone"]
        assert age["analysis_lunar_year"] - age["birth_lunar_year"] + 1 == run["age"]
        if "analysis_in_age_zone" in expected:
            assert age["analysis_civil_datetime"] == expected["analysis_in_age_zone"]
        if not project:
            assert f"虚岁参考时区：{clock['timezone']}" in body["snapshot_text"]
            assert (
                "出生时区来源：" + expected["timezone_source"] in body["snapshot_text"]
            )
            if expected.get("assumed"):
                assert "未核实实际出生时区" in body["snapshot_text"]


def test_same_physical_analysis_instant_has_same_age_in_two_display_zones():
    utc, tokyo = [AUDIT.calculate(CASES[i]["input"]) for i in (19, 20)]
    assert (
        utc["liureng"]["calendar_policy"]["civil_instant_utc"]
        == tokyo["liureng"]["calendar_policy"]["civil_instant_utc"]
    )
    # Age uses one birth civil zone. Year-fate placements still belong to each
    # analysis board, whose day/hour can differ across display zones.
    for key in (
        "age",
        "ganzhi",
        "birth_lunar_year",
        "birth_civil_clock",
        "age_calendar",
    ):
        assert utc["runyear"][key] == tokyo["runyear"][key]
    assert utc["runyear"]["age"] == 1


def test_age_changes_once_at_birth_zone_lunar_new_year_midnight():
    after, before = [AUDIT.calculate(CASES[i]["input"]) for i in (21, 22)]
    assert before["runyear"]["age"] == 1 and after["runyear"]["age"] == 2
    assert (
        before["runyear"]["ganzhi"] == "丙寅" and after["runyear"]["ganzhi"] == "丁卯"
    )
    assert before["runyear"]["age_calendar"]["analysis_civil_datetime"].startswith(
        "2024-02-09T23:59:59"
    )
    assert after["runyear"]["age_calendar"]["analysis_civil_datetime"].startswith(
        "2024-02-10T00:00:00"
    )


def test_birth_zone_correction_does_not_rebase_analysis_board_or_solar_clock():
    data = CASES[1]["input"]
    ny = AUDIT.calculate(data)
    tokyo = AUDIT.calculate({**data, "birth_timezone": "Asia/Tokyo"})
    assert ny["liureng"] == tokyo["liureng"]
    assert ny["four_pillars"] == tokyo["four_pillars"]
    assert (
        ny["runyear"]["birth_civil_clock"]["instant_utc"]
        != tokyo["runyear"]["birth_civil_clock"]["instant_utc"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"runyear": {"birth_civil_clock": {"timezone_assumed": 0}}},
        {"runyear": {"age_calendar": {"analysis_lunar_year": "2024"}}},
        {"runyear": {"age_calendar": {"policy": "universal_classical_certification"}}},
    ],
)
def test_false_clock_claims_cannot_hide_behind_projection(
    bad, rest, monkeypatch, tmp_path, capsys
):
    reject_fault("liureng_runyear", bad, rest, monkeypatch, tmp_path, capsys)
