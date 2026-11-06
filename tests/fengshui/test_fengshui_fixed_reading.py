"""Fixed prose must retain countervailing facts, frames and complete coverage."""

import asyncio
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application import result_delivery as delivery
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.support.fengshui_transports import mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client


def inputs(current=8, angle=0, forms=None, half=None):
    interpretation = {
        "include_calculation_reading": True,
        "timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1",
        "fixed_lingzheng": {},
        "external_forms": forms or [],
    }
    if current is not None:
        interpretation.update(
            current_period_number=current, period_evidence="独立评价运"
        )
    if half:
        interpretation["fixed_lingzheng"].update(
            five_period_half=half, half_evidence="明确五运分段"
        )
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 2,
            "evidence": "独立历史宅运",
        },
        "city_gate": {
            "reference_period_number": 9,
            "period_evidence": "独立城门参考运",
        },
        "interpretation": interpretation,
    }


def executed(req=None, tool="xuankong_natal"):
    spec = next(s for s in CATALOG if s.key == "fengshui_" + tool)
    return execute_tool(spec, spec.request_model.model_validate(req or inputs()))


def trusted(payload):
    return {"trusted_payload": deepcopy(payload)}


def test_reading_defaults_on_with_selected_interpretation_and_can_be_disabled():
    req = inputs()
    plain = deepcopy(req)
    plain["interpretation"]["include_calculation_reading"] = False
    old = calculate_xuankong_natal(**plain)
    new = calculate_xuankong_natal(**req)
    assert "calculation_reading" not in old
    default = deepcopy(req)
    default["interpretation"].pop("include_calculation_reading")
    assert (
        calculate_xuankong_natal(**default)["calculation_reading"]
        == new["calculation_reading"]
    )
    raw = deepcopy(req)
    raw.pop("interpretation")
    assert "calculation_reading" not in calculate_xuankong_natal(**raw)
    assert {k: v for k, v in new.items() if k != "calculation_reading"} == old
    reading = new["calculation_reading"]
    assert reading["status"] == "rendered"
    assert {s["kind"] for s in reading["statements"]} >= {
        "sources",
        "natal_context",
        "evaluation_context",
        "natal_palace",
        "fixed_context",
        "fixed_form",
        "city_gate",
        "author_scope",
    }
    assert len([s for s in reading["statements"] if s["kind"] == "natal_palace"]) == 9
    assert len([s for s in reading["statements"] if s["kind"] == "city_gate"]) == 2
    assert "历史宅运为2运" in reading["text"] and "当前评价运为8运" in reading["text"]
    assert "城门独立参考运为9运" in reading["text"]
    assert "不由生克直接断吉凶" in reading["text"]
    assert "不证明完整纳气、现实效果或开门许可" in reading["text"]
    for statement in reading["statements"]:
        assert all(path in reading["basis"] for path in statement["basis_paths"])
    # A whole candidate, not a naked condition_match=True, is quoted.
    assert all(
        "palaces" in value and "candidate_only" in value
        for path, value in reading["basis"].items()
        if path.startswith("layers.xuankong_natal.interpretation.candidates.")
        and path.count(".") == 4
    )


def test_unknown_period_fifth_halves_and_bearing_candidates_are_retained():
    unknown = calculate_xuankong_natal(**inputs(None))["calculation_reading"]
    assert "当前评价运为未确认" in unknown["text"]
    assert "互用数字未确定" in unknown["text"]
    assert "互用数字为[]" not in unknown["text"]
    five = calculate_xuankong_natal(**inputs(5))["calculation_reading"]
    fixed = [s for s in five["statements"] if s["kind"] == "fixed_form"]
    assert len(fixed) == 4
    assert all("分段未确认的候选" in s["text"] for s in fixed)
    assert any("五运前十年" in s["text"] for s in fixed) and any(
        "五运后十年" in s["text"] for s in fixed
    )
    req = inputs(angle=7.5)
    result = calculate_xuankong_natal(**req)
    original = result["layers"]["xuankong_natal"]["candidates"]
    assert len(original) > 1
    assert len(
        [
            s
            for s in result["calculation_reading"]["statements"]
            if s["kind"] == "natal_distribution"
        ]
    ) == len(original)
    assert "宅盘待确认候选" in result["calculation_reading"]["text"]


def test_missing_historical_period_does_not_hide_independent_fixed_ground_facts():
    result = calculate_xuankong_natal(
        interpretation={
            "current_period_number": 8,
            "period_evidence": "仅独立确认评价八运",
            "fixed_lingzheng": {},
        }
    )
    reading = result["calculation_reading"]
    assert reading["status"] == "rendered"
    assert "历史宅运为未确认" in reading["text"]
    assert "固定零正参考评价运为8运" in reading["text"]
    assert len([s for s in reading["statements"] if s["kind"] == "fixed_form"]) == 2
    assert not [s for s in reading["statements"] if s["kind"] == "natal_palace"]


