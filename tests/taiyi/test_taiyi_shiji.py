"""Frozen ring readings, retained edition differences and real shared outputs."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.contracts.output_chinese import Taiyi
from fatebridge.core.metaphysics.taiyi_board import assemble_board
from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES, RING
from fatebridge.core.metaphysics.taiyi_shiji import (
    rotate_shiji,
    shiji_derivation,
    shiji_derivation_text,
)
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.taiyi.audit_taiyi_shiji import CORPUS, audit, source_data
from tests.support.reference_data import resolve
from tests.support.transports import AS_OF, SPECS, business, call_calculation
from tests.unit_test.fixtures.taiyi import same_run_payload, transport_payload


def test_original_example_handwork_and_witnesses_keep_separate_denominators() -> None:
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


def test_same_core_paths_and_zero_interval_explanation_are_literal() -> None:
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


def test_rotation_does_not_collapse_different_spirits_for_any_legal_jishen() -> None:
    # A software bijection property, not 192 independent classical cases.
    for jishen in BRANCHES:
        results = [rotate_shiji(wenchang, jishen) for wenchang in RING]
        assert {r["derived_shiji"] for r in results} == set(RING)
        assert {r["step_count"] for r in results} == set(range(16))


def test_counterfactual_actual_value_is_retained_and_not_repaired_to_fit_rule() -> None:
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
def test_unknown_or_multiple_positions_are_not_filled(
    field: str, value: bool | str | None
) -> None:
    result = shiji_derivation({**cyclic_core(1), field: value})
    assert result["status"] == "not_assessed" and "pairs" not in result
    assert "reason" in result


def test_jishen_cannot_be_a_four_corner_spirit() -> None:
    for spirit in "乾坤艮巽":
        with pytest.raises(ValueError):
            rotate_shiji("子", spirit)


def test_all_new_output_leaves_support_partial_projection() -> None:
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
def test_public_snapshot_uses_the_exact_same_derived_and_actual_facts(
    mode: str,
) -> None:
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
def test_source_or_hand_oracle_mutation_is_rejected(tmp_path: Path, file: str) -> None:
    dest = tmp_path / "source"
    shutil.copytree(CORPUS, dest)
    with (dest / file).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_data(dest)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["year", "month", "day", "hour"])
def test_real_rest_mcp_cli_and_new_first_views(
    key: str,
    mode: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    args = [
        spec.tool_name,
        "--strict-fields",
        "--no-use-true-solar-time",
        "--fields",
        *fields,
    ]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += [
                "--" + name.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
        else:
            pass
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["taiyi"] == expected

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(
                client,
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
            first = await call_calculation(
                client,
                spec.tool_name,
                {
                    **payload,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            await same_run_payload(client, first, require_business_inline=True)

    asyncio.run(call())


@pytest.mark.parametrize(
    "month,day,ju,profile,spirit,count,recount,generals",
    [
        (8, 30, 37, "jinjing_vol2_rotation_v1", "坤", 25, 25, (5, 5)),
        (8, 30, 37, "jinjing_vol3_table_v1", "午", 27, 27, (7, 1)),
        (8, 30, 37, "jinjing_vol3_table_literal_v1", "午", 25, 27, (5, 5)),
        (9, 5, 43, "jinjing_vol3_table_literal_v1", "坤", 38, 38, (8, 4)),
        (9, 6, 44, "jinjing_vol3_table_literal_v1", "酉", 31, 31, (1, 3)),
    ],
)
def test_sanshi_taiyi_editions_preserve_guest_count_and_trace(
    month: int,
    day: int,
    ju: int,
    profile: str,
    spirit: str,
    count: int,
    recount: int,
    generals: tuple[int, int],
    surface_calls,
) -> None:
    payload = {
        **transport_payload("sanshiunited", 2026),
        "date": f"2026-{month:02d}-{day:02d}",
        "taiyi_options": {"calculation_mode": "day", "shiji_profile": profile},
    }
    http, mcp, code, cli = surface_calls(
        SPECS["sanshiunited"],
        payload,
        projection={
            "detail": "audit",
            "fields": [
                "taiyi.core_board",
                "taiyi.rule_trace.guest",
                "taiyi.shiji_derivation",
            ],
            "strict_fields": True,
            "response_char_limit": 0,
            "include_snapshot_text": False,
        },
        rest_as_of=AS_OF,
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    board = cli["taiyi"]
    core = board["core_board"]
    assert core["yin_dun"] is True and core["kook_number"] == ju
    assert (core["shiji_profile"], core["shiji"], core["guest_count"]) == (
        profile,
        spirit,
        count,
    )
    assert (core["guest_general"], core["guest_vice_general"]) == generals
    trace = board["rule_trace"]["guest"]
    assert trace["count"] == sum(step["value"] for step in trace["path"]) == recount
    derivation = board["shiji_derivation"]
    assert derivation["actual_shiji"] == spirit
    if profile == "jinjing_vol3_table_literal_v1":
        assert trace["selected_count"] == count
        assert "卷三原表字面" in trace["selected_count_basis"]
        assert derivation["guest_count_basis"] == "卷三原表字面"
    elif profile == "jinjing_vol3_table_v1":
        assert derivation["guest_count_basis"] == "卷二算路重算"


@pytest.mark.parametrize("ju,yin", [(37, False), (38, True)])
def test_outside_vol3_witness_reports_effective_rotation(ju: int, yin: bool) -> None:
    requested = "jinjing_vol3_table_literal_v1"
    core = cyclic_core(ju, yin=yin, shiji_profile=requested)
    default = cyclic_core(ju, yin=yin)
    assert core == {**default, "requested_shiji_profile": requested}
    derivation = shiji_derivation(core)
    assert derivation["shiji_profile"] == "jinjing_vol2_rotation_v1"
    assert derivation["requested_shiji_profile"] == requested
    assert "selected_source" not in derivation
    assert "在本局无适用卷三行" in shiji_derivation_text(derivation)
