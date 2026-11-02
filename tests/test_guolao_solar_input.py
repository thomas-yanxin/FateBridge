"""Explicit solar labels must not become a silently recorded UTC birth hour."""

import asyncio
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import guolao
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroGuolaoRequest,
    AstroIndiaRequest,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import astrology
from fatebridge.services.tool_catalog import CATALOG
from tests.test_guolao_native_frames import fixed_moshier  # noqa:F401

FIXTURE = Path(__file__).parent / "fixtures/guolao-solar-input-integration-v1"
CASES = [
    dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_longitude=10,
        birth_latitude=53.55,
    ),
    dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=1,
        birth_minute=0,
        birth_second=30,
        birth_microsecond=123456,
        birth_longitude=10,
        birth_latitude=40,
    ),
]
SOLAR_REFERENCE = json.loads(
    (FIXTURE.parent / "jyotish-solar-input-reference.json").read_text()
)


def chart(args, **extra):
    return astrology.calculate_core_chart_analysis(
        **args, chart_variant="guolao_chart", **extra
    )


def test_prechange_reference_and_sdk_wrong_hour_are_retained():
    ref = json.loads((FIXTURE / "reference-before-implementation.json").read_text())
    root = Path(__file__).parents[1]
    for n, h in ref["source_assets_sha256"].items():
        assert hashlib.sha256((root / n).read_bytes()).hexdigest() == h
    rows = json.loads((FIXTURE / "before-input-probes.json").read_text())["cases"]
    assert len(rows) == 4 and all("error" in r["public"] for r in rows)
    assert all(
        r["sdk"]["guolao"]["life_palace"]["birth_hour_branch"] == "亥" for r in rows
    )
    assert ref["historical_lmt_hand_reference"]["input_hour"] == "子"


@pytest.mark.parametrize("row", SOLAR_REFERENCE["cases"])
def test_reused_independent_clock_labels_preserve_three_epochs_and_sun(
    fixed_moshier, row
):
    wall = datetime.fromisoformat(row["input_wall_datetime"])
    value = chart(
        dict(
            birth_year=wall.year,
            birth_month=wall.month,
            birth_day=wall.day,
            birth_hour=wall.hour,
            birth_minute=wall.minute,
            birth_second=wall.second,
            birth_microsecond=wall.microsecond,
            birth_longitude=row["longitude"],
            birth_latitude=0,
        ),
        birth_clock_basis=row["basis"],
    )
    assert "error" not in value, value
    actual = datetime.fromisoformat(value["person_info"]["utc_datetime"])
    assert abs((actual - datetime.fromisoformat(row["utc"])).total_seconds()) < (
        SOLAR_REFERENCE["utc_tolerance_seconds"]
    )
    sun = next(b for b in value["guolao"]["bodies"] if b["id"] == "Sun")
    error = abs((sun["right_ascension"] - row["sun_ra_degrees"] + 180) % 360 - 180)
    assert error * 3600 < SOLAR_REFERENCE["sky_tolerance_arcseconds"]