@pytest.mark.parametrize(
    "observed,basis",
    [(True, "measured"), (False, "user_confirmed"), (True, "image_observed")],
)
def test_positive_negative_and_photo_facts_are_explained_without_full_verdict(
    observed, basis
):
    req = inputs(
        8,
        forms=[
            dict(
                direction="W",
                mountain_present=observed,
                water_present=observed,
                observation_basis=basis,
                evidence="现场事实单独记录",
            )
        ],
    )
    result = calculate_xuankong_natal(**req)
    text = next(
        s["text"]
        for s in result["calculation_reading"]["statements"]
        if s["kind"] == "natal_palace" and s["target_path"].endswith(".palaces.W")
    )
    assert "观察记录为" + ("存在" if observed else "不存在") in text
    if basis == "image_observed":
        assert "仅为候选，不能当作已确认" in text
    elif observed:
        assert "指定存在条件满足，未评价完整形势质量" in text
    else:
        assert "指定存在条件未满足，不等于整体不利" in text


def test_noncurrent_and_unsupported_placement_meanings_and_counterfacts_survive():
    req = inputs(7)
    params = {
        "methods": ["xuankong_natal"],
        "xuankong": req,
        "placements": [
            {"object_id": "desk", "purpose": "desk", "location_direction": "N"},
            {"object_id": "bed", "purpose": "bed", "location_direction": "SW"},
        ],
    }
    result = executed(params, "assess")
    reading = result["calculation_reading"]
    assert "本有限床门规则不覆盖该用途" in reading["text"]
    assert "不在本条存在规则覆盖内，不据此判凶" in reading["text"]
    assert "非当令（不等于凶）" in reading["text"]
    assert (
        verify_fengshui_reading(result, **trusted(result))["status"]
        == "verified_served_fixed_reading"
    )


def test_verifier_requires_complete_original_payload_and_independent_trusted_receipt():
    result = executed()
    anchor = trusted(result)
    assert (
        verify_fengshui_reading(result, **anchor)["status"]
        == "verified_served_fixed_reading"
    )
    changed = deepcopy(result)
    changed["calculation_reading"]["text"] += "必定旺财，成功率100%"
    assert verify_fengshui_reading(changed, **anchor)["status"] == "rejected"
    projected = {
        "calculation_reading": result["calculation_reading"],
        "run_metadata": result["run_metadata"],
    }
    assert verify_fengshui_reading(projected, **anchor)["status"] == "rejected"
    other = executed()
    assert verify_fengshui_reading(other, **anchor)["status"] == "rejected"


@pytest.mark.parametrize(
    "mutation",
    [
        "prose",
        "narrow_quote",
        "omit_negative_gate",
        "omit_source_dispute",
        "choose_half",
        "invent_prediction",
        "swap_period",
        "omit_layer_scope",
        "wrong_target",
    ],
)
def test_even_a_trusted_malformed_reading_cannot_pass_template_or_coverage_checks(
    mutation,
):
    req = inputs(5)
    req["city_gate"]["reference_period_number"] = 8
    params = {
        "methods": ["xuankong_natal", "annual_stars"],
        "effective_year": 2026,
        "xuankong": req,
    }
    result = executed(params, "assess")
    reading = result["calculation_reading"]
    if mutation == "prose":
        reading["text"] += "所有非当令星皆凶"
    elif mutation == "narrow_quote":
        reading["basis"] = {"condition_match": True}
    elif mutation == "omit_negative_gate":
        assert (
            result["layers"]["xuankong_natal"]["city_gate_analysis"]["candidates"][0][
                "gates"
            ][1]["reference_star_reaches_gate_by_reverse_flight"]
            is False
        )
        reading["statements"] = [
            s
            for s in reading["statements"]
            if not (s["kind"] == "city_gate" and s["target_path"].endswith(".gates.1"))
        ]
    elif mutation == "omit_source_dispute":
        reading["statements"] = [
            s for s in reading["statements"] if s["kind"] != "author_scope"
        ]
    elif mutation == "choose_half":
        reading["statements"] = [
            s for s in reading["statements"] if "五运后十年" not in s["text"]
        ]
    elif mutation == "invent_prediction":
        reading["real_world_prediction_established"] = True
    elif mutation == "swap_period":
        reading["text"] = reading["text"].replace("历史宅运为2运", "历史宅运为5运")
    elif mutation == "wrong_target":
        next(s for s in reading["statements"] if s["kind"] == "natal_palace")[
            "target_path"
        ] = "layers.xuankong_natal.interpretation.candidates.0.palaces.NE"
    else:
        reading["uncovered_layers"] = []
    # This test supplies a synthetic trusted receipt for the wrong response to
    # check semantic/coverage rejection separately from the outer hash guard.
    report = verify_fengshui_reading(result, **trusted(result))
    assert report["status"] == "rejected"
    assert {e["code"] for e in report["errors"]} == {
        "fixed_text_context_or_coverage_mismatch"
    }
    assert (
        report["free_model_prose_verified"] is False
        and report["authority_certified"] is False
    )


