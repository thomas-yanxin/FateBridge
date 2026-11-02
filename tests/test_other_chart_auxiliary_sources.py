"""Auxiliary lunar states keep file guards without adding chart bodies."""

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.utils.errors import EphemerisSourceError
from tests import test_other_chart_physical_sources as shared_sources

ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration


def test_equal13_compares_the_same_primary_factors_with_lunar_support(ephemeris_files):
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    assert e.configured_ephemeris_path() == str(directory)
    result = calculate_core_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=10,
        chart_variant="chart13",
    )
    assert "error" not in result, result
    nominal = result["chart_profile"]["physical_ephemeris_source"]
    sampled = result["time_sensitivity"]["physical_ephemeris_sources"]
    assert result["time_sensitivity"]["status"] == "sampled"
    assert len(result["time_sensitivity"]["samples"]) == 41
    for source in [nominal, *sampled]:
        assert set(source["by_factor"]) == set(PHYSICAL_BODIES)
        assert {row["model"] for row in source["by_factor"].values()} == {"swieph"}
        assert {row["filename"] for row in source["files"]} == {
            "sepl_18.se1",
            "semo_18.se1",
        }


def test_auxiliary_only_file_mutation_still_rejects_the_calculation(ephemeris_files):
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    assert e.configured_ephemeris_path() == str(directory)
    e.ephemeris_call("calc", 2451545.0, e.swe.MOON, e.swe.FLG_SWIEPH)
    trace = PhysicalEphemerisTrace()
    context = trace.observe("auxiliary_moon_state", "swieph", record_factor=False)
    assert context["file_ids"]
    target = directory / "semo_18.se1"
    with target.open("r+b") as stream:
        stream.seek(-1, 2)
        old = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([old[0] ^ 1]))
    with pytest.raises(EphemerisSourceError) as error:
        trace.finish()
    assert error.value.reason == "changed_during"
