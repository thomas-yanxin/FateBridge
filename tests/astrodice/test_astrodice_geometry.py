"""Unrounded context counterexamples and conditional primary-text relationships."""

import json
import math
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.astro import layout
from fatebridge.core.astro.context_geometry import build_context_geometry
from fatebridge.core.astro.geometry import _house_for_longitude
from fatebridge.core.astrodice import PLANETS, build_symbolic_evidence
from fatebridge.core.classical_western import compute_lot
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.ptolemy import triplicity_rulers
from fatebridge.validation import astrodice_study

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-ptolemy-robbins-1940.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "longitude", [1e-14, math.nextafter(30.0, 0.0), math.nextafter(360.0, 0.0)]
)
def test_shared_lot_does_not_round_across_a_boundary_during_normalization(longitude):
    assert (
        compute_lot(["a", "b", "c"], {"a": longitude, "b": 0.0, "c": 0.0}) == longitude
    )


def test_sidereal_context_keeps_a_tiny_negative_offset_in_pisces():
    context = build_context_geometry(
        {"Mercury": {"longitude": 0.0}},
        ["Mercury"],
        ascendant=0.0,
        midheaven=270.0,
        house_system="whole_sign",
        house_cusps=[i * 30.0 for i in range(12)],
        ayanamsha=1e-14,
        chart_sect="day",
    )
    mercury = context["objects"][0]
    assert mercury["lon"] == math.nextafter(360.0, 0.0)
    assert mercury["sign"] == "Pisces"
    assert mercury["house"] == "House12"
    assert 0 <= mercury["signlon"] < 30


@pytest.mark.parametrize("row,planet", list(product(REFERENCE["signs"], PLANETS)))
def test_conditional_triplicities_against_separately_transcribed_edition(row, planet):
    result = build_symbolic_evidence(planet, row["sign"], 0)
    relation = result["symbolic_details"]["triplicity_condition"]
    assert relation["sect"] is None
    seven = planet in REFERENCE["exaltations"]
    for sect in ("day", "night"):
        assert relation["rulers_by_sect"][sect] == row[sect]
        expected = planet in row[sect].values() if seven else None
        assert relation["matches_by_sect"][sect] is expected
    trace = next(
        t for t in result["rule_trace"] if t["rule_id"] == "conditional_triplicity"
    )
    assert trace["result"] == relation
    assert "conditional_triplicity" in result["interpretation"]["basis"]
    assert (
        result["interpretation"]["triplicity_meaning"]
        in build_otherbu_result(planet=planet, sign=row["sign"], house=0)[
            "snapshot_text"
        ]
    )


def test_water_joint_rulership_is_not_dorothean_rotating_third_lord():
    assert triplicity_rulers("Cancer", "day") == {
        "primary": "Mars",
        "co_ruler": "Venus",
    }
    assert triplicity_rulers("Cancer", "night") == {
        "primary": "Mars",
        "co_ruler": "Moon",
    }
    assert "Saturn" not in triplicity_rulers("Aries", "day").values()
    with pytest.raises(ValueError):
        triplicity_rulers("Aries", "unknown")


def test_geometry_keeps_node_and_lot_on_original_side_of_sign_and_house():
    # Hand-constructed geometry: rounding the north node to 180 changes its
    # opposite from Pisces to Aries. Rounding Sun/Moon before the lot formula
    # changes Fortune from Aries to Taurus. Both are <0.0001 degree cases.
    states = {
        "Sun": {"longitude": 0.00001},
        "Moon": {"longitude": 29.99998},
        "North Node": {"longitude": 179.99996},
    }
    result = build_context_geometry(
        states,
        list(states),
        ascendant=0.00002,
        midheaven=270.0,
        house_system="whole_sign",
        house_cusps=[30.0 * i for i in range(12)],
        ayanamsha=0,
        chart_sect="day",
    )
    points = {p["id"]: p for p in result["objects"]}
    assert points["South Node"]["lon"] == pytest.approx(359.99996, abs=1e-12)
    assert points["South Node"]["sign"] == "Pisces"
    assert points["South Node"]["house"] == "House12"
    assert points["Pars Fortuna"]["lon"] == pytest.approx(29.99999, abs=1e-12)
    assert points["Pars Fortuna"]["sign"] == "Aries"
    assert points["Pars Fortuna"]["house"] == "House1"
    assert all(0 <= p["signlon"] < 30 for p in points.values())


