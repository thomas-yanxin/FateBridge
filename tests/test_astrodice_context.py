"""Coordinate conflict, provenance and named Fortune-method counterexamples."""

import json
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro.context_geometry import build_context_geometry
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.requests.divination import OtherBuRequest
from fatebridge.services.divination import calculate_otherbu_analysis

FACES = {"planet": "Moon", "sign": "Cancer", "house": 0}
SKY = {
    "date": "2024-03-20",
    "time": "00:30",
    "zone": "UTC",
    "lat": "51.500000123",
    "lon": "0.000000123",
}
REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/western-ptolemy-fortune-robbins-1940.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "changes",
    [
        {"gps_lat": 0.0},
        {"gps_lon": 30.0},
        {"lat": "nonsense", "gps_lat": 0.0},
        {"lon": "200", "gps_lon": 0.0},
        {"lat": "", "gps_lat": 0.0},
        {"lon": "", "gps_lon": 0.0},
        {"gps_lat": True},
        {"gps_lon": False},
        {"gps_lat": ""},
        {"gps_lat": float("nan")},
        {"gps_lon": float("inf")},
    ],
)
def test_invalid_or_conflicting_coordinate_aliases_are_not_ignored(changes):
    inputs = {**FACES, **SKY, **changes}
    with pytest.raises(ValueError):
        build_otherbu_result(**inputs)
    with pytest.raises(ValidationError):
        OtherBuRequest(**inputs)
    assert calculate_otherbu_analysis(**inputs)["error_code"] == "validation_error"


@pytest.mark.parametrize(
    "latitude,longitude,gps_lat,gps_lon",
    [
        ("51N30", "0E00", 51.5, 0),
        ("33S30", "151E12", -33.5, 151.2),
        ("0", "180", 0, -180),
        ("0", "-180", 0, 180),
        ("51.500000123", "0.000000123", 51.500000123, 0.000000123),
    ],
)
def test_equivalent_coordinate_aliases_keep_exact_calculation_metadata(
    latitude, longitude, gps_lat, gps_lon
):
    result = build_otherbu_result(
        **{
            **FACES,
            **SKY,
            "lat": latitude,
            "lon": longitude,
            "gps_lat": gps_lat,
            "gps_lon": gps_lon,
        }
    )
    params = result["chart"]["params"]
    assert params["birthLatitude"] == gps_lat
    assert params["birthLongitude"] == gps_lon
    assert f"经纬度：{float(gps_lon)} {float(gps_lat)}" in result["snapshot_text"]


def test_reported_location_is_the_actual_unrounded_location():
    result = build_otherbu_result(**FACES, **SKY)
    params = result["chart"]["params"]
    assert params["birthLatitude"] == 51.500000123
    assert params["birthLongitude"] == 0.000000123
    assert params["housePositionMethod"] == "ecliptic_longitude_cusp_intervals"
    assert params["lunarNodeModel"] == "mean_node_and_its_opposite"


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_ptolemy_context_fortune_against_annotated_edition_arithmetic(case):
    states = {p: {"longitude": case[p]} for p in ("Sun", "Moon")}
    start = int(case["ascendant"] // 30) * 30
    context = build_context_geometry(
        states,
        list(states),
        ascendant=case["ascendant"],
        midheaven=270,
        house_system="whole_sign",
        house_cusps=[(start + i * 30) % 360 for i in range(12)],
        ayanamsha=0,
        chart_sect=case["sect"],
        fortune_method="ptolemy_iii10",
    )
    fortune = next(p for p in context["objects"] if p["id"] == "Pars Fortuna")
    assert fortune["lon"] == case["expected_longitude"]
    assert context["fortune_definition"]["source_url"] == REFERENCE["source_url"]
    assert context["fortune_definition"]["sect_applied"] is None


@pytest.mark.parametrize(
    "hsys,zodiacal,time", list(product([0, 3, 5, 8], [0, 1], ["00:30", "12:30"]))
)
def test_method_selection_changes_only_fortune_and_its_provenance(hsys, zodiacal, time):
    inputs = {**FACES, **SKY, "time": time, "hsys": hsys, "zodiacal": zodiacal}
    a = build_otherbu_result(**inputs, fortune_method="sect_reversing")
    b = build_otherbu_result(**inputs, fortune_method="ptolemy_iii10")
    for key in (
        "planet",
        "sign",
        "house",
        "symbolic_details",
        "interpretation",
        "diceChart",
        "rulesets",
        "rule_trace",
        "validation",
    ):
        assert a[key] == b[key]
    ac = a["chart"]["chart"]
    bc = b["chart"]["chart"]
    for key in ("houses", "angles"):
        assert ac[key] == bc[key]
    ap = {p["id"]: p for p in ac["objects"]}
    bp = {p["id"]: p for p in bc["objects"]}
    for name in ap.keys() - {"Pars Fortuna"}:
        assert ap[name] == bp[name]
    expected = (bc["angles"]["ascendant"] + bp["Moon"]["lon"] - bp["Sun"]["lon"]) % 360
    assert bp["Pars Fortuna"]["lon"] == pytest.approx(expected, abs=1e-12)
    if time == "00:30":
        assert abs(ap["Pars Fortuna"]["lon"] - bp["Pars Fortuna"]["lon"]) > 100
    else:
        assert ap["Pars Fortuna"]["lon"] == pytest.approx(
            bp["Pars Fortuna"]["lon"], abs=1e-12
        )
    definition = b["chart"]["params"]["fortuneDefinition"]
    assert definition["method"] == "ptolemy_iii10"
    assert definition["formula"] == "ASC + Moon - Sun"
    assert "ptolemy_iii10 / ASC + Moon - Sun" in b["snapshot_text"]
    assert b["symbolic_details"]["triplicity_condition"]["sect"] is None


def test_unknown_fortune_policy_cannot_silently_select_another_formula():
    with pytest.raises(ValueError):
        build_otherbu_result(**FACES, **SKY, fortune_method="unknown")
    with pytest.raises(ValidationError):
        OtherBuRequest(**FACES, **SKY, fortune_method="unknown")
    with pytest.raises(ValueError):
        build_context_geometry(
            {},
            [],
            ascendant=0,
            midheaven=0,
            house_system="whole_sign",
            house_cusps=[i * 30 for i in range(12)],
            ayanamsha=0,
            chart_sect="unknown",
        )
