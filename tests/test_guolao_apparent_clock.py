"""USNO definition, independent JPL operands, exact boundaries and real surfaces."""

import asyncio
import csv
import hashlib
import io
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import guolao
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao_clock import METHOD_ID, apparent_solar_clock
from fatebridge.mcp_server import create_mcp_app
from tests.test_guolao_depth import chart

FIXTURE = Path(__file__).parent / "fixtures/guolao-apparent-clock-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
CASE = REFERENCE["boundary_case"]
AS_OF = "2026-10-22T12:00:00+08:00"


def source_rows(filename):
    result = json.loads((FIXTURE / filename).read_text())["result"]
    body = result.split("$$SOE\n")[1].split("$$EOE")[0]
    return list(csv.reader(io.StringIO(body)))


@pytest.mark.parametrize("asset", REFERENCE["assets"])
def test_independently_fetched_jpl_raw_bytes_are_unchanged(asset):
    raw = (FIXTURE / asset["path"]).read_bytes()
    assert len(raw) == asset["bytes"]
    assert hashlib.sha256(raw).hexdigest() == asset["sha256"]


@pytest.mark.parametrize("index", [0, 1])
def test_solar_clock_against_independent_jpl_ra_and_greenwich_sidereal_time(index):
    sun = source_rows("geocentric_sun.json")[index]
    sidereal = source_rows("greenwich_sidereal.json")[index]
    # Preserve printed decimal precision, and derive the external oracle from
    # JPL operands under the USNO definition rather than FateBridge output.
    sun_ra = Fraction(sun[3].strip())
    gast_hours = Fraction(sidereal[3].strip())
    hours = (12 + gast_hours + (Fraction(CASE["birth_longitude"]) - sun_ra) / 15) % 24
    result = chart(**{**CASE, "birth_minute": index})
    clock = result["guolao"]["profile"]["apparent_solar_clock"]
    phase = Fraction(clock["apparent_day_fraction_exact"]) * 24
    delta_hours = (phase - hours + 12) % 24 - 12
    assert (
        abs(float(delta_hours) * 3600)
        < REFERENCE["external_solar_clock_tolerance_seconds"]
    )
    assert (
        abs(clock["sun_apparent_right_ascension"] - float(sun_ra)) * 3600
        < REFERENCE["coordinate_tolerance_arcsec"]
    )
    assert (
        abs(clock["greenwich_apparent_sidereal_degrees"] - float(gast_hours * 15))
        * 3600
        < REFERENCE["coordinate_tolerance_arcsec"]
    )
    assert 1 < hours < 2
    assert clock["birth_hour_branch"] == REFERENCE["external_hour_angle_branch"] == "丑"
    assert result["guolao"]["life_palace"]["branch"] == "辰"
    assert not clock["physical_time_accuracy_certified"]
    assert (
        clock["sun_apparent_right_ascension"]
        == next(b for b in result["guolao"]["bodies"] if b["id"] == "Sun")[
            "right_ascension"
        ]
    )
    assert clock["julian_day_ut1"] == result["guolao"]["profile"]["julian_day_ut1"]


def manual_clock(**changes):
    # An algebraic Sun-at-meridian case, not an external astronomical oracle.
    return apparent_solar_clock(
        **{
            "julian_day_ut1": 2451545.0,
            "sun_right_ascension": 0.0,
            "greenwich_apparent_sidereal_degrees": 0.0,
            "longitude": 0.0,
            "civil_datetime": datetime(2000, 1, 1, 12, tzinfo=timezone.utc),
            **changes,
        }
    )


