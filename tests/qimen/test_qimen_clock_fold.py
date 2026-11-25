"""Pinned astronomical observations and clock-ordering regressions, not outcomes."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.almanac import (
    get_adjacent_solar_terms,
    get_bazi_month_boundaries,
    get_bazi_year,
    get_solar_terms_for_year,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    resolve_civil_clock,
    utc_instant,
)
from fatebridge.validation.qimen_clock import audit_clock_fold
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    rest,
    surface_calls,
    three_surfaces,
)

FIXTURES = Path(__file__).parents[1] / "fixtures/qimen_clock_fold_v1"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["clock_probes"])
@pytest.mark.parametrize("solar", [False, True])
def test_published_havana_boundary_survives_repeated_midnight(case, solar):
    local = datetime.fromisoformat(case["utc"]).astimezone(ZoneInfo(REFERENCE["zone"]))
    assert local.isoformat() == case["local"] and local.fold == case["fold"]
    assert get_adjacent_solar_terms(local, REFERENCE["zone"])[0].name == case["term"]
    assert (
        get_bazi_month_boundaries(local, REFERENCE["zone"])[2] == case["month_branch"]
    )
    dedicated = calculate_qimen_analysis(
        analysis_year=local.year,
        analysis_month=local.month,
        analysis_day=local.day,
        analysis_hour=local.hour,
        analysis_minute=local.minute,
        analysis_timezone=REFERENCE["zone"],
        analysis_utc_offset=format_utc_offset(local.utcoffset()),
        analysis_longitude=-82.36,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )
    aggregate = calculate_sanshiunited_analysis(
        date="2021-11-07",
        time=case["local"].split("T")[1],
        zone=REFERENCE["zone"],
        gps_lat=23.1,
        gps_lon=-82.36,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )
    for result in (dedicated, aggregate):
        assert "error" not in result, result
        assert result["qimen"]["ju_term"] == case["term"]
        assert result["qimen"]["calendar_policy"]["timezone"] == REFERENCE["zone"]
        assert (
            result["qimen"]["calendar_policy"]["astronomical_term"]["name"]
            == case["term"]
        )
        assert result["qimen"]["assessment"]["authority_certified"] is False
    assert dedicated["qimen"]["palaces"] == aggregate["qimen"]["palaces"]
    resolution = dedicated["qimen"]["calendar_policy"]["civil_clock_resolution"]
    assert resolution["instant_utc"] == case["utc"]
    assert resolution["fold"] == case["fold"]
    assert "民用时刻" in dedicated["snapshot_text"]


def test_clock_auditor_has_two_observations_not_four_more_term_references():
    report = audit_clock_fold(FIXTURES)
    assert report["disagreements"] == []
    assert report["independent_calendar_reference_count"] == 2
    assert report["iana_derived_clock_probes"] == 4
    assert report["term_error_seconds"] < 60
    assert not report["whole_history_accuracy_established"]


@pytest.mark.parametrize("offset,fold", [("-04:00", 0), ("-05:00", 1)])
def test_explicit_offset_resolves_both_instants_without_replacing_zone(offset, fold):
    at = resolve_civil_clock(datetime(2026, 11, 1, 1, 30), "America/New_York", offset)
    assert at.fold == fold and at.tzinfo.key == "America/New_York"
    assert format_utc_offset(at.utcoffset()) == offset
    assert utc_instant(at).hour == 5 + fold


@pytest.mark.parametrize(
    "wall,zone,offset,message",
    [
        (datetime(2026, 11, 1, 1, 30), "America/New_York", None, "ambiguous"),
        (datetime(2026, 11, 1, 1, 30), "America/New_York", "-06:00", "不一致"),
        (datetime(2026, 3, 8, 2, 30), "America/New_York", "-05:00", "nonexistent"),
        (datetime(2026, 1, 1), "Asia/Hong_Kong", "+09:00", "不一致"),
        (datetime(2026, 1, 1), "UTC", "+00:00:60", "范围"),
        (datetime(2026, 1, 1), "UTC", "+15:01", "不一致"),
        (datetime(2026, 1, 1), "UTC", "+24:00", "范围"),
        (datetime(2026, 1, 1), "UTC", "+8", "须为"),
    ],
)
def test_offsets_never_invent_a_clock(wall, zone, offset, message):
    with pytest.raises(ValueError, match=message):
        resolve_civil_clock(wall, zone, offset)


@pytest.mark.parametrize("offset", ["+11:00", "+10:30"])
def test_half_hour_fold_is_not_assumed_to_be_one_hour(offset):
    at = resolve_civil_clock(datetime(2026, 4, 5, 1, 45), "Australia/Lord_Howe", offset)
    assert format_utc_offset(at.utcoffset()) == offset


def test_historical_seconds_are_preserved_and_naive_instants_rejected():
    offset = timedelta(hours=8, minutes=5, seconds=43)
    assert format_utc_offset(offset) == "+08:05:43"
    at = resolve_civil_clock(datetime(1890, 1, 1), "Asia/Shanghai", "+08:05:43")
    assert at.utcoffset() == offset
    with pytest.raises(ValueError, match="实际时刻"):
        utc_instant(datetime(2026, 1, 1))


def test_lichun_exact_instant_boundary():
    term = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == "立春")
    assert get_bazi_year(term.moment - timedelta(seconds=1), "UTC") == 2025
    assert get_bazi_year(term.moment, "UTC") == 2026


@pytest.mark.parametrize(
    "month,day,hour,offset,expected_hour,message",
    [
        (11, 1, 1, "-04:00", 5, None),
        (11, 1, 1, "-05:00", 6, None),
        (11, 1, 1, "-06:00", None, "不一致"),
        (3, 8, 2, "-05:00", None, "nonexistent"),
    ],
)
def test_explicit_offset_across_rest_mcp_cli(
    monkeypatch, capsys, month, day, hour, offset, expected_hour, message
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = dict(
        analysis_year=2026,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=30,
        analysis_timezone="America/New_York",
        analysis_utc_offset=offset,
        use_true_solar_time=False,
        qimen_options={"ju_method": "zhirun"},
    )
    fields = ["qimen", "snapshot_text"]
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/cn/qimen",
        json=payload,
        params=[
            ("as_of", controls["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "qimen", {**payload, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            "2026",
            "--analysis-month",
            str(month),
            "--analysis-day",
            str(day),
            "--analysis-hour",
            str(hour),
            "--analysis-minute",
            "30",
            "--analysis-timezone",
            "America/New_York",
            f"--analysis-utc-offset={offset}",
            "--no-use-true-solar-time",
            "--qimen-options",
            json.dumps(payload["qimen_options"]),
            "--as-of",
            controls["as_of"],
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    bodies = [response.json(), native.structured_content, cli]
    if message:
        assert code != 0 and native.is_error and response.status_code in (400, 422)
        assert all(message in str(b) and "qimen" not in b for b in bodies)
    else:
        assert code == 0 and not native.is_error and response.status_code == 200
        selected = [{k: b[k] for k in ("qimen", "snapshot_text")} for b in bodies]
        assert selected[0] == selected[1] == selected[2]
        policy = selected[0]["qimen"]["calendar_policy"]
        assert policy["timezone"] == "America/New_York"
        assert (
            datetime.fromisoformat(policy["civil_clock_resolution"]["instant_utc"]).hour
            == expected_hour
        )
        assert "civil_clock_resolution" in str(selected[0]["qimen"]["rule_trace"])


@pytest.mark.parametrize(
    "term_name,previous,jd_tt",
    [
        ("清明", "春分", 2461135.2785690883),
        ("立冬", "霜降", 2461351.9119620677),
    ],
)
@pytest.mark.parametrize("method", ["chaibu", "zhirun"])
def test_dedicated_seconds_at_independent_term_roots(
    term_name, previous, jd_tt, method, tmp_path, monkeypatch, capsys
):
    # Frozen Skyfield 1.53 / DE440 geocentric apparent-longitude roots from
    # tests/data/solar_tt_de440_v1/reference.json.gz (no FateBridge imports in
    # its producer). TT-UTC = 69.184 s in 2026. These two retained vectors keep
    # clean-checkout CI independent of the optional full reference archive.
    # The existing independent TT acceptance is 1 s; branch tests below use
    # adjacent integer seconds around the actual production root, not a
    # minute-rounded table or an assumed subsecond physical accuracy.
    independent = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(
        days=jd_tt - 2451545.0, seconds=-69.184
    )
    term = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == term_name)
    assert abs((term.moment - independent).total_seconds()) < 1
    before = term.moment.replace(microsecond=0)
    if before == term.moment:
        before -= timedelta(seconds=1)
    after = before + timedelta(seconds=1)
    assert before < term.moment <= after
    assert before < independent <= after
    boards = []
    for instant, astronomical in ((before, previous), (after, term_name)):
        payload = dict(
            analysis_year=instant.year,
            analysis_month=instant.month,
            analysis_day=instant.day,
            analysis_hour=instant.hour,
            analysis_minute=instant.minute,
            analysis_second=instant.second,
            analysis_timezone="UTC",
            analysis_utc_offset="+00:00",
            use_true_solar_time=False,
            qimen_options={"ju_method": method},
        )
        dedicated = three_surfaces(
            SPECS["qimen"], payload, ["qimen"], AS_OF, tmp_path, monkeypatch, capsys
        )
        aggregate = three_surfaces(
            SPECS["sanshiunited"],
            dict(
                date=instant.date().isoformat(),
                time=instant.strftime("%H:%M:%S+00:00"),
                zone="UTC",
                gps_lat=0.0,
                gps_lon=0.0,
                use_true_solar_time=False,
                qimen_options={"ju_method": method},
            ),
            ["qimen"],
            AS_OF,
            tmp_path,
            monkeypatch,
            capsys,
        )
        board = dedicated["qimen"]
        assert set(dedicated) == set(aggregate) == {"qimen"}
        assert board["calendar_policy"]["astronomical_term"]["name"] == astronomical
        assert (
            board["calendar_policy"]["civil_clock_resolution"]["instant_utc"]
            == instant.isoformat()
        )
        for field in (
            "ju_term",
            "ju_decision",
            "ju_number",
            "palaces",
            "day_ganzhi",
            "time_ganzhi",
        ):
            assert board[field] == aggregate["qimen"][field]
        if method == "chaibu":
            assert board["ju_term"] == astronomical
        boards.append(board)
    if method == "chaibu":
        assert boards[0]["ju_number"] != boards[1]["ju_number"]
        assert boards[0]["palaces"] != boards[1]["palaces"]


@pytest.mark.parametrize("second", [0, 59])
@pytest.mark.parametrize("offset,fold", [("-04:00", 0), ("-05:00", 1)])
@pytest.mark.parametrize("solar", [False, True])
def test_seconds_preserve_dst_fold_and_minute_default(second, offset, fold, solar):
    payload = dict(
        analysis_year=2026,
        analysis_month=11,
        analysis_day=1,
        analysis_hour=1,
        analysis_minute=30,
        analysis_timezone="America/New_York",
        analysis_utc_offset=offset,
        analysis_longitude=-74.0,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )
    dedicated = calculate_qimen_analysis(**payload, analysis_second=second)
    aggregate = calculate_sanshiunited_analysis(
        date="2026-11-01",
        time=f"01:30:{second:02d}{offset}",
        zone="America/New_York",
        gps_lat=40.7,
        gps_lon=-74.0,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )
    resolution = dedicated["qimen"]["calendar_policy"]["civil_clock_resolution"]
    assert resolution["fold"] == fold
    instant = datetime.fromisoformat(resolution["instant_utc"])
    assert instant.hour == 5 + fold and instant.second == second
    for field in ("ju_term", "ju_decision", "palaces"):
        assert dedicated["qimen"][field] == aggregate["qimen"][field]
    if second == 0:
        assert dedicated == calculate_qimen_analysis(**payload)


@pytest.mark.parametrize("second", [0, 59, 60])
def test_seconds_validation_and_projection_across_surfaces(surface_calls, second):
    payload = dict(
        analysis_year=2026,
        analysis_month=11,
        analysis_day=1,
        analysis_hour=1,
        analysis_minute=30,
        analysis_second=second,
        analysis_timezone="America/New_York",
        analysis_utc_offset="-05:00",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    controls = dict(
        fields=["qimen.calendar_policy", "qimen.palaces"],
        strict_fields=True,
        response_char_limit=0,
        include_snapshot_text=False,
    )
    http, protocol, code, local = surface_calls(
        SPECS["qimen"],
        payload,
        projection=controls,
        rest_as_of=AS_OF,
    )
    if second == 60:
        assert http.status_code == 422 and protocol.is_error and code != 0
        assert http.json()["error_code"] == "validation_error"
        assert "analysis_second" in str(http.json())
        assert "analysis_second" in str(protocol.content)
        assert "analysis_second" in str(local)
        return
    assert http.status_code == 200 and not protocol.is_error and code == 0
    bodies = [
        business(http.json()),
        business(protocol.structured_content),
        business(local),
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert set(bodies[0]) == {"qimen"}
    assert set(bodies[0]["qimen"]) == {"calendar_policy", "palaces"}
    # Compare projections with the same public full result: delivery removes
    # internal provenance hashes, which raw service dictionaries still contain.
    full_http, full_protocol, full_code, full_local = surface_calls(
        SPECS["qimen"],
        payload,
        projection={**controls, "fields": ["qimen"]},
        rest_as_of=AS_OF,
    )
    assert (
        full_http.status_code == 200 and not full_protocol.is_error and full_code == 0
    )
    full_bodies = [
        business(full_http.json()),
        business(full_protocol.structured_content),
        business(full_local),
    ]
    assert full_bodies[0] == full_bodies[1] == full_bodies[2]
    full = full_bodies[0]["qimen"]
    assert bodies[0]["qimen"] == {
        key: full[key] for key in ("calendar_policy", "palaces")
    }
