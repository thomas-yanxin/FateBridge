"""Independent ancient enclosure example, physical geometry and real transports."""

import asyncio
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_enclosures import principal_enclosures
from fatebridge.core.metaphysics.taiyi_year import (
    assemble_board,
    cyclic_core,
    yearly_core,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_enclosures import CORPUS, audit
from tests.test_taiyi_transports import _same_run_payload


def test_entire_selected_example_and_initial_transcription_correction_are_visible():
    report = audit()
    assert report["independent_classical_cases"] == 1
    assert report["required_numeric_observations"] == 11
    assert report["initial_transcription_matches"] == 10
    assert report["initial_transcription_disagreements"] == ["wenchang_palace"]
    assert report["source_correction"]["corrected_value"] == "未"
    assert report["matching_numeric_observations"] == 11
    assert report["source_ju_matches"] is True
    assert report["required_enclosure_targets"] == 2
    assert report["enclosure_targets_match"] is True
    assert report["selected_example_geometry_passed"] is True
    assert report["whole_enclosure_family_acceptance_passed"] is False
    assert report["historical_calendar_reconstructed"] is False


@pytest.mark.parametrize("side", [-1, 1])
@pytest.mark.parametrize("index", range(8))
def test_each_physical_bearing_both_sides_and_wraparound(index, side):
    # Independently written physical bearing order, not the production ring.
    ring = [
        (1, "乾"),
        (8, "子"),
        (3, "艮"),
        (4, "卯"),
        (9, "巽"),
        (2, "午"),
        (7, "坤"),
        (6, "酉"),
    ]
    target = ring[(index + side) % 8][1]
    endpoint = ring[(index + 2 * side) % 8][0]
    core = {
        **cyclic_core(1),
        "taiyi_palace": ring[index][1],
        "main_general": endpoint,
        "main_vice_general": 5,
        "guest_general": 5,
        "guest_vice_general": 5,
        "wenchang_palace": "亥",
        "shiji": target,
    }
    result = principal_enclosures(core)
    assert len(result) == 1
    assert result[0]["subject"] == "始击"
    assert result[0]["basis"] == [
        {"field": "taiyi_palace", "value": ring[index][1]},
        {"field": "core_board.main_general", "value": endpoint},
        {"field": "core_board.shiji", "value": target},
    ]
    # A principal's neighboring intercalary spirit is not that principal.
    core["shiji"] = "亥"
    assert principal_enclosures(core) == []


@pytest.mark.parametrize("endpoint", [1, 2, 5, 6, 7, 9])
def test_no_long_arc_opposite_endpoint_center_or_same_palace_is_manufactured(endpoint):
    core = {
        **cyclic_core(70),
        "main_general": endpoint,
        "main_vice_general": 5,
        "guest_general": 5,
        "guest_vice_general": 5,
    }
    assert principal_enclosures(core) == []


def resolve(root, path):
    for key in path.split("."):
        root = root[int(key)] if isinstance(root, list) else root[key]
    return root


def transport_payload(key, year):
    if key == "taiyi":
        return {
            "analysis_year": year,
            "analysis_month": 7,
            "analysis_day": 1,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
        }
    return {
        "date": f"{year}-07-01",
        "time": "12:00:00",
        "zone": "+08:00",
        "use_true_solar_time": False,
    }


def test_historical_core_and_modern_phase_twin_keep_distinct_calendar_claims():
    ancient = assemble_board(yearly_core(385))
    result = calculate_taiyi_analysis(
        analysis_year=1969,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
    )
    board = result["taiyi"]
    assert board["calendar_rules"]["year"] == 1969
    assert board["core_board"]["kook_number"] == 70
    assert (
        board["core_board"]["accumulation"] - ancient["core_board"]["accumulation"]
        == 1584
    )
    assert board["enclosure_assessment"] == ancient["enclosure_assessment"]
    hit = board["enclosure_assessment"]["principal_enclosure"]
    assert hit["present"] is True
    assert len(hit["pattern_paths"]) == 2
    for path in hit["pattern_paths"]:
        pattern = resolve(result, path)
        assert pattern["name"] == "提挟"
        assert pattern["traditional_meaning"] in result["snapshot_text"]
        assert path in result["snapshot_text"]
        for fact in pattern["basis"]:
            assert resolve(board, fact["field"]) == fact["value"]
    assert {p["subject"] for p in board["patterns"] if p["name"] == "提挟"} == {
        "始击",
        "客大将",
    }
    assert {r["status"] for r in board["enclosure_assessment"]["unassessed"]} == {
        "not_assessed"
    }
    Taiyi.model_validate(board)
    unsupported = calculate_taiyi_analysis(
        analysis_year=385,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
    )
    assert "1900" in unsupported["error"] and "taiyi" not in unsupported


def test_non_hit_is_not_a_denial_of_unadjudicated_enclosure_rules():
    board = assemble_board(yearly_core(2026))
    assessment = board["enclosure_assessment"]
    assert assessment["principal_enclosure"]["present"] is False
    assert "不据此断言全部" in assessment["principal_enclosure"]["meaning"]
    assert {r["name"] for r in assessment["unassessed"]} == {"挟闭", "四郭固", "四郭杜"}


def test_each_new_enclosure_leaf_has_projection_safe_typed_output():
    b = assemble_board(yearly_core(385))

    def leaves(obj, path):
        if isinstance(obj, dict) and obj:
            for key, value in obj.items():
                yield from leaves(value, (*path, key))
        else:
            yield ".".join(path)

    for field in leaves(b["enclosure_assessment"], ("taiyi", "enclosure_assessment")):
        Taiyi.model_validate(
            project_fields({"taiyi": b}, [field], strict_fields=True)["taiyi"]
        )


def test_all_144_ju_same_core_facts_and_five_general_result_are_preserved():
    from fatebridge.core.metaphysics.taiyi_conditions import five_general_conditions

    for yin in (False, True):
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            core.update(ruler_branch="子", ruler_label="测试", heshen="丑")
            board = assemble_board(core)
            patterns = board["patterns"]
            assert board["condition_assessment"] == five_general_conditions(
                # Keep the original indices: later appended eye/general
                # blockers must still resolve to this same board's patterns.
                [
                    (
                        {**p, "name": "not_a_five_general_blocker"}
                        if p["name"] == "提挟"
                        else p
                    )
                    for p in patterns
                ],
                core=core,
            )
            for path in board["enclosure_assessment"]["principal_enclosure"][
                "pattern_paths"
            ]:
                pattern = patterns[int(path.rsplit(".", 1)[1])]
                assert len(pattern["basis"]) == 3
                for fact in pattern["basis"]:
                    assert resolve(board, fact["field"]) == fact["value"]


@pytest.mark.parametrize(
    "attempt", ["drop_number", "drop_target", "alter_image", "alter_correction"]
)
def test_source_cannot_be_reduced_or_correction_proof_replaced(tmp_path, attempt):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    if attempt == "alter_image":
        (corpus / "ncl06604-page51.jpg").write_bytes(b"changed")
        with pytest.raises(ValueError, match="指纹"):
            audit(corpus)
        return
    if attempt == "alter_correction":
        (corpus / "vol02.txt").write_text("computed values instead of primary proof")
        with pytest.raises(ValueError, match="指纹"):
            audit(corpus)
        return
    path = corpus / "principal-enclosure.json"
    data = json.loads(path.read_text())
    if attempt == "drop_number":
        del data["expected"]["wenchang_palace"]
    else:
        data["enclosures"].pop()
    path.write_text(json.dumps(data))
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["source_files"]:
        if item["file"] == path.name:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    correction_path = corpus / "correction-manifest.json"
    correction = json.loads(correction_path.read_text())
    correction["original_manifest_sha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    correction_path.write_text(json.dumps(correction))
    with pytest.raises(ValueError, match="完整11项.*2个"):
        audit(corpus)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year,present", [(1969, True), (2026, False)])
def test_enclosure_facts_match_real_rest_mcp_cli(
    key, year, present, capsys, monkeypatch
):
    fields = ["taiyi.enclosure_assessment", "taiyi.patterns", "taiyi.core_board"]
    payload = transport_payload(key, year)
    kwargs = {
        **payload,
        "strict_fields": True,
        "fields": fields,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    response = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(key, kwargs)
            assert not result.is_error
            return result.structured_content

    mcp = asyncio.run(call())
    args = [key]
    for name, value in payload.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    args += ["--strict-fields", "--response-char-limit", "0", "--fields", *fields]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    for path in fields:
        assert (
            resolve(response.json(), path) == resolve(mcp, path) == resolve(cli, path)
        )
    assert (
        mcp["taiyi"]["enclosure_assessment"]["principal_enclosure"]["present"]
        is present
    )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1969, 2026])
def test_published_enclosure_first_view_keeps_business_inline_under_default_budget(
    key, year
):
    spec = next(s for s in CATALOG if s.key == key)
    view = "enclosures" if key == "taiyi" else "taiyi_enclosures"
    fields = suggested_fields(spec, view=view)
    assert "taiyi.enclosure_assessment" in fields
    kwargs = {
        **transport_payload(key, year),
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(key, kwargs)
            return await _same_run_payload(client, result)

    result = asyncio.run(call())
    projected = project_fields(result, fields, strict_fields=True)
    Taiyi.model_validate(projected["taiyi"])
    assert result["taiyi"]["enclosure_assessment"]["principal_enclosure"][
        "present"
    ] is (year == 1969)


def test_month_comparison_hypothesis_is_not_a_proved_source_calendar_basis():
    r = calculate_taiyi_analysis(
        analysis_year=1561,
        analysis_month=11,
        analysis_day=10,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode="month",
        month_profile="key_month_tianzheng_jie_v1",
    )
    reference = r["taiyi"]["calendar_rules"]["month_origin"]["calendar_reference"]
    assert reference["month_label_matches"] is False
    assert reference["source_calendar_basis"] == "not_adjudicated"
    assert reference["comparison_hypothesis"] == "original_month_label_as_lunar_month"
    assert "不据此证明原例必用朔月" in r["snapshot_text"]
    assert "朔月假设对照" in r["snapshot_text"]
    Taiyi.model_validate(r["taiyi"])
