"""Exact supplied-longitude sector identity, independent of physical accuracy.

Equal27 and equal28 overlays are numerical partitions. They do not replace
Guolao's separately named unequal right-ascension mansion boundaries.
"""

import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core import jyotish
from fatebridge.core.astro import chart as core_chart
from fatebridge.core.astro.geometry import _nakshatra, _su28
from fatebridge.core.astro.reference import NAKSHATRAS, SU28
from fatebridge.core.local_techniques import chart as local_chart
from fatebridge.core.local_techniques.chart import _su28_position
from fatebridge.core.suzhan_astronomy import apply_equatorial_mansions
from tests.support.transports import SPECS, business
from tests.support.transports import inputs as representative_inputs
from tests.support.transports import rest, surface_calls


@pytest.mark.parametrize("count", [27, 28])
def test_every_equal_sector_boundary_and_neighbor_has_the_exact_input_identity(count):
    with localcontext() as context:
        context.prec = 1200  # Also retain the subnormal neighbor just below0.
        for boundary in range(count + 1):
            value = 360 * boundary / count
            for longitude in (
                math.nextafter(value, -math.inf),
                value,
                math.nextafter(value, math.inf),
            ):
                reduced = Decimal.from_float(longitude) % 360
                if reduced < 0:
                    reduced += 360
                index = int(reduced * count // 360)
                if count == 27:
                    assert _nakshatra(longitude) == NAKSHATRAS[index]
                    assert _nakshatra(longitude) == jyotish.nakshatra(longitude)["name"]
                else:
                    assert _su28(longitude) == SU28[index]
                    assert _su28_position(longitude)[0] == SU28[index].removesuffix(
                        "宿"
                    )


@pytest.mark.parametrize("longitude", [40, 80, 120, 160, 200, 240, 280, 320])
def test_exact_forty_degree_multiples_enter_the_next_nakshatra(longitude):
    assert _nakshatra(longitude) == NAKSHATRAS[longitude * 27 // 360]


@pytest.mark.parametrize("longitude", [90, 180, 270])
def test_exact_quarter_turns_enter_the_next_equal28_mansion(longitude):
    assert _su28(longitude) == SU28[longitude * 28 // 360]
    assert _su28_position(longitude)[0] == SU28[longitude * 28 // 360].removesuffix(
        "宿"
    )


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("tool", ["astro_india", "astro_chart"])
def test_public_indian_chart_layers_share_the_same_controlled_boundary_coordinate(
    monkeypatch, tool, surface_calls
):
    original_record = core_chart._build_planet_record
    original_positions = jyotish.positions

    def record(planet, *args, **kwargs):
        if planet == "Moon":
            kwargs["zodiac_longitude"] = 40.0
        return original_record(planet, *args, **kwargs)

    def positions(*args, **kwargs):
        result = original_positions(*args, **kwargs)
        result["longitudes"]["Moon"] = 40.0
        return result

    monkeypatch.setattr(core_chart, "_build_planet_record", record)
    monkeypatch.setattr(jyotish, "positions", positions)
    spec = SPECS[tool]
    inputs = {**representative_inputs(spec), "divisions": []}
    if tool == "astro_chart":
        inputs["chart_variant"] = "india_chart"
    fields = ["planets", "india.nakshatras", "india.moon_nakshatra"]
    query = [("fields", field) for field in fields]
    query += [("strict_fields", "true"), ("include_snapshot_text", "false")]
    http, mcp, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        legacy = next(row for row in value["planets"] if row["id"] == "Moon")
        assert legacy["longitude"] == 40
        assert legacy["nakshatra"] == "Rohini"
        assert value["india"]["moon_nakshatra"] == "Rohini"
        assert value["india"]["nakshatras"]["Moon"]["name"] == "Rohini"


def test_public_legacy_equal28_keeps_source_membership_when_display_longitudes_tie(
    monkeypatch, surface_calls
):
    original = local_chart.build_core_chart_payload
    before = math.nextafter(90.0, -math.inf)
    after = math.nextafter(90.0, math.inf)

    def controlled(*args, **kwargs):
        result = original(*args, **kwargs)
        values = {"Sun": 90.0, "Moon": before, "Mercury": after, "North Node": before}
        for point in result["planets"]:
            if point["id"] in values:
                point["longitude"] = values[point["id"]]
        return result

    monkeypatch.setattr(local_chart, "build_core_chart_payload", controlled)
    spec = SPECS["suzhan"]
    inputs = {
        **representative_inputs(spec),
        "mansion_method": "legacy_equal28",
        "szchart": 0,
        "doubing_su28": True,
    }
    fields = ["chart.objects", "params.su28Method", "snapshot_text"]
    query = [("fields", field) for field in fields] + [("response_char_limit", 0)]
    http, mcp, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={"fields": fields, "strict_fields": True},
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for result in values:
        points = {row["id"]: row for row in result["chart"]["objects"]}
        assert result["params"]["su28Method"] == "legacy_equal_ecliptic28_illustration"
        assert (
            points["Sun"]["lon"]
            == points["Moon"]["lon"]
            == points["Mercury"]["lon"]
            == 90
        )
        assert points["Sun"]["su28"] == points["Mercury"]["su28"] == "斗"
        assert points["Sun"]["su28_degree"] == 0
        assert points["Mercury"]["su28_degree"] > 0
        assert points["Moon"]["su28"] == points["North Node"]["su28"] == "箕"
        assert 12 < points["Moon"]["su28_degree"] < 360 / 28
        assert points["South Node"]["su28"] == "参"
        assert "星曜：Sun 0˚斗0分" in result["snapshot_text"]


def test_modern_unequal_projection_replaces_equal_degrees_and_clears_unassigned_points():
    chart = {
        "objects": [
            {"id": "Sun", "su28": "斗", "su28_degree": 0},
            {"id": "South Node", "su28": "井", "su28_degree": 0},
        ]
    }
    astronomy = {
        "bodies": [
            {
                "id": "Sun",
                "right_ascension": 123,
                "declination": 4,
                "mansion": {
                    "su28": "井宿",
                    "degree_in_mansion": 32.2,
                    "mansion_width": 40,
                    "boundary_distance": 7.8,
                },
            }
        ]
    }
    apply_equatorial_mansions(chart, astronomy)
    assert chart["objects"][0]["su28"] == "井"
    assert chart["objects"][0]["su28_degree"] == 32.2
    assert chart["objects"][0]["su28_width"] == 40
    assert "su28" not in chart["objects"][1]
    assert "su28_degree" not in chart["objects"][1]
