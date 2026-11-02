"""A solar clock label cannot move a recorded civil birth to another instant."""

from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.jyotish import calculate_vimshottari

BIRTH = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
    birth_longitude=121.4667,
    birth_latitude=31.2167,
)


def test_solar_display_does_not_change_physical_sky_or_periods():
    charts = [
        calculate_core_chart_analysis(
            **BIRTH,
            chart_variant="india_chart",
            divisions=[],
            use_true_solar_time=solar,
        )
        for solar in [False, True]
    ]
    assert (
        charts[0]["person_info"]["utc_datetime"]
        == charts[1]["person_info"]["utc_datetime"]
        == "1990-04-06T01:33:00+00:00"
    )
    assert charts[0]["india"]["charts"] == charts[1]["india"]["charts"]
    periods = [
        calculate_vimshottari(
            **BIRTH, divisions=[], use_true_solar_time=solar, analysis_year=2026
        )
        for solar in [False, True]
    ]
    assert periods[0]["vimshottari"] == periods[1]["vimshottari"]


def test_solar_display_cannot_reenter_a_model_window():
    options = dict(
        birth_year=2051,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=-180,
        cheshta_model="simon1994_j2000",
        divisions=[],
    )
    for solar in [False, True]:
        result = calculate_core_chart_analysis(
            **options, chart_variant="india_chart", use_true_solar_time=solar
        )
        context = result["india"]["strengths"]["cheshta_bala"]["model_context"]
        assert context["status"] == "outside_validated_model_window"


import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroIndiaRequest,
    AstroVimshottariRequest,
)

# Calendar/zone expectations are fixed independently of the production resolver.
CIVIL_CASES = [
    (dict(BIRTH), "1990-04-06T01:33:00+00:00"),
    (
        dict(
            birth_year=1990,
            birth_month=6,
            birth_day=15,
            birth_hour=0,
            birth_minute=5,
            birth_timezone="Asia/Shanghai",
            birth_longitude=121.4667,
            birth_latitude=31.2167,
        ),
        "1990-06-14T15:05:00+00:00",
    ),
    (
        dict(
            birth_year=2024,
            birth_month=6,
            birth_day=21,
            birth_hour=0,
            birth_minute=5,
            birth_timezone="Europe/London",
            birth_longitude=0,
            birth_latitude=51.5,
        ),
        "2024-06-20T23:05:00+00:00",
    ),
    (
        dict(
            birth_year=2024,
            birth_month=3,
            birth_day=10,
            birth_hour=1,
            birth_minute=30,
            birth_timezone="America/New_York",
            birth_longitude=-60,
            birth_latitude=40.7,
        ),
        "2024-03-10T06:30:00+00:00",
    ),
    (
        dict(
            birth_year=2024,
            birth_month=11,
            birth_day=3,
            birth_hour=1,
            birth_minute=30,
            birth_timezone="UTC-04:00",
            birth_longitude=-74,
            birth_latitude=40.7,
        ),
        "2024-11-03T05:30:00+00:00",
    ),
    (
        dict(
            birth_year=2024,
            birth_month=11,
            birth_day=3,
            birth_hour=1,
            birth_minute=30,
            birth_timezone="UTC-05:00",
            birth_longitude=-74,
            birth_latitude=40.7,
        ),
        "2024-11-03T06:30:00+00:00",
    ),
    (
        dict(
            birth_year=1965,
            birth_month=7,
            birth_day=1,
            birth_hour=8,
            birth_minute=0,
            birth_timezone="Asia/Kolkata",
            birth_longitude=77.2,
            birth_latitude=28.6,
        ),
        "1965-07-01T02:30:00+00:00",
    ),
    (
        dict(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=5,
            birth_timezone="UTC",
            birth_longitude=-180,
            birth_latitude=0,
        ),
        "2000-01-01T00:05:00+00:00",
    ),
]


