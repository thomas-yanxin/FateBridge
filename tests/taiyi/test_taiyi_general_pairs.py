"""Source readings, all short arcs, provenance and real protocol delivery."""

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
from fatebridge.core.metaphysics.taiyi_enclosures import (
    PAIR_PROFILE,
    enclosure_assessment,
    enclosures_text,
    general_pair_enclosures,
)
from fatebridge.core.metaphysics.taiyi_year import assemble_board, cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.taiyi.audit_taiyi_general_pairs import CORPUS, audit
from tests.taiyi.test_taiyi_enclosures import resolve, transport_payload
from tests.taiyi.test_taiyi_transports import _same_run_payload


def test_all_frozen_source_requirements_and_unresolved_literal_survive():
    r = audit()
    assert r["independent_worked_cases"] == 2
    assert r["worked_case_numeric_observations"] == 17
    assert r["initial_transcription_matching_observations"] == 13
    assert len(r["name_map_corrections"]) == 4
    assert r["worked_case_matching_numeric_observations"] == 17
    assert r["worked_pair_enclosures_matching"] == 2
    assert r["all_yang_literal_mentions"] == 17
    assert r["unique_mentioned_cyclic_ju"] == 11
    assert r["unique_camp_target_observations"] == 16
    assert r["matching_literal_mentions"] == 17
    assert r["worked_cases"][1]["unadjudicated"][0]["literal"] == "地"
    assert not r["whole_family_acceptance_passed"]
    assert not r["historical_calendar_reconstructed"]
    assert not r["full_judgment_validated"]


@pytest.mark.parametrize("camp", ["main", "guest"])
@pytest.mark.parametrize("start", range(8))
@pytest.mark.parametrize("step", [-1, 1])
@pytest.mark.parametrize("offset", [1, 2, 3])
def test_every_bearing_direction_and_unequal_intercalary_distance(
    camp, start, step, offset
):
    # Independently declared physical order, not imported from the algorithm.
    physical = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
    principals = [
        (8, "子"),
        (3, "艮"),
        (4, "卯"),
        (9, "巽"),
        (2, "午"),
        (7, "坤"),
        (6, "酉"),
        (1, "乾"),
    ]
    first, second = principals[start], principals[(start + 2 * step) % 8]
    palace = physical[(physical.index(first[1]) + step * offset) % 16]
    eye = "shiji" if camp == "main" else "wenchang_palace"
    core = {
        "taiyi_palace": "中",
        "wenchang_palace": "中",
        "shiji": "中",
        "main_general": 5,
        "main_vice_general": 5,
        "guest_general": 5,
        "guest_vice_general": 5,
        camp + "_general": first[0],
        camp + "_vice_general": second[0],
        eye: palace,
    }
    found = general_pair_enclosures(core)
    assert len(found) == 1
    assert found[0]["subject"] == ("始击" if camp == "main" else "文昌")
    assert found[0]["basis"][-1]["value"] == palace
    assert ("间神" in found[0]["variant"]) == (offset != 2)
    for endpoint in (first[1], second[1]):
        core[eye] = endpoint
        assert general_pair_enclosures(core) == []


@pytest.mark.parametrize("endpoint", [1, 5, 6, 7, 8, 9])
def test_no_center_same_opposite_long_arc_or_cross_side_pair(endpoint):
    core = {
        "taiyi_palace": "子",
        "wenchang_palace": "中",
        "shiji": "中",
        "main_general": 1,
        "main_vice_general": endpoint,
        "guest_general": 3,
        "guest_vice_general": 5,
    }
    assert general_pair_enclosures(core) == []


def test_same_side_eye_is_outside_adjudicated_target_policy():
    core = {
        "taiyi_palace": "中",
        "wenchang_palace": "子",
        "shiji": "中",
        "main_general": 1,
        "main_vice_general": 3,
        "guest_general": 5,
        "guest_vice_general": 5,
    }
    assert general_pair_enclosures(core) == []


def test_yang19_does_not_collapse_shen_to_kun_or_demand_midpoint():
    board = board_for_ju(19)
    found = [
        p
        for p in board["enclosure_assessment"]["two_general_enclosure"]["patterns"]
        if p.get("relation_profile") == PAIR_PROFILE and p["subject"] == "文昌"
    ]
    assert len(found) == 1
    assert found[0]["basis"][-1] == {"field": "wenchang_palace", "value": "申"}
    assert "间神" in found[0]["variant"]
    assert {r["name"] for r in board["enclosure_assessment"]["unassessed"]} == {
        "挟闭",
        "四郭固",
        "四郭杜",
    }


