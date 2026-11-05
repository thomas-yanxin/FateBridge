"""Pinned IANA clock controls, true-solar labels and same-profile transports."""

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.core.metaphysics.taiyi_clock import validate_seed_civil_clock
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from tests.support.transports import SPECS, business, call_cli
from tests.taiyi.test_taiyi_periods import seed_at
from tests.taiyi.test_taiyi_transports import _same_run_payload

CORPUS = Path(__file__).parents[1] / "fixtures/taiyi_jinjing_v29"
FREEZE_SHA256 = "ab311d41c12241218ed4ea29c2c66402e19323ffb09126dea4222fa5a071c348"
REFERENCE = json.loads((CORPUS / "cases.json").read_text())
VALID = REFERENCE["valid"]
INVALID = REFERENCE["invalid"]
PROFILES = [
    ("year", {}),
    ("month", {}),
    ("month", {"month_profile": "key_month_tianzheng_jie_v1"}),
    ("day", {}),
    ("hour", {}),
    ("hour", {"hour_profile": "key_hour_winter_jiazi_v1"}),
]


def inputs(case, *, solar=False, mode="day", options=None):
    t = datetime.fromisoformat(case["wall"])
    return dict(
        analysis_year=t.year,
        analysis_month=t.month,
        analysis_day=t.day,
        analysis_hour=t.hour,
        analysis_minute=t.minute,
        analysis_timezone=case["zone"],
        analysis_utc_offset=case["offset"],
        analysis_longitude=case.get("longitude", 0.0),
        use_true_solar_time=solar,
        calculation_mode=mode,
        **(options or {}),
    )


def sanshi_inputs(case, *, solar, mode, options):
    t = datetime.fromisoformat(case["wall"])
    return dict(
        date=t.date().isoformat(),
        time=t.time().isoformat() + case["offset"],
        zone=case["zone"],
        gps_lon=case["longitude"],
        use_true_solar_time=solar,
        taiyi_options={"calculation_mode": mode, **options},
    )


def without_explicit_receipt(board):
    # ISO actual-instant input and wall+offset input have different input
    # semantics; the dedicated receipt must not be fabricated for the former.
    return {
        k: (
            {kk: vv for kk, vv in v.items() if kk != "civil_clock_resolution"}
            if k in {"calendar_rules", "calendar_summary"}
            else v
        )
        for k, v in board.items()
    }


def check_clock(result, case):
    assert "taiyi" in result, result
    board = result["taiyi"]
    r = board["calendar_rules"]["civil_clock_resolution"]
    assert r["timezone"] == case["zone"]
    assert r["input_utc_offset"] == r["resolved_utc_offset"] == case["offset"]
    assert r["fold"] == case["fold"]
    assert r["instant_utc"] == case["utc"]
    assert r["wall_datetime"] == case["wall"]
    assert board["calendar_summary"]["civil_clock_resolution"] == r
    assert r["timezone_rules"]["provider"]
    assert case["utc"] in result["snapshot_text"]
    assert "民用时刻消歧" in result["snapshot_text"]
    Taiyi.model_validate(board)


def test_original_iana_rules_and_clock_cases_remain_frozen():
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == FREEZE_SHA256
    )
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == digest
    assert len(VALID) == 7 and len(INVALID) == 6
    assert freeze["production_expectations_generated"] is False


@pytest.mark.parametrize("case", VALID[:4], ids=lambda c: c["id"])
@pytest.mark.parametrize("mode,options", PROFILES)
@pytest.mark.parametrize("solar", [False, True])
def test_selected_fold_instant_survives_all_profiles_and_matches_iso_aggregate(
    case, mode, options, solar
):
    dedicated = calculate_taiyi_analysis(
        **inputs(case, solar=solar, mode=mode, options=options)
    )
    check_clock(dedicated, case)
    aggregate = calculate_sanshiunited_analysis(
        **sanshi_inputs(case, solar=solar, mode=mode, options=options)
    )
    assert "taiyi" in aggregate, aggregate
    assert without_explicit_receipt(dedicated["taiyi"]) == aggregate["taiyi"]


