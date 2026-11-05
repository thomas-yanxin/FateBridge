"""Physical Jie months survive published fractional UTC gaps and overlaps.

Published coefficients and calendar days are independent controls. Boundary
ULP probes and longitudes derived from a selected model are synthetic tests,
not newly observed Sun epochs or evidence of predictive efficacy.
"""

import asyncio
import json
import math
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import guolao_epoch as module
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time, ut1_from_tt
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.guolao.test_guolao_native_frames import fixed_moshier  # noqa:F401

REFERENCE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/guolao-native-jie-month-v1/reference-before-implementation.json"
    ).read_text()
)
CASES = REFERENCE["cases"]
LUNAR_CASES = {
    row["id"]: row["expected_lunar"]
    for row in json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/guolao-native-lunar-date-v1/reference-before-implementation.json"
        ).read_text()
    )["cases"]
}


def epoch_for(case):
    return PhysicalEpoch.from_ut1(ut1_from_tt(case["jd_tt"]))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_published_nonzero_UTC_adjustments_keep_Jie_but_not_invent_lunar_dates(
    fixed_moshier, case
):
    epoch = epoch_for(case)
    assert epoch.utc_label is None and epoch.utc_datetime is None
    assert abs(epoch.time.jd_tt - case["jd_tt"]) * 86400 <= 0.0002
    jie = module.native_month_context(epoch, "jie_month")
    assert jie["status"] == "available"
    assert jie["instant_utc"] is None and jie["calendar_datetime"] is None
    assert jie["month_number"] == case["expected_month"]
    assert jie["month_branch"] == case["expected_branch"]
    assert jie["term_search_year"] == int(case["id"][:4])
    assert jie["term_search_year_basis"] == (
        "primary_TT_Gregorian_year_selects_candidates_only"
    )
    assert jie["comparison_basis"] == "primary_TT_not_a_datetime_surrogate"
    assert jie["next_boundary"]["name"] == case["next_term"]
    # HKO's day-resolution tables note historical HK summer time. The
    # conservative one-hour expansion concerns the published date only,
    # and never changes the200us physical inverse contract.
    actual = datetime.fromisoformat(jie["next_boundary"]["datetime_with_offset"])
    date = datetime.fromisoformat(case["next_term_hko_date"]).replace(
        tzinfo=timezone(timedelta(hours=8))
    )
    assert date - timedelta(hours=1) <= actual < date + timedelta(days=1)
    lunar = module.native_month_context(epoch, "chinese_lunar_utc8")
    expected = LUNAR_CASES[case["id"]]
    assert lunar["month_number"] == expected["month"]
    assert lunar["lunar_day"] == expected["day"]
    assert lunar["lunar_year"] == expected["year"]
    assert lunar["calendar_date"] == case["id"]
    assert lunar["instant_utc"] is None and lunar["calendar_datetime"] is None


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_TT_search_is_half_open_at_actual_shared_Jie_boundaries(
    fixed_moshier, case, side
):
    epoch = epoch_for(case)
    jie = module.native_month_context(epoch, "jie_month")
    boundary = datetime.fromisoformat(jie["next_boundary"]["datetime_with_offset"])
    tt = ephemeris_time(boundary).jd_tt
    if side:
        tt = math.nextafter(tt, -math.inf if side < 0 else math.inf)
    # Synthetic numerical probe: vary TT, without asserting a new physical
    # observation or constructing a valid birth-input replay receipt.
    probe = replace(epoch, time=replace(epoch.time, jd_tt=tt))
    found = module.native_month_context(probe, "jie_month")
    expected = case["expected_month"] if side < 0 else case["expected_month"] % 12 + 1
    assert found["month_number"] == expected
    assert found["instant_utc"] is None and found["calendar_datetime"] is None


def test_unverified_shared_boundary_is_not_converted_to_optional_unavailability(
    fixed_moshier, monkeypatch
):
    def reject(_):
        raise EphemerisSourceError("birth_clock_source_mismatch")

    monkeypatch.setattr(module.almanac, "require_calculated_solar_term", reject)
    with pytest.raises(EphemerisSourceError) as raised:
        module.native_month_context(epoch_for(CASES[3]), "jie_month")
    assert raised.value.reason == "birth_clock_source_mismatch"


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("case", [CASES[1], CASES[3], CASES[-1]], ids=lambda c: c["id"])
def test_gap_and_overlap_full_results_match_REST_MCP_CLI(
    fixed_moshier, monkeypatch, capsys, record_testsuite_property, tool, case
):
    epoch = epoch_for(case)
    date = datetime.fromisoformat(case["id"])
    wall_jd = date.toordinal() + 1721424.5
    payload = dict(
        birth_year=date.year,
        birth_month=date.month,
        birth_day=date.day,
        birth_hour=0,
        birth_longitude=(wall_jd - epoch.time.jd_ut1) * 360,
        birth_latitude=40,
        birth_clock_basis="local_mean_solar",
        analysis_datetime="2027-06-01T00:00:00+00:00",
        guolao_month_basis="jie_month",
    )
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    options = dict(
        as_of="2026-10-25T00:00:00+08:00",
        include_snapshot_text=False,
        response_char_limit=0,
    )
    spec = next(s for s in CATALOG if s.key == tool)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params={
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in options.items()
        },
    )
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )
            assert not result.is_error
            return result.structured_content

    mcp = asyncio.run(call())
    argv = [spec.tool_name]
    for k, v in payload.items():
        argv += ["--" + k.replace("_", "-"), str(v)]
    argv += [
        "--as-of",
        options["as_of"],
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
    ]
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    wire = dict(input=payload, options=options, rest=response.json(), mcp=mcp, cli=cli)
    record_testsuite_property(
        f"native-jie-{tool}-{case['id']}", json.dumps(wire, ensure_ascii=False)
    )
    if folder := os.environ.get("FATEBRIDGE_NATIVE_JIE_WIRE_DIR"):
        path = Path(folder) / f"{tool}-{case['id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(wire, stream, ensure_ascii=False)
    values = [
        {k: v for k, v in result.items() if k != "run_metadata"}
        for result in [response.json(), mcp, cli]
    ]
    assert values[0] == values[1] == values[2]
    birth = values[0]["guolao"]["timing"]["month_limit"]["birth_month"]
    assert birth["month_number"] == case["expected_month"]
    assert birth["instant_utc"] is None and birth["calendar_datetime"] is None
    assert "没有唯一UTC标签" in values[0]["interpretation"]["input_clock"]
