"""Exact supplied-longitude sector identity, independent of physical accuracy.

Equal27 and equal28 overlays are numerical partitions. They do not replace
Guolao's separately named unequal right-ascension mansion boundaries.
"""

import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro import chart as core_chart
from fatebridge.core.astro.geometry import _nakshatra, _su28
from fatebridge.core.astro.reference import NAKSHATRAS, SU28
from fatebridge.core.jyotish import jyotish
from fatebridge.core.local_techniques import chart as local_chart
from fatebridge.core.local_techniques.chart import _su28_position
from fatebridge.core.sukuyo.suzhan_astronomy import apply_equatorial_mansions
from tests.support.transports import SPECS, business
from tests.support.transports import inputs as representative_inputs
from tests.support.transports import rest, surface_calls


@pytest.mark.parametrize("count", [27, 28])
def test_every_equal_sector_boundary_and_neighbor_has_the_exact_input_identity(
    count: int,
) -> None:
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
                else:
                    pass
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
def test_exact_forty_degree_multiples_enter_the_next_nakshatra(longitude: int) -> None:
    assert _nakshatra(longitude) == NAKSHATRAS[longitude * 27 // 360]


@pytest.mark.parametrize("longitude", [90, 180, 270])
def test_exact_quarter_turns_enter_the_next_equal28_mansion(longitude: int) -> None:
    assert _su28(longitude) == SU28[longitude * 28 // 360]
    assert _su28_position(longitude)[0] == SU28[longitude * 28 // 360].removesuffix(
        "宿"
    )


def test_public_legacy_equal28_preserves_raw_boundary_coordinates_and_membership(
    monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
    original = local_chart.build_core_chart_payload
    before = math.nextafter(90.0, -math.inf)
    after = math.nextafter(90.0, math.inf)

    def controlled(*args, **kwargs):
        result = original(*args, **kwargs)
        values = {"Sun": 90.0, "Moon": before, "Mercury": after, "North Node": before}
        for point in result["planets"]:
            if point["id"] in values:
                point["longitude"] = values[point["id"]]
            else:
                pass
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
        assert {name: points[name]["lon"] for name in ("Sun", "Moon", "Mercury")} == {
            "Sun": 90.0,
            "Moon": before,
            "Mercury": after,
        }
        assert points["Sun"]["su28"] == points["Mercury"]["su28"] == "斗"
        assert points["Sun"]["su28_degree"] == 0
        assert points["Mercury"]["su28_degree"] > 0
        assert points["Moon"]["su28"] == points["North Node"]["su28"] == "箕"
        assert 12 < points["Moon"]["su28_degree"] < 360 / 28
        assert points["South Node"]["su28"] == "参"
        assert "星曜：Sun 0˚斗0分" in result["snapshot_text"]


def test_modern_unequal_projection_replaces_equal_degrees_and_clears_unassigned_points() -> (
    None
):
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