@pytest.mark.parametrize("args", CASES, ids=["historical", "modern"])
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("zodiac", [0, 1])
def test_solar_input_epoch_hour_and_declared_clock_metadata(
    fixed_moshier, args, basis, solar, zodiac
):
    result = chart(
        args, birth_clock_basis=basis, use_true_solar_time=solar, zodiacal=zodiac
    )
    assert "error" not in result, result
    g = result["guolao"]
    ctx = g["profile"]["input_clock"]
    life = g["life_palace"]
    assert ctx["input_clock_basis"] == basis and ctx["true_solar_requested"] is solar
    assert ctx["physical_instant_shifted"] is False
    assert result["person_info"]["birth_timezone"] is None
    assert result["person_info"]["birth_datetime"] == ctx["input_wall_datetime"]
    assert result["person_info"]["utc_datetime"] == ctx["converted_utc"]
    assert ctx["classical_clock_mapping_accepted"] is False
    assert abs(ctx["same_natal_sky_label_residual_seconds"]) <= 0.0002
    if basis == "local_apparent_solar" or not solar:
        assert life["birth_hour_branch"] == (
            "子" if args["birth_year"] == 1879 else "丑"
        )
        assert life["clock_basis"] == "recorded_" + basis + "_clock"
        assert ctx["additional_correction_to_input_seconds"] == 0
    else:
        assert (
            life["birth_hour_branch"]
            == g["profile"]["apparent_solar_clock"]["birth_hour_branch"]
        )
    assert "民用钟时" not in result["interpretation"]["core_identity"]
    assert "不代表原记录采用UTC民用时区" in result["interpretation"]["input_clock"]
    assert "时区：None" not in result["snapshot_text"]
    assert g["validation"]["full_marks_established"] is False


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_equivalent_civil_carrier_has_identical_sky_not_a_borrowed_hour(
    fixed_moshier, basis
):
    args = CASES[0]
    birth = build_astro_birth_info(**args, birth_clock_basis=basis)
    result = chart(args, birth_clock_basis=basis)
    t = birth.require_utc_datetime
    civil = chart(
        dict(
            birth_year=t.year,
            birth_month=t.month,
            birth_day=t.day,
            birth_hour=t.hour,
            birth_minute=t.minute,
            birth_second=t.second,
            birth_microsecond=t.microsecond,
            birth_timezone="UTC",
            birth_longitude=10,
            birth_latitude=53.55,
        )
    )
    assert "error" not in result and "error" not in civil
    for key in ["bodies", "mansion_boundaries"]:
        assert result["guolao"][key] == civil["guolao"][key]
    assert (
        result["guolao"]["profile"]["julian_day_tt"]
        == civil["guolao"]["profile"]["julian_day_tt"]
    )
    assert result["guolao"]["life_palace"]["birth_hour_branch"] == "子"
    assert civil["guolao"]["life_palace"]["birth_hour_branch"] == "亥"


def test_lmt_apparent_preference_changes_hour_without_changing_the_epoch(fixed_moshier):
    args = {**CASES[1], "birth_second": 0, "birth_microsecond": 0}
    ordinary = chart(args, birth_clock_basis="local_mean_solar")
    apparent = chart(
        args, birth_clock_basis="local_mean_solar", use_true_solar_time=True
    )
    assert "error" not in ordinary and "error" not in apparent
    assert ordinary["guolao"]["bodies"] == apparent["guolao"]["bodies"]
    assert (
        ordinary["person_info"]["utc_datetime"]
        == apparent["person_info"]["utc_datetime"]
    )
    assert ordinary["guolao"]["life_palace"]["birth_hour_branch"] == "丑"
    assert apparent["guolao"]["life_palace"]["birth_hour_branch"] == "子"


@pytest.mark.parametrize("microsecond", [0, 1, 999999])
def test_nominal_lat_hour_at_boundary_is_the_given_label_and_forward_residual_is_visible(
    fixed_moshier, microsecond
):
    result = chart(
        {**CASES[1], "birth_second": 0, "birth_microsecond": microsecond},
        birth_clock_basis="local_apparent_solar",
    )
    assert "error" not in result, result
    assert result["guolao"]["life_palace"]["birth_hour_branch"] == "丑"
    c = result["guolao"]["profile"]["input_clock"]
    assert (
        c["hour_from_input_label"]
        and abs(c["same_natal_sky_label_residual_seconds"]) <= 0.0002
    )
    if c["input_label_and_forward_hour_differ"]:
        assert "分侧" in result["interpretation"]["input_clock"]


def test_lat_redundant_display_preference_does_not_apply_another_correction(
    fixed_moshier,
):
    a = chart(CASES[0], birth_clock_basis="local_apparent_solar")
    b = chart(
        CASES[0], birth_clock_basis="local_apparent_solar", use_true_solar_time=True
    )
    for key in ["bodies", "life_palace", "god_positions", "moira_patterns"]:
        assert a["guolao"][key] == b["guolao"][key]
    assert a["person_info"] == b["person_info"]
    assert a["person_info"]["true_solar"]["correction_minutes"] == 0


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
@pytest.mark.parametrize("month", [None, "jie_month", "chinese_lunar_utc8"])
def test_target_and_months_use_the_converted_epoch_and_declared_reference(
    fixed_moshier, basis, month
):
    args = {
        **CASES[1],
        "birth_month": 2,
        "birth_day": 5,
        "birth_hour": 0,
        "birth_minute": 7,
        "birth_second": 0,
        "birth_microsecond": 0,
        "birth_longitude": 180,
    }
    target = datetime(2027, 6, 1, tzinfo=timezone.utc)
    result = chart(
        args,
        birth_clock_basis=basis,
        analysis_datetime=target,
        guolao_month_basis=month,
    )
    assert "error" not in result, result
    timing = result["guolao"]["timing"]
    assert timing["analysis_datetime"] == target.isoformat()
    assert timing["calendar_timezone_role"].startswith("UTC_reference")
    if month:
        birth = timing["month_limit"]["birth_month"]
        assert birth["calendar_datetime"].startswith("2000-02-04T20:")
    converted = datetime.fromisoformat(result["person_info"]["utc_datetime"])
    earlier = chart(
        args,
        birth_clock_basis=basis,
        analysis_datetime=converted - timedelta(microseconds=1),
    )
    assert "不能早于" in earlier["error"]