@pytest.mark.parametrize("case", VALID[4:], ids=lambda c: c["id"])
@pytest.mark.parametrize("solar", [False, True])
def test_nonfold_solar_gap_label_historical_seconds_and_canonical_utc(case, solar):
    result = calculate_taiyi_analysis(**inputs(case, solar=solar))
    check_clock(result, case)
    aggregate = calculate_sanshiunited_analysis(
        **sanshi_inputs(case, solar=solar, mode="day", options={})
    )
    assert "taiyi" in aggregate, aggregate
    assert without_explicit_receipt(result["taiyi"]) == aggregate["taiyi"]
    if case["id"] == "ny_spring_valid_solar_gap_label" and solar:
        assert result["analysis_context"]["corrected_datetime"].startswith(
            "2026-03-08 02:"
        )


@pytest.mark.parametrize("case", INVALID, ids=lambda c: c["id"])
@pytest.mark.parametrize("solar", [False, True])
def test_explicit_offset_never_invents_missing_or_mismatched_clock(case, solar):
    result = calculate_taiyi_analysis(**inputs(case, solar=solar))
    assert "taiyi" not in result and result["retryable"] is False
    assert case["error_contains"] in result["error"]


@pytest.mark.parametrize("kind", ["naive_fold", "aware_gap"])
def test_domain_guards_keep_unresolved_wall_clock_and_nonexistent_clock_rejections(
    kind,
):
    base = seed_at(datetime(2026, 1, 1, 12), zone="America/New_York")
    moment = (
        datetime(2026, 11, 1, 1, 30)
        if kind == "naive_fold"
        else datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo("America/New_York"))
    )
    with pytest.raises(ValueError, match="ambiguous|nonexistent"):
        validate_seed_civil_clock(replace(base, input_datetime=moment))


@pytest.mark.parametrize("value", [True, 2, -1, "0"])
def test_receipt_fold_is_a_strict_zero_or_one(value):
    with pytest.raises(ValidationError):
        Taiyi.model_validate(
            {"calendar_rules": {"civil_clock_resolution": {"fold": value}}}
        )


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


@pytest.mark.parametrize(
    "case",
    [VALID[0], VALID[1], VALID[3], VALID[4], INVALID[1], INVALID[2], INVALID[4]],
    ids=lambda c: c["id"],
)
@pytest.mark.parametrize("solar", [False, True])
def test_real_rest_mcp_cli_clock_contract_and_default_budget(
    rest, tmp_path, capsys, case, solar
):
    spec = SPECS["taiyi"]
    data = inputs(
        case,
        solar=solar,
        mode="hour",
        options={"hour_profile": "key_hour_winter_jiazi_v1"},
    )
    fields = suggested_fields(spec, view="clock_basis")
    params = [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("as_of", "2026-10-12T02:00:00Z"),
        *[("fields", f) for f in fields],
    ]
    http = rest.post(spec.rest_path, json=data, params=params)
    code, cli = call_cli(
        spec,
        data,
        tmp_path,
        capsys,
        flags=[
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **data,
                    "as_of": "2026-10-12T02:00:00Z",
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            if "utc" in case:
                return result, await _same_run_payload(
                    client, result, require_business_inline=True
                )
            return result, result.structured_content

    native, body = asyncio.run(protocol())
    if "utc" not in case:
        assert code != 0 and native.is_error and http.status_code in (400, 422)
        assert all(case["error_contains"] in str(r) for r in [http.json(), cli, body])
    else:
        assert code == 0 and not native.is_error and http.status_code == 200
        from fatebridge.application.result_delivery import RESULT_STORE

        def full(value):
            return (
                RESULT_STORE.get(value["result_delivery"]["result_id"])
                if value.get("result_delivery")
                else value
            )

        assert business(full(http.json())) == business(full(cli)) == business(body)
        assert (
            body["taiyi"]["calendar_rules"]["civil_clock_resolution"]["instant_utc"]
            == case["utc"]
        )
