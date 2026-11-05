"""Explicit modern mean model, separately labelled across the real transports."""

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_mean import FRAME, MODEL, SOURCE, STAR_PLANETS
from tests.fixtures.surface_payloads import astro_payload
from tests.jyotish.test_jyotish_transports import SPECS, call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
@pytest.mark.parametrize("model", ["unadjudicated", MODEL])
def test_optional_mean_model_across_three_real_surfaces(
    monkeypatch, capsys, key, model
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**astro_payload(), "cheshta_model": model},
        [
            "india.profile",
            "india.strengths.cheshta_bala",
            "india.strengths.shadbala_assessment",
            "india.rulesets",
            "india.rule_trace",
            "india.topic_evidence",
        ],
    )
    india = result["india"]
    assert india["profile"]["cheshta_model"] == model
    motion = india["strengths"]["cheshta_bala"]
    context = motion["model_context"]
    assessment = india["strengths"]["shadbala_assessment"]
    assert assessment["total_virupa"] is None
    if model == "unadjudicated":
        assert motion["missing_planets"] == list(STAR_PLANETS)
        assert all(motion["summary"][p] is None for p in STAR_PLANETS)
        assert context["status"] == "mean_model_unadjudicated"
        return
    assert motion["missing_planets"] == []
    assert context["status"] == "computed_declared_secular_model"
    assert context["frame"] == FRAME
    assert context["source_id"] == SOURCE["id"]
    assert SOURCE["id"] in {entry["id"] for entry in india["rulesets"]}
    assert "jyotish.cheshta_simon1994.v1" in {
        entry["rule_id"] for entry in india["rule_trace"]
    }
    for planet in STAR_PLANETS:
        assert 0 <= motion["summary"][planet] <= 60
        assert (
            motion["summary"][planet]
            == context["planet_evidence"][planet]["arc"]["value"]
        )
    assert "cheshta_bala_five_star_mean_model" not in assessment["missing"]
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor.get("rule_id") != "jyotish.cheshta_simon1994.v1":
                continue
            value = {"india": india}
            for part in factor["fact_path"].split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert value == factor["fact"]
            assert factor["supporting_source_id"] == SOURCE["id"]
            assert "Raman1900" in factor["traditional_interpretation"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_selected_model_nested_frame_evidence_projects_across_surfaces(
    monkeypatch, capsys, key
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**astro_payload(), "cheshta_model": MODEL},
        ["india.strengths.cheshta_bala.model_context.planet_evidence.Mars.arc.value"],
    )
    assert (
        0
        <= result["india"]["strengths"]["cheshta_bala"]["model_context"][
            "planet_evidence"
        ]["Mars"]["arc"]["value"]
        <= 60
    )


def test_target_year_does_not_change_natal_mean_model_window(monkeypatch, capsys):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {**astro_payload(), "cheshta_model": MODEL, "analysis_year": 2200},
        ["analysis_context", "india.strengths.cheshta_bala"],
    )
    assert result["analysis_context"]["analysis_datetime"].startswith("2200-")
    assert result["india"]["strengths"]["cheshta_bala"]["missing_planets"] == []


def test_non_indian_variants_reject_a_custom_mean_model_and_accept_neutral_default():
    request = SPECS["astro_chart"].request_model
    request.model_validate({**astro_payload(), "cheshta_model": "unadjudicated"})
    with pytest.raises(ValueError, match="cheshta_model"):
        request.model_validate({**astro_payload(), "cheshta_model": MODEL})
    with pytest.raises(ValueError):
        SPECS["astro_india"].request_model.model_validate(
            {**astro_payload(), "cheshta_model": "osculating_fallback"}
        )


