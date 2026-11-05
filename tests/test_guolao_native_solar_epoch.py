"""Known solar labels must retain genuine non-datetime physical epochs."""

import asyncio
import hashlib
import json
import os
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
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import NativeSolarBirthInfo, build_astro_birth_info
from fatebridge.core.astro.birth_clock import (
    resolve_solar_birth_clock,
    resolve_solar_epoch,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch, utc_from_tt
from fatebridge.core.guolao_epoch import native_utc8_clock
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_guolao_native_frames import fixed_moshier  # noqa:F401

FIXTURE = Path(__file__).parent / "fixtures/guolao-native-solar-epoch-v1"
REFERENCE = json.loads((FIXTURE / "reference-before-implementation.json").read_text())
LEAPS = json.loads((FIXTURE.parent / "western-leap-epoch-reference.json").read_text())
BASES = ["local_mean_solar", "local_apparent_solar"]


def args_for(era, basis):
    return dict(
        birth_year=1 if era == "year0" else 1978,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_longitude=(
            180
            if era == "year0"
            else (
                0 if basis == BASES[0] else REFERENCE["leap"]["LAT_synthetic_longitude"]
            )
        ),
        birth_latitude=40,
        birth_clock_basis=basis,
    )


def chart(args, **extra):
    return calculate_core_chart_analysis(**args, chart_variant="guolao_chart", **extra)


@pytest.mark.parametrize("era", ["year0", "second60"])
@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("zodiac", [0, 1])
def test_native_birth_uses_physical_axes_and_preserves_the_supplied_hour(
    fixed_moshier, era, basis, solar, zodiac
):
    args = args_for(era, basis)
    result = chart(args, use_true_solar_time=solar, zodiacal=zodiac)
    assert "error" not in result, result
    g = result["guolao"]
    context = g["profile"]["input_clock"]
    native = g["profile"]["native_time_axis"]
    assert native["datetime_representable"] is False
    assert context["carrier_datetime"] is None
    assert context["nominal_utc_replay_difference_seconds"] is None
    assert abs(context["native_UT1_replay_difference_seconds"]) <= 0.0002
    assert context["physical_instant_shifted"] is False
    assert result["person_info"]["birth_timezone"] is None
    assert result["person_info"]["birth_datetime"] == context["input_wall_datetime"]
    assert g["life_palace"]["birth_hour_branch"] == "子"
    assert g["validation"]["full_marks_established"] is False
    assert "转换载体为None" not in result["interpretation"]["input_clock"]
    assert "原生TT/UT1" in result["interpretation"]["input_clock"]
    assert "时区：None" not in result["snapshot_text"]
    if era == "year0":
        assert result["person_info"]["utc_datetime"].startswith("0000-12-31T12:")
        assert native["utc_is_leap_second"] is False
        assert g["god_positions"]["native_year_comparison"]["year"] == 0
        if basis == BASES[0]:
            assert g["profile"]["julian_day_ut1"] == float(
                Fraction(REFERENCE["year_zero_lmt"]["expected_UT1_jd"])
            )
    else:
        assert result["person_info"]["utc_datetime"].startswith("1977-12-31T23:59:60.")
        assert native["utc_is_leap_second"] is True
        # This synthetic label is bounded by the retained IERS leap TT interval.
        assert (
            Fraction(REFERENCE["leap"]["start_TT_JD_exact"])
            <= Fraction(g["profile"]["julian_day_tt"])
            < Fraction(REFERENCE["leap"]["end_TT_JD_exact"])
        )
        assert g["god_positions"]["native_year_comparison"]["year"] == 1977
    if basis == BASES[0] and not solar:
        assert context["input_label_and_forward_hour_differ"] is None


@pytest.mark.parametrize("era", ["year0", "second60"])
@pytest.mark.parametrize("basis", BASES)
def test_native_opt_in_cannot_masquerade_as_a_datetime(fixed_moshier, era, basis):
    args = args_for(era, basis)
    with pytest.raises(ValueError, match="datetime"):
        build_astro_birth_info(**args)
    birth = build_astro_birth_info(**args, allow_native_solar_epoch=True)
    assert isinstance(birth, NativeSolarBirthInfo)
    with pytest.raises(ValueError, match="no UTC datetime"):
        _ = birth.physical_datetime
    with pytest.raises(ValueError, match="civil instant"):
        replace(birth, recorded_datetime=datetime(2000, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="preserve the solar input"):
        replace(birth, local_datetime=datetime(1500, 1, 1, tzinfo=timezone.utc))


def test_year0_natal_sky_equals_an_existing_representable_fixed_offset_carrier(
    fixed_moshier,
):
    args = args_for("year0", BASES[0])
    native = chart(args)
    civil_args = {k: v for k, v in args.items() if k != "birth_clock_basis"}
    civil = chart({**civil_args, "birth_timezone": "+12:00"})
    assert "error" not in native and "error" not in civil
    for key in ["bodies", "mansion_boundaries"]:
        assert native["guolao"][key] == civil["guolao"][key]
    assert (
        native["guolao"]["profile"]["julian_day_tt"]
        == civil["guolao"]["profile"]["julian_day_tt"]
    )


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("era", ["year0", "second60"])
@pytest.mark.parametrize("month", [None, "jie_month", "chinese_lunar_utc8"])
def test_native_target_sky_clears_birth_epoch_and_months_use_real_date_or_tt(
    fixed_moshier, basis, era, month
):
    target = datetime(2027, 6, 1, tzinfo=timezone.utc)
    result = chart(
        args_for(era, basis), analysis_datetime=target, guolao_month_basis=month
    )
    assert "error" not in result, result
    g = result["guolao"]
    assert g["timing"]["profile"]["julian_day_tt"] != g["profile"]["julian_day_tt"]
    assert g["timing"]["calendar_datetime"] == target.isoformat()
    assert g["timing"]["target_order_evidence"]["nominal_TT_difference_seconds"] > 0
    sky, _ = runtime.ephemeris_call(
        "calc",
        g["timing"]["profile"]["julian_day_tt"],
        runtime.swe.SUN,
        runtime.swe.FLG_SWIEPH,
    )
    sun = next(b for b in g["timing"]["transit_bodies"] if b["id"] == "Sun")
    assert abs(sun["longitude"] - sky[0]) < 1e-10
    if month is not None:
        m = g["timing"]["month_limit"]
        if era == "year0":
            assert m["status"] == "unassigned_calendar_unavailable"
            assert m["branch"] is None and m["birth_month"]["month_number"] is None
        else:
            b = m["birth_month"]
            assert m["status"] == "research_partial"
            assert b["calendar_datetime"].startswith("1978-01-01T07:59:60.")
            if month == "jie_month":
                assert b["month_number"] == 11
                assert b["comparison_basis"] == "primary_TT_not_a_datetime_surrogate"
            else:
                assert (
                    b["calendar_lookup_basis"]
                    == "unique_UTC8_date_only_no_epoch_substitution"
                )


@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_native_target_numerical_order_ties_are_not_silently_accepted(
    fixed_moshier, shift
):
    target = datetime(1, 1, 1, 1, tzinfo=timezone(timedelta(hours=13))) + timedelta(
        microseconds=shift
    )
    result = chart(args_for("year0", BASES[0]), analysis_datetime=target)
    assert "数值区间" in result["error"] and "guolao" not in result


@pytest.mark.parametrize("hour,offset,accepted", [(0, 14, False), (1, 12, True)])
def test_native_target_UTC_year0_orders_by_physical_TT(
    fixed_moshier, hour, offset, accepted
):
    target = datetime(1, 1, 1, hour, tzinfo=timezone(timedelta(hours=offset)))
    result = chart(args_for("year0", BASES[0]), analysis_datetime=target)
    if accepted:
        assert "error" not in result, result
        assert result["guolao"]["timing"]["calendar_datetime"].startswith(
            "0000-12-31T13:"
        )
    else:
        assert "不能早于" in result["error"] and "guolao" not in result


@pytest.mark.parametrize(
    "row", [r for r in LEAPS["controls"] if r["seconds_from_leap_start"] == "0.25"]
)
def test_reused_27_published_leaps_reach_guolao_without_adjacent_second_substitution(
    fixed_moshier, row
):
    # Published TT is independent. UT1 and the synthetic input longitude are
    # model-derived controls, not 27 new observed celestial epochs.
    tt = float(row["jd_tt"])
    ut1 = tt
    for _ in range(4):
        ut1 = tt - runtime.ephemeris_call("deltat_ex", ut1, runtime.swe.FLG_SWIEPH)
    utc_date = datetime.fromisoformat(row["utc_label"].split("T")[0]) + timedelta(
        days=1
    )
    wall_jd = utc_date.toordinal() + 1721424.5
    lon = (wall_jd - ut1) * 360
    result = chart(
        dict(
            birth_year=utc_date.year,
            birth_month=utc_date.month,
            birth_day=utc_date.day,
            birth_hour=0,
            birth_longitude=lon,
            birth_latitude=40,
            birth_clock_basis=BASES[0],
        )
    )
    assert "error" not in result, result
    profile = result["guolao"]["profile"]
    assert profile["native_time_axis"]["utc_is_leap_second"]
    assert (
        abs(profile["julian_day_tt"] - tt) * 86400
        <= REFERENCE["numerical_threshold_seconds"]
    )
    assert profile["utc_datetime"][:17] == row["utc_label"][:17]
    assert 60 <= float(profile["utc_datetime"][17:-6]) < 61


def test_extended_future_epoch_reports_frozen_leap_assumption(fixed_moshier):
    jd = float(Fraction(REFERENCE["upper_lmt"]["expected_UT1_jd"]))
    epoch = PhysicalEpoch.from_ut1(jd)
    assert epoch.utc_datetime is None and epoch.utc_label.startswith("+010000-")
    assert epoch.time.future_leap_seconds_assumed_unchanged is True
    assert utc_from_tt(epoch.time.jd_tt)[0] == epoch.utc_label


def test_strict_projection_keeps_native_axes_and_absent_datetime_carrier(
    fixed_moshier, monkeypatch
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        "/api/astro/guolao",
        json=args_for("year0", BASES[0]),
        params=[
            ("fields", "guolao.profile.native_time_axis.utc_label"),
            ("fields", "guolao.profile.input_clock.carrier_datetime"),
            ("fields", "guolao.god_positions.native_year_comparison.year"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    assert response.status_code == 200, response.text
    g = response.json()["guolao"]
    assert (
        g["profile"]["native_time_axis"]["utc_label"]
        == REFERENCE["year_zero_lmt"]["expected_UT1_label"]
    )
    assert g["profile"]["input_clock"]["carrier_datetime"] is None
    assert g["god_positions"]["native_year_comparison"]["year"] == 0


@pytest.mark.parametrize("poison", ["TT", "UTC_label", "version", "source"])
def test_native_source_or_epoch_disagreement_cannot_publish_a_chart(
    fixed_moshier, poison
):
    birth = build_astro_birth_info(
        **args_for("second60", BASES[1]), allow_native_solar_epoch=True
    )
    assert isinstance(birth, NativeSolarBirthInfo) and birth.native_epoch is not None
    if poison == "TT":
        epoch = birth.native_epoch
        changed = replace(epoch.time, jd_tt=epoch.time.jd_tt + 1 / 86400)
        birth = replace(birth, native_epoch=replace(epoch, time=changed))
    elif poison == "UTC_label":
        birth = replace(
            birth,
            native_epoch=replace(
                birth.native_epoch, utc_label="1978-01-01T00:00:00+00:00"
            ),
        )
    else:
        receipt = json.loads(json.dumps(birth.clock_conversion))
        if poison == "version":
            receipt["swisseph_version"] = "unverified"
        else:
            receipt["solar_source_comparison"]["physical_ephemeris_sources"] = []
        birth = replace(birth, clock_conversion=receipt)
    with pytest.raises(EphemerisSourceError) as raised:
        guolao.build_chart(birth)
    assert raised.value.reason == "birth_clock_source_mismatch"


@pytest.mark.parametrize("month", [None, "jie_month", "chinese_lunar_utc8"])
def test_fractional_UTC_adjustment_keeps_primary_axes_without_inventing_a_label(
    fixed_moshier, month
):
    # Reuse the pre-existing published1964 adjustment control. The longitude
    # is a supplementary model-derived input, not a new measured solar label.
    date = datetime(1964, 4, 1)
    wall_jd = date.toordinal() + 1721424.5
    tt = wall_jd + (2.983730 + 32.184 - 0.05) / 86400
    ut1 = tt
    for _ in range(4):
        ut1 = tt - runtime.ephemeris_call("deltat_ex", ut1, runtime.swe.FLG_SWIEPH)
    args = dict(
        birth_year=1964,
        birth_month=4,
        birth_day=1,
        birth_hour=0,
        birth_longitude=(wall_jd - ut1) * 360,
        birth_latitude=40,
        birth_clock_basis=BASES[0],
    )
    result = chart(
        args,
        analysis_datetime=datetime(2027, 6, 1, tzinfo=timezone.utc),
        guolao_month_basis=month,
    )
    assert "error" not in result, result
    assert result["person_info"]["utc_datetime"] is None
    assert result["guolao"]["profile"]["native_time_axis"]["label_status"] == (
        "unrepresentable_historical_fractional_UTC_adjustment"
    )
    assert "没有唯一UTC标签" in result["interpretation"]["input_clock"]
    if month is not None:
        m = result["guolao"]["timing"]["month_limit"]
        birth_month = m["birth_month"]
        assert birth_month["instant_utc"] is None
        assert birth_month["calendar_datetime"] is None
        if month == "jie_month":
            # Independently frozen HKO1964 calendar: April1 precedes April5
            # Qingming. The original unassigned row remains in the archive.
            assert m["status"] == "research_partial" and m["branch"] is not None
            assert birth_month["month_number"] == 2
            assert birth_month["month_branch"] == "卯"
            assert birth_month["term_search_year"] == 1964
        else:
            # HKO1964: the proved UTC+08 date is lunar February19. The
            # original unassigned response remains in the frozen baseline.
            assert m["status"] == "research_partial" and m["branch"] is not None
            assert birth_month["month_number"] == 2
            assert birth_month["lunar_day"] == 19
            assert birth_month["calendar_date"] == "1964-04-01"
            assert (
                birth_month["calendar_date_evidence"]["utc_clock_label_assigned"]
                is False
            )


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize(
    "era,basis,failed",
    [(e, b, False) for e in ["year0", "second60"] for b in BASES]
    + [(e, BASES[1], True) for e in ["year0", "second60"]],
)
def test_native_three_surface_full_results_and_failures_agree(
    fixed_moshier,
    monkeypatch,
    capsys,
    record_testsuite_property,
    tool,
    era,
    basis,
    failed,
):
    if failed:
        native = guolao.runtime.ephemeris_call

        def radians(operation, *a, **kw):
            if (
                operation == "calc"
                and a[1] == runtime.swe.SUN
                and a[2] & runtime.swe.FLG_EQUATORIAL
            ):
                a = list(a)
                a[2] |= runtime.swe.FLG_RADIANS
            return native(operation, *a, **kw)

        monkeypatch.setattr(guolao.runtime, "ephemeris_call", radians)
    spec = next(s for s in CATALOG if s.key == tool)
    payload = args_for(era, basis)
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    options = dict(
        as_of="2026-10-25T00:00:00+08:00",
        include_snapshot_text=False,
        response_char_limit=0,
    )
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
    assert response.status_code == (503 if failed else 200), response.text

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )
            assert result.is_error is failed
            return (
                json.loads(result.content[0].text)
                if failed
                else result.structured_content
            )

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
    capsys.readouterr()
    assert run(argv) == int(failed)
    cli = json.loads(capsys.readouterr().out)
    wire = dict(
        rest_status=response.status_code, rest=response.json(), mcp=mcp, cli=cli
    )
    record_testsuite_property(
        f"native-wire-{tool}-{era}-{basis}-{failed}",
        json.dumps(wire, ensure_ascii=False),
    )
    if folder := os.environ.get("FATEBRIDGE_NATIVE_SOLAR_TEST_WIRE_DIR"):
        path = Path(folder) / f"{tool}-{era}-{basis}-{failed}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(wire, stream, ensure_ascii=False)
    values = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [response.json(), mcp, cli]
    ]
    if failed:
        assert values[2] == {**values[0], "status_code": response.status_code}
        assert values[1] == {**values[2], "operation": spec.operation_label_zh}
        assert "guolao" not in values[0]
    else:
        assert values[0] == values[1] == values[2]
        assert values[0]["guolao"]["profile"]["input_clock"]["carrier_datetime"] is None
