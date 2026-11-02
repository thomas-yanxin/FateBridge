"""Independent full source-input matrix, arithmetic probes and real transports."""

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
from fatebridge.core.metaphysics.taiyi_source_alignment import (
    count_source_assessment,
    source_alignment_text,
)
from fatebridge.core.metaphysics.taiyi_year import assemble_board, cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_source_alignment import CORPUS, audit
from scripts.build_taiyi_source_alignment import source_data
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload


def board(ju, yin=False):
    core = cyclic_core(ju, yin=yin)
    core.update(ruler_branch="子", ruler_label="软件背景", heshen="丑")
    return assemble_board(core)


def test_full_positions_old_counts_and_source_recounts_have_separate_denominators():
    r = audit()
    assert r["source_rows"] == 144
    assert r["required_position_observations"] == 576
    assert r["matching_position_observations"] == 573
    assert [(x["case_id"], x["field"]) for x in r["position_disagreements"]] == [
        ("yin-37", "shiji"),
        ("yin-43", "shiji"),
        ("yin-44", "shiji"),
    ]
    assert r["prior_count_observations"] == 288
    assert r["matching_prior_count_observations"] == 277
    assert len(r["prior_count_disagreements"]) == 11
    assert r["source_position_recounts"] == 288
    assert r["matching_source_position_recounts"] == 278
    assert len(r["source_position_recount_disagreements"]) == 10
    assert len(r["manual_probe_checks"]) == 12 and r["manual_probe_checks_match"]
    assert [x["id"] for x in r["facsimile_transcription_corrections"]] == [
        "yang-41",
    ]
    assert [x["id"] for x in r["initial_manual_entry_semantic_errors"]] == ["yin-59"]
    assert len(r["initial_manual_literal_corrections"]) == 13
    assert not r["classical_acceptance_passed"]


@pytest.mark.parametrize(
    "ju,source,count,recount,diagnosis",
    [
        (37, "午", 25, 27, "count_agrees_despite_source_input_difference"),
        (43, "坤", 38, 38, "source_inputs_explain_count_difference"),
        (44, "酉", 31, 31, "source_inputs_explain_count_difference"),
        (46, "乾", 2, 1, "same_position_rule_table_disagreement"),
    ],
)
def test_upstream_marker_and_arithmetic_are_not_conflated(
    ju, source, count, recount, diagnosis
):
    a = board(ju, yin=True)["count_source_assessment"]
    guest = next(c for c in a["counts"] if c["camp"] == "guest")
    assert guest["source_marker"] == source and guest["source_table_count"] == count
    assert guest["source_position_recount"]["count"] == recount
    assert guest["diagnosis"] == diagnosis
    assert "本盘" in source_alignment_text(a) and "原表" in source_alignment_text(a)
    assert "重算不是本盘替代值" in source_alignment_text(a)


@pytest.mark.parametrize(
    "ju,yin,field,initial,text,scan,normalized",
    [
        (41, False, "jishen", "戊", "戊", "戌", "戌"),
        (59, True, "wenchang_palace", "大神", "大炅", "大炅", "巽"),
    ],
)
def test_scanned_readings_do_not_silently_rewrite_transcription(
    ju, yin, field, initial, text, scan, normalized
):
    a = board(ju, yin)["count_source_assessment"]
    fact = next(p for p in a["positions"] if p["field"] == field)
    assert fact["transcription_literal"] == text and fact["source_literal"] == scan
    assert fact["initial_manual_literal"] == initial
    assert fact["source_value"] == normalized and fact["matches"]
    assert fact["source_layer"] == "selected_facsimile"
    assert initial in source_alignment_text(a) and scan in source_alignment_text(a)
    if ju == 59:
        assert "不是旧转录错误" in source_alignment_text(a)


def test_initial_manual_glyphs_do_not_replace_exact_transcription_literals():
    a = board(28)["count_source_assessment"]
    wenchang = next(p for p in a["positions"] if p["field"] == "wenchang_palace")
    assert wenchang["initial_manual_literal"] == "吕申"
    assert wenchang["transcription_literal"] == "呂申"
    jishen = next(
        p
        for p in board(12)["count_source_assessment"]["positions"]
        if p["field"] == "jishen"
    )
    assert jishen["initial_manual_literal"] == "卯"
    assert jishen["transcription_literal"] == "夘"
    assert jishen["actual_value"] == jishen["source_value"] == "卯"


