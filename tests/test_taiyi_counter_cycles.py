"""A local ju is not the selected full counter or an actual calendar stem."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics import taiyi_year
from fatebridge.core.metaphysics.taiyi_cycles import counter_cycles, counter_cycles_text
from fatebridge.core.output_chinese import TaiyiCounterCycles
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.taiyi_caption_cycles import caption_candidates
from scripts.audit_taiyi_cycles import audit

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_cycles_v42"
FREEZE = "19e96a08e9bc7f55fafa12803e83a6e098b1e46e79bc1d2cfeb0e041424b8cfa"


def source():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == FREEZE
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for base, key in ((CORPUS, "files"), (ROOT, "prior_sources")):
        for name, sha in frozen[key].items():
            assert hashlib.sha256((base / name).read_bytes()).hexdigest() == sha
    return json.loads((CORPUS / "arithmetic-reference.json").read_text())


def test_full887_counter_is_retained_with_different_sixty_and_seventy_two_positions():
    core = taiyi_year.cyclic_core(887)
    core.update(suijun="子", heshen="丑")
    board = taiyi_year.assemble_board(core, calculation_mode="hour")
    assert "counter_cycles" in board
    cycles = board["counter_cycles"]
    assert cycles["counter"] == board["core_board"]["accumulation"] == 887
    assert cycles["position360"] == 167
    assert cycles["ji60"] == {"number": 3, "position": 47, "size": 60}
    assert cycles["yuan72"] == {"number": 3, "position": 23, "size": 72}
    assert cycles["actual_kook_number"] == board["core_board"]["kook_number"] == 23


def test_the_frozen_expectations_are_not_derived_from_the_production_core():
    rows = source()["rows"]
    assert len(rows) == 13 and rows[-1] == [887, 2, 167, 3, 47, 3, 23]


@pytest.mark.parametrize("vector", source()["rows"])
def test_manual_counter_vectors_and_exact_recomposition(vector):
    n, complete, position, ji, within_ji, yuan, within_yuan = vector
    core = {"accumulation": n, "kook_number": within_yuan}
    original = deepcopy(core)
    result = counter_cycles(core, calculation_mode="hour")
    TaiyiCounterCycles.model_validate(result)
    assert (result["completed_cycles_before_current360"], result["position360"]) == (
        complete,
        position,
    )
    assert result["ji60"] == dict(number=ji, position=within_ji, size=60)
    assert result["yuan72"] == dict(number=yuan, position=within_yuan, size=72)
    assert complete * 360 + (ji - 1) * 60 + within_ji == n
    assert complete * 360 + (yuan - 1) * 72 + within_yuan == n
    assert core == original
    assert (
        result["calendar_ganzhi_alignment"] == "not_assessed_by_counter_decomposition"
    )
    assert not any(
        "ganzhi" in key for key in result if key != "calendar_ganzhi_alignment"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("accumulation", True),
        ("accumulation", 0),
        ("accumulation", 1.0),
        ("accumulation", "1"),
        ("kook_number", True),
        ("kook_number", "23"),
        ("kook_number", 0),
        ("kook_number", 72),
    ],
)
def test_bad_or_disagreeing_core_counters_cannot_make_a_plausible_trace(field, value):
    core = {"accumulation": 887, "kook_number": 23, field: value}
    with pytest.raises(ValueError):
        counter_cycles(core, calculation_mode="hour")


@pytest.mark.parametrize("mode", ["unknown", "", False, 0])
def test_unknown_counter_unit_is_not_silently_called_years(mode):
    with pytest.raises(ValueError):
        counter_cycles({"accumulation": 1, "kook_number": 1}, calculation_mode=mode)


def test_887_and_47_have_the_same_palace_but_different_eyes_and_ju():
    full, shortcut = [taiyi_year.cyclic_core(n) for n in (887, 47)]
    assert full["accumulation"] == 887 and shortcut["accumulation"] == 47
    assert full["taiyi_number"] == shortcut["taiyi_number"]
    assert full["kook_number"] != shortcut["kook_number"]
    assert full["wenchang_palace"] != shortcut["wenchang_palace"]


def test_all_ten_caption_cases_and_omitted_constraints_remain_visible():
    report = audit()
    assert report["source_volumes"] == 10 and report["inventory_contexts"] == 15
    assert report["captioned_cases"] == 10
    assert report["unique_phase_cases_under_assumption"] == 9
    assert report["incompatible_caption_cases_under_assumption"] == ["enemy_movement"]
    assert report["all_solver_controls_match_frozen_math"]
    case = next(c for c in report["cases"] if c["id"] == "enemy_movement")
    assert case["phase_only_numeric_controls"][0]["matching_fields"] == 7
    assert case["candidates_under_declared_coordinate_assumption"] == []
    omitted = {
        c["omitted_constraint_for_diagnostic_only"]: c["candidates"]
        for c in case["single_constraint_omission_controls"]
    }
    assert omitted == {"ji60": [52], "ju": [172], "ganzhi": [124]}
    armies = next(c for c in report["cases"] if c["id"] == "two_armies")
    assert [
        (c["matching_fields"], c["required_fields"])
        for c in armies["phase_only_numeric_controls"]
    ] == [(1, 10), (0, 10)]
    assert all(not c["whole_classical_case_passed"] for c in report["cases"])
    assert not report["whole_goal_complete"] and report["new_model_invocations"] == 0


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"ji60": True},
        {"ji60": 7},
        {"yuan72": 6},
        {"ju": 73},
        {"ju": 1.0},
        {"ganzhi": "甲丑"},
        {"ganzhi": "乙卯时"},
    ],
)
def test_caption_solver_requires_explicit_valid_coordinate_constraints(args):
    with pytest.raises(ValueError):
        caption_candidates(**args)


def test_source_dangshi_phase_can_omit_the_unadjudicated_yuan_glyph():
    assert caption_candidates(ji60=6, ju=27, ganzhi="戊寅") == [315]


@pytest.mark.parametrize(
    "mode,unit", [("year", "年"), ("month", "节月"), ("day", "日"), ("hour", "时辰")]
)
def test_actual_selected_counter_mode_and_unit_are_read_from_the_same_board(mode, unit):
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=25,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode=mode,
    )
    board = result["taiyi"]
    trace = board["counter_cycles"]
    assert trace["counter_unit"] == unit and trace["calculation_mode"] == mode
    assert trace["counter"] == board["core_board"]["accumulation"]
    assert trace["actual_kook_number"] == board["core_board"]["kook_number"]
    text = counter_cycles_text(trace)
    assert text in result["snapshot_text"]
    section = next(
        s for s in result["snapshot_export"]["sections"] if s["title"] == "规则依据"
    )
    assert (
        text in section["content"] and text in result["snapshot_export"]["export_text"]
    )


def test_sanshi_retains_the_same_actual_counter_evidence_and_its_scope():
    result = calculate_sanshiunited_analysis(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options={
            "calculation_mode": "hour",
            "hour_profile": "key_hour_winter_jiazi_v1",
        },
    )
    trace = result["taiyi"]["counter_cycles"]
    assert trace == result["subresults"]["taiyi"]["pan"]["counter_cycles"]
    text = counter_cycles_text(trace)
    section = next(
        s for s in result["snapshot_export"]["sections"] if s["title"] == "太乙规则依据"
    )
    assert text in result["snapshot_text"] and text in section["content"]


def test_cycle_projection_accepts_missing_siblings_but_rejects_numeric_strings():
    TaiyiCounterCycles.model_validate({"yuan72": {"position": 23}})
    with pytest.raises(ValidationError):
        TaiyiCounterCycles.model_validate({"yuan72": {"position": "23"}})


@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "profile", ["jinjing_hour_solstice_v1", "key_hour_winter_jiazi_v1"]
)
def test_same_counter_division_reaches_rest_mcp_cli(monkeypatch, capsys, tool, profile):
    spec = next(s for s in CATALOG if s.key == tool)
    fields = suggested_fields(spec, view="counter_cycles")
    if tool == "taiyi":
        payload = dict(
            analysis_year=2026,
            analysis_month=10,
            analysis_day=25,
            analysis_hour=12,
            analysis_timezone="+08:00",
            use_true_solar_time=False,
            calculation_mode="hour",
            hour_profile=profile,
        )
    else:
        payload = dict(
            date="2026-10-25",
            time="12:00:00",
            zone="+08:00",
            use_true_solar_time=False,
            taiyi_options={"calculation_mode": "hour", "hour_profile": profile},
        )
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-25T12:00:00+08:00",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    http = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", options["as_of"]),
        ],
    )
    assert http.status_code == 200, http.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.mcp_name, {**payload, **options}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    protocol = asyncio.run(invoke())
    argv = [tool]
    for key, value in payload.items():
        argv += [
            "--" + key.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    argv += [
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--as-of",
        options["as_of"],
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in (http.json(), protocol, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    trace = bodies[0]["taiyi"]["counter_cycles"]
    assert trace["actual_kook_number"] == trace["yuan72"]["position"]


@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
def test_default_mcp_counter_view_keeps_all_business_evidence_in_same_run(tool):
    from tests.test_taiyi_transports import _same_run_payload

    spec = next(s for s in CATALOG if s.key == tool)
    payload = (
        dict(
            analysis_year=2026,
            analysis_month=10,
            analysis_day=25,
            analysis_hour=12,
            analysis_timezone="+08:00",
            use_true_solar_time=False,
            calculation_mode="hour",
            hour_profile="key_hour_winter_jiazi_v1",
        )
        if tool == "taiyi"
        else dict(
            date="2026-10-25",
            time="12:00:00",
            zone="+08:00",
            use_true_solar_time=False,
            taiyi_options={
                "calculation_mode": "hour",
                "hour_profile": "key_hour_winter_jiazi_v1",
            },
        )
    )

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.mcp_name,
                {
                    **payload,
                    "fields": suggested_fields(spec, view="counter_cycles"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            full = await _same_run_payload(client, result, require_business_inline=True)
            assert full["taiyi"]["counter_cycles"]["counter_unit"] == "时辰"
            assert (
                full["taiyi"]["counter_cycles"]["calendar_ganzhi_alignment"]
                == "not_assessed_by_counter_decomposition"
            )

    asyncio.run(invoke())