def test_equal_house_layout_does_not_round_before_membership(monkeypatch):
    birth, _, _ = _build_birth_info(
        date_text="2024-03-20", time_text="06:30", timezone_name="UTC", lat=0, lon=0
    )
    monkeypatch.setattr(
        layout,
        "_swisseph_angles",
        lambda *args: {
            "ascendant": 29.99996,
            "midheaven": 270.123456789,
        },
    )
    result = layout._relative_house_layout(
        birth, house_system_info={"key": "equal"}, zodiacal_info={"sidereal": False}
    )
    assert result["house_cusps"][0] == 29.99996
    assert (
        _house_for_longitude(
            29.99997, result["ascendant"], "equal", house_cusps=result["house_cusps"]
        )
        == 1
    )
    assert (
        _house_for_longitude(
            29.99997,
            result["ascendant"],
            "equal",
            house_cusps=[round(c, 4) for c in result["house_cusps"]],
        )
        == 12
    )


@pytest.mark.parametrize(
    "cusp_index,offset", list(product(range(12), [-0.000001, 0, 0.000001]))
)
def test_context_house_intervals_use_unrounded_cusps(cusp_index, offset):
    cusps = [(29.99996 + 30.0 * i) % 360 for i in range(12)]
    longitude = (cusps[cusp_index] + offset) % 360
    geometry = build_context_geometry(
        {"Mercury": {"longitude": longitude}},
        ["Mercury"],
        ascendant=cusps[0],
        midheaven=270,
        house_system="equal",
        house_cusps=cusps,
        ayanamsha=0,
        chart_sect="day",
    )
    expected = (cusp_index - 1) % 12 + 1 if offset < 0 else cusp_index + 1
    assert geometry["objects"][0]["house"] == f"House{expected}"
    assert geometry["houses"][cusp_index]["lon"] == cusps[cusp_index]
    assert not any(p["id"] == "Pars Fortuna" for p in geometry["objects"])


@pytest.mark.parametrize("hsys,zodiacal", list(product(range(9), [0, 1])))
def test_optional_sky_coordinates_are_consistent_and_sect_stays_unselected(
    hsys, zodiacal
):
    result = build_otherbu_result(
        planet="Mars",
        sign="Cancer",
        house=0,
        date="2024-03-20",
        time="06:30:00.123456",
        zone="UTC",
        lat=51.5,
        lon=0,
        hsys=hsys,
        zodiacal=zodiacal,
    )
    chart = result["chart"]
    signs = [r["sign"] for r in REFERENCE["signs"]]
    for point in chart["chart"]["objects"]:
        assert 0 <= point["lon"] < 360
        assert 0 <= point["signlon"] < 30
        assert point["sign"] == signs[int(point["lon"] // 30)]
        assert point["signlon"] == point["lon"] % 30
        assert f"{point['lon']}°" in result["snapshot_text"]
    assert "unrounded" in chart["params"]["coordinatePolicy"]
    assert result["symbolic_details"]["triplicity_condition"]["sect"] is None
    assert result["symbolic_details"]["triplicity_condition"]["matches_by_sect"] == {
        "day": True,
        "night": True,
    }


def test_study_fingerprint_includes_shared_triplicity_source(monkeypatch, tmp_path):
    before = astrodice_study.engine_fingerprint()
    fake_source = tmp_path / "ptolemy.py"
    fake_source.write_text("changed conditional triangle rules")
    monkeypatch.setattr(astrodice_study.ptolemy, "__file__", str(fake_source))
    assert astrodice_study.engine_fingerprint() != before