@pytest.mark.parametrize("birth,expected_utc", CIVIL_CASES)
def test_known_civil_instants_survive_display_all_vargas_strengths_and_full_grid(
    birth, expected_utc
):
    results = [
        calculate_core_chart_analysis(
            **birth,
            chart_variant="india_chart",
            divisions=[2, 3, 7, 9, 10, 12, 30],
            birth_time_uncertainty_minutes=1,
            use_true_solar_time=solar,
        )
        for solar in [False, True]
    ]
    for result, solar in zip(results, [False, True]):
        assert "error" not in result, result
        assert result["person_info"]["utc_datetime"] == expected_utc
        context = result["india"]["profile"]["clock_context"]
        assert context["calculation_utc_datetime"] == expected_utc
        assert context["physical_instant_shifted"] is False
        assert context["solar_display_requested"] is solar
        if solar:
            assert datetime.fromisoformat(context["solar_wall_datetime"]).tzinfo is None
        else:
            assert context["solar_wall_datetime"] is None
    for key in [
        "charts",
        "nakshatras",
        "strengths",
        "birth_time_sensitivity",
        "reading_basis",
        "topic_evidence",
    ]:
        assert results[0]["india"][key] == results[1]["india"][key], key
    for key in [
        "julian_day_ut",
        "julian_day_tt",
        "julian_day_utc",
        "time_scale_context",
    ]:
        assert (
            results[0]["india"]["profile"][key] == results[1]["india"]["profile"][key]
        )
    periods = [
        calculate_vimshottari(
            **birth,
            divisions=[],
            birth_time_uncertainty_minutes=1,
            use_true_solar_time=solar,
            analysis_year=2026,
        )
        for solar in [False, True]
    ]
    assert periods[0]["vimshottari"] == periods[1]["vimshottari"]


def test_solar_label_can_cross_year_without_changing_birth_or_target_clock():
    birth = CIVIL_CASES[-1][0]
    result = calculate_vimshottari(
        **birth,
        divisions=[],
        use_true_solar_time=True,
        analysis_year=2000,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=0,
        analysis_minute=5,
    )
    assert "error" not in result, result
    context = result["india"]["profile"]["clock_context"]
    assert context["solar_wall_datetime"].startswith("1999-12-31T")
    assert result["person_info"]["utc_datetime"] == "2000-01-01T00:05:00+00:00"
    assert (
        result["analysis_context"]["analysis_datetime"] == "2000-01-01T00:05:00+00:00"
    )


def test_solar_label_is_valid_even_if_its_digits_would_be_a_nonexistent_zone_clock():
    birth = CIVIL_CASES[3][0]
    result = calculate_core_chart_analysis(
        **birth, chart_variant="india_chart", divisions=[], use_true_solar_time=True
    )
    context = result["india"]["profile"]["clock_context"]
    assert context["solar_wall_datetime"].startswith("2024-03-10T02:")
    assert context["calculation_utc_datetime"] == "2024-03-10T06:30:00+00:00"


@pytest.mark.parametrize("hour,month,day", [(2, 3, 10), (1, 11, 3)])
def test_unresolved_civil_gap_or_fold_remains_invalid_with_display_enabled(
    hour, month, day
):
    birth = {
        **BIRTH,
        "birth_year": 2024,
        "birth_month": month,
        "birth_day": day,
        "birth_hour": hour,
        "birth_timezone": "America/New_York",
    }
    for solar in [False, True]:
        assert (
            calculate_vimshottari(
                **birth, use_true_solar_time=solar, analysis_year=2026
            )["error_code"]
            == "validation_error"
        )
        assert (
            calculate_core_chart_analysis(
                **birth, chart_variant="india_chart", use_true_solar_time=solar
            )["error_code"]
            == "validation_error"
        )


def test_domain_does_not_silently_accept_already_rebased_legacy_birth_objects():
    legacy = build_astro_birth_info(**BIRTH, use_true_solar_time=True)
    for calculate in [positions, build_india]:
        with pytest.raises(ValueError, match="物理时刻"):
            calculate(legacy)
    corrected = build_astro_birth_info(
        **BIRTH, use_true_solar_time=True, preserve_instant=True
    )
    assert (
        build_india(corrected, divisions=[])["profile"]["clock_context"][
            "physical_instant_shifted"
        ]
        is False
    )
    # Direct callers cannot defeat the service invariant with the internal flag.
    result = calculate_vimshottari(
        **BIRTH,
        preserve_instant=False,
        use_true_solar_time=True,
        analysis_year=2026,
        divisions=[],
    )
    assert result["person_info"]["utc_datetime"] == "1990-04-06T01:33:00+00:00"


