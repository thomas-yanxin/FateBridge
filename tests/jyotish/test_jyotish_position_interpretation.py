"""Model meanings stay with the correct D1 ruler and discrete birth sample."""

import copy
from datetime import datetime, timedelta, timezone

from fatebridge.core.astro.sensitivity_grid import civil_recorded_sample
from fatebridge.core.jyotish.jyotish import GRAHAS, divisional_chart
from fatebridge.core.jyotish.jyotish_dasha_grid import DashaGrid


def synthetic_raw():
    return {
        "longitudes": {p: 80.0 for p in GRAHAS},
        "ascendant": 10.0,
        "time_scale_context": {"method": "synthetic_mapping_for_grouping_test"},
        "apparent_position_policy": {
            "bodies": {
                "Jupiter": {
                    "status": "computed",
                    "unbent_ray_domain": "behind_solar_disc",
                    "position_interpretation": "virtual_continuous_solar_disc_extension",
                    "impact_solar_radius_fraction": 0.8,
                    "observational_accuracy_certified": False,
                }
            }
        },
    }


def test_virtual_direction_is_d1_evidence_without_becoming_a_divisional_physical_state() -> (
    None
):
    raw = synthetic_raw()
    d1, d9 = divisional_chart(raw, 1), divisional_chart(raw, 9)
    jupiter = next(p for p in d1["planets"] if p["id"] == "Jupiter")
    assert (
        jupiter["native_position_interpretation"]["position_interpretation"]
        == "virtual_continuous_solar_disc_extension"
    )
    assert all("native_position_interpretation" not in p for p in d9["planets"])


def test_dasha_model_regions_group_by_meaning_without_continuous_geometry_explosion() -> (
    None
):
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    grid = DashaGrid(birth + timedelta(days=365), "sidereal_365_25636", [])
    raw = synthetic_raw()
    grid.observe(0.0, civil_recorded_sample(birth), raw)
    changed_radius = copy.deepcopy(raw)
    changed_radius["apparent_position_policy"]["bodies"]["Jupiter"][
        "impact_solar_radius_fraction"
    ] = 0.9
    sample = civil_recorded_sample(birth + timedelta(seconds=30))
    grid.observe(30.0, sample, changed_radius)
    variant = grid.result()["stage_variants"][0]
    assert (variant["major_lord"], variant["sub_lord"]) == ("Jupiter", "Jupiter")
    contexts = variant["natal_ruler_contexts"]
    assert len(contexts) == 1 and contexts[0]["sample_count"] == 2
    assert (
        "impact_solar_radius_fraction"
        not in contexts[0]["native_position_interpretation"]
    )
    outside = copy.deepcopy(changed_radius)
    outside["apparent_position_policy"]["bodies"]["Jupiter"].update(
        unbent_ray_domain="outside_solar_disc",
        position_interpretation="native_apparent_direction",
    )
    sample = civil_recorded_sample(birth + timedelta(seconds=60))
    grid.observe(60.0, sample, outside)
    contexts = grid.result()["stage_variants"][0]["natal_ruler_contexts"]
    assert sorted(c["sample_count"] for c in contexts) == [1, 2]
    assert {
        c["native_position_interpretation"]["position_interpretation"] for c in contexts
    } == {"virtual_continuous_solar_disc_extension", "native_apparent_direction"}


def test_dasha_uncertainty_orders_extended_utc_boundaries_chronologically() -> None:
    """An ISO sign prefix must not reverse the order of the sampled edges."""
    birth = datetime(9993, 2, 6, tzinfo=timezone.utc)
    grid = DashaGrid(datetime(9999, 12, 1, tzinfo=timezone.utc), "savana_360", [], 6)
    raw = synthetic_raw()
    raw["longitudes"]["Moon"] = 0.0
    for offset_seconds in (-1.0, 1.0):
        sample = civil_recorded_sample(birth + timedelta(seconds=offset_seconds))
        grid.observe(offset_seconds, sample, raw, endpoint_subset=True)

    result = grid.result()
    (variant,) = result["stage_variants"]
    assert variant["sample_count"] == 2
    ranges = variant["period_boundary_ranges"]
    expected = {
        "minimum": "9999-12-31T23:59:59+00:00",
        "maximum": "+010000-01-01T00:00:01+00:00",
    }
    assert ranges["current_major.end"] == expected
    assert ranges["subdivisions.current_levels.2.end"] == expected
    assert [sample["current_major"]["end"] for sample in result["samples"]] == list(
        expected.values()
    )
