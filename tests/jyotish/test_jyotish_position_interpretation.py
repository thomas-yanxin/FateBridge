"""Model meanings stay with the correct D1 ruler and discrete birth sample."""

import copy
from datetime import datetime, timedelta, timezone

from fatebridge.core.jyotish import GRAHAS, divisional_chart
from fatebridge.core.jyotish_dasha_grid import DashaGrid


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


def test_virtual_direction_is_d1_evidence_without_becoming_a_divisional_physical_state():
    raw = synthetic_raw()
    d1, d9 = divisional_chart(raw, 1), divisional_chart(raw, 9)
    jupiter = next(p for p in d1["planets"] if p["id"] == "Jupiter")
    assert (
        jupiter["native_position_interpretation"]["position_interpretation"]
        == "virtual_continuous_solar_disc_extension"
    )
    assert all("native_position_interpretation" not in p for p in d9["planets"])


def test_dasha_model_regions_group_by_meaning_without_continuous_geometry_explosion():
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    grid = DashaGrid(birth, birth + timedelta(days=365), "sidereal_365_25636", [])
    raw = synthetic_raw()
    grid.observe(0.0, raw)
    changed_radius = copy.deepcopy(raw)
    changed_radius["apparent_position_policy"]["bodies"]["Jupiter"][
        "impact_solar_radius_fraction"
    ] = 0.9
    grid.observe(30.0, changed_radius)
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
    grid.observe(60.0, outside)
    contexts = grid.result()["stage_variants"][0]["natal_ruler_contexts"]
    assert sorted(c["sample_count"] for c in contexts) == [1, 2]
    assert {
        c["native_position_interpretation"]["position_interpretation"] for c in contexts
    } == {"virtual_continuous_solar_disc_extension", "native_apparent_direction"}