@pytest.mark.parametrize(
    "policy",
    ["source_solar_days_winter_exclusive", "source_solar_days_winter_inclusive"],
)
@pytest.mark.parametrize(
    "basis,solar", [("local_mean_solar", True), ("local_apparent_solar", False)]
)
def test_solar_day_policies_accept_an_apparent_clock_without_double_correction(
    fixed_moshier, policy, basis, solar
):
    result = chart(
        CASES[0],
        birth_clock_basis=basis,
        use_true_solar_time=solar,
        guolao_seasonal_anchor_policy=policy,
    )
    assert "error" not in result, result
    assert result["guolao"]["profile"]["ruleset_id"] == "guolao_research_v8"


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
@pytest.mark.parametrize("kind", ["year0", "second60"])
def test_original_unrepresented_epochs_now_reach_native_physical_axes(
    fixed_moshier, basis, kind, record_testsuite_property
):
    if kind == "year0":
        args = {
            **CASES[1],
            "birth_year": 1,
            "birth_month": 1,
            "birth_day": 1,
            "birth_hour": 0,
            "birth_minute": 0,
            "birth_second": 0,
            "birth_microsecond": 0,
            "birth_longitude": 180,
        }
    else:
        ref = json.loads(
            (FIXTURE.parent / "western-leap-epoch-reference.json").read_text()
        )["reused_ut1_epoch"]
        args = {
            **CASES[1],
            "birth_year": 1978,
            "birth_month": 1,
            "birth_day": 1,
            "birth_hour": 0,
            "birth_minute": 0,
            "birth_second": 0,
            "birth_microsecond": 0,
            "birth_longitude": (
                0 if basis == "local_mean_solar" else ref["synthetic_lat_longitude"]
            ),
        }
    result = chart(args, birth_clock_basis=basis)
    record_testsuite_property(
        "RESOLVED_NATIVE-" + basis + "-" + kind,
        json.dumps(
            dict(
                input=args,
                result=result,
                successful_calculation=True,
                original_goal_unfinished=True,
            ),
            ensure_ascii=False,
        ),
    )
    assert "error" not in result, result
    context = result["guolao"]["profile"]["input_clock"]
    assert context["carrier_datetime"] is None
    assert context["native_epoch"]["datetime_representable"] is False
    assert context["converted_utc"].startswith(
        "0000-12-31" if kind == "year0" else "1977-12-31T23:59:60."
    )


@pytest.mark.parametrize(
    "policy",
    ["source_solar_days_winter_exclusive", "source_solar_days_winter_inclusive"],
)
def test_solar_day_numerical_boundary_is_not_relabelled_as_an_accepted_result(
    fixed_moshier, policy, record_testsuite_property
):
    args = {
        **CASES[1],
        "birth_hour": 0,
        "birth_minute": 0,
        "birth_second": 0,
        "birth_microsecond": 0,
    }
    result = chart(
        args,
        birth_clock_basis="local_apparent_solar",
        guolao_seasonal_anchor_policy=policy,
    )
    record_testsuite_property(
        "OPEN-midnight-" + policy,
        json.dumps(
            dict(input=args, result=result, successful_calculation=False),
            ensure_ascii=False,
        ),
    )
    assert "error" in result and "夹逼" in result["error"]


