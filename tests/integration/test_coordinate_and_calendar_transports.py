"""Coordinate, neutral-score and calendar-option repairs agree across transports."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.description import resolve_spec
from fatebridge.cli import run
from fatebridge.mcp_server import app as mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.output_facts import canonical_json
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    call_calculation,
    rest,
    surface_calls,
)

__all__ = ["rest", "surface_calls"]


def invoke(tool, inputs, monkeypatch, capsys, *, detail="standard"):
    spec = resolve_spec(CATALOG, tool)
    assert spec is not None
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path, json=inputs, params={"detail": detail}
    )
    args = [tool, "--detail", detail, "--response-char-limit", "0"]
    for key, value in inputs.items():
        if value is None:
            # CLI optional flags represent JSON null by omission.
            continue
        else:
            pass
        if isinstance(value, list):
            args.extend(["--" + key.replace("_", "-"), *map(str, value)])
            continue
        else:
            pass
        args.extend(
            [
                "--" + key.replace("_", "-"),
                str(value).lower() if isinstance(value, bool) else str(value),
            ]
        )
    code = run(args)
    local = json.loads(capsys.readouterr().out)

    async def call():
        async with Client(mcp_app) as client:
            return await call_calculation(
                client,
                tool,
                {**inputs, "detail": detail, "response_char_limit": 0},
                raise_on_error=False,
            )

    protocol = asyncio.run(call())
    return (
        response,
        code,
        protocol,
        [response.json(), local, protocol.structured_content],
    )


def test_zero_gps_coordinates_drive_the_actual_chart_on_every_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, protocol, outputs = invoke(
        "suzhan",
        {
            "date": "2026-10-20",
            "time": "12:00",
            "zone": "UTC",
            "lat": "ignored because GPS is supplied",
            "lon": "ignored because GPS is supplied",
            "gps_lat": 0,
            "gps_lon": 0,
        },
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        assert output["params"]["birthLatitude"] == output["params"]["gpsLat"] == 0
        assert output["params"]["birthLongitude"] == output["params"]["gpsLon"] == 0
    assert outputs[0]["chart"] == outputs[1]["chart"] == outputs[2]["chart"]


@pytest.mark.parametrize(
    "coordinates",
    [
        {"lat": "31n13"},
        {"lon": "121e28"},
        {"hsys": 8},
        {"lat": "", "lon": "121e28"},
        {"lat": "31n13", "lon": " "},
        {"gps_lat": 0},
        {"gps_lon": 0},
    ],
)
def test_timed_suzhan_requires_both_confirmed_coordinate_components(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], coordinates
) -> None:
    response, code, protocol, outputs = invoke(
        "suzhan",
        {"date": "2026-10-20", "time": "12:00", "zone": "UTC", **coordinates},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in outputs:
        assert output["error_code"] == "validation_error"
        assert "完整经纬度" in output["error"]
        assert "run_metadata" not in output


@pytest.mark.parametrize(
    "coordinates",
    [{"lat": "0", "gps_lon": 0}, {"gps_lat": 0, "lon": "0"}],
)
def test_timed_suzhan_accepts_mixed_explicit_coordinate_sources(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], coordinates
) -> None:
    response, code, protocol, outputs = invoke(
        "suzhan",
        {"date": "2026-10-20", "time": "12:00", "zone": "UTC", **coordinates},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert outputs[0]["chart"] == outputs[1]["chart"] == outputs[2]["chart"]
    assert all(
        output["params"]["birthLatitude"] == output["params"]["birthLongitude"] == 0
        for output in outputs
    )


@pytest.mark.parametrize("coordinates", [{}, {"lat": None, "lon": None}])
def test_timed_suzhan_keeps_calendar_clock_without_coordinates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    coordinates: dict[str, None],
) -> None:
    response, code, protocol, outputs = invoke(
        "suzhan",
        {"date": "2026-10-20", "time": "12:00", "zone": "UTC", **coordinates},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        assert output["chart"] is output["astronomy"] is None
        assert output["params"]["calculationMode"] == "calendar_with_clock"
        assert output["params"]["birthTimeImputed"] is False
        assert output["params"]["coordinatesApplied"] is False


@pytest.mark.parametrize("unknown_time", [{}, {"time": None, "lat": None, "lon": None}])
def test_untimed_suzhan_keeps_date_only_mode_without_coordinates(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], unknown_time
) -> None:
    response, code, protocol, outputs = invoke(
        "suzhan",
        {"date": "2026-10-20", "zone": "UTC", **unknown_time},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        assert output["chart"] is output["astronomy"] is None
        assert output["params"]["calculationMode"] == "calendar_date_only"
        assert output["params"]["birthTimeImputed"] is False
        assert output["params"]["coordinatesApplied"] is False


@pytest.mark.parametrize(
    "changes", [{"lon": "190"}, {"lat": "31N90"}, {"gps_lon": -181}]
)
def test_bad_calendar_coordinates_fail_identically(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], changes
) -> None:
    response, code, protocol, outputs = invoke(
        "lunar_calendar_time",
        {"date": "2026-10-20", "time": "12:00", **changes},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 400 and code == 1 and protocol.is_error
    assert all(output["error_code"] == "validation_error" for output in outputs)
    assert all("run_metadata" not in output for output in outputs)


@pytest.mark.parametrize(
    "date,time,reason",
    [
        ("2024-03-10", "02:30", "nonexistent local time"),
        ("2024-11-03", "01:30", "ambiguous local time"),
    ],
)
@pytest.mark.parametrize("time_alg", [0, 1])
def test_nongli_rejects_unresolved_civil_clock_on_every_transport(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    date: str,
    time: str,
    reason: str,
    time_alg: int,
) -> None:
    response, code, protocol, outputs = invoke(
        "lunar_calendar_time",
        {
            "date": date,
            "time": time,
            "zone": "America/New_York",
            "time_alg": time_alg,
        },
        monkeypatch,
        capsys,
    )
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in outputs:
        assert output["error_code"] == "validation_error"
        assert output["retryable"] is False
        assert reason in output["error"]
        assert "run_metadata" not in output


@pytest.mark.parametrize(
    "date,clock,lunar_day,year_pillar,month_pillar",
    [
        ("2024-02-04", "16:25", (12, 25), "癸卯", "乙丑"),
        ("2024-02-04", "16:29", (12, 25), "甲辰", "丙寅"),
        ("2024-02-10", "00:10", (12, 30), "甲辰", "丙寅"),
    ],
)
def test_lunar_calendar_separates_civil_season_and_solar_day_across_surfaces(
    date: str,
    clock: str,
    lunar_day: tuple[int, int],
    year_pillar: str,
    month_pillar: str,
    surface_calls,
) -> None:
    # At 60°E the solar clock is hours behind the civil time in UTC+8.
    response, protocol, code, cli = surface_calls(
        SPECS["nongli_time"],
        {
            "date": date,
            "time": clock,
            "zone": "Asia/Shanghai",
            "gps_lon": 60,
            "time_alg": 0,
        },
        projection={
            "detail": "audit",
            "fields": [
                "yearGanZi",
                "monthGanZi",
                "monthInt",
                "dayInt",
                "analysis_context.corrected_datetime",
            ],
            "strict_fields": True,
            "response_char_limit": 0,
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        canonical_json(response.json())
        == canonical_json(protocol.structured_content)
        == canonical_json(cli)
    )
    assert (cli["yearGanZi"], cli["monthGanZi"]) == (year_pillar, month_pillar)
    assert (cli["monthInt"], cli["dayInt"]) == lunar_day
    assert cli["analysis_context"]["corrected_datetime"] < f"{date} {clock}"


def test_nongli_uses_selected_fold_for_seasonal_elapsed_time(surface_calls) -> None:
    inputs = {
        "date": "2024-11-03",
        "time": "01:30",
        "zone": "America/New_York",
        "time_alg": 1,
    }
    elapsed_days = []
    for offset in ("-04:00", "-05:00"):
        response, protocol, code, cli = surface_calls(
            SPECS["nongli_time"],
            {**inputs, "analysis_utc_offset": offset},
            projection={"detail": "audit", "response_char_limit": 0},
        )
        assert response.status_code == 200 and code == 0 and not protocol.is_error
        http = response.json()
        assert business(http) == business(cli) == business(protocol.structured_content)
        elapsed_days.append(
            http["calendar_context"]["solar_term_delta"]["days_since_current"]
        )
    assert elapsed_days[1] - elapsed_days[0] == pytest.approx(1 / 24, abs=0.0001)


def test_unknown_gender_still_delivers_hourly_facts_on_every_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, protocol, outputs = invoke(
        "bazi_hourly_timing",
        dict(
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            birth_hour=10,
            gender="未知",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
            analysis_year=2026,
            analysis_month=10,
            analysis_day=20,
            analysis_hour=12,
        ),
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        hour = output["liushi_info"]
        assert hour["branch"] == "午"
        assert hour["pillar"] == hour["stem"] + hour["branch"]
        assert output["analysis_calendar"]["analysis_date_context"]


def test_removed_rollover_switch_is_rejected_on_every_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, protocol, outputs = invoke(
        "lunar_calendar_time",
        {"date": "2026-10-20", "time": "23:30", "after23_new_day": False},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 422 and code == 2 and protocol.is_error
    assert outputs[0]["error_code"] == outputs[2]["error_code"] == "validation_error"
    assert outputs[1]["error_code"] == "usage_error"


@pytest.mark.parametrize(
    "tool,inputs,canonical,removed",
    [
        ("solar_terms_for_year", {"year": 2028}, "jieqi_year", {"jieqi24"}),
        (
            "lunar_calendar_time",
            {"date": "2028-04-01", "time": "09:00:00"},
            "timeGanZi",
            {"year", "time"},
        ),
        ("gua_meanings", {"name": ["111", "000"]}, "results", {"111", "000"}),
    ],
)
def test_canonical_helper_results_agree_without_duplicate_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tool: str,
    inputs,
    canonical: str,
    removed,
) -> None:
    response, code, protocol, outputs = invoke(tool, inputs, monkeypatch, capsys)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert all(removed.isdisjoint(output) for output in outputs)
    assert outputs[0][canonical] == outputs[1][canonical] == outputs[2][canonical]


def test_compact_solar_term_year_preserves_requested_filter(surface_calls) -> None:
    response, protocol, code, cli = surface_calls(
        SPECS["jieqi_year"],
        {"year": 2028, "jieqis": ["春分", "未知节气", "冬至"]},
        projection={"detail": "compact", "response_char_limit": 8192},
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    http = response.json()
    assert business(http) == business(cli) == business(protocol.structured_content)
    assert [term["name"] for term in http["selected_jieqi"]] == ["春分", "冬至"]
    assert all(term["datetime_with_offset"] for term in http["selected_jieqi"])
    assert http["warnings"] == ["未识别的节气名称：未知节气"]
    assert "jieqi_year" not in http and "result_delivery" not in http


def test_birth_strength_uses_one_assessment_on_every_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    response, code, protocol, outputs = invoke(
        "bazi_birth_chart",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "gender": "男",
            "use_true_solar_time": False,
        },
        monkeypatch,
        capsys,
        detail="audit",
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    births = [output["bazi_birth"] for output in outputs]
    assert births[0] == births[1] == births[2]
    for birth in births:
        assert "element_distribution_adjusted" not in birth
        assert "element_relations" not in birth
        assessment = birth["day_master"]["assessment"]
        assert set(assessment["effective_elements"]) == {"木", "火", "土", "金", "水"}
        assert assessment["method_id"] == "season_root_revelation_relations_v12"
        assert assessment["seasonal_phases"] == {
            "木": "休",
            "火": "旺",
            "土": "相",
            "金": "死",
            "水": "囚",
        }
