"""Typed same-point rotation evidence on REST, local fresh MCP and CLI."""

import pytest

from fatebridge.core import ephemeris_runtime as e
from tests.test_jyotish_rotation_policy import ROOT
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces


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