def test_all_144_same_board_paths_and_original_counts_survive():
    for yin in (False, True):
        for ju in range(1, 73):
            b = board(ju, yin)
            a = b["count_source_assessment"]
            for fact in a["positions"]:
                assert resolve(b, fact["actual_path"]) == fact["actual_value"]
            for fact in a["counts"]:
                assert resolve(b, fact["actual_count_path"]) == fact["actual_count"]
                assert resolve(b, fact["actual_marker_path"]) == fact["actual_marker"]
            if a["summary"]["status"] == "differences_unadjudicated":
                assert b["pattern_summary"]["source_table_warning"] == a["summary"]


def test_returned_facsimile_notes_cannot_mutate_the_next_run_source():
    first = count_source_assessment(cyclic_core(41))
    first["facsimile_readings"][0]["facsimile_reading"] = "caller annotation"
    second = count_source_assessment(cyclic_core(41))
    assert second["facsimile_readings"][0]["facsimile_reading"] == "戌"


@pytest.mark.parametrize(
    "changes",
    [
        {"yin_dun": None},
        {"yin_dun": 0},
        {"kook_number": 2},
        {"accumulation": True},
        {"taiyi_palace": "中"},
        {"main_count": True},
    ],
)
def test_unknown_or_inconsistent_cyclic_identity_is_not_assumed_yang(changes):
    c = {**cyclic_core(1), **changes}
    a = count_source_assessment(c)
    assert a["status"] == "not_assessed" and not a["counts"] and not a["positions"]


def test_every_new_output_leaf_has_safe_partial_projection():
    a = {"taiyi": board(43, yin=True)}

    def leaves(value, prefix):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from leaves(child, (*prefix, key))
        else:
            yield ".".join(prefix)

    for field in leaves(
        a["taiyi"]["count_source_assessment"], ("taiyi", "count_source_assessment")
    ):
        selected = project_fields(a, [field], strict_fields=True)
        Taiyi.model_validate(selected["taiyi"])


@pytest.mark.parametrize(
    "kind",
    [
        "drop_row",
        "alter_old_count",
        "alter_image",
        "alter_probe",
        "alter_quote",
        "alter_collation",
    ],
)
def test_source_expectations_or_differences_cannot_be_removed(tmp_path, kind):
    d = tmp_path / "corpus"
    shutil.copytree(CORPUS, d)
    if kind in {"drop_row", "alter_old_count"}:
        p = d / "raw-position-rows.json"
        rows = json.loads(p.read_text())
        if kind == "drop_row":
            rows.pop()
        else:
            rows[38]["main_count"] = 35
        p.write_text(json.dumps(rows))
    elif kind == "alter_image":
        (d / "cadal06056494-page123.jpg").write_bytes(b"changed")
    elif kind == "alter_quote":
        (d / "proof-quote-correction.json").write_text("{}")
    elif kind == "alter_collation":
        (d / "transcription-collation.json").write_text("{}")
    else:
        (d / "arithmetic-probes.json").write_text("[]")
    with pytest.raises(ValueError, match="指纹"):
        source_data(d)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("year", [1938, 1940, 1949])
def test_actual_rest_mcp_cli_and_complete_first_source_view(
    key, year, capsys, monkeypatch
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = transport_payload(key, year)
    fields = ["taiyi.core_board", "taiyi.count_source_assessment"]
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
                *[("fields", f) for f in fields],
            ],
        )
    assert response.status_code == 200, response.text
    expected = response.json()["taiyi"]
    args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += ["--" + name.replace("_", "-"), str(value)]
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["taiyi"] == expected

    async def call():
        async with Client(create_mcp_app()) as c:
            selected = await c.call_tool(
                key,
                {
                    **payload,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert (
                not selected.is_error
                and selected.structured_content["taiyi"] == expected
            )
            view = suggested_fields(
                spec, view="count_sources" if key == "taiyi" else "taiyi_count_sources"
            )
            result = await c.call_tool(
                key,
                {
                    **payload,
                    "fields": view,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            await _same_run_payload(c, result, require_business_inline=True)

    asyncio.run(call())
