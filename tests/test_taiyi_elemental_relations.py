"""Source roles, full element graph, independent components and real protocols."""

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
from fatebridge.core.metaphysics.taiyi_elemental_relations import (
    element_relation,
    elemental_guan_assessment,
    elemental_relations_text,
)
from fatebridge.core.metaphysics.taiyi_year import assemble_board, cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_elemental import TaiyiElementalAssessment
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_elemental_relations import audit
from scripts.build_taiyi_elemental_relations import CORPUS, source_data
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload

DATA = source_data()


@pytest.mark.parametrize("case", DATA["worked_examples"], ids=lambda c: c["id"])
def test_all_literal_cases_use_context_roles_and_preserve_source_outcomes(case):
    core = {
        "wenchang_palace": case["main"]["position"],
        "shiji": case["guest"]["position"],
    }
    a = elemental_guan_assessment(core, calculation_mode="day")
    TaiyiElementalAssessment.model_validate(a)
    assert a["relation"] == case["relation"]
    for eye in a["eyes"]:
        assert eye["element"] == case[eye["camp"]]["element"]
        assert eye["role"] == ("文昌" if eye["camp"] == "main" else "始击")
    assert a["source_interpretation"]["overall_outcome_assessed"] is False
    assert a["full_daily_na_yin_method_verified"] is False
    if case["profile"] == "jinjing_vol4":
        assert (
            case["main"]["source_label"] == "地目"
            and case["guest"]["source_label"] == "天目"
        )
    assert "十六神" in a["method_scope"] and "日柱纳音" in a["method_scope"]


def test_all_25_handwritten_relations_and_four_examples_keep_separate_counts():
    r = audit()
    assert r["source_spirit_elements"] == 16
    assert r["literal_examples"] == 4 and r["literal_source_fields"] == 20
    assert r["given_position_inputs"] == 8
    assert r["computed_literal_fields"] == r["matched_computed_literal_fields"] == 12
    assert r["synthetic_relations"] == r["matching_synthetic_relations"] == 25
    assert r["software_cyclic_boards"] == 144
    assert (
        not r["whole_classic_acceptance_passed"] and not r["matrix_128_cells_accepted"]
    )


def test_all_256_positions_compare_the_actual_elements_and_keep_spatial_separate():
    counts = {}
    for m in DATA["spirit_elements"]:
        for g in DATA["spirit_elements"]:
            a = elemental_guan_assessment(
                {"wenchang_palace": m["position"], "shiji": g["position"]}, []
            )
            assert [e["element"] for e in a["eyes"]] == [m["element"], g["element"]]
            assert a["relation"] == element_relation(m["element"], g["element"])
            assert a["implemented_spatial_guan"]["present"] is False
            assert a["source_day_usage"] == "time_method_not_supplied"
            counts[a["relation"]] = counts.get(a["relation"], 0) + 1
    assert len(counts) == 5 and sum(counts.values()) == 256
    a = elemental_guan_assessment({"wenchang_palace": "寅", "shiji": "午"}, [])
    assert (
        a["relation"] == "main_generates_guest"
        and a["source_interpretation"]["reading"] is None
    )
    assert a["source_interpretation"]["kind"] == "relation_only"


@pytest.mark.parametrize("mode", [None, "year", "month", "day", "hour"])
def test_daily_usage_never_becomes_whole_method_acceptance(mode):
    a = elemental_guan_assessment(
        {"wenchang_palace": "卯", "shiji": "酉"}, calculation_mode=mode
    )
    assert a["source_day_usage"] == (
        "day_mode_selected_fragment_only"
        if mode == "day"
        else (
            "reference_only_source_names_day_method"
            if mode
            else "time_method_not_supplied"
        )
    )
    assert a["full_daily_na_yin_method_verified"] is False
    assert a["source_interpretation"]["overall_outcome_assessed"] is False
    if mode != "day":
        assert "本次不是已确认采用该日计方法" in elemental_relations_text(a)


@pytest.mark.parametrize(
    "core",
    [
        {},
        {"wenchang_palace": "中", "shiji": "酉"},
        {"wenchang_palace": "卯", "shiji": None},
        {"wenchang_palace": True, "shiji": "酉"},
    ],
)
def test_missing_positions_stay_unknown(core):
    a = elemental_guan_assessment(core)
    assert a["status"] == "not_assessed" and not a["eyes"] and "relation" not in a
    assert "不猜" in elemental_relations_text(a)


def test_each_actual_eye_and_legacy_pattern_path_resolves_on_all_144_boards():
    for yin in [False, True]:
        for ju in range(1, 73):
            c = cyclic_core(ju, yin=yin)
            c.update(ruler_branch="子", ruler_label="软件", heshen="丑")
            b = assemble_board(c)
            a = b["elemental_guan_assessment"]
            for e in a["eyes"]:
                assert resolve(b, e["actual_path"]) == e["position"]
            for path in a["implemented_spatial_guan"]["pattern_paths"]:
                assert resolve(b, path)["name"] == "关"


def test_partial_projection_and_strict_claim_booleans():
    a = {
        "taiyi": {
            "elemental_guan_assessment": elemental_guan_assessment(
                {"wenchang_palace": "卯", "shiji": "酉"}
            )
        }
    }

    def leaves(v, p):
        if isinstance(v, dict) and v:
            for k, x in v.items():
                yield from leaves(x, (*p, k))
        else:
            yield ".".join(p)

    for f in leaves(
        a["taiyi"]["elemental_guan_assessment"], ("taiyi", "elemental_guan_assessment")
    ):
        Taiyi.model_validate(project_fields(a, [f], strict_fields=True)["taiyi"])
    with pytest.raises(ValidationError):
        TaiyiElementalAssessment.model_validate({"elemental_control": "false"})
    a["taiyi"]["elemental_guan_assessment"]["ruleset"]["source_urls"].clear()
    assert (
        len(
            elemental_guan_assessment({"wenchang_palace": "卯", "shiji": "酉"})[
                "ruleset"
            ]["source_urls"]
        )
        == 3
    )


@pytest.mark.parametrize(
    "name",
    [
        "spirit-elements.json",
        "worked-cases.json",
        "synthetic-truth.json",
        "gujin477-page74.jpg",
    ],
)
def test_frozen_source_and_expectations_cannot_be_removed(tmp_path, name):
    d = tmp_path / "corpus"
    shutil.copytree(CORPUS, d)
    (d / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_data(d)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["year", "month", "day", "hour"])
def test_real_rest_mcp_cli_and_new_first_views(key, mode, capsys, monkeypatch):
    spec = next(s for s in CATALOG if s.key == key)
    payload = transport_payload(key, 2026)
    if key == "taiyi":
        payload["calculation_mode"] = mode
    else:
        payload["taiyi_options"] = {"calculation_mode": mode}
    fields = ["taiyi.elemental_guan_assessment"]
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
    expected = response.json()["taiyi"]["elemental_guan_assessment"]
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
        json.loads(capsys.readouterr().out)["taiyi"]["elemental_guan_assessment"]
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
                and r.structured_content["taiyi"]["elemental_guan_assessment"]
                == expected
            )
            view = (
                "elemental_relations" if key == "taiyi" else "taiyi_elemental_relations"
            )
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
