"""Prove a calendar date independently of an unavailable UTC clock label.

Published calendar cells and affine coefficients are independent controls.
Exact TT boundary probes and model-derived input longitudes are numerical
engineering tests, not observed Sun epochs or real-world prediction data.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import guolao_epoch as module
from fatebridge.core.astro.historical_utc import historical_utc_to_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_guolao_native_frames import fixed_moshier  # noqa:F401
from tests.test_guolao_native_jie_month import epoch_for

REFERENCE = json.loads(
    (
        Path(__file__).parent
        / "fixtures/guolao-native-lunar-date-v1/reference-before-implementation.json"
    ).read_text()
)
CASES = REFERENCE["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_exact_forward_points_match_independent_published_midnight_coefficients(case):
    for prefix, key in [
        ("previous", "day_start_TT_exact"),
        ("next", "day_end_TT_exact"),
    ]:
        moment = datetime.fromisoformat(
            case["date_proof"][prefix + "_local_midnight_UTC"]
        )
        point = historical_utc_to_tt_point(moment)
        if moment.year >= 1972:
            assert point is None  # Closed by the explicitly separate atomic table.
        else:
            assert point.days == Fraction(case["date_proof"][key])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("sample", [0, 1, 2])
def test_entire_clock_adjustment_has_one_proved_UTC8_date(case, sample):
    low, high = map(Fraction, case["date_proof"]["adjustment_TT_interval_exact"])
    point = [low, (low + high) / 2, high][sample]
    lookup, evidence = module._historical_utc8_date(TTInstant(point))
    assert lookup.date().isoformat() == case["id"]
    assert evidence["calendar_date"] == case["id"]
    assert Fraction(evidence["start_boundary"]["julian_day_tt_exact"]) == Fraction(
        case["date_proof"]["day_start_TT_exact"]
    )
    assert Fraction(evidence["next_boundary"]["julian_day_tt_exact"]) == Fraction(
        case["date_proof"]["day_end_TT_exact"]
    )
    assert evidence["utc_clock_label_assigned"] is False
    assert evidence["classical_clock_mapping_accepted"] is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_exact_midnight_half_open_contract_searches_adjacent_hint_dates(case, side):
    start = Fraction(case["date_proof"]["day_start_TT_exact"])
    point = start + Fraction(side, 86_400_000_000)
    lookup, proof = module._historical_utc8_date(TTInstant(point))
    expected = datetime.fromisoformat(case["id"]).date()
    if side < 0:
        expected -= timedelta(days=1)
    assert lookup.date() == expected
    assert Fraction(proof["start_boundary"]["julian_day_tt_exact"]) <= point
    assert point < Fraction(proof["next_boundary"]["julian_day_tt_exact"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_native_lunar_lookup_matches_HKO_and_does_not_assign_a_clock_label(
    fixed_moshier, case
):
    epoch = epoch_for(case)
    assert epoch.utc_label is None and epoch.utc_datetime is None
    actual = module.native_month_context(epoch, "chinese_lunar_utc8")
    expected = case["expected_lunar"]
    assert actual["status"] == "available"
    assert actual["month_number"] == expected["month"]
    assert actual["lunar_year"] == expected["year"]
    assert actual["lunar_day"] == expected["day"]
    assert actual["is_leap_month"] is expected["is_leap_month"]
    assert actual["calendar_date"] == case["id"]
    assert actual["instant_utc"] is None and actual["calendar_datetime"] is None
    assert actual["calendar_date_evidence"]["primary_julian_day_tt_exact"] == str(
        Fraction(epoch.time.jd_tt)
    )


@pytest.mark.parametrize(
    "moment", ["1959-12-31T23:59:59+00:00", "1972-01-01T00:00:00+00:00"]
)
def test_exact_affine_encoder_does_not_extend_coefficient_coverage(moment):
    assert historical_utc_to_tt_point(datetime.fromisoformat(moment)) is None


def test_exact_affine_encoder_rejects_naive_labels():
    with pytest.raises(ValueError, match="aware datetime"):
        historical_utc_to_tt_point(datetime(1964, 4, 1))


def test_date_proof_does_not_substitute_a_missing_lunar_table(
    fixed_moshier, monkeypatch
):
    monkeypatch.setattr(module.almanac, "get_lunar_context", lambda *a, **k: None)
    actual = module.native_month_context(epoch_for(CASES[3]), "chinese_lunar_utc8")
    assert actual["status"] == "calendar_unavailable"
    assert actual["month_number"] is None
    assert actual["calendar_date"] == "1964-04-01"
    assert actual["instant_utc"] is None and actual["calendar_datetime"] is None


@pytest.mark.parametrize("point", [Fraction(2_000_000), Fraction(2_500_000)])
def test_date_proof_does_not_extrapolate_outside_the_historical_adjustment_scope(point):
    assert module._historical_utc8_date(TTInstant(point)) is None


def test_incoherent_atomic_transition_is_a_source_error(monkeypatch):
    original = module.leap_table()
    altered = {
        **original,
        "entries": [{"effective_date": "1972-01-02", "tai_minus_utc_seconds": 10}],
    }
    monkeypatch.setattr(module, "leap_table", lambda: altered)
    with pytest.raises(EphemerisSourceError) as raised:
        module._historical_utc8_date(TTInstant(Fraction(CASES[0]["exact_jd_tt"])))
    assert raised.value.reason == "birth_clock_source_mismatch"


def test_missing_date_source_never_yields_a_partial_valid_chart(
    fixed_moshier, monkeypatch
):
    case = CASES[3]
    epoch = epoch_for(case)
    date = datetime.fromisoformat(case["id"])
    wall_jd = date.toordinal() + 1721424.5
    monkeypatch.setattr(module, "historical_utc_to_tt_point", lambda _: None)
    result = calculate_core_chart_analysis(
        birth_year=date.year,
        birth_month=date.month,
        birth_day=date.day,
        birth_hour=0,
        birth_longitude=(wall_jd - epoch.time.jd_ut1) * 360,
        birth_latitude=40,
        birth_clock_basis="local_mean_solar",
        chart_variant="guolao_chart",
        analysis_datetime=datetime(2027, 6, 1, tzinfo=timezone.utc),
        guolao_month_basis="chinese_lunar_utc8",
    )
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503
    assert result["issues"][0]["code"] == "birth_clock_source_mismatch"
    assert "guolao" not in result


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("case", [CASES[0], CASES[1], CASES[-1]], ids=lambda c: c["id"])
@pytest.mark.parametrize("projected", [False, True])
def test_lunar_gap_overlap_and_transition_match_all_three_surfaces(
    fixed_moshier, monkeypatch, capsys, record_testsuite_property, tool, case, projected
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
        guolao_month_basis="chinese_lunar_utc8",
    )
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    options = dict(
        as_of="2026-10-25T00:00:00+08:00",
        include_snapshot_text=False,
        response_char_limit=0,
    )
    fields = [
        "guolao.timing.month_limit.birth_month." + key
        for key in [
            "calendar_date",
            "calendar_date_evidence",
            "calendar_datetime",
            "instant_utc",
            "month_number",
            "lunar_year",
            "lunar_day",
            "is_leap_month",
        ]
    ]
    if projected:
        options.update(fields=fields, strict_fields=True)
    spec = next(s for s in CATALOG if s.key == tool)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in options.items()
        if k != "fields"
    ]
    if projected:
        params += [("fields", value) for value in fields]
    response = TestClient(api.app).post(spec.rest_path, json=payload, params=params)
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
    if projected:
        argv += ["--strict-fields", "--fields", *fields]
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    wire = dict(input=payload, options=options, rest=response.json(), mcp=mcp, cli=cli)
    record_testsuite_property(
        f"native-lunar-{tool}-{case['id']}-{projected}",
        json.dumps(wire, ensure_ascii=False),
    )
    if folder := os.environ.get("FATEBRIDGE_NATIVE_LUNAR_WIRE_DIR"):
        path = Path(folder) / f"{tool}-{case['id']}-{projected}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(wire, stream, ensure_ascii=False)
    values = [
        {k: v for k, v in result.items() if k != "run_metadata"}
        for result in [response.json(), mcp, cli]
    ]
    assert values[0] == values[1] == values[2]
    actual = values[0]["guolao"]["timing"]["month_limit"]["birth_month"]
    expected = case["expected_lunar"]
    assert actual["calendar_date"] == case["id"]
    assert actual["month_number"] == expected["month"]
    assert (
        actual["lunar_year"] == expected["year"]
        and actual["lunar_day"] == expected["day"]
    )
    assert actual["instant_utc"] is None and actual["calendar_datetime"] is None
    if not projected:
        assert (
            values[0]["guolao"]["timing"]["month_limit"]["status"] == "research_partial"
        )
        assert "没有唯一UTC标签" in values[0]["interpretation"]["input_clock"]
        assert (
            "不能据此判断晋升或岗位变动" in values[0]["interpretation"]["month_limit"]
        )
