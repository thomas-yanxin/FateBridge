"""Equivalent civil instants must keep one solar label across DST changes.

These are regression/metamorphic checks, not new independent astronomical
references or evidence of predictive accuracy.
"""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.local_techniques.chart import _build_metaphysics_seed
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/qimen-clock-representations-v1.json"
    ).read_text()
)
CASES = [
    tuple(
        case[key]
        for key in (
            "zone",
            "longitude",
            "civil_date",
            "civil_time",
            "utc_date",
            "utc_time",
        )
    )
    for case in REFERENCE["cases"]
]


@pytest.mark.parametrize("zone,longitude,date,time,utc_date,utc_time", CASES)
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("method", ["chaibu", "zhirun"])
def test_equivalent_offset_inputs_keep_the_same_seed_and_qimen(
    zone, longitude, date, time, utc_date, utc_time, solar, method
):
    seeds = [
        _build_metaphysics_seed(
            date_text=d,
            time_text=t,
            timezone_name=zone,
            gps_lon=longitude,
            use_true_solar_time=solar,
        )
        for d, t in [(date, time), (utc_date, utc_time)]
    ]
    a, b = seeds
    assert a.input_datetime.isoformat() == b.input_datetime.isoformat()
    assert a.corrected_datetime.isoformat() == b.corrected_datetime.isoformat()
    assert a.total_correction_minutes == b.total_correction_minutes
    assert a.pillars == b.pillars
    assert a.calendar_context == b.calendar_context
    assert build_qimen_with_options(
        a, {"ju_method": method}
    ) == build_qimen_with_options(b, {"ju_method": method})


@pytest.mark.parametrize("time", ["01:30:00", "04:30:00+00:00", "23:00:00-05:30"])
@pytest.mark.parametrize("method", ["chaibu", "zhirun"])
def test_santiago_offset_regression_matches_dedicated_qimen(time, method):
    date = "2026-09-05" if time.endswith("-05:30") else "2026-09-06"
    aggregate = calculate_sanshiunited_analysis(
        date=date,
        time=time,
        zone="America/Santiago",
        gps_lat=-33.45,
        gps_lon=-70.6693,
        use_true_solar_time=True,
        qimen_options={"ju_method": method},
    )
    dedicated = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=9,
        analysis_day=6,
        analysis_hour=1,
        analysis_minute=30,
        analysis_timezone="America/Santiago",
        analysis_longitude=-70.6693,
        use_true_solar_time=True,
        qimen_options={"ju_method": method},
    )
    assert "error" not in aggregate, aggregate
    assert "error" not in dedicated, dedicated
    q = aggregate["qimen"]
    assert (q["day_ganzhi"], q["time_ganzhi"]) == ("癸未", "壬子")
    assert aggregate["analysis_context"]["corrected_datetime"].startswith(
        "2026-09-05 23:48:"
    )
    assert q["palaces"] == dedicated["qimen"]["palaces"]

    # The dedicated endpoint accepts a naive local clock; its provenance
    # strings need not carry the explicit offset emitted by the aggregate.
    def policy_without_clock_provenance(board):
        return {
            key: value
            for key, value in board["calendar_policy"].items()
            if key not in {"civil_datetime", "corrected_datetime"}
        }

    assert policy_without_clock_provenance(q) == policy_without_clock_provenance(
        dedicated["qimen"]
    )
    assert aggregate["subresults"]["qimen"]["pan"] == q


@pytest.mark.parametrize("offset,solar_branch", [("-04:00", "子"), ("-05:00", "丑")])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("method", ["chaibu", "zhirun"])
def test_explicit_iso_offset_resolves_named_zone_fold(
    offset, solar_branch, solar, method
):
    aggregate = calculate_sanshiunited_analysis(
        date="2026-11-01",
        time=f"01:30:00{offset}",
        zone="America/New_York",
        gps_lat=40.7,
        gps_lon=-74.006,
        use_true_solar_time=solar,
        qimen_options={"ju_method": method},
    )
    dedicated = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=11,
        analysis_day=1,
        analysis_hour=1,
        analysis_minute=30,
        analysis_timezone=offset,
        analysis_longitude=-74.006,
        use_true_solar_time=solar,
        qimen_options={"ju_method": method},
    )
    assert "error" not in aggregate, aggregate
    assert "error" not in dedicated, dedicated
    assert (
        aggregate["analysis_context"]["corrected_datetime"]
        == dedicated["analysis_context"]["corrected_datetime"]
    )
    assert aggregate["qimen"]["palaces"] == dedicated["qimen"]["palaces"]
    assert aggregate["qimen"]["time_ganzhi"][-1] == (solar_branch if solar else "丑")


@pytest.mark.parametrize("time", ["01:30:00", "04:30:00+00:00"])
def test_santiago_civil_and_utc_clock_agree_across_real_transports(
    monkeypatch, capsys, time
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["analysis_context", "qimen", "subresults.qimen"]
    payload = dict(
        date="2026-09-06",
        time=time,
        zone="America/Santiago",
        gps_lat=-33.45,
        gps_lon=-70.6693,
        use_true_solar_time=True,
        qimen_options={"ju_method": "chaibu"},
    )
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/divination/sanshiunited",
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
                "sanshiunited", {**payload, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    capsys.readouterr()
    code = run(
        [
            "sanshiunited",
            "--date",
            payload["date"],
            "--time",
            time,
            "--zone",
            payload["zone"],
            "--gps-lat=-33.45",
            "--gps-lon=-70.6693",
            "--use-true-solar-time",
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
    assert code == 0, cli
    assert response.status_code == 200, response.text
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    for body in bodies:
        assert body["analysis_context"]["corrected_datetime"].startswith(
            "2026-09-05 23:48:"
        )
        assert body["qimen"]["day_ganzhi"] == "癸未"
        assert body["qimen"]["time_ganzhi"] == "壬子"
        assert body["subresults"]["qimen"]["pan"] == body["qimen"]