def test_each_new_assessment_leaf_projects_and_all_facts_resolve():
    board = board_for_ju(2)
    assessment = board["enclosure_assessment"]
    assert assessment["two_general_enclosure"]["present"]
    for p in board["enclosure_assessment"]["two_general_enclosure"]["patterns"]:
        if p.get("relation_profile") == PAIR_PROFILE:
            for fact in p["basis"]:
                assert resolve(board, fact["field"]) == fact["value"]

    def leaves(value, path):
        if isinstance(value, dict) and value:
            for k, v in value.items():
                yield from leaves(v, (*path, k))
        else:
            yield ".".join(path)

    for path in leaves(assessment, ("taiyi", "enclosure_assessment")):
        projected = project_fields({"taiyi": board}, [path], strict_fields=True)
        Taiyi.model_validate(projected["taiyi"])


def test_missing_core_is_unknown_and_all_144_components_keep_same_board_facts_and_text():
    unknown = enclosure_assessment([])
    assert unknown["two_general_enclosure"]["present"] is None
    assert unknown["two_general_enclosure"]["status"] == "not_assessed"
    for yin in (False, True):
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            core.update(ruler_branch="子", ruler_label="合成背景", heshen="丑")
            b = assemble_board(core)
            a = b["enclosure_assessment"]
            text = enclosures_text(a)
            pair = a["two_general_enclosure"]
            assert b["pattern_summary"]["pair_enclosures"] == len(pair["patterns"])
            for path, p in zip(pair["pattern_paths"], pair["patterns"]):
                assert resolve({"taiyi": b}, path) == p
                assert path in text and p["traditional_meaning"] in text
                assert len(p["basis"]) == 3
                for fact in p["basis"]:
                    assert resolve(b, fact["field"]) == fact["value"]


def board_for_ju(ju):
    core = cyclic_core(ju)
    core.update(ruler_branch="子", ruler_label="合成背景", heshen="丑")
    return assemble_board(core)


@pytest.mark.parametrize(
    "kind",
    [
        "drop_case",
        "drop_mention",
        "alter_image",
        "alter_manifest",
        "alter_correction",
        "alter_name_proof",
    ],
)
def test_source_cases_cannot_be_removed_or_replaced(tmp_path, kind):
    d = tmp_path / "corpus"
    shutil.copytree(CORPUS, d)
    if kind == "alter_image":
        (d / "gujin477-page70.jpg").write_bytes(b"changed")
    elif kind == "alter_manifest":
        (d / "manifest.json").write_text("{}")
    elif kind == "alter_correction":
        (d / "name-map-corrections.json").write_text("{}")
    elif kind == "alter_name_proof":
        (d / "name-map-proof.txt").write_text("generated mapping")
    else:
        p = d / (
            "worked-cases.json" if kind == "drop_case" else "mention-readings.json"
        )
        rows = json.loads(p.read_text())
        rows.pop()
        p.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="指纹"):
        audit(d)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1913, 1926, 1930])
def test_actual_rest_mcp_cli_and_same_run_enclosure_view(
    key, year, tmp_path, capsys, monkeypatch
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = transport_payload(key, year)
    fields = ["taiyi.enclosure_assessment", "taiyi.patterns", "taiyi.core_board"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(
            spec.rest_path,
            json=payload,
            params={
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    assert response.status_code == 200, response.text
    expected = response.json()
    args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += ["--" + name.replace("_", "-"), str(value)]
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)

    async def native():
        async with Client(create_mcp_app()) as client:
            selected = await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            view = suggested_fields(
                spec, view="enclosures" if key == "taiyi" else "taiyi_enclosures"
            )
            first = await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "fields": view,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not selected.is_error and not first.is_error
            full = await _same_run_payload(client, first, require_business_inline=True)
            business = {
                k: v
                for k, v in first.structured_content.items()
                if k not in {"run_metadata", "result_delivery"}
            }
            projected = project_fields(full, view, strict_fields=True)
            assert business == {
                k: v for k, v in projected.items() if k != "run_metadata"
            }
            return selected.structured_content

    native_result = asyncio.run(native())
    for value in [cli, native_result]:
        assert {k: v for k, v in value.items() if k != "run_metadata"} == {
            k: v for k, v in expected.items() if k != "run_metadata"
        }