@pytest.mark.parametrize("poison", ["library", "missing_identity", "natal_Sun"])
def test_inverse_and_natal_source_or_value_disagreement_never_publishes_a_chart(
    monkeypatch, fixed_moshier, poison
):
    if poison == "natal_Sun":
        native = guolao.runtime.ephemeris_call

        def changed(op, *a, **kw):
            v = native(op, *a, **kw)
            if (
                op == "calc"
                and a[1] == guolao.runtime.swe.SUN
                and a[2] & guolao.runtime.swe.FLG_SPEED
                and a[2] & guolao.runtime.swe.FLG_EQUATORIAL
            ):
                coords, flags = v
                coords = list(coords)
                coords[0] += 0.1
                return tuple(coords), flags
            return v

        monkeypatch.setattr(guolao.runtime, "ephemeris_call", changed)
    else:
        construct = astrology._build_birth_info

        def altered(*a, **kw):
            b = construct(*a, **kw)
            c = json.loads(json.dumps(b.clock_conversion))
            if poison == "library":
                c["swisseph_version"] = "unidentified"
            else:
                c["solar_source_comparison"]["physical_ephemeris_sources"] = []
            return replace(b, clock_conversion=c)

        monkeypatch.setattr(astrology, "_build_birth_info", altered)
    result = chart(CASES[0], birth_clock_basis="local_apparent_solar")
    assert (
        result["error_code"] == "ephemeris_source_inconsistent"
        and "guolao" not in result
    )


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_solar_and_civil_timezone_claims_cannot_be_combined(basis):
    for model, args in [
        (AstroGuolaoRequest, {}),
        (AstroChartPolyRequest, dict(chart_variant="guolao_chart")),
    ]:
        with pytest.raises(ValidationError):
            model(**CASES[0], **args, birth_clock_basis=basis, birth_timezone="UTC")
    with pytest.raises(ValidationError):
        AstroIndiaRequest(**CASES[0], birth_clock_basis=basis, use_true_solar_time=True)


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize(
    "basis,solar,failed",
    [
        (b, s, False)
        for b in ["local_mean_solar", "local_apparent_solar"]
        for s in [False, True]
    ]
    + [(b, False, True) for b in ["local_mean_solar", "local_apparent_solar"]],
)
def test_actual_three_surfaces_preserve_labels_epochs_and_complete_error_mapping(
    monkeypatch,
    fixed_moshier,
    capsys,
    record_testsuite_property,
    tool,
    basis,
    solar,
    failed,
):
    if failed:
        native = guolao.runtime.ephemeris_call

        def radians(op, *a, **kw):
            if (
                op == "calc"
                and a[1] == guolao.runtime.swe.SUN
                and a[2] & guolao.runtime.swe.FLG_EQUATORIAL
            ):
                a = list(a)
                a[2] |= guolao.runtime.swe.FLG_RADIANS
            return native(op, *a, **kw)

        monkeypatch.setattr(guolao.runtime, "ephemeris_call", radians)
    spec = next(s for s in CATALOG if s.key == tool)
    payload = {**CASES[0], "birth_clock_basis": basis, "use_true_solar_time": solar}
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
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params={
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in options.items()
        },
    )
    assert rest.status_code == (503 if failed else 200), rest.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            v = await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )
            assert v.is_error is failed
            return json.loads(v.content[0].text) if failed else v.structured_content

    mcp = asyncio.run(protocol())
    arguments = [spec.tool_name]
    for k, v in payload.items():
        arguments.extend(["--" + k.replace("_", "-"), str(v)])
    arguments.extend(
        [
            "--as-of",
            options["as_of"],
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ]
    )
    capsys.readouterr()
    assert run(arguments) == int(failed)
    cli = json.loads(capsys.readouterr().out)
    wire = dict(rest_status=rest.status_code, rest=rest.json(), mcp=mcp, cli=cli)
    record_testsuite_property(
        f"input-wire-{tool}-{basis}-{solar}-{failed}",
        json.dumps(wire, ensure_ascii=False),
    )
    if folder := os.environ.get("FATEBRIDGE_GUOLAO_SOLAR_TEST_WIRE_DIR"):
        path = Path(folder) / f"{tool}-{basis}-{solar}-{failed}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(wire, stream, ensure_ascii=False)
    values = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [rest.json(), mcp, cli]
    ]
    if failed:
        assert values[2] == {**values[0], "status_code": rest.status_code}
        assert values[1] == {**values[2], "operation": spec.operation_label_zh}
    else:
        assert values[0] == values[1] == values[2]
        assert values[0]["guolao"]["life_palace"]["birth_hour_branch"] == "子"


def test_new_clock_evidence_projection_is_available_with_strict_fields(
    monkeypatch, fixed_moshier
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        "/api/astro/guolao",
        json={**CASES[0], "birth_clock_basis": "local_apparent_solar"},
        params=[
            ("fields", "guolao.profile.input_clock.source_comparison.status"),
            ("fields", "guolao.life_palace.clock_basis"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["guolao"]["profile"]["input_clock"]["source_comparison"][
            "status"
        ]
        == "compatible_observed_sun_contexts"
    )
