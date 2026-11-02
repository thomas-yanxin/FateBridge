"""Independent annotated charts, exact palaces and same-run public delivery."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_conditions import five_general_conditions
from fatebridge.core.metaphysics.taiyi_eye_relations import (
    GENERAL_FIELDS,
    PROFILE,
    eye_general_relations,
)
from fatebridge.core.metaphysics.taiyi_year import cyclic_core, structural_patterns
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_eye_relations import CORPUS, audit, pair_key
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload


def test_full_frozen_selected_corpus_keeps_numerical_and_pair_denominators():
    report = audit()
    assert report["selected_cyclic_charts"] == 8
    assert report["required_numeric_observations"] == 88
    assert report["matching_numeric_observations"] == 88
    assert report["required_stated_relations"] == 12
    assert report["matching_stated_relations"] == 12
    assert report["selected_numerical_and_pair_conformance_passed"] is True
    assert report["whole_72_ju_annotation_acceptance_passed"] is False
    assert report["whole_classic_acceptance_passed"] is False
    assert report["historical_calendar_reconstructed"] is False
    assert all(not r["annotation_absence_is_negative"] for r in report["rows"])


@pytest.mark.parametrize("eye,name", [("wenchang_palace", "关"), ("shiji", "掩")])
def test_all_four_generals_all_sixteen_positions_without_gate_sector_merging(eye, name):
    # Independent, literal physical mapping. No production PALACES or sector map.
    bearings = {1: "乾", 2: "午", 3: "艮", 4: "卯", 6: "酉", 7: "坤", 8: "子", 9: "巽"}
    spirits = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
    for general, label in GENERAL_FIELDS.items():
        for number in [*bearings, 5]:
            for position in spirits:
                core = {
                    **cyclic_core(13),
                    **dict.fromkeys(GENERAL_FIELDS, 5),
                    general: number,
                    "wenchang_palace": "亥",
                    "shiji": "丑",
                    eye: position,
                }
                found = eye_general_relations(core)
                wanted = (
                    {("关", label, "文昌")} if name == "关" else {("掩", "始击", label)}
                )
                assert {pair_key(p) for p in found} == (
                    wanted if bearings.get(number) == position else set()
                )
                for p in found:
                    board = {
                        "core_board": core,
                        "wenchang_palace": core["wenchang_palace"],
                    }
                    for fact in p["basis"]:
                        assert resolve(board, fact["field"]) == fact["value"]
                    assert p["relation_profile"] == PROFILE
                    assert "版本范围不同" in p["scope"]


def test_eyes_and_same_camp_generals_do_not_gain_unadjudicated_relations():
    core = {
        **cyclic_core(1),
        **dict.fromkeys(GENERAL_FIELDS, 5),
        "shiji": "丑",
        "wenchang_palace": "丑",
    }
    assert eye_general_relations(core) == []
    # Existing cross-camp center pairs stay visible; this extension adds none.
    assert any(p["name"] == "关" for p in structural_patterns(core))
    core.update(
        main_general=1, main_vice_general=1, guest_general=2, guest_vice_general=2
    )
    assert eye_general_relations(core) == []
    assert not any(p["name"] == "关" for p in structural_patterns(core))


@pytest.mark.parametrize(
    "year,ju,clause",
    [
        (1900, 1, "shiji_clear"),
        (1912, 13, "generals_unconnected"),
        (1926, 27, "generals_unconnected"),
    ],
)
def test_actual_false_positive_five_general_results_are_blocked_by_named_pairs(
    year, ju, clause
):
    result = calculate_taiyi_analysis(**transport_payload("taiyi", year))
    board = result["taiyi"]
    assert board["core_board"]["kook_number"] == ju
    patterns = board["patterns"]
    # Counterfactual uses the exact old relation set, not a second calculation.
    before = [p for p in patterns if p.get("relation_profile") != PROFILE]
    assert (
        five_general_conditions(before)["five_generals"][
            "assessed_conditions_satisfied"
        ]
        is True
    )
    assessed = board["condition_assessment"]
    assert assessed["five_generals"]["conditions_satisfied"] is False
    assert assessed["ruleset"]["version"] == "1.2.0"
    assert assessed["ruleset"]["relation_profile"] == PROFILE
    blocker = next(c for c in assessed["five_generals"]["clauses"] if c["id"] == clause)
    assert blocker["satisfied"] is False and blocker["blockers"]
    for c in assessed["five_generals"]["clauses"]:
        for ref in c["blockers"]:
            p = resolve(result, ref["source_path"])
            assert all(ref[k] == p[k] for k in ["name", "subject", "variant"])
            assert ref["source_path"] in result["snapshot_text"]
            assert p["traditional_meaning"] in result["snapshot_text"]
    assert board["ruleset"]["classical_acceptance_passed"] is False


def test_all_144_boards_append_without_reindexing_existing_relations_or_recasting():
    from fatebridge.core.metaphysics.taiyi_enclosures import principal_enclosures

    for yin in (False, True):
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            original = json.loads(json.dumps(core, ensure_ascii=False))
            patterns = structural_patterns(core)
            added = eye_general_relations(core)
            assert core == original
            assert [
                p for p in patterns if p.get("relation_profile") == PROFILE
            ] == added
            old = [p for p in patterns if p.get("relation_profile") != PROFILE]
            if added:
                assert patterns[-len(added) :] == added
            old_enclosures = [p for p in old if p["name"] == "提挟"]
            assert old_enclosures == principal_enclosures(core)
            assessed = five_general_conditions(patterns, core=core)
            if (
                five_general_conditions(old)["five_generals"][
                    "assessed_conditions_satisfied"
                ]
                is False
            ):
                assert assessed["five_generals"]["conditions_satisfied"] is False
            assert sum(
                len(c["blockers"]) for c in assessed["five_generals"]["clauses"]
            ) >= len(added)


def test_every_added_projection_leaf_is_typed_and_retains_false_values():
    result = calculate_taiyi_analysis(**transport_payload("taiyi", 1912))

    def leaves(obj, prefix):
        if isinstance(obj, dict) and obj:
            for key, value in obj.items():
                yield from leaves(value, f"{prefix}.{key}")
        else:
            yield prefix

    paths = list(
        leaves(
            result["taiyi"]["condition_assessment"]["ruleset"],
            "taiyi.condition_assessment.ruleset",
        )
    )
    index = next(
        i
        for i, p in enumerate(result["taiyi"]["patterns"])
        if p.get("relation_profile")
    )
    for field in paths:
        Taiyi.model_validate(
            project_fields(result, [field], strict_fields=True)["taiyi"]
        )
    # Public arrays are selected whole. Check each optional entry leaf by
    # projecting an object wrapper, then validating it in the actual array type.
    pattern = result["taiyi"]["patterns"][index]
    for field in leaves(pattern, "pattern"):
        partial = project_fields({"pattern": pattern}, [field], strict_fields=True)
        Taiyi.model_validate({"patterns": [partial["pattern"]]})


@pytest.mark.parametrize("mutation", ["remove_case", "change_count", "drop_pair"])
def test_source_oracle_changes_cannot_improve_acceptance(tmp_path, mutation):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    source = target / "eye-general-cases.json"
    data = json.loads(source.read_text())
    if mutation == "remove_case":
        data["cases"].pop()
    elif mutation == "change_count":
        data["cases"][0]["expected"]["main_count"] = 17
    else:
        data["cases"][0]["stated_relations"].pop()
    source.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹"):
        audit(target)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1900, 1912])
@pytest.mark.parametrize("transport", ["REST", "MCP", "CLI"])
def test_real_public_transports_return_corrected_pairs_and_conditions(
    key, year, transport, capsys, monkeypatch
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = transport_payload(key, year)
    fields = [
        "taiyi.core_board.kook_number",
        "taiyi.patterns",
        "taiyi.condition_assessment",
        "snapshot_text",
    ]
    if transport == "REST":
        api._reset_runtime_state_for_tests()
        monkeypatch.setattr(
            api,
            "API_KEY_AUTHENTICATOR",
            api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
        )
        with TestClient(api.app) as client:
            response = client.post(
                spec.rest_path,
                params=[
                    ("strict_fields", "true"),
                    ("response_char_limit", "0"),
                    *[("fields", f) for f in fields],
                ],
                json=payload,
            )
        assert response.status_code == 200, response.text
        result = response.json()
    elif transport == "MCP":

        async def call():
            async with Client(create_mcp_app()) as client:
                response = await client.call_tool(
                    spec.mcp_name,
                    {**payload, "fields": fields, "strict_fields": True},
                    raise_on_error=False,
                )
                assert not response.is_error, response
                return await _same_run_payload(client, response)

        result = asyncio.run(call())
    else:
        args = [key]
        for name, value in payload.items():
            args += ["--" + name.replace("_", "-"), str(value)]
        code = run(
            [
                *args,
                "--fields",
                *fields,
                "--strict-fields",
                "--response-char-limit",
                "0",
            ]
        )
        result = json.loads(capsys.readouterr().out)
        assert code == 0, result
    assert result["taiyi"]["core_board"]["kook_number"] == year - 1899
    assessment = result["taiyi"]["condition_assessment"]
    assert assessment["five_generals"]["conditions_satisfied"] is False
    assert any(
        p.get("relation_profile") == PROFILE for p in result["taiyi"]["patterns"]
    )
    expected = calculate_taiyi_analysis(**transport_payload("taiyi", year))["taiyi"]
    assert result["taiyi"]["patterns"] == expected["patterns"]
    assert assessment == expected["condition_assessment"]
    assert assessment["scope"] in result["snapshot_text"]


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1900, 1910, 1912, 1926])
def test_native_first_condition_view_keeps_all_business_and_full_same_run_receipt(
    key, year
):
    spec = next(s for s in CATALOG if s.key == key)
    view = "conditions" if key == "taiyi" else "taiyi_conditions"

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.mcp_name,
                {
                    **transport_payload(key, year),
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            assert not result.is_error, result
            await _same_run_payload(client, result, require_business_inline=True)
            return result.structured_content

    result = asyncio.run(call())
    assert (
        result["taiyi"]["condition_assessment"]["five_generals"]["conditions_satisfied"]
        is False
    )
    assert any(
        p.get("relation_profile") == PROFILE for p in result["taiyi"]["patterns"]
    )
