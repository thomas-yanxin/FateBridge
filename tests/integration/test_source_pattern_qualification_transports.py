"""Actual specialty transports and independent reconstruction of returned inputs."""

import json
import math

import pytest
from fastapi.testclient import TestClient

from fatebridge import api
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import three_surfaces


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("mode", ["ordinary", "polar", "asc_only", "polar_boundary"])
def test_source_pattern_qualification_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal, mode
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        "name": "虚构：原文条件资格的三端核验",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 4,
        "birth_minute": 30,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "zodiacal": zodiacal,
        "hsys": 1,
    }
    if variant:
        payload["chart_variant"] = variant
    payload["birth_time_uncertainty_minutes"] = 0
    as_of = "2000-01-01T04:30:00Z"
    if mode in ("polar", "polar_boundary"):
        payload["birth_latitude"] = 90.0
    if mode == "polar_boundary":
        payload["birth_time_uncertainty_minutes"] = 1
    if mode == "asc_only":
        payload.update(
            birth_hour=12,
            birth_minute=0,
            birth_longitude=169.5414439374805,
            birth_latitude=-66.56232328397007,
            birth_time_uncertainty_minutes=1,
        )
        as_of = "2050-01-01T00:00:00Z"
    payload["analysis_datetime"] = as_of
    fields = [
        "midpoint_analysis.profile",
        "midpoint_analysis.factors",
        "midpoint_analysis.interpretations",
        "midpoint_analysis.time_sensitivity",
        "midpoint_analysis.solar_arc_analysis.interpretations",
        "midpoint_analysis.solar_arc_analysis.birth_time_sensitivity",
    ]
    body = three_surfaces(spec, payload, fields, as_of, tmp_path, monkeypatch, capsys)
    layer = body["midpoint_analysis"]
    natal = layer["time_sensitivity"]
    directed = layer["solar_arc_analysis"]["birth_time_sensitivity"]
    for sensitivity in (natal, directed):
        pattern = sensitivity["source_pattern"]
        if mode in ("polar", "polar_boundary"):
            assert pattern["sampled_status"] == "underdetermined"
            assert (
                pattern["present_sample_count"] == pattern["absent_sample_count"] == 0
            )
            assert pattern["minimum_sampled_direct_orb_degrees"] is None
            assert all(v is None for v in pattern["condition_by_sample"])
        else:
            assert "unresolved_reference_sample_count" not in pattern
            assert (
                pattern["present_sample_count"] + pattern["absent_sample_count"]
                == sensitivity["sample_count"]
            )
    # Independent phase reconstruction from the actual same-run native inputs.
    for native, sample in zip(natal["samples"], directed["samples"]):
        v = native["factor_longitudes"]
        phase = math.radians(v["Mars"] + v["Jupiter"] - v["Zeus"] - v["Midheaven"])
        orb = abs(math.degrees(math.atan2(math.sin(phase), math.cos(phase))))
        if mode == "polar":
            assert natal["source_pattern"]["backend_convention"][
                "minimum_sampled_direct_orb_degrees"
            ] == pytest.approx(orb, abs=1e-10)
        if sample.get("status") == "unavailable":
            assert mode == "polar_boundary"
            assert (
                "backend_convention" not in sample and "solar_arc_degrees" not in sample
            )
            continue
        phase = math.radians(
            v["Mars"]
            + v["Jupiter"]
            - v["Zeus"]
            - v["Midheaven"]
            - sample["solar_arc_degrees"]
        )
        orb = abs(math.degrees(math.atan2(math.sin(phase), math.cos(phase))))
        actual = (
            sample["backend_convention"]
            if mode in ("polar", "polar_boundary")
            else sample
        )
        assert actual["source_direct_orb_degrees"] == pytest.approx(orb, abs=1e-10)
        assert actual["source_condition_met"] is (orb <= 2)
        if mode in ("polar", "polar_boundary"):
            assert sample["source_condition_met"] is None
            assert sample["source_direct_orb_degrees"] is None
            assert sample["directed_midheaven_longitude"] is None
            assert sample["source_reference_geometry_resolved"] is False
    for reading in (
        layer["interpretations"] + layer["solar_arc_analysis"]["interpretations"]
    ):
        if mode in ("polar", "polar_boundary"):
            assert (
                reading["source_application_status"]
                == "underdetermined_reference_geometry"
            )
            assert reading["physical_reference_geometry_resolved"] is False
            assert reading["backend_reading_zh"] != reading["reading_zh"]
        else:
            assert "source_application_status" not in reading
    if mode == "polar_boundary":
        assert (
            directed["computed_sample_count"] == 3
            and directed["unavailable_sample_count"] == 2
        )
        assert directed["source_pattern"]["unresolved_reference_sample_count"] == 3
    if mode == "asc_only":
        assert (
            natal["samples"][2]["angle_definition"]["geometric_ascendant_resolved"]
            is False
        )
        assert "status" not in natal["factor_spans"]["Midheaven"]


@pytest.mark.parametrize(
    "key,variant", [("astro_chart13", None), ("astro_chart", "chart13")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_shared_polar_factor_spans_across_equal13_surfaces(
    key, variant, zodiacal, tmp_path, monkeypatch, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = dict(
        name="虚构：十三分区共用参考范围核验",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=90,
        birth_time_uncertainty_minutes=0.5,
        zodiacal=zodiacal,
        hsys=1,
    )
    if variant:
        payload["chart_variant"] = variant
    body = three_surfaces(
        spec,
        payload,
        ["time_sensitivity", "sector_profile", "planets"],
        "2000-01-01T04:30:00Z",
        tmp_path,
        monkeypatch,
        capsys,
    )
    sensitivity = body["time_sensitivity"]
    for name in ["Ascendant", "Midheaven"]:
        span = sensitivity["factor_spans"][name]
        assert span["status"] == f"underdetermined_{name.lower()}"
        assert span["unresolved_sample_count"] == 3
        assert span["minimum_offset_from_nominal_degrees"] is None
        assert (
            span["backend_convention_span"]["maximum_offset_from_nominal_degrees"]
            is not None
        )
    assert (
        body["sector_profile"]["angle_definition"]["status"]
        == "geographic_pole_meridian_convention"
    )
    assert all(p["sector13"] is not None for p in body["planets"])
    assert all(
        None not in row["sector_by_sample"] for row in sensitivity["sector_assignments"]
    )


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("hsys", [0, 3])
def test_polar_house_system_contract_is_preserved(
    zodiacal, hsys, monkeypatch, tmp_path
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = dict(
        name="虚构：保留极点宫制拒绝",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=90,
        zodiacal=zodiacal,
        hsys=hsys,
    )
    response = TestClient(api.app).post(
        "/api/astro/germany", json=payload, params={"as_of": "2050-01-01T00:00:00Z"}
    )
    (tmp_path / "request.json").write_text(json.dumps(payload, ensure_ascii=False))
    (tmp_path / "rest.json").write_text(json.dumps(response.json(), ensure_ascii=False))
    if hsys == 3:
        assert response.status_code == 400
        assert response.json()["error_code"] == "validation_error"
        assert "midpoint_analysis" not in response.json()
    else:
        assert response.status_code == 200
        assert (
            response.json()["base_chart"]["chart_profile"]["house_system"]
            == "whole_sign"
        )
        assert response.json()["base_chart"]["chart_profile"]["house_system_code"] == 0