def test_public_solar_clock_schema_describes_the_indian_policy():
    for model in [AstroIndiaRequest, AstroVimshottariRequest]:
        description = model.model_json_schema()["properties"]["use_true_solar_time"][
            "description"
        ]
        assert "preserved" in description and "wall-clock label" in description
    poly = AstroChartPolyRequest.model_json_schema()["properties"][
        "use_true_solar_time"
    ]["description"]
    assert "Guolao and Indian charts" in poly


HORIZONS = json.loads(
    (Path(__file__).parent / "fixtures/jyotish-horizons.json").read_text()
)


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize(
    "instant", [row["utc"] for row in HORIZONS["references"][0]["rows"]]
)
def test_both_clock_settings_match_frozen_seven_body_nasa_horizons(
    monkeypatch, tmp_path, solar, instant
):
    from fatebridge.core import ephemeris_runtime

    # configure_ephemeris_path also updates this managed selection. Restore it
    # with the temporary environment, so later tests retain their caller's path.
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", ephemeris_runtime._configured_path
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    time = datetime.fromisoformat(instant)
    result = calculate_core_chart_analysis(
        birth_year=time.year,
        birth_month=time.month,
        birth_day=time.day,
        birth_hour=time.hour,
        birth_minute=time.minute,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
        chart_variant="india_chart",
        divisions=[],
        use_true_solar_time=solar,
    )
    assert result["person_info"]["utc_datetime"] == instant
    profile = result["india"]["profile"]
    assert profile["ephemeris_models"] == ["moshier"]
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        _, offset = runtime.swe.get_ayanamsa_ex(
            profile["julian_day_tt"], runtime.swe.FLG_SWIEPH
        )
    points = {
        p["id"]: p["longitude"] for p in result["india"]["charts"]["D1"]["planets"]
    }
    for reference in HORIZONS["references"]:
        assert (
            hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
            == reference["response_sha256"]
        )
        row = next(r for r in reference["rows"] if r["utc"] == instant)
        tropical = (points[reference["body"]] + offset) % 360
        error = (
            abs((tropical - row["apparent_ecliptic_longitude"] + 180) % 360 - 180)
            * 3600
        )
        assert error < HORIZONS["tolerance_arcseconds"], (reference["body"], error)


def test_domain_rejects_naive_or_inconsistent_manual_epoch_objects():
    from dataclasses import replace
    from datetime import timedelta

    birth = build_astro_birth_info(**BIRTH)
    with pytest.raises(ValueError, match="带时区"):
        positions(birth, birth.utc_datetime.replace(tzinfo=None))
    for invalid in [
        replace(birth, utc_datetime=birth.utc_datetime.replace(tzinfo=None)),
        replace(
            birth,
            recorded_datetime=None,
            local_datetime=birth.local_datetime + timedelta(minutes=1),
        ),
    ]:
        with pytest.raises(ValueError, match="带时区|物理时刻"):
            positions(invalid)


def test_unrepresentable_solar_display_does_not_invalidate_valid_physical_chart():
    options = dict(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=5,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=-180,
        chart_variant="india_chart",
        divisions=[],
    )
    civil = calculate_core_chart_analysis(**options, use_true_solar_time=False)
    displayed = calculate_core_chart_analysis(**options, use_true_solar_time=True)
    assert "error" not in civil, civil
    assert "error" not in displayed, displayed
    assert displayed["india"]["charts"] == civil["india"]["charts"]
    context = displayed["india"]["profile"]["clock_context"]
    assert context["solar_display_requested"] is True
    assert context["solar_wall_datetime"] is None
    assert context["solar_display_status"] == "unavailable"
    assert context["calculation_utc_datetime"] == "0001-01-01T00:05:00+00:00"
