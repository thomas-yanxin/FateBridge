"""Natal point identities follow actual factors, models and delivery contracts."""

import json
import os
from pathlib import Path

import pytest

from fatebridge.core.astro import chart as core_chart
from fatebridge.core.output_charts import ChartProfile
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/natal_reference_points"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
INPUT = dict(
    birth_year=2026,
    birth_month=9,
    birth_day=19,
    birth_hour=0,
    birth_minute=0,
    birth_longitude=0,
    birth_latitude=40,
    birth_timezone="UTC",
    use_true_solar_time=False,
)


def test_expected_point_contract_was_frozen_before_production_change():
    verify_source_files(FIXTURE)
    assert len(PROTOCOL["cases"]) == 18
    assert PROTOCOL["real_world_outcomes"] == 0


@pytest.mark.parametrize("case", PROTOCOL["cases"])
def test_natal_point_receipt_tracks_actual_models(case, monkeypatch, tmp_path):
    mode = case["mode"]
    ephe = Path(
        os.environ.get("FATEBRIDGE_TEST_EPHE_DIR", Path(__file__).parents[2] / "ephe")
    )
    if mode != "moshier":
        assert (ephe / "sepl_18.se1").is_file(), "Set FATEBRIDGE_TEST_EPHE_DIR"
        assert (ephe / "semo_18.se1").is_file(), "Set FATEBRIDGE_TEST_EPHE_DIR"
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if mode == "moshier" else ephe))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if mode == "controlled_saturn_approximation":
        original = core_chart._build_planet_states

        def mixed(*args, **kwargs):
            # Exercise the real per-factor fallback, retaining other native bodies.
            from fatebridge.core.astro import ephemeris

            actual = ephemeris._swisseph_planet_state

            def selected(name, *a, **kw):
                return None if name == "Saturn" else actual(name, *a, **kw)

            with monkeypatch.context() as patch:
                patch.setattr(ephemeris, "_swisseph_planet_state", selected)
                return original(*args, **kwargs)

        monkeypatch.setattr(core_chart, "_build_planet_states", mixed)
    result = calculate_core_chart_analysis(
        **INPUT, chart_variant=case["variant"], zodiacal=case["zodiacal"]
    )
    p = result["chart_profile"]["ephemeris_reference_points"]
    ChartProfile.model_validate(result["chart_profile"])
    planets = {x["id"] for x in result["planets"]}
    approximate = {"Saturn"} if mode == "controlled_saturn_approximation" else set()
    assert set(p["body_centers"]) == set(PROTOCOL["native_body_centers"]) & planets
    assert (
        set(p["system_barycenters"])
        == (set(PROTOCOL["native_system_barycenters"]) & planets) - approximate
    )
    assert set(p["approximate_points"]) == approximate
    assert set(p["theoretical_points"]) == {"North Node"} & planets
    assert not p["unresolved_points"]
    assert set(p["derived_points"]) == set(PROTOCOL["derived_points"])
    assert p["center_body_correction_applied"] is False
    assert p["note_zh"] in result["summary"]
    assert p["note_zh"] in result["snapshot_text"]
    groups = [
        set(p[k])
        for k in [
            "body_centers",
            "system_barycenters",
            "theoretical_points",
            "approximate_points",
            "unresolved_points",
        ]
    ]
    assert set.union(*groups) == planets
    assert sum(map(len, groups)) == len(planets)
    if mode == "controlled_saturn_approximation":
        assert "近似参考点：Saturn" in p["note_zh"]
        assert result["chart_profile"]["planetary_models"]["Saturn"] == (
            "fatebridge_approximate_orbital_model"
        )
    else:
        assert result["chart_profile"]["ephemeris_model"] == mode


def test_reference_point_subfields_are_declared_in_projectable_chart_schema():
    schema = ChartProfile.model_json_schema()
    assert "ephemeris_reference_points" in schema["properties"]
    points = schema["$defs"]["EphemerisReferencePoints"]["properties"]
    assert "body_centers" in points and "system_barycenters" in points
