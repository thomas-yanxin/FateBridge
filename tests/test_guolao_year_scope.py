"""Year decisions do not require irrelevant month/day/hour calendar layers."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import almanac
from fatebridge.core import calendar as calendar_module
from fatebridge.core import guolao, guolao_monthly, guolao_timing
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.mcp_server import create_mcp_app
from tests.fixtures.surface_payloads import astro_payload
from tests.test_guolao_depth import chart

AS_OF = "2026-10-22T12:00:00+08:00"
TARGET = datetime(2, 6, 1, tzinfo=timezone.utc)
EARLY = {
    **astro_payload(),
    "birth_year": 1,
    "birth_month": 1,
    "birth_day": 1,
    "birth_hour": 0,
    "birth_minute": 0,
    "birth_timezone": "UTC",
    "birth_longitude": -180.0,
    "birth_latitude": 0.0,
    "use_true_solar_time": True,
}


@pytest.mark.parametrize(
    "month,day,hour,expected",
    [(1, 1, 0, ("庚", "申")), (6, 1, 12, ("辛", "酉")), (12, 31, 23, ("辛", "酉"))],
)
@pytest.mark.parametrize("solar", [False, True])
def test_real_early_year_chart_uses_existing_year_policy_without_adjacent_year_zero(
    month, day, hour, expected, solar
):
    result = chart(
        **{
            **EARLY,
            "birth_month": month,
            "birth_day": day,
            "birth_hour": hour,
            "use_true_solar_time": solar,
        }
    )
    assert "guolao" in result, result
    g = result["guolao"]
    gods = g["god_positions"]
    assert (gods["year_stem"], gods["year_branch"]) == expected
    assert (
        "lichun_research_policy_not_source_adjudicated" in gods["year_boundary_basis"]
    )
    assert len(g["bodies"]) == 11
    assert not g["validation"]["classical_acceptance_passed"]
    if solar and month == 1:
        assert (
            g["profile"]["apparent_solar_clock"]["display_status"]
            == "outside_datetime_year_range"
        )
        assert g["life_palace"]["birth_clock"] is None
        # The known solar phase remains usable; it is not a civil-hour fallback.
        assert g["life_palace"]["birth_hour_branch"] == "午"


def test_irrelevant_month_failure_cannot_invalidate_natal_or_target_year(monkeypatch):
    def unavailable_month(*args, **kwargs):
        raise OverflowError("unrepresentable neighbouring month-year")

    monkeypatch.setattr(calendar_module, "get_bazi_month_context", unavailable_month)
    result = chart(analysis_datetime=datetime(2027, 6, 1, tzinfo=timezone.utc))
    assert "guolao" in result, result
    assert result["guolao"]["god_positions"]["year_stem"] == "庚"
    assert result["guolao"]["timing"]["small_limit"]["target_year_stem"] == "丁"


def test_explicit_early_target_keeps_valid_year_core_and_real_sky():
    result = chart(**EARLY, analysis_datetime=TARGET)
    assert "guolao" in result, result
    g = result["guolao"]
    limit = g["timing"]["small_limit"]
    assert (limit["target_year_stem"], limit["target_year_branch"]) == ("壬", "戌")
    assert limit["life_branch"] == g["life_palace"]["branch"]
    assert len(g["timing"]["transit_bodies"]) == 11
    assert "month_limit" not in g["timing"]


@pytest.mark.parametrize("layer", ["natal", "target"])
def test_year_only_does_not_accept_linear_or_unknown_lichun_boundaries(
    monkeypatch, layer
):
    birth = build_astro_birth_info(**astro_payload(), preserve_instant=True)
    payload = guolao.build_chart(birth)
    original = almanac.get_solar_terms_for_year
    selected_year = 1990 if layer == "natal" else 2027

    def terms(year, timezone_name):
        if year == selected_year:
            return (
                almanac.SolarTerm(
                    "立春",
                    datetime(year, 2, 4, tzinfo=timezone.utc),
                    "",
                    "",
                    resolution_provider="linear_1900_fallback",
                ),
            )
        return original(year, timezone_name)

    monkeypatch.setattr(almanac, "get_solar_terms_for_year", terms)
    with pytest.raises(RuntimeError, match="不能使用线性或未知节气边界"):
        if layer == "natal":
            guolao.build_chart(birth)
        else:
            guolao_timing.enrich_guolao_timing(
                payload, birth, datetime(2027, 6, 1, tzinfo=timezone.utc)
            )


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("offset,expected", [(-3, ("乙", "巳")), (3, ("丙", "午"))])
def test_natal_year_around_independently_published_hko_minute_uses_physical_clock(
    solar, offset, expected
):
    fixture = json.loads(
        (Path(__file__).parent / "data/bazi-timing-hko-2026.json").read_text()
    )
    assert fixture["precision"] == "published_minute"
    published = datetime.fromisoformat(
        next(c["at"] for c in fixture["cases"] if c["term"] == "立春")
    )
    clock = published + timedelta(minutes=offset)
    result = chart(
        birth_year=clock.year,
        birth_month=clock.month,
        birth_day=clock.day,
        birth_hour=clock.hour,
        birth_minute=clock.minute,
        birth_timezone="Asia/Hong_Kong",
        birth_longitude=-180.0,
        birth_latitude=0.0,
        use_true_solar_time=solar,
    )
    gods = result["guolao"]["god_positions"]
    assert (gods["year_stem"], gods["year_branch"]) == expected
    if solar:
        assert (
            datetime.fromisoformat(
                result["guolao"]["profile"]["solar_clock_display"]
            ).day
            == 3
        )


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
def test_optional_unavailable_month_does_not_remove_valid_year_core_or_target_sky(
    basis,
):
    result = chart(**EARLY, analysis_datetime=TARGET, guolao_month_basis=basis)
    assert "guolao" in result, result
    timing = result["guolao"]["timing"]
    monthly = timing["month_limit"]
    assert monthly["status"] == "unassigned_calendar_unavailable"
    assert monthly["branch"] is None
    assert len(timing["transit_bodies"]) == 11
    assert timing["small_limit"]["branch"] is not None
    if basis == "jie_month":
        assert (
            monthly["birth_month"]["unavailable_reason"]
            == "jie_neighbour_calendar_year_outside_datetime_range"
        )
        assert "节月换算范围" in result["interpretation"]["month_limit"]
        assert "农历" not in result["interpretation"]["month_limit"]


@pytest.mark.parametrize("basis", ["jie_month", "chinese_lunar_utc8"])
def test_fixed_utc8_label_overflow_leaves_month_unknown_not_a_default_number(basis):
    context = guolao_monthly.month_context(
        datetime(9999, 12, 31, 23, tzinfo=timezone.utc), basis
    )
    assert context["status"] == "outside_datetime_calendar_range"
    assert context["calendar_datetime"] is None
    assert context["month_number"] is None
    assert context["is_leap_month"] is None
    assert context["unavailable_reason"] == "fixed_utc8_label_outside_datetime_range"


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("unverified ephemeris provider"),
        ValueError("invalid numerical month"),
    ],
)
def test_range_handling_does_not_swallow_unverified_provider_or_numerical_errors(
    monkeypatch, error
):
    def invalid(*args, **kwargs):
        raise error

    monkeypatch.setattr(guolao_monthly, "get_bazi_month_context", invalid)
    with pytest.raises(type(error), match=str(error)):
        guolao_monthly.month_context(
            datetime(2027, 6, 1, tzinfo=timezone.utc), "jie_month"
        )


@pytest.mark.parametrize(
    "basis,leaf",
    [
        (None, False),
        ("jie_month", False),
        ("chinese_lunar_utc8", False),
        ("jie_month", True),
    ],
)
def test_early_native_and_partial_month_roundtrip_real_rest_mcp_cli(
    monkeypatch, capsys, basis, leaf
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {**EARLY, "analysis_datetime": TARGET.isoformat()}
    if basis:
        payload["guolao_month_basis"] = basis
    fields = [
        "person_info",
        "guolao.life_palace",
        "guolao.profile",
        "guolao.god_positions",
        "guolao.timing.small_limit",
        "guolao.timing.transit_bodies",
        "guolao.validation",
        "interpretation",
        "interpretation_evidence",
    ]
    if basis:
        fields += (
            [
                "guolao.timing.month_limit.status",
                "guolao.timing.month_limit.branch",
                "guolao.timing.month_limit.birth_month.unavailable_reason",
            ]
            if leaf
            else ["guolao.timing.month_limit"]
        )
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    rest = TestClient(api.app).post(
        "/api/astro/guolao",
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "astro_guolao_chart", {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    assert not native.is_error, native
    args = ["astro_guolao_chart"]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [rest.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    g = bodies[0]["guolao"]
    assert g["god_positions"]["year_stem"] == "庚"
    assert g["life_palace"]["birth_clock"] is None
    assert not g["validation"]["classical_acceptance_passed"]
    if basis:
        assert g["timing"]["month_limit"]["status"] == "unassigned_calendar_unavailable"
        assert g["timing"]["month_limit"]["branch"] is None
