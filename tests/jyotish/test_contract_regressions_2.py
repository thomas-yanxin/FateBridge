"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import json
import shutil
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.jyotish.test_jyotish_rotation_policy import ROOT
from tests.jyotish.test_jyotish_segment_motion import full_files
from tests.jyotish.test_jyotish_solar_display import SYNTHETIC
from tests.jyotish.test_jyotish_sources import data18, edge_birth, restore_runtime
from tests.jyotish.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize("year", [1800, 2024, 2050])
def test_profile_rotation_point_and_meridian_project_across_all_surfaces(
    key, year, monkeypatch, capsys
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    payload = dict(
        name="工程合成：印占自转依据",
        birth_year=year,
        birth_month=3,
        birth_day=20,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        birth_time_uncertainty_minutes=0,
        divisions=[],
        ephemeris_policy="require_data_files",
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = year + 1
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.earth_rotation",
            "india.profile.local_apparent_sidereal_meridian_degrees",
            "india.profile.julian_day_tt",
            "india.profile.julian_day_ut",
        ],
    )
    profile = result["india"]["profile"]
    policy = profile["earth_rotation"]
    assert policy["policy_id"] == "fatebridge_standard_rotation_v3"
    assert policy["model_epoch_jd_tt"] == profile["julian_day_tt"]
    assert policy["model_epoch_jd_ut1"] == profile["julian_day_ut"]
    assert policy["measured_eop_applied"] is False
    assert 0 <= profile["local_apparent_sidereal_meridian_degrees"] < 360
    if year == 2024:
        assert policy["tt_argument_policy"] == "native_internal_sidereal_time_argument"
        assert policy["sidereal_time_model"] == "Swiss_native"
    else:
        assert (
            policy["tt_argument_policy"]
            == "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
        )
        assert policy["sidereal_time_model"] == "IERS2010_expression_Swiss_nutation"


