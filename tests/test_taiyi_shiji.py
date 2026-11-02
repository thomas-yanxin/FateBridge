"""Frozen ring readings, retained edition differences and real shared outputs."""

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
from fatebridge.core.metaphysics.taiyi_shiji import (
    rotate_shiji,
    shiji_derivation,
    shiji_derivation_text,
)
from fatebridge.core.metaphysics.taiyi_year import (
    BRANCHES,
    RING,
    assemble_board,
    cyclic_core,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_shiji import CORPUS, audit, source_data
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload


def test_original_example_handwork_and_witnesses_keep_separate_denominators():
    result = audit()
    assert len(result["given_position_examples"]) == 1
    assert len(result["manual_applications_of_existing_rows"]) == 3
    assert result["manual_rotation_pairs"] == 25
    assert all(
        r["matches"]
        for key in ("given_position_examples", "manual_applications_of_existing_rows")
        for r in result[key]
    )
    assert (
        result["witness_observations"] == result["witness_matching_observations"] == 18
    )
    assert [r["jinjing_source_shiji"] for r in result["witnesses"]] == [
        "午",
        "坤",
        "酉",
    ]
    assert [r["jinjing_source_guest_count"] for r in result["witnesses"]] == [
        25,
        38,
        31,
    ]
    assert not result["siku_source_replaced"]
    assert not result["siku_three_shiji_differences_resolved"]
    assert not result["production_numeric_correction_claimed"]
    assert not result["classical_acceptance_passed"] and result["new_dated_cases"] == 0
    readings = source_data()["readings"]
    assert readings["ncl_rule"]["view_wenchang_clause_not_written_here"]
    assert not readings["ncl_section_boundary"]["whole_book_absence_or_stemma_claimed"]


def test_same_core_paths_and_zero_interval_explanation_are_literal():
    for yin in (False, True):
        for ju in range(1, 73):
            core = cyclic_core(ju, yin=yin)
            core.update(ruler_branch="子", ruler_label="软件背景", heshen="丑")
            board = assemble_board(core)
            trace = board["shiji_derivation"]
            for name, field in (
                ("wenchang", "wenchang_path"),
                ("jishen", "jishen_path"),
                ("actual_shiji", "actual_path"),
            ):
                assert trace[name] == resolve(board, trace[field])
            assert trace["matches_actual"]
            assert trace["pairs"][0] == {
                "step": 0,
                "heaven_spirit": core["jishen"],
                "earth_spirit": "艮",
            }
            assert trace["pairs"][-1]["heaven_spirit"] == core["wenchang_palace"]
            assert trace["pairs"][-1]["earth_spirit"] == core["shiji"]
            assert trace["step_count"] == len(trace["pairs"]) - 1
            text = shiji_derivation_text(trace)
            assert (
                f"计神{core['jishen']}" in text and f"实际始击{core['shiji']}" in text
            )
    identity = rotate_shiji("丑", "丑")
    assert identity["step_count"] == 0 and identity["derived_shiji"] == "艮"


def test_rotation_does_not_collapse_different_spirits_for_any_legal_jishen():
    # A software bijection property, not 192 independent classical cases.
    for jishen in BRANCHES:
        results = [rotate_shiji(wenchang, jishen) for wenchang in RING]
        assert {r["derived_shiji"] for r in results} == set(RING)
        assert {r["step_count"] for r in results} == set(range(16))


def test_counterfactual_actual_value_is_retained_and_not_repaired_to_fit_rule():
    core = {**cyclic_core(37, yin=True), "shiji": "午"}
    result = shiji_derivation(core)
    assert result["actual_shiji"] == core["shiji"] == "午"
    assert result["derived_shiji"] == "坤" and not result["matches_actual"]
    assert "保留本盘值待核" in shiji_derivation_text(result)
    result["pairs"][0]["earth_spirit"] = "caller edit"
    result["ruleset"]["author"] = "caller edit"
    assert shiji_derivation(core)["pairs"][0]["earth_spirit"] == "艮"
    assert shiji_derivation(core)["ruleset"]["author"] == "FateBridge contributors"


@pytest.mark.parametrize("field", ["wenchang_palace", "jishen", "shiji"])
@pytest.mark.parametrize("value", [None, "", "子丑", True])
def test_unknown_or_multiple_positions_are_not_filled(field, value):
    result = shiji_derivation({**cyclic_core(1), field: value})
    assert result["status"] == "not_assessed" and "pairs" not in result
    assert "reason" in result


def test_jishen_cannot_be_a_four_corner_spirit():
    for spirit in "乾坤艮巽":
        with pytest.raises(ValueError):
            rotate_shiji("子", spirit)


def test_all_new_output_leaves_support_partial_projection():
    data = {"taiyi": {"shiji_derivation": shiji_derivation(cyclic_core(37, yin=True))}}

    def leaves(value, prefix):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from leaves(child, (*prefix, key))
        else:
            yield ".".join(prefix)

    for field in leaves(
        data["taiyi"]["shiji_derivation"], ("taiyi", "shiji_derivation")
    ):
        Taiyi.model_validate(project_fields(data, [field], strict_fields=True)["taiyi"])


@pytest.mark.parametrize("mode", ["year", "month", "day", "hour"])
def test_public_snapshot_uses_the_exact_same_derived_and_actual_facts(mode):
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode=mode,
    )
    board = result["taiyi"]
    trace = board["shiji_derivation"]
    assert shiji_derivation_text(trace) in result["snapshot_text"]
    assert trace["actual_shiji"] == board["core_board"]["shiji"]
    assert trace["wenchang"] == board["wenchang_palace"]
    assert trace["jishen"] == board["core_board"]["jishen"]


@pytest.mark.parametrize(
    "file",
    [
        "manual-ring-pairs.json",
        "wujing-focus-readings.json",
        "ncl-page36.png",
        "manifest.json",
    ],
)
def test_source_or_hand_oracle_mutation_is_rejected(tmp_path, file):
    dest = tmp_path / "source"
    shutil.copytree(CORPUS, dest)
    with (dest / file).open("ab") as stream:
        stream.write(b"changed")
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
    fields = [
        "taiyi.shiji_derivation",
        "taiyi.wenchang_palace",
        "taiyi.core_board.jishen",
        "taiyi.core_board.shiji",
    ]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post(
            spec.rest_path,
            json=payload,
            params=[
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
                *[("fields", field) for field in fields],
            ],
        )
    assert response.status_code == 200, response.text
    expected = response.json()["taiyi"]
    assert (
        expected["shiji_derivation"]["actual_shiji"] == expected["core_board"]["shiji"]
    )
    assert expected["shiji_derivation"]["matches_actual"]
    args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += [
                "--" + name.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["taiyi"] == expected

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
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
                not result.is_error and result.structured_content["taiyi"] == expected
            )
            view = "shiji_derivation" if key == "taiyi" else "taiyi_shiji_derivation"
            first = await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            await _same_run_payload(client, first, require_business_inline=True)

    asyncio.run(call())