@pytest.mark.native_engine_fault
def test_geometric_frame_fallback_cannot_hide_behind_other_frames(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    original = runtime.swe.calc

    def mixed(jd, body, flags):
        value, actual = original(jd, body, flags)
        if not flags & runtime.swe.FLG_ICRS:
            actual = (actual & ~runtime.swe.FLG_MOSEPH) | runtime.swe.FLG_SWIEPH
        return value, actual

    monkeypatch.setattr(runtime.swe, "calc", mixed)
    # This fixture simulates backend flags, not data-backed reconstruction.
    # Keep the actual source checks in their independent integration tests.
    from fatebridge.core import ephemeris_runtime

    endpoint_calls = []

    def synthetic_endpoint(native, operation, args, kwargs, invoke, *, configured_path):
        endpoint_calls.append(operation)
        return invoke(native, operation, args, kwargs)

    monkeypatch.setattr(
        ephemeris_runtime, "compressed_endpoint_call", synthetic_endpoint
    )
    # These return flags are simulated, with no actual file identity available.
    monkeypatch.setattr(
        runtime.swe, "get_current_file_data", lambda slot: ("", 0, 0, 0)
    )
    # Backend flags above are intentionally synthetic. Isolate the new D1
    # motion dependency rather than asking Swiss barycentric reconstruction
    # to treat Moshier vectors as data-backed vectors. The geometric-frame
    # fallback assertions below are all retained.
    from fatebridge.core import jyotish

    motion_calls = []

    def synthetic_motion(planet, jd, coordinates, model, **kwargs):
        motion_calls.append(planet)
        return {
            "longitude_speed_degrees_per_day": float(coordinates[3]),
            "longitude_speed_native_degrees_per_day": float(coordinates[3]),
            "longitude_motion_context": {
                "rate_basis": "synthetic_flag_fixture",
                "epoch_jd_tt": jd,
            },
        }

    monkeypatch.setattr(jyotish, "longitude_motion", synthetic_motion)
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth, cheshta_model=MODEL)
    assert "calc" in endpoint_calls
    assert motion_calls == [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
    ]
    scope = raw["apparent_position_policy"]["bodies"]["Mars"]
    assert scope["status"] == "not_evaluated"
    assert scope["reason"] == "geometric_coordinate_backend_mismatch"
    assert scope["coordinate_backends"]["geometric_j2000"] == "moshier"
    assert raw["physical_ephemeris_source"]["has_unidentified_sources"]
    assert all(
        v == "moshier"
        for v in raw["ephemeris_quality"]["motion_ephemeris_by_body"].values()
    )
    with pytest.raises(ValueError, match="运动力J2000"):
        positions(birth, cheshta_model=MODEL, ephemeris_policy="require_data_files")


def test_model_admission_boundary_is_retained_in_birth_time_sensitivity():
    birth = build_astro_birth_info(
        birth_year=2050,
        birth_month=12,
        birth_day=31,
        birth_hour=23,
        birth_minute=58,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    result = build_india(
        birth, cheshta_model=MODEL, divisions=[], birth_time_uncertainty_minutes=2
    )
    statuses = result["birth_time_sensitivity"]["cheshta_model_statuses_on_grid"]
    assert statuses == [
        "computed_declared_secular_model",
        "outside_validated_model_window",
    ]
    assert result["birth_time_sensitivity"]["status"] == "changes_detected"


def test_missingness_outside_admitted_birth_year_is_local_to_motion():
    birth = build_astro_birth_info(
        birth_year=2051,
        birth_month=1,
        birth_day=2,
        birth_hour=0,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    result = build_india(birth, cheshta_model=MODEL, divisions=[])
    assert result["charts"]["D1"]["planets"]
    motion = result["strengths"]["cheshta_bala"]
    assert motion["model_context"]["status"] == "outside_validated_model_window"
    assert motion["missing_planets"] == list(STAR_PLANETS)
    assert motion["summary"]["Sun"] is not None


def test_same_instant_and_node_choice_preserve_five_star_motion():
    common = dict(
        birth_year=1990,
        birth_month=4,
        birth_day=6,
        birth_minute=33,
        birth_latitude=31.23,
        birth_longitude=121.47,
    )
    local = build_astro_birth_info(
        **common, birth_hour=9, birth_timezone="Asia/Shanghai"
    )
    utc = build_astro_birth_info(**common, birth_hour=1, birth_timezone="UTC")
    left = build_india(local, cheshta_model=MODEL, divisions=[])
    right = build_india(utc, cheshta_model=MODEL, divisions=[], node_mode="true")
    for planet in STAR_PLANETS:
        assert (
            left["strengths"]["cheshta_bala"]["summary"][planet]
            == right["strengths"]["cheshta_bala"]["summary"][planet]
        )
    assert (
        left["strengths"]["cheshta_bala"]["model_context"]
        == right["strengths"]["cheshta_bala"]["model_context"]
    )
    nodes = [
        next(p for p in chart["charts"]["D1"]["planets"] if p["id"] == "Rahu")
        for chart in (left, right)
    ]
    assert nodes[0] != nodes[1]
