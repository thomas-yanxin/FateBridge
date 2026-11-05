"""Corrected Yi facts survive REST, native MCP, CLI and strict projection."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.cli import run as cli_run
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)


def assert_same_run_receipt(store, shaped, original):
    """Restore an explicitly deferred runtime before comparing exact receipts."""
    from tests.integration.test_result_delivery import reconstruct

    inline = dict(shaped["run_metadata"])
    evidence = inline.get("calculation_evidence")
    if isinstance(evidence, dict) and "delivery_path" in evidence:
        from fatebridge.utils.json_digest import digest

        path = evidence["delivery_path"]
        assert path == "run_metadata.calculation_evidence"
        assert path in shaped["result_delivery"]["deferred_fields"]
        restored_evidence = reconstruct(
            store, shaped["result_delivery"]["result_id"], path
        )
        assert digest(restored_evidence) == evidence["sha256"]
        assert restored_evidence["coverage"] == evidence["coverage"]
        inline["calculation_evidence"] = restored_evidence
    runtime = inline["runtime"]
    if "delivery_path" in runtime:
        assert runtime["delivery_path"] == "run_metadata.runtime"
        assert runtime["delivery_path"] in shaped["result_delivery"]["deferred_fields"]
        restored = reconstruct(
            store, shaped["result_delivery"]["result_id"], runtime["delivery_path"]
        )
        assert len(restored["ephemeris"]["files"]) == runtime["ephemeris_files_count"]
        assert restored["ephemeris"]["sha256"] == runtime["ephemeris_inventory_sha256"]
        if "environment_sha256" in runtime:
            assert restored["environment_sha256"] == runtime["environment_sha256"]
        inline["runtime"] = restored
    elif "files_delivery_path" in runtime.get("ephemeris", {}):
        # The pinned earlier shared contract deferred just the inventory.
        ephemeris = runtime["ephemeris"]
        path = ephemeris["files_delivery_path"]
        assert path == "run_metadata.runtime.ephemeris.files"
        assert path in shaped["result_delivery"]["deferred_fields"]
        files = reconstruct(store, shaped["result_delivery"]["result_id"], path)
        assert len(files) == ephemeris["files_count"]
        full_ephemeris = {
            k: v
            for k, v in ephemeris.items()
            if k not in ("files_delivery_path", "files_count")
        }
        inline["runtime"] = {**runtime, "ephemeris": {**full_ephemeris, "files": files}}
    assert original["run_metadata"] == inline


@pytest.mark.parametrize(
    "key,payload",
    [
        (
            "sixyao",
            {
                "date": "2026-02-10",
                "time": "12:00:00",
                "zone": "Asia/Shanghai",
                "gua_code": "111010",
                "changed_code": "010111",
                "focus_line": 3,
                "focus_kinship": "兄弟",
                "timing_days": 14,
            },
        ),
        ("gua_lookup", {"query": "111111", "lookup_mode": "hexagram"}),
        (
            "meihua_analysis",
            {
                "analysis_year": 2026,
                "analysis_month": 2,
                "analysis_day": 10,
                "analysis_hour": 12,
                "analysis_timezone": "Asia/Shanghai",
            },
        ),
    ],
)
def test_classical_facts_are_equal_across_three_surfaces(
    key, payload, rest, tmp_path, capsys
):
    spec = SPECS[key]
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    validator = Draft202012Validator(spec.output_model.model_json_schema())
    for output in outputs:
        validator.validate(output)
    if key == "sixyao":
        assert outputs[0]["moving_lines"] == [1, 3, 4, 6]
        assert "changed_branch" not in outputs[0]["lines"][1]
        assert (
            outputs[0]["liuyao_evidence"]["prediction_validation"]["status"]
            == "not_established"
        )
        conditions = outputs[0]["liuyao_evidence"]["conditional_analysis"]
        assert conditions["focus"]["selected"]["position"] == 3
        assert conditions["timing_candidates"]["status"] == "condition_windows_only"
    elif key == "gua_lookup":
        assert outputs[0]["result"]["classical"]["guaci"] == "乾：元亨。利貞。"
    else:
        assert outputs[0]["meihua"]["seed"]["year_branch"] == "巳"


def test_classical_and_calendar_projections_are_supported_on_all_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2026-02-10",
        "time": "12:00:00",
        "gua_code": "111111",
        "focus_line": 3,
        "timing_days": 12,
    }
    fields = [
        "current_hexagram.classical.guaci",
        "classical_text_evidence.moving_yaoci",
        "liuyao_evidence.calendar_conventions.xunkong",
        "liuyao_evidence.source_revisions",
        "liuyao_evidence.prediction_validation",
        "liuyao_evidence.conditional_analysis.focus.selected.branch",
        "liuyao_evidence.conditional_analysis.lines",
        "liuyao_evidence.conditional_analysis.timing_candidates.windows",
    ]
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["current_hexagram"]["classical"] == {"guaci": "乾：元亨。利貞。"}
        assert output["classical_text_evidence"]["moving_yaoci"] == []
        assert (
            output["liuyao_evidence"]["prediction_validation"]["status"]
            == "not_established"
        )
        assert "snapshot_text" not in output
        conditional = output["liuyao_evidence"]["conditional_analysis"]
        assert conditional["focus"] == {"selected": {"branch": "辰"}}
        assert len(conditional["lines"]) == 6
        assert conditional["timing_candidates"]["windows"]


def test_same_run_condition_quotes_cannot_be_replaced_with_outcome_claims(rest):
    response = rest.post(
        SPECS["sixyao"].rest_path,
        json={
            "date": "2000-01-07",
            "time": "12:00:00",
            "gua_code": "111111",
            "focus_line": 3,
        },
        params={"response_char_limit": 0},
    )
    assert response.status_code == 200
    payload = response.json()
    receipt = payload["run_metadata"]

    def claim(path, value):
        return CalculationClaim(
            path=path,
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    path = "liuyao_evidence.conditional_analysis.focus.roles.3.role"
    assert (
        verify_calculation_claims(payload, [claim(path, "元神")])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(payload, [claim(path, "元神已经生效")])["status"]
        == "rejected"
    )
    assert (
        verify_calculation_claims(
            payload,
            [claim("liuyao_evidence.conditional_analysis.predicted_success", True)],
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "--gua-code",
            "111111",
            "--focus-line",
            "6",
            "--focus-kinship",
            "父母",
            "--timing-days",
            "11",
        ],
        ["--method", "coin", "--coins", "6", "7", "8", "9", "7", "8", "--seed", "42"],
        ["--method", "coin", "--seed", "42"],
    ],
)
def test_strict_integer_cli_flags_work_without_a_subject_file(arguments, capsys):
    code = cli_run(
        [
            "sixyao",
            "--date",
            "2000-01-07",
            "--time",
            "12:00:00",
            "--zone",
            "Asia/Shanghai",
            *arguments,
            "--response-char-limit",
            "0",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and "error" not in result
    assert len(result["lines"]) == 6
    if "--focus-line" in arguments:
        conditional = result["liuyao_evidence"]["conditional_analysis"]
        assert conditional["focus"]["selected"]["position"] == 6
        assert conditional["timing_candidates"]["requested_days"] == 11
    else:
        assert result["cast"]["method"] == "coin"
        assert result["cast"]["coin_source"] == (
            "provided" if "--coins" in arguments else "random"
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"gua_code": "111x111"},
        {"coins": [7.5] * 6},
        {"gua_code": "111111", "lines": [{"value": 0}] * 6},
        {"gua_code": "111111", "focus_line": 3, "focus_kinship": "妻财"},
        {"gua_code": "111111", "timing_days": 2},
        {"gua_code": "111111", "focus_line": 3, "timing_days": 61},
        {
            "gua_code": "111111",
            "date": "2026-03-08",
            "time": "02:30:00",
            "zone": "America/New_York",
        },
    ],
)
def test_bad_casts_fail_on_three_surfaces(payload, rest, tmp_path, capsys):
    spec = SPECS["sixyao"]
    payload = {"date": "2026-02-10", "time": "12:00:00", **payload}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code in (400, 422) and code != 0 and protocol.is_error
    assert "current_code" not in local


@pytest.mark.parametrize(
    "focus",
    [
        {
            "gua_code": "100000",
            "changed_code": "100100",
            "focus_kind": "changed",
            "focus_line": 4,
            "focus_kinship": "父母",
        },
        {
            "gua_code": "011111",
            "focus_kind": "hidden",
            "focus_line": 2,
            "focus_kinship": "妻财",
        },
        {"gua_code": "111111", "focus_kind": "day"},
        {"gua_code": "101101", "changed_code": "000000", "focus_kind": "month"},
    ],
)
def test_scan_conditions_and_distinct_focus_locations_survive_strict_projection(
    focus, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-01-07",
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "timing_days": 3,
        **focus,
    }
    fields = [
        "input_normalized.focus_kind",
        "liuyao_evidence.conditional_analysis.focus",
        "liuyao_evidence.conditional_analysis.three_harmony",
        "liuyao_evidence.conditional_analysis.hidden_conditions",
        "liuyao_evidence.conditional_analysis.role_effects",
        "liuyao_evidence.conditional_analysis.classical_scan.source.sha256",
        "liuyao_evidence.conditional_analysis.timing_candidates",
    ]
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert "snapshot_text" not in output
        detail = output["liuyao_evidence"]["conditional_analysis"]
        assert detail["focus"]["selected"]["location"] == focus["focus_kind"]
        assert detail["classical_scan"]["source"] == {
            "sha256": "caac111bc5c5b1c08fd27b3828e7cf6b5430503800f2427d8f2b28809022abaa"
        }
        if focus["focus_kind"] == "hidden":
            assert len(detail["hidden_conditions"][0]["supporting_conditions"]) == 6
        if focus["focus_kind"] in ("hidden", "day", "month"):
            assert detail["timing_candidates"]["windows"] == []


def test_direct_cli_changed_focus_flag_does_not_select_the_base_line(capsys):
    code = cli_run(
        [
            "sixyao",
            "--date",
            "2000-01-07",
            "--time",
            "12:00:00",
            "--gua-code",
            "100000",
            "--changed-code",
            "100100",
            "--focus-kind",
            "changed",
            "--focus-line",
            "4",
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    focus = output["liuyao_evidence"]["conditional_analysis"]["focus"]
    assert (focus["selected"]["location"], focus["selected"]["branch"]) == (
        "changed",
        "午",
    )
    assert focus["roles"][3]["branch"] == "丑" and focus["roles"][3]["role"] != "用神"


def test_published_sixyao_contract_exposes_focus_kind_and_evidence_in_first_view():
    from fatebridge.application.examples import example_input
    from scripts.build_codex_call_contracts import call_contracts

    records = {r["tool"]: r for r in asyncio.run(call_contracts())}
    contract = records["sixyao"]
    kind = contract["input"]["properties"]["focus_kind"]
    assert {"visible", "changed", "hidden", "month", "day"} <= {
        value for option in kind["anyOf"] for value in option.get("enum", [])
    }
    assert "liuyao_evidence" in contract["first_view"]["fields"]
    assert "classical_text_evidence" in contract["first_view"]["fields"]
    assert example_input(SPECS["gua_lookup"]) == {
        "query": "111111",
        "lookup_mode": "hexagram",
    }


def test_large_classical_evidence_is_read_losslessly_from_the_same_run(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from fatebridge.application.examples import suggested_fields
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "private-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-01-07",
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "gua_code": "100000",
        "changed_code": "100100",
        "focus_kind": "changed",
        "focus_line": 4,
        "focus_kinship": "父母",
    }
    fields = suggested_fields(spec)
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "8192"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "8192",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for shaped in [response.json(), local, protocol.structured_content]:
        ref = shaped["result_delivery"]
        original = reconstruct(store, ref["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        assert detail["focus"]["selected"]["branch"] == "午"
        assert detail["focus"]["selected"]["location"] == "changed"
        assert (
            detail["classical_assessment"]["ruleset_id"] == "zengshan_strength_tombs_v5"
        )
        assert len(detail["classical_assessment"]["lines"]) == 6
        assert detail["classical_assessment"].get("focus") is None
        fanfu = original["liuyao_evidence"]["fanfu"]
        same_fanfu = reconstruct(store, ref["result_id"], "liuyao_evidence.fanfu")
        assert same_fanfu == fanfu and fanfu["ruleset_id"] == "zengshan_fanfu_v6"
        same_void = reconstruct(
            store,
            ref["result_id"],
            "liuyao_evidence.conditional_analysis.void_conditions",
        )
        assert same_void == detail["void_conditions"]
        assert same_void["ruleset_id"] == "zengshan_void_effects_v7"
        assert (
            detail["classical_scan"]["source"]["sha256"]
            == "caac111bc5c5b1c08fd27b3828e7cf6b5430503800f2427d8f2b28809022abaa"
        )
        same_focus = reconstruct(
            store,
            ref["result_id"],
            "liuyao_evidence.conditional_analysis.focus.selected",
        )
        assert same_focus == detail["focus"]["selected"]


def test_role_effects_strict_projection_keeps_conditional_routing_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-01-07",
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "gua_code": "011110",
        "changed_code": "011101",
        "focus_line": 4,
    }
    fields = [
        "liuyao_evidence.conditional_analysis.role_effects.ruleset_id",
        "liuyao_evidence.conditional_analysis.role_effects.lines",
        "liuyao_evidence.conditional_analysis.role_effects.chains",
        "liuyao_evidence.conditional_analysis.role_effects.focus_robustness",
        "liuyao_evidence.conditional_analysis.role_effects.textual_issues",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
            "--include-snapshot-text",
            "false",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        roles = output["liuyao_evidence"]["conditional_analysis"]["role_effects"]
        assert roles["ruleset_id"] == "zengshan_role_conditions_v4"
        assert roles["focus_robustness"] == "not_adjudicated"
        assert any(
            c["positions"] == [6, 5, 4]
            and c["status"] == "successive_generation_candidate"
            for c in roles["chains"]
        )
        assert roles["textual_issues"][0]["id"] == "five-versus-three-tombs"


def test_strength_and_tomb_leaves_project_without_unrequested_siblings_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-01-08",
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "gua_code": "011100",
        "focus_line": 3,
        "timing_days": 12,
    }
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        f"{root}.classical_assessment.focus.strength.status",
        f"{root}.classical_assessment.focus.strength.is_supported",
        f"{root}.classical_assessment.focus.tombs",
        f"{root}.classical_assessment.source_sha256",
        f"{root}.role_effects.textual_issues",
        f"{root}.timing_candidates.windows",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        detail = output["liuyao_evidence"]["conditional_analysis"]
        assessment = detail["classical_assessment"]
        assert set(assessment) == {"source_sha256", "focus"}
        assert set(assessment["focus"]) == {"strength", "tombs"}
        assert assessment["focus"]["strength"] == {
            "status": "supported_unopposed",
            "is_supported": True,
        }
        tombs = assessment["focus"]["tombs"]
        assert [(t["location"], t["branch"], t["is_true_tomb"]) for t in tombs] == [
            ("day", "丑", False),
        ]
        assert detail["role_effects"]["textual_issues"][0]["resolution_update"][
            "status"
        ] == ("three_locations_explicitly_defined_in_same_edition")
        assert any(
            w["day_ganzhi"] == "辛未" and "三墓关系逢冲开候选" in w["matched_rules"]
            for w in detail["timing_candidates"]["windows"]
        )
        assert "snapshot_text" not in output


@pytest.mark.parametrize(
    "base,changed,body,relations",
    [
        ("111111", "000000", "反吟", ["其他纳支关系", "其他纳支关系"]),
        ("000011", "000000", None, ["未动", "反吟"]),
        ("011111", "011100", None, ["未动", "伏吟"]),
    ],
)
def test_fanfu_domains_and_body_leaf_survive_strict_projection_on_three_surfaces(
    base, changed, body, relations, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-01-07",
        "time": "12:00:00",
        "gua_code": base,
        "changed_code": changed,
    }
    fields = [
        "liuyao_evidence.fanfu.regions",
        "liuyao_evidence.fanfu.moving_line_relations",
        "liuyao_evidence.fanfu.body_classification",
    ]
    if body:
        fields.append("liuyao_evidence.fanfu.explicit_body_example.kind")
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        fanfu = output["liuyao_evidence"]["fanfu"]
        assert [r["nazhi_relation"] for r in fanfu["regions"]] == relations
        assert [r["position"] for r in fanfu["moving_line_relations"]] == [
            i + 1 for i in range(6) if base[i] != changed[i]
        ]
        if body:
            assert fanfu["explicit_body_example"] == {"kind": body}
        else:
            assert "explicit_body_example" not in fanfu
        assert "source_sha256" not in fanfu and "snapshot_text" not in output


def test_void_conflicts_and_blocked_generator_project_consistently_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = dict(
        date="2000-04-27",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="101011",
        changed_code="101001",
        focus_line=2,
    )
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        f"{root}.void_conditions.focus.classification",
        f"{root}.void_conditions.focus.is_xunkong",
        f"{root}.void_conditions.focus.not_empty_conditions",
        f"{root}.classical_assessment.focus.strength.blocked_supports",
        f"{root}.lines",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        detail = output["liuyao_evidence"]["conditional_analysis"]
        focus = detail["void_conditions"]["focus"]
        assert set(focus) == {"classification", "is_xunkong", "not_empty_conditions"}
        assert (
            focus["classification"] == "conflicting_or_unresolved_conditions"
            and focus["is_xunkong"]
        )
        blocked = detail["classical_assessment"]["focus"]["strength"][
            "blocked_supports"
        ]
        assert [a["position"] for a in blocked] == [5]
        assert detail["lines"][4]["outgoing_obstructions"]


def test_official_2100_extension_and_source_metadata_survive_all_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = dict(
        date="2100-12-31", time="12:00:00", zone="Asia/Shanghai", method="time"
    )
    fields = [
        "calendar_context.lunar_calendar.year",
        "calendar_context.lunar_calendar.month",
        "calendar_context.lunar_calendar.day",
        "calendar_context.lunar_calendar.conversion_source",
        "cast.method",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        lunar = output["calendar_context"]["lunar_calendar"]
        assert (lunar["year"], lunar["month"], lunar["day"]) == (2100, 12, 1)
        assert lunar["conversion_source"]["method_id"] == "hko_2100_month_starts_v1"
        assert output["cast"]["method"] == "time_meihua"