def test_future_unknown_rule_version_fails_closed_without_losing_calculation():
    result = calculate_xuankong_natal(**inputs())
    result["rulesets"][0]["version"] = "99.0.0"
    reading = build_natal_reading(result)
    assert reading["status"] == "unsupported_context" and not reading["statements"]
    assert result["layers"]["xuankong_natal"]["chart"]["palaces"]


def test_candidate_raw_negative_and_unknown_applicability_are_both_explained():
    req = inputs(5)
    req["interpretation"]["fixed_lingzheng"]["observations"] = [
        dict(
            direction="SW",
            high_solid_terrain_present=False,
            observation_basis="measured",
            evidence="明确高实不存在，不推导低洼或河流",
        )
    ]
    reading = calculate_xuankong_natal(**req)["calculation_reading"]
    text = next(
        s["text"]
        for s in reading["statements"]
        if s["kind"] == "fixed_form"
        and s["target_path"].endswith(".candidates.0.palaces.SW")
    )
    assert "分段未确认的候选" in text and "高实不存在" in text
    assert "本候选存在条件运算不符合" in text


def test_branch_and_registered_source_version_must_agree():
    result = calculate_xuankong_natal(**inputs())
    result["layers"]["xuankong_natal"]["interpretation"]["fixed_lingzheng_analysis"][
        "ruleset"
    ]["version"] = "99.0.0"
    assert build_natal_reading(result)["status"] == "unsupported_context"


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_reading_and_verification_match_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, tool
):
    req = inputs(5)
    if tool == "assess":
        req = {"methods": ["xuankong_natal"], "xuankong": req}
    spec = next(s for s in CATALOG if s.key == "fengshui_" + tool)
    http = rest_client(monkeypatch).post(spec.rest_path, json=req)
    assert http.status_code == 200, http.text
    protocol = asyncio.run(mcp_call(tool, req))
    assert not protocol.is_error
    p = tmp_path / "reading.json"
    p.write_text(json.dumps(req))
    assert run(["fengshui_" + tool, "--request-file", str(p)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    for response in (http.json(), protocol.structured_content, cli):
        Draft202012Validator(spec.output_model.model_json_schema()).validate(response)
        assert (
            verify_fengshui_reading(response, **trusted(response))["status"]
            == "verified_served_fixed_reading"
        )


def test_bounded_same_run_full_readback_can_be_verified_without_recalculation(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        delivery, "RESULT_STORE", delivery.ResultStore(tmp_path / "results")
    )

    async def check():
        from fastmcp import Client

        from fatebridge.mcp_server import create_mcp_app

        async with Client(create_mcp_app(families="fengshui")) as client:
            result = await client.call_tool(
                "fengshui_assess",
                {
                    "methods": ["xuankong_natal"],
                    "xuankong": inputs(5),
                    "response_char_limit": 4096,
                },
            )
            assert not result.is_error and len(result.content[0].text) <= 4096
            shaped = result.structured_content
            ref = shaped["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            uri = ref["first_page_uri"]
            raw = ""
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                raw += page["text"]
                uri = page["next_uri"]
            full = json.loads(raw)
            anchor = {"trusted_payload": deepcopy(full)}
            assert (
                verify_fengshui_reading(full, **anchor)["status"]
                == "verified_served_fixed_reading"
            )
            assert full["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]

    asyncio.run(check())


def test_separately_saved_receipt_and_audit_command_detect_changes(tmp_path):
    result = executed()
    payload = tmp_path / "payload.json"
    receipt = tmp_path / "receipt.json"
    payload.write_text(json.dumps(result))
    receipt.write_text(json.dumps(result))
    script = Path(__file__).parents[2] / "scripts/fengshui/audit_fengshui_reading.py"
    command = [
        sys.executable,
        str(script),
        "--payload",
        str(payload),
        "--trusted-payload",
        str(receipt),
    ]
    valid = subprocess.run(command, capture_output=True, text=True)
    assert (
        valid.returncode == 0
        and json.loads(valid.stdout)["status"] == "verified_served_fixed_reading"
    )
    result["run_metadata"]["engine_is_approximate"] = not result["run_metadata"][
        "engine_is_approximate"
    ]
    payload.write_text(json.dumps(result))
    invalid = subprocess.run(command, capture_output=True, text=True)
    assert invalid.returncode == 1
    assert any(
        e["code"] == "trusted_original_receipt_mismatch"
        for e in json.loads(invalid.stdout)["errors"]
    )


@pytest.mark.parametrize(
    "current,angle,phrase",
    [
        (8, 7.5, "宅盘仍为候选"),
        (5, 0, "仅本分段候选下的比较"),
        (5, 7.5, "宅盘与分段均为候选"),
    ],
)
def test_fixed_comparison_explains_the_actual_source_of_candidacy(
    current, angle, phrase
):
    reading = calculate_xuankong_natal(**inputs(current, angle))["calculation_reading"]
    assert reading["status"] == "rendered"
    statements = [s for s in reading["statements"] if s["kind"] == "fixed_form"]
    assert statements and all(phrase in s["text"] for s in statements)
    assert all(
        any(p.endswith(".flying_star_comparison_status") for p in s["basis_paths"])
        for s in statements
    )
