"""Complete columns, retained disagreements, missing roles, and actual protocols."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_victory_matrix import (
    victory_matrix_assessment,
    victory_matrix_text,
)
from fatebridge.core.metaphysics.taiyi_year import (
    PALACES,
    assemble_board,
    count_to_taiyi,
    cyclic_core,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_matrix import TaiyiVictoryMatrixAssessment
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.taiyi.audit_taiyi_victory_matrix import audit
from scripts.taiyi.build_taiyi_victory_matrix import CORPUS, source_data
from tests.taiyi.test_taiyi_enclosures import resolve, transport_payload
from tests.taiyi.test_taiyi_transports import _same_run_payload

CELLS = json.loads((CORPUS / "matrix-columns.json").read_text())["cells"]


@pytest.mark.parametrize("cell", CELLS, ids=lambda c: c["id"])
def test_every_source_cell_preserves_both_columns_locators_and_unknown_roles(cell):
    core = {
        "wenchang_palace": cell["wenchang_position"],
        "taiyi_number": cell["taiyi_number"],
        "taiyi_palace": PALACES[cell["taiyi_number"]],
    }
    a = victory_matrix_assessment(core)
    assert a["source_cell"] == cell
    TaiyiVictoryMatrixAssessment.model_validate(a)
    assert (
        a["source_outcome_applied"] is False
        and a["table_applicability_verified"] is False
    )
    assert a["comparison_summary"]["whole_cell_conformance_assessed"] is False
    for c in a["clauses"]:
        if c.get("role_resolution") == "camp_unadjudicated":
            assert all(v["matches_geometry"] is None for v in c["candidates"])
            assert {v["field"].split("_")[0] for v in c["candidates"]} == {
                "main",
                "guest",
            }
    text = victory_matrix_text(a)
    for k in ["condition_column", "result_column"]:
        assert (cell[k]["text"] or "空栏") in text


def test_entire_audit_retains_six_eye_differences_and_all_unadjudicated_fragments():
    a = audit()
    assert a["source_cells"] == a["retrieved_source_cells"] == 128
    assert a["copied_source_fields_counted_as_calculated_hits"] == 0
    assert a["source_eye_geometric_clauses"] == 33
    assert a["matching_eye_geometry"] == 27 and a["different_eye_geometry"] == 6
    assert a["unqualified_general_clauses"] == 51
    assert a["hypothetical_main_general_predicates"] == 61
    assert a["hypothetical_main_matching_geometry"] == 39
    assert a["hypothetical_main_different_geometry"] == 17
    assert a["hypothetical_main_unknown_geometry"] == 5
    assert a["unadjudicated_fragments"] == 76 and a["blank_columns"] == 4
    assert a["source_lacuna_cells"] == 1 and not a["matrix_128_cells_accepted"]
    for row in a["source_rows"]:
        for g in row["geometry"]:
            if g["field"].startswith("guest_"):
                assert g["status"] == "not_assessed" and g["same_palace"] is None


@pytest.mark.parametrize(
    "eye,n,distance",
    [
        ("酉", 3, 10),
        ("子", 4, 12),
        ("丑", 7, 7),
        ("巳", 2, 15),
        ("午", 8, 8),
        ("坤", 6, 14),
    ],
)
def test_source_eye_disagreements_are_visible_without_overwriting_geometry(
    eye, n, distance
):
    a = victory_matrix_assessment(
        {"wenchang_palace": eye, "taiyi_number": n, "taiyi_palace": PALACES[n]}
    )
    assert a["actual_geometry"][0]["distance"] == distance
    assert a["comparison_summary"]["different_eye_geometry"] >= 1
    assert "差异保留" in victory_matrix_text(a)


def test_main_candidate_conflict_never_becomes_a_replacement_calculation_or_outcome():
    a = victory_matrix_assessment(
        {
            "wenchang_palace": "申",
            "taiyi_number": 8,
            "taiyi_palace": "子",
            "main_general": 8,
            "main_vice_general": 4,
            "guest_general": 1,
            "guest_vice_general": 3,
        }
    )
    assert a["source_cell"]["condition_column"]["text"] == "大將迫"
    claim = next(c for c in a["clauses"] if c["kind"] == "geometric_claim")
    assert claim["role_resolution"] == "camp_unadjudicated"
    assert [v["matches_geometry"] for v in claim["candidates"]] == [False, True]
    actual = next(g for g in a["actual_geometry"] if g["field"] == "main_general")
    assert (
        actual["position"] == "子" and actual["same_palace"] and not actual["adjacent"]
    )
    assert not a["source_outcome_applied"]


def test_center_and_missing_generals_stay_unknown_and_do_not_turn_false():
    a = victory_matrix_assessment(
        {
            "wenchang_palace": "申",
            "taiyi_number": 8,
            "taiyi_palace": "子",
            "main_general": 5,
            "guest_general": True,
        }
    )
    clause = next(c for c in a["clauses"] if c["kind"] == "geometric_claim")
    assert all(c["matches_geometry"] is None for c in clause["candidates"])
    assert a["actual_geometry"][1]["position"] == "中"


@pytest.mark.parametrize(
    "core",
    [
        {},
        {"wenchang_palace": "中", "taiyi_number": 1, "taiyi_palace": "乾"},
        {"wenchang_palace": "申", "taiyi_number": True, "taiyi_palace": "乾"},
        {"wenchang_palace": "申", "taiyi_number": 1, "taiyi_palace": "午"},
    ],
)
def test_missing_or_conflicting_table_keys_are_not_guessed(core):
    a = victory_matrix_assessment(core)
    assert a["status"] == "not_assessed" and "source_cell" not in a
    assert "不猜" in victory_matrix_text(a)


def test_all_144_boards_and_projected_leaves_use_actual_same_core_facts():
    for yin in [False, True]:
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            core.update(ruler_branch="子", heshen="丑")
            b = assemble_board(core)
            a = b["victory_matrix_assessment"]
            for g in a["actual_geometry"]:
                value = resolve(b, g["actual_path"])
                assert g["position"] == (
                    value if g["field"] == "wenchang_palace" else PALACES[value]
                )
            Taiyi.model_validate(b)
    value = {"taiyi": {"victory_matrix_assessment": a}}

    def leaves(v, path):
        if isinstance(v, dict) and v:
            for k, x in v.items():
                yield from leaves(x, (*path, k))
        else:
            yield ".".join(path)

    for path in leaves(a, ("taiyi", "victory_matrix_assessment")):
        Taiyi.model_validate(project_fields(value, [path], strict_fields=True)["taiyi"])
    with pytest.raises(ValidationError):
        TaiyiVictoryMatrixAssessment.model_validate({"source_outcome_applied": "false"})
    a["source_cell"]["condition_column"]["text"] = "mutated"
    a["ruleset"]["source_urls"].clear()
    fresh = victory_matrix_assessment(core)
    assert fresh["source_cell"]["condition_column"]["text"] != "mutated"
    assert len(fresh["ruleset"]["source_urls"]) == 3


@pytest.mark.parametrize(
    "name",
    ["matrix-columns.json", "adjudication.json", "cadal-page100.jpg", "manifest.json"],
)
def test_no_source_cell_image_or_freeze_may_be_silently_replaced(tmp_path, name):
    dest = tmp_path / "corpus"
    shutil.copytree(CORPUS, dest)
    (dest / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_data(dest)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["year", "month", "day", "hour"])
def test_real_rest_mcp_cli_and_new_first_views(key, mode, capsys, monkeypatch):
    spec = next(s for s in CATALOG if s.key == key)
    payload = transport_payload(key, 2026)
    if key == "taiyi":
        payload["calculation_mode"] = mode
    else:
        payload["taiyi_options"] = {"calculation_mode": mode}
    fields = ["taiyi.victory_matrix_assessment"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as c:
        response = c.post(
            spec.rest_path,
            json=payload,
            params=[
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
                ("fields", fields[0]),
            ],
        )
    assert response.status_code == 200, response.text
    expected = response.json()["taiyi"]["victory_matrix_assessment"]
    assert expected["calculation_mode"] == mode
    args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += [
                "--" + name.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
    assert run(args) == 0
    assert (
        json.loads(capsys.readouterr().out)["taiyi"]["victory_matrix_assessment"]
        == expected
    )

    async def call():
        async with Client(create_mcp_app()) as c:
            r = await c.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert (
                not r.is_error
                and r.structured_content["taiyi"]["victory_matrix_assessment"]
                == expected
            )
            view = "victory_matrix" if key == "taiyi" else "taiyi_victory_matrix"
            r = await c.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            await _same_run_payload(c, r, require_business_inline=True)

    asyncio.run(call())


@pytest.mark.parametrize(
    "marker,n",
    [
        ("", 1),
        ("子丑", 1),
        ("乾乾", 1),
        (None, 1),
        (True, 1),
        (1, 1),
        ("子", True),
        ("子", 1.0),
        ("子", 5),
        ("子", None),
    ],
)
def test_count_to_taiyi_rejects_non_single_spirit_and_non_strict_palace(marker, n):
    with pytest.raises(ValueError, match="十六神"):
        count_to_taiyi(marker, n)


@pytest.mark.parametrize("position", ["", "子丑"])
def test_matrix_empty_and_multichar_keys_are_unknown_instead_of_stopiteration(position):
    a = victory_matrix_assessment(
        {"wenchang_palace": position, "taiyi_number": 1, "taiyi_palace": "乾"}
    )
    assert a["status"] == "not_assessed" and "source_cell" not in a