@pytest.mark.parametrize("key", ["astro_india", "astro_chart"])
def test_replayed_center_source_evidence_survives_rest_mcp_cli(
    data18, monkeypatch, capsys, key
):
    directory = full_files(data18)
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    e.configure_ephemeris_path(str(directory))
    payload = dict(
        birth_year=2400,
        birth_month=1,
        birth_day=10,
        birth_hour=20,
        birth_minute=36,
        birth_second=1,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=1,
        divisions=[],
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "person_info.utc_datetime",
            "chart_profile.longitude_motion.complete_position_derivatives",
            "india.profile.clock_context",
        ],
    )
    assert result["person_info"]["utc_datetime"] == "2400-01-10T20:36:01+00:00"
    assert (
        result["india"]["profile"]["clock_context"]["physical_instant_shifted"] is False
    )
    policies = result["chart_profile"]["longitude_motion"][
        "complete_position_derivatives"
    ]
    for label in [
        "Sun:tropical",
        "Mercury:tropical",
        "Venus:tropical",
        "Mars:tropical",
    ]:
        policy = policies[label]
        assert policy["method_id"] == "fatebridge_complete_position_derivative_v8"
        assert policy["status"] == "applied"
        replay = policy["source_branch_motion"]["center_file_replay"]
        assert replay["center_native_state_reproduced_exactly"] is True
        assert replay["displayed_native_position_changed"] is False
        assert {w["slot"] for w in replay["center_windows"]} == {0, 1}


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize(
    "month,day,latitude,lord", [(2, 23, 80, "Moon"), (8, 27, -80, "Jupiter")]
)
def test_first_polar_day_components_survive_three_real_surfaces(
    monkeypatch, capsys, key, month, day, latitude, lord
):
    data = dict(
        birth_year=2026,
        birth_month=month,
        birth_day=day,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=latitude,
        birth_longitude=0,
        divisions=[],
        birth_time_uncertainty_minutes=0,
    )
    if key == "astro_chart":
        data["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        data,
        [
            "india.strengths.kala_bala.solar_context",
            "india.strengths.kala_bala.components",
            "india.birth_time_sensitivity.solar_bracket_states_on_grid",
            "india.topic_evidence",
            "india.rule_trace",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert (
        kala["solar_context"]["sunrise_day_status"]
        == kala["solar_context"]["active_arc_status"]
        == "bracketed"
    )
    assert (
        kala["components"]["dina_bala"]["ruler"]
        == kala["components"]["hora_bala"]["ruler"]
        == lord
    )
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Sun"
    assert result["india"]["birth_time_sensitivity"][
        "solar_bracket_states_on_grid"
    ] == [
        {
            "sunrise_day_status": "bracketed",
            "active_arc_status": "bracketed",
            "sample_count": 1,
        }
    ]


def test_component_dependency_statuses_support_nested_strict_projection(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        dict(
            birth_year=2026,
            birth_month=6,
            birth_day=21,
            birth_hour=12,
            birth_timezone="UTC",
            birth_latitude=80,
            birth_longitude=0,
            divisions=[],
        ),
        [
            "india.strengths.kala_bala.solar_context.sunrise_day_status",
            "india.strengths.kala_bala.solar_context.active_arc_status",
            "india.strengths.kala_bala.components.tribhaga_bala.summary.Jupiter",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert kala["solar_context"] == {
        "sunrise_day_status": "not_bracketed",
        "active_arc_status": "not_bracketed",
    }
    assert kala["components"]["tribhaga_bala"]["summary"]["Jupiter"] == 60


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_model_solar_label_and_source_projection_agree_on_all_three_surfaces(
    monkeypatch, capsys, tmp_path, key
):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    e.configure_ephemeris_path(str(empty))
    payload = {**SYNTHETIC, "use_true_solar_time": True, "divisions": []}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        ["person_info.utc_datetime", "india.profile.clock_context"],
    )
    context = result["india"]["profile"]["clock_context"]
    expected = datetime.fromisoformat("2000-01-01T13:11:38.671836")
    actual = datetime.fromisoformat(context["solar_wall_datetime"])
    assert abs((actual - expected).total_seconds()) <= 0.0002
    assert result["person_info"]["utc_datetime"] == "2000-01-01T12:34:56.123456+00:00"
    assert context["physical_instant_shifted"] is False
    assert (
        context["display_equation_of_time_method"]
        == "apparent_solar_hour_angle_shared_TT_model_UT1"
    )
    display = context["solar_display_context"]
    assert display["representation_status"] == "available"
    assert display["julian_day_tt"] == display["sun_julian_day_tt"]
    assert display["solar_ephemeris_model"] == "moshier"


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_second_rise_in_one_ut1_date_on_three_real_surfaces(monkeypatch, capsys, key):
    payload = dict(
        birth_year=2026,
        birth_month=3,
        birth_day=24,
        birth_hour=0,
        birth_minute=10,
        birth_timezone="UTC",
        birth_latitude=30,
        birth_longitude=91,
        divisions=[],
        birth_time_uncertainty_minutes=0,
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.strengths.kala_bala.solar_context",
            "india.strengths.kala_bala.components",
            "india.strengths.kala_bala.solar_events.enumeration",
            "india.rule_trace",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert kala["solar_context"]["status"] == "bracketed"
    assert kala["solar_context"]["hora_number"] == 1
    assert kala["components"]["dina_bala"]["ruler"] == "Mars"
    assert kala["components"]["hora_bala"]["ruler"] == "Mars"
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Mercury"
    assert kala["solar_events"]["enumeration"]["post_event_search_advance_seconds"] == 1
    assert any(
        r["rule_id"] == "jyotish.solar_event_enumeration.v1"
        for r in result["india"]["rule_trace"]
    )


def test_uncertainty_across_restored_sunrise_keeps_both_actual_day_lords(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        dict(
            birth_year=2026,
            birth_month=3,
            birth_day=24,
            birth_hour=0,
            birth_minute=10,
            birth_timezone="UTC",
            birth_latitude=30,
            birth_longitude=91,
            divisions=[],
            birth_time_uncertainty_minutes=12,
        ),
        ["india.birth_time_sensitivity"],
    )
    sensitivity = result["india"]["birth_time_sensitivity"]
    assert sensitivity["status"] == "changes_detected"
    alternatives = sensitivity["time_lord_alternatives"]["dina_bala"]
    assert set(alternatives) == {"Moon", "Mars"}


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_explicit_input_label_and_resolved_instant_survive_three_surfaces(
    monkeypatch, capsys, key, basis
):
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_microsecond=123456,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis=basis,
        divisions=[],
        birth_time_uncertainty_minutes=1,
    )
    if key == "astro_chart":
        data["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        data.update(analysis_year=2026, analysis_timezone="Asia/Shanghai")
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        data,
        [
            "person_info.utc_datetime",
            "person_info.clock_conversion",
            "india.profile.clock_context",
            "india.birth_time_sensitivity",
        ],
    )
    clock = result["india"]["profile"]["clock_context"]
    assert clock["input_clock_basis"] == basis
    assert clock["input_wall_datetime"] == "1879-05-14T23:01:17.123456"
    assert clock["calculation_utc_datetime"] == result["person_info"]["utc_datetime"]
    assert clock["recorded_datetime"] is None
    assert (
        result["person_info"]["clock_conversion"]["input_calendar"]
        == "proleptic_gregorian"
    )
    if basis == "local_mean_solar":
        assert clock["calculation_utc_datetime"] == "1879-05-14T22:21:17.123456+00:00"
    else:
        assert clock["input_clock_conversion"]["solar_ephemeris_models_observed"]
    bounds = result["india"]["birth_time_sensitivity"]["clock_interval"]
    assert bounds["input_clock_basis"] == basis
    assert bounds["input_wall_start"] == "1879-05-14T23:00:17.123456"


def test_target_zone_and_nested_clock_fields_survive_three_surfaces(
    monkeypatch, capsys
):
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
        analysis_year=2026,
        analysis_hour=8,
        analysis_timezone="Asia/Shanghai",
        divisions=[],
    )
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        data,
        [
            "analysis_context",
            "india.profile.clock_context.input_wall_datetime",
            "india.profile.clock_context.calculation_utc_datetime",
            "india.profile.clock_context.input_clock_conversion.solar_ephemeris_policy",
        ],
    )
    assert (
        result["analysis_context"]["analysis_datetime"] == "2026-01-01T08:00:00+08:00"
    )
    assert result["analysis_context"]["timezone_basis"] == "explicit_analysis_timezone"
    assert (
        result["india"]["profile"]["clock_context"]["input_wall_datetime"]
        == "1879-05-14T23:00:00"
    )
    assert (
        result["india"]["profile"]["clock_context"]["input_clock_conversion"][
            "solar_ephemeris_policy"
        ]
        == "auto"
    )


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_india", None),
        ("astro_vimshottari", None),
        ("astro_chart", "india_chart"),
    ],
)
def test_source_grid_boundary_errors_and_complete_files_across_surfaces(
    data18, monkeypatch, tmp_path, capsys, key, variant
):
    root, directory = data18
    center = edge_birth().utc_datetime
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    payload = {
        "name": "虚构：印占文件覆盖边界",
        "birth_year": center.year,
        "birth_month": center.month,
        "birth_day": center.day,
        "birth_hour": center.hour,
        "birth_minute": center.minute,
        "birth_second": center.second,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 1.0,
        "divisions": [],
    }
    if key == "astro_vimshottari":
        payload["analysis_year"] = center.year + 1
    if variant:
        payload["chart_variant"] = variant
    spec = next(s for s in CATALOG if s.key == key)
    fields = ["india.profile.physical_ephemeris_source", "india.birth_time_sensitivity"]
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))

    def surfaces():
        params = [("fields", field) for field in fields] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def protocol():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        mcp = asyncio.run(protocol())
        capsys.readouterr()
        code = run(
            [
                spec.tool_name,
                "--subject-file",
                str(request),
                "--fields",
                *fields,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
                "--as-of",
                options["as_of"],
            ]
        )
        return rest, mcp, code, json.loads(capsys.readouterr().out)

    rest, mcp, code, cli = surfaces()
    assert rest.status_code == 503 and mcp.is_error and code == 1
    # Chart derivatives and the native birth grid must both retain an actual
    # missing-file model transition. Restoring coverage must compute the same
    # original birth epoch; a neighbor cannot substitute for this assertion.
    reason = "model_changed"
    for error in [rest.json(), json.loads(mcp.content[0].text), cli]:
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert error["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
        assert error["retryable"] is False
        assert str(directory) not in json.dumps(error)
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(root / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    rest, mcp, code, cli = surfaces()
    assert rest.status_code == 200 and not mcp.is_error and code == 0
    bodies = [rest.json(), mcp.structured_content, cli]
    assert bodies[0]["india"] == bodies[1]["india"] == bodies[2]["india"]
    grid = bodies[0]["india"]["birth_time_sensitivity"]
    assert grid["sample_count"] == 5
    assert len(grid["source_comparison"]["sample_source_indices"]) == 5
    assert grid["sampled_ephemeris_fallback_bodies"] == []