@pytest.mark.parametrize("hour", list(range(1, 24, 2)))
def test_all_twelve_half_open_hour_boundaries_use_exact_supplied_doubles(hour):
    longitude = float((hour - 12) * 15)
    before = manual_clock(longitude=math.nextafter(longitude, -math.inf))
    at = manual_clock(longitude=longitude)
    after = manual_clock(longitude=math.nextafter(longitude, math.inf))
    branches = "子丑寅卯辰巳午未申酉戌亥"
    assert before["birth_hour_branch"] == branches[((hour - 1) // 2) % 12]
    assert (
        at["birth_hour_branch"]
        == after["birth_hour_branch"]
        == branches[((hour + 1) // 2) % 12]
    )
    assert Fraction(at["hour_boundary_distance_seconds_exact"]) == 0
    assert Fraction(before["hour_boundary_distance_seconds_exact"]) > 0
    assert Fraction(after["hour_boundary_distance_seconds_exact"]) > 0


def test_solar_noon_midnight_east_west_dateline_and_date_carry():
    noon = manual_clock()
    assert noon["display"] == "2000-01-01T12:00:00"
    assert noon["birth_hour_branch"] == "午"
    assert noon["equation_of_time_seconds"] == 0
    west = manual_clock(longitude=-180.0)
    east = manual_clock(longitude=180.0)
    assert west["display"] == "2000-01-01T00:00:00"
    assert east["display"] == "2000-01-02T00:00:00"
    assert west["birth_hour_branch"] == east["birth_hour_branch"] == "子"
    assert west["solar_day_offset_from_civil"] == 0
    assert east["solar_day_offset_from_civil"] == 1
    assert east["total_correction_seconds"] == 43200
    assert west["total_correction_seconds"] == -43200


def test_equivalent_civil_offsets_change_correction_but_not_solar_label_or_hour():
    utc = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    a = manual_clock(civil_datetime=utc)
    b = manual_clock(civil_datetime=utc.astimezone(timezone(timedelta(hours=8))))
    for key in ("display", "birth_hour_branch", "apparent_day_fraction_exact"):
        assert a[key] == b[key]
    assert b["total_correction_seconds"] - a["total_correction_seconds"] == -28800
    assert datetime.fromisoformat(a["display"]).tzinfo is None


@pytest.mark.parametrize(
    "ut1,ra,civil,longitude,branch",
    [
        (1721425.5, 180.0, datetime(1, 1, 1, tzinfo=timezone.utc), -180.0, "午"),
        (5373484.0, 0.0, datetime(9999, 12, 31, 12, tzinfo=timezone.utc), 180.0, "子"),
    ],
)
def test_unrepresentable_solar_date_does_not_replace_known_solar_hour_with_civil(
    ut1, ra, civil, longitude, branch
):
    # Helper scope only: other native calendar/ephemeris year limits remain.
    result = manual_clock(
        julian_day_ut1=ut1,
        sun_right_ascension=ra,
        civil_datetime=civil,
        longitude=longitude,
    )
    assert result["display"] is None
    assert result["display_status"] == "outside_datetime_year_range"
    assert result["birth_hour_branch"] == branch


@pytest.mark.parametrize(
    "changes",
    [
        {"julian_day_ut1": float("nan")},
        {"greenwich_apparent_sidereal_degrees": float("inf")},
        {"greenwich_apparent_sidereal_degrees": 360.0},
        {"sun_right_ascension": -1.0},
        {"sun_right_ascension": 360.0},
        {"sun_right_ascension": True},
        {"longitude": 180.00001},
        {"longitude": "0"},
        {"civil_datetime": datetime(2000, 1, 1)},
    ],
)
def test_invalid_solar_clock_operands_are_not_normalized_or_guessed(changes):
    with pytest.raises((ValueError, TypeError)):
        manual_clock(**changes)


def test_native_ignores_legacy_solar_display_and_keeps_sky_and_physical_instant():
    birth = build_astro_birth_info(**CASE, preserve_instant=True)
    assert birth.solar_datetime.hour == 0  # old UTC-as-UT1 clock is before 01:00
    old_branch = "子丑寅卯辰巳午未申酉戌亥"[((birth.solar_datetime.hour + 1) // 2) % 12]
    assert old_branch == REFERENCE["baseline_old_hour_branch"]
    on = guolao.build_chart(replace(birth, solar_datetime=None))
    off = guolao.build_chart(
        replace(birth, applied_true_solar=False, solar_datetime=None)
    )
    assert on["guolao"]["life_palace"]["birth_hour_branch"] == "丑"
    for key in ("bodies", "mansion_boundaries", "conditions"):
        assert on["guolao"][key] == off["guolao"][key]
    for key in ("angles", "houses", "planets"):
        assert on[key] == off[key]
    assert on["person_info"]["utc_datetime"] == off["person_info"]["utc_datetime"]
    assert on["guolao"]["profile"]["ruleset_id"] == "guolao_research_v7"


def test_trace_reading_and_correction_all_use_returned_clock_and_keep_acceptance_false():
    result = chart(**CASE, analysis_datetime=datetime(2027, 6, 1, tzinfo=timezone.utc))
    g = result["guolao"]
    clock = g["profile"]["apparent_solar_clock"]
    assert (
        g["life_palace"]["birth_clock"]
        == clock["display"]
        == g["profile"]["solar_clock_display"]
    )
    trace = next(
        t for t in g["rule_trace"] if t["rule_id"] == "source_life_palace_hour_count"
    )
    assert trace["inputs"]["apparent_solar_clock"] == clock
    assert trace["inputs"]["birth_hour_branch"] == clock["birth_hour_branch"]
    assert result["person_info"]["true_solar"]["correction_minutes"] == round(
        clock["total_correction_seconds"] / 60, 4
    )
    assert "同次太阳赤经与估算UT1" in result["interpretation"]["core_identity"]
    assert "生时丑" in result["interpretation"]["core_identity"]
    assert g["timing"]["small_limit"]["life_branch"] == "辰"
    assert not g["validation"]["classical_acceptance_passed"]
    assert not clock["classical_clock_mapping_accepted"]
    assert g["validation"]["real_world_prediction_status"] == "not_tested"
    assert g["life_palace"]["longitude"] is None


@pytest.mark.parametrize(
    "solar,leaf_projection", [(False, False), (True, False), (True, True)]
)
def test_boundary_clock_and_reading_agree_on_actual_rest_native_mcp_and_cli(
    monkeypatch, capsys, solar, leaf_projection
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {**CASE, "use_true_solar_time": solar}
    fields = [
        "person_info",
        "guolao.profile",
        "guolao.life_palace",
        "guolao.rule_trace",
        "guolao.validation",
        "interpretation",
        "interpretation_evidence",
    ]
    if leaf_projection:
        fields.remove("guolao.profile")
        fields.extend(
            [
                "guolao.profile.apparent_solar_clock.method_id",
                "guolao.profile.apparent_solar_clock.birth_hour_branch",
                "guolao.profile.apparent_solar_clock.sun_apparent_right_ascension",
            ]
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
    assert g["life_palace"]["birth_hour_branch"] == ("丑" if solar else "子")
    if solar:
        assert g["profile"]["apparent_solar_clock"]["method_id"] == METHOD_ID
    else:
        assert g["profile"].get("apparent_solar_clock") is None
