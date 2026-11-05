"""The corrected facts and strict projections agree across REST/native MCP/CLI."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views, example_input
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

PAYLOAD = dict(
    analysis_year=2026,
    analysis_month=4,
    analysis_day=4,
    analysis_hour=21,
    analysis_minute=18,
    analysis_second=37,
    analysis_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    is_diurnal=False,
    guiren_profile="tanyuan_xieji_v1",
)


@pytest.fixture(autouse=True)
def native_solar_control(monkeypatch):
    # This module asserts actual Swiss native flags; keep its model premise
    # explicit as the application's automatic solar policy evolves.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")


def test_source_annotation_disagreement_survives_all_three_transports(
    rest, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    payload = {
        **PAYLOAD,
        "analysis_month": 2,
        "analysis_day": 23,
        "analysis_hour": 18,
    }
    fields = ["liureng.classification", "liureng.four_lessons", "four_pillars"]
    options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *[("fields", field) for field in fields],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for result in bodies:
        assert result["four_pillars"]["day"] == {"stem": "戊", "branch": "辰"}
        board = result["liureng"]
        assert board["four_lessons"][0]["upper_branch"] == "未"
        classification = board["classification"]
        assert classification["labels"] == ["始入"]
        note = classification["source_note"]
        assert note["annotation"] == "重审"
        assert note["original_pdf_page"] == 49
        assert len(note["source_sha256"]) == 64


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_corrected_facts_survive_each_transport_and_field_projection(
    key, project, rest, tmp_path, capsys
):
    payload = {**PAYLOAD, **({"di_fen": "酉"} if key == "jinkou" else {})}
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    fields = (
        [
            "jinkou.rows",
            "jinkou.motions",
            "jinkou.internal_strength",
            "jinkou.qi_evidence",
            "jinkou.patterns",
            "jinkou.use_evidence",
            "jinkou.relations",
            "jinkou.combinations",
            "jinkou.calendar_policy",
            "jinkou.ruleset",
            "jinkou.rule_trace",
            "jinkou.overview.guishen.intrinsic_ganzhi",
            "jinkou.overview.is_diurnal",
            "jinkou.overview.diurnal_evidence",
        ]
        if key == "jinkou"
        else [
            "liureng.three_transmissions",
            "liureng.guiren_order",
            "liureng.classification",
            "liureng.meta",
            "liureng.calendar_policy",
            "liureng.ruleset",
            "liureng.rule_trace",
        ]
    )
    if key == "liureng_runyear":
        fields += ["runyear"]
    spec = SPECS[key]
    params = [("response_char_limit", "0"), ("as_of", "2026-10-12T02:00:00Z")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for result in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        board = result["jinkou" if key == "jinkou" else "liureng"]
        assert board["calendar_policy"]["mode"] == "civil_instant_checked"
        assert board["calendar_policy"]["day_boundary"] == "23:00"
        dependencies = board["calendar_policy"]["solar_term_dependencies"]
        assert len(dependencies) == 5
        for dependency in dependencies:
            assert dependency["solver_time_scale"] == "TT"
            assert dependency["ephemeris_model"] in {"swieph", "moshier", "jpl"}
            assert dependency["ephemeris_retflags"]
            assert dependency["ephemeris_library_version"]
            for flags in dependency["ephemeris_retflags"]:
                assert flags > 0
                expected_model = (
                    "moshier" if flags & 4 else "jpl" if flags & 1 else "swieph"
                )
                assert dependency["ephemeris_model"] == expected_model
            assert (
                dependency["civil_time_method"] == "IERS_UTC_to_TT_swiss_delta_t_to_UT1"
            )
            assert dependency["future_leap_seconds_assumed_unchanged"] is False
            assert dependency["leap_table_expires_at"]
            assert dependency["leap_table_source"]
        assert board["ruleset"]["classical_acceptance_passed"] is False
        assert board["ruleset"]["real_world_efficacy"] == "not_tested"
        if key == "jinkou":
            diurnal = board["overview"]["diurnal_evidence"]
            assert board["overview"]["is_diurnal"] is False
            assert board["patterns"]["catalog_count"] == 64
            evaluations = board["patterns"]["evaluations"]
            assert len(evaluations) == 64
            assert sum(board["patterns"]["evaluation_counts"].values()) == 64
            undecided = next(p for p in evaluations if p["id"] == "P52")
            assert undecided["status"] == "unresolved_definition"
            assert undecided["matched"] is None
            assert any(p["matched"] is False for p in evaluations)
            assert len(board["combinations"]["trines"]) == 4
            assert all(
                trine["transformation_confirmed"] is None
                and trine["du_he"] is None
                and trine["calendar_candidates"] is None
                for trine in board["combinations"]["trines"]
            )
            assert board["patterns"]["evaluated_rule_count"] == 58
            assert len(board["patterns"]["unresolved"]) == 6
            assert board["use_evidence"]["comprehensive_position"] is None
            assert len(board["relations"]["si_jue"]["checks"]) == 5
            assert board["relations"]["si_jue"]["unavailable"][0]["matched"] is None
            assert (
                board["relations"]["transcription_variants"][0]["scan_element"] == "火"
            )
            assert board["qi_evidence"]["source_section"] == "月建旺相 / 月破休囚"
            assert all(
                r["internal_power"] == board["internal_strength"]["powers"][r["label"]]
                for r in board["rows"]
            )
        else:
            diurnal = board["meta"]["diurnal_evidence"]
            assert board["meta"]["guiren_profile"] == "tanyuan_xieji_v1"
        assert diurnal["explicit_choice"] is False
        assert diurnal["is_diurnal"] is False
        assert diurnal["selection_source"] == "explicit_parameter"
        assert diurnal["stellar_visibility_observed"] is None
        assert diurnal["astronomical_boundary_computed"] is False
        if not project:
            assert result["analysis_context"]["input_datetime"].endswith(":37")
            assert "实际交气星历模型" in result["snapshot_text"]
        if project:
            assert "snapshot_text" not in result
    if key == "jinkou" and not project:
        original = bodies[0]
        receipt = original["run_metadata"]
        claim = CalculationClaim(
            path="jinkou.overview.guishen.name",
            value="太阴",
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )
        assert (
            verify_calculation_claims(original, [claim])["status"]
            == "verified_structured_facts"
        )
        false = claim.model_copy(update={"value": "玄武"})
        assert verify_calculation_claims(original, [false])["status"] == "rejected"
        changed = deepcopy(original)
        changed["jinkou"]["overview"]["guishen"]["name"] = "玄武"
        assert verify_calculation_claims(changed, [false])["status"] == "rejected"
        internal = original["jinkou"]["internal_strength"]
        power_claim = CalculationClaim(
            path="jinkou.internal_strength.powers.贵神",
            value=internal["powers"]["贵神"],
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )
        assert (
            verify_calculation_claims(original, [power_claim])["status"]
            == "verified_structured_facts"
        )
        assert (
            verify_calculation_claims(
                original, [power_claim.model_copy(update={"value": "虚构旺衰"})]
            )["status"]
            == "rejected"
        )
        assert "四季旺衰" in original["snapshot_text"]
        assert "课内旺衰" in original["snapshot_text"]
        assert "月建与日辰得气" in original["snapshot_text"]
        assert "六十四课钤结构" in original["snapshot_text"]
        assert "三合与虚一待用" in original["snapshot_text"]
        assert (
            original["jinkou"]["overview"]["diurnal_evidence"]["basis"]
            in original["snapshot_text"]
        )
        assert (
            "三合与虚一待用"
            not in original["snapshot_export"]["unknown_detected_sections"]
        )
        unknown_transformation = CalculationClaim(
            path="jinkou.combinations.trines.0.transformation_confirmed",
            value=None,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )
        assert (
            verify_calculation_claims(original, [unknown_transformation])["status"]
            == "verified_structured_facts"
        )
        assert (
            verify_calculation_claims(
                original, [unknown_transformation.model_copy(update={"value": True})]
            )["status"]
            == "rejected"
        )
        undecided_pattern = CalculationClaim(
            path="jinkou.patterns.evaluations.51.matched",
            value=None,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )
        assert (
            verify_calculation_claims(original, [undecided_pattern])["status"]
            == "verified_structured_facts"
        )
        assert (
            verify_calculation_claims(
                original,
                [undecided_pattern.model_copy(update={"value": False})],
            )["status"]
            == "rejected"
        )


@pytest.mark.parametrize(
    "field,value",
    [("di_fen", "north"), ("guiren_profile", "unknown"), ("analysis_second", 60)],
)
def test_invalid_ground_is_rejected_by_all_three_surfaces(
    rest, tmp_path, capsys, field, value
):
    spec = SPECS["jinkou"]
    payload = {**PAYLOAD, field: value}
    assert rest.post(spec.rest_path, json=payload).status_code == 422
    result = asyncio.run(native(spec, payload))
    assert result.is_error
    code, result = call_cli(spec, payload, tmp_path, capsys)
    assert code != 0


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_published_evidence_view_projects_live_facts(key, rest):
    spec = SPECS[key]
    views = evidence_views(spec)
    assert views and views["core"]["fields"]
    payload = {**PAYLOAD, "is_diurnal": True}
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *[("fields", field) for field in views["core"]["fields"]],
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    assert response.status_code == 200, response.text
    result = response.json()
    if key == "jinkou":
        assert result["jinkou"]["overview"]["guishen"]["start_branch"] == "丑"
        assert result["jinkou"]["overview"]["diurnal_basis"] == "explicit_override"
    else:
        assert result["liureng"]["meta"]["diurnal_basis"] == "explicit_override"


@pytest.mark.parametrize("section", ["六十四课钤结构", "三合与虚一待用"])
def test_pattern_section_export_survives_rest_mcp_and_cli(
    section, rest, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    payload = {**PAYLOAD, "di_fen": "酉", "selected_sections": [section]}
    http = rest.post(spec.rest_path, json=payload, params={"response_char_limit": 0})
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        exported = body["snapshot_export"]
        assert exported["selected_sections"] == [section]
        assert f"[{section}]" in exported["export_text"]
        assert "[起盘信息]" not in exported["export_text"]
        if section == "六十四课钤结构":
            for pattern in body["jinkou"]["patterns"]["matched"]:
                assert pattern["condition"] in exported["export_text"]
        else:
            assert body["jinkou"]["combinations"]["scope"] in exported["export_text"]
            for trine in body["jinkou"]["combinations"]["trines"]:
                if len(trine["present_branches"]) >= 2:
                    assert trine["basis"] in exported["export_text"]


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
def test_generated_call_contract_alone_can_drive_real_mcp(key):
    spec = SPECS[key]
    file = Path(__file__).resolve().parents[2] / "docs/contracts" / (key + ".json")
    contract = json.loads(file.read_text())
    params = {**example_input(spec), **contract["first_view"]}
    Draft202012Validator(contract["input"]).validate(params)
    result = asyncio.run(native(spec, params))
    assert not result.is_error
    body = result.structured_content
    assert body["run_metadata"]["tool_name"] == key
    assert (
        body["jinkou" if key == "jinkou" else "liureng"]["ruleset"][
            "classical_conformance"
        ]
        == "partial_excerpt"
    )
