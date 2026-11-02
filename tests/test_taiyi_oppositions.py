"""Physical opposition is returned even while the original names differ."""

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
from fatebridge.core.metaphysics.taiyi_oppositions import (
    opposition_assessment,
    oppositions_text,
)
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_oppositions import TaiyiOppositionEntry
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_oppositions import CORPUS, audit
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload


def test_all_twelve_notes_keep_twenty_four_positions_names_and_source53_conflict():
    report = audit()
    assert report["selected_annotation_records"] == 12
    assert (
        report["matching_numeric_observations"]
        == report["required_numeric_observations"]
        == 24
    )
    assert (
        report["matching_opposition_observations"]
        == report["required_opposition_observations"]
        == 12
    )
    assert report["source_name_counts"] == {"格": 10, "對": 2}
    assert report["additional_reading_disagreements"] == 1
    assert report["selected_geometry_passed"] is True
    assert report["names_unified"] is False
    assert report["whole_selected_annotation_conformance_passed"] is False
    assert report["whole_classic_acceptance_passed"] is False


def test_all_six_actors_each_physical_axis_and_all_intercalary_spirits():
    bearings = [
        (1, "乾"),
        (8, "子"),
        (3, "艮"),
        (4, "卯"),
        (9, "巽"),
        (2, "午"),
        (7, "坤"),
        (6, "酉"),
    ]
    general_fields = (
        "main_general",
        "main_vice_general",
        "guest_general",
        "guest_vice_general",
    )
    for index, (number, center) in enumerate(bearings):
        opposite_number, opposite = bearings[(index + 4) % 8]
        core = {
            **cyclic_core(1),
            "taiyi_number": number,
            "taiyi_palace": center,
            "wenchang_palace": opposite,
            "shiji": opposite,
            **dict.fromkeys(general_fields, opposite_number),
        }
        result = opposition_assessment(core)
        assert len(result["entries"]) == 6
        assert all(
            r["is_opposite"] is True and r["relative_steps"] == 8
            for r in result["entries"]
        )
        for field in ("wenchang_palace", "shiji"):
            for spirit in "丑寅辰巳未申戌亥":
                core[field] = spirit
                row = next(
                    r
                    for r in opposition_assessment(core)["entries"]
                    if r["field"] == field
                )
                assert row["is_opposite"] is False


def test_center_is_null_bearing_and_no_rotation_is_not_assumed_yang():
    core = {**cyclic_core(53), "main_general": 5, "main_vice_general": 5}
    rows = opposition_assessment(core)["entries"]
    for row in rows:
        if row["field"] in {"main_general", "main_vice_general"}:
            assert row["is_opposite"] is None and row["relative_steps"] is None
            assert row["status"] == "no_ring_bearing"
    for core in [
        cyclic_core(53, yin=True),
        {k: v for k, v in cyclic_core(53).items() if k != "yin_dun"},
    ]:
        assert all(
            "source_comparison" not in row
            for row in opposition_assessment(core)["entries"]
        )


@pytest.mark.parametrize("year,ju", [(1912, 13), (1920, 21), (1952, 53)])
def test_source_names_actual_facts_and_extra_disagreement_survive_text(year, ju):
    result = calculate_taiyi_analysis(**transport_payload("taiyi", year))
    board = result["taiyi"]
    a = board["opposition_assessment"]
    assert board["core_board"]["kook_number"] == ju
    assert oppositions_text(a) in result["snapshot_text"]
    assert board["pattern_summary"]["main_oppositions"]
    for row in a["entries"]:
        for fact in row["basis"]:
            assert resolve(board, fact["field"]) == fact["value"]
    note = next(
        r["source_comparison"] for r in a["entries"] if "source_comparison" in r
    )
    assert note["numeric_values_match"] and note["opposition_matches"]
    assert note["source_reading"] in result["snapshot_text"]
    if ju == 53:
        assert (
            note["additional_readings"][0]["matches_selected_taiyi_reference"] is False
        )
        assert board["pattern_summary"]["opposition_source_disagreements"]
    else:
        assert note["additional_readings"] == []
    Taiyi.model_validate(board)


def test_every_assessment_projection_and_entry_leaf_is_strictly_typed():
    result = calculate_taiyi_analysis(**transport_payload("taiyi", 1952))
    a = result["taiyi"]["opposition_assessment"]
    for field in [
        "ruleset.id",
        "ruleset.version",
        "ruleset.author",
        "ruleset.classical_sources",
        "ruleset.annotation_data_sha256",
        "entries",
        "main_names_unified",
        "scope",
    ]:
        partial = project_fields(
            result, ["taiyi.opposition_assessment." + field], strict_fields=True
        )
        Taiyi.model_validate(partial["taiyi"])
    row = next(r for r in a["entries"] if "source_comparison" in r)
    for field in row:
        TaiyiOppositionEntry.model_validate(
            project_fields({"entry": row}, ["entry." + field], strict_fields=True)[
                "entry"
            ]
        )


@pytest.mark.parametrize("mutation", ["drop_note", "alter_number", "erase_conflict"])
def test_oracle_cannot_be_reduced_to_make_the_scope_pass(tmp_path, mutation):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    p = target / "opposition-notes.json"
    data = json.loads(p.read_text())
    if mutation == "drop_note":
        data["records"].pop()
    elif mutation == "alter_number":
        data["records"][0]["expected_general_number"] = 9
    else:
        next(r for r in data["records"] if r["ju"] == 53)["additional_readings"] = []
    p.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹"):
        audit(target)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1912, 1920, 1952])
def test_actual_rest_mcp_cli_match_geometry_source_words_and_unknowns(
    key, year, capsys, monkeypatch
):
    fields = [
        "taiyi.opposition_assessment",
        "taiyi.pattern_summary.main_oppositions",
        "taiyi.core_board.yin_dun",
    ]
    inputs = transport_payload(key, year)
    spec = next(s for s in CATALOG if s.key == key)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post(
            spec.rest_path,
            json=inputs,
            params=[
                ("strict_fields", "true"),
                ("response_char_limit", "0"),
                *[("fields", f) for f in fields],
            ],
        )
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            return await _same_run_payload(client, result)

    mcp = asyncio.run(call())
    args = [key]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    capsys.readouterr()
    code = run(
        [*args, "--fields", *fields, "--strict-fields", "--response-char-limit", "0"]
    )
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    for field in fields:
        assert (
            resolve(response.json(), field)
            == resolve(mcp, field)
            == resolve(cli, field)
        )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1912, 1920, 1952])
def test_published_opposition_view_keeps_all_requested_business_inline(key, year):
    spec = next(s for s in CATALOG if s.key == key)
    view = "oppositions" if key == "taiyi" else "taiyi_oppositions"

    async def call():
        async with Client(create_mcp_app()) as client:
            r = await client.call_tool(
                spec.tool_name,
                {
                    **transport_payload(key, year),
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            await _same_run_payload(client, r, require_business_inline=True)
            return r.structured_content

    result = asyncio.run(call())
    assert len(result["taiyi"]["opposition_assessment"]["entries"]) == 6
    assert result["taiyi"]["opposition_assessment"]["main_names_unified"] is False
