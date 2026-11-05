"""House topology, native polar projection and unrelabelled evidence.

The direct Swiss API is a method oracle, not independent astronomical truth.
Boundary expectations apply only where cusps form one prograde partition.
"""

import math
from datetime import datetime
from itertools import product

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import (
    _house_for_longitude,
    combine_longitudes,
    is_prograde_house_partition,
)
from fatebridge.core.astro.house_positions import (
    HOUSE_POSITION_SOURCE,
    NATIVE_PROJECTION_METHOD,
    EclipticHouseProjection,
)
from fatebridge.core.astro.house_projection_precision import RC_PLANE_PROJECTION_METHOD
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.topocentric_precision import TOPOCENTRIC_PROJECTION_METHOD
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.predictive.native_chart import HOUSE_NAMES, build_native_subject
from tests.western.test_western_topocentric_precision import (
    legacy_references,
    phase_error,
)

swe = pytest.importorskip("swisseph")
FACES = {"planet": "Moon", "sign": "Cancer", "house": 0}
CODES = [b"W", b"B", b"R", b"P", b"K", b"V", b"T", b"S", b"D"]
POLAR = [
    (66.5, "2024-06-21", 6),  # Folded Polich/Page cusps below the polar circle.
    (80, "2024-03-20", 6),
    (80, "2024-06-21", 2),  # Reversed Regiomontanus cusps.
    (-80, "1900-01-01", 2),
]


@pytest.mark.parametrize(
    "date,latitude",
    list(
        product(
            ["1900-01-01", "2000-01-01", "2024-03-20", "2024-06-21"],
            [0, 51.5, 66.5, 80, -80, 90, -90],
        )
    ),
)
def test_actual_regular_cusps_keep_adjacent_floats_in_the_correct_half_open_house(
    date, latitude
):
    times = ephemeris_time(datetime.fromisoformat(date + "T00:30:00+00:00"))
    with runtime.preserve_ephemeris_path():
        for code in CODES:
            try:
                cusps, angles = swe.houses_ex(times.jd_ut1, latitude, 0, code)
            except swe.Error:
                continue  # No fabricated Placidus/Koch fallback in this oracle.
            cusps = list(cusps)
            # Independent mathematical precondition; not the production helper.
            wraps = sum(cusps[i] >= cusps[(i + 1) % 12] for i in range(12))
            if wraps != 1 or len(set(cusps)) != 12:
                continue
            for index, cusp in enumerate(cusps):
                for longitude, expected in [
                    (math.nextafter(cusp, -math.inf), (index - 1) % 12 + 1),
                    (cusp, index + 1),
                    (math.nextafter(cusp, math.inf), index + 1),
                ]:
                    assert (
                        _house_for_longitude(longitude, angles[0], "cusps", cusps)
                        == expected
                    )


@pytest.mark.parametrize("latitude,date,hsys", POLAR)
@pytest.mark.parametrize(
    "zodiacal,fortune_method",
    list(product([0, 1], ["sect_reversing", "ptolemy_iii10"])),
)
def test_folded_and_reversed_context_uses_declared_zero_latitude_native_projection(
    latitude, date, hsys, zodiacal, fortune_method
):
    result = build_otherbu_result(
        **FACES,
        date=date,
        time="00:30",
        zone="UTC",
        lat=latitude,
        lon=0,
        hsys=hsys,
        zodiacal=zodiacal,
        fortune_method=fortune_method,
    )
    params = result["chart"]["params"]
    chart = result["chart"]["chart"]
    times = ephemeris_time(datetime.fromisoformat(date + "T00:30:00+00:00"))
    with runtime.preserve_ephemeris_path():
        cusps, angles = swe.houses_ex(times.jd_ut1, latitude, 0, CODES[hsys])
        eps = swe.calc(times.jd_tt, swe.ECL_NUT, swe.FLG_SWIEPH)[0][0]
        physical = {
            name: swe.calc(times.jd_tt, body, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][0]
            for name, body in [
                ("Sun", swe.SUN),
                ("Moon", swe.MOON),
                ("Mercury", swe.MERCURY),
                ("Venus", swe.VENUS),
                ("Mars", swe.MARS),
                ("Jupiter", swe.JUPITER),
                ("Saturn", swe.SATURN),
                ("Uranus", swe.URANUS),
                ("Neptune", swe.NEPTUNE),
                ("Pluto", swe.PLUTO),
                ("North Node", swe.MEAN_NODE),
            ]
        }
        physical["South Node"] = combine_longitudes(physical["North Node"], 180.0)
        offset = params["chart_profile"]["ayanamsha"]
        fortune = next(p for p in chart["objects"] if p["id"] == "Pars Fortuna")
        physical["Pars Fortuna"] = combine_longitudes(fortune["lon"], offset)
        expected = {
            name: swe.house_pos(angles[2], latitude, eps, (lon, 0), CODES[hsys])
            for name, lon in physical.items()
        }
    assert not is_prograde_house_partition([p["lon"] for p in chart["houses"]])
    projection = params["housePositionProjection"]
    for point in chart["objects"]:
        position = expected[point["id"]]
        if CODES[hsys] == b"T":
            # The historical node name is retained; T is now checked against
            # the independently frozen vector answer, not old native bits.
            checks = projection["precision"]["checks"]
            check = min(
                checks,
                key=lambda r: abs(r["tropical_longitude"] - physical[point["id"]]),
            )
            assert abs(check["tropical_longitude"] - physical[point["id"]]) < 1e-10
            key = (latitude, angles[2], eps, check["tropical_longitude"])
            reference = legacy_references()[key]
            assert phase_error(point["ecliptic_house_position"], reference) <= 1
            assert point["house"] == f"House{reference['house']}"
        else:
            assert point["ecliptic_house_position"] == position
            assert point["house"] == f"House{math.floor(position)}"
    assert projection["armc"] == angles[2]
    assert projection["library_version"] == swe.version
    assert projection["true_obliquity"] == eps
    assert projection["input_ecliptic_latitude"] == 0.0
    assert projection["input_frame"] == "tropical_true_ecliptic_of_date"
    assert projection["source_url"] == HOUSE_POSITION_SOURCE
    assert projection == params["chart_profile"]["house_position_projection"]
    assert params["housePositionMethod"] == (
        RC_PLANE_PROJECTION_METHOD
        if CODES[hsys] in (b"R", b"C")
        else (
            TOPOCENTRIC_PROJECTION_METHOD
            if CODES[hsys] == b"T"
            else NATIVE_PROJECTION_METHOD
        )
    )
    assert params["houseOrientation"] == "native_nonprograde_cusps"
    assert "不是计入星体实际黄纬的空间落宫" in result["snapshot_text"]
    assert result["symbolic_details"]["triplicity_condition"]["sect"] is None
    plain = build_otherbu_result(**FACES)
    for key in [
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ]:
        assert result[key] == plain[key]


def test_actual_polar_counterexample_changes_wrong_first_house_assignments():
    result = build_otherbu_result(
        **FACES,
        date="2024-06-21",
        time="00:30",
        zone="UTC",
        lat=66.5,
        lon=0,
        hsys=6,
    )
    houses = {p["id"]: p["house"] for p in result["chart"]["chart"]["objects"]}
    assert houses["Mercury"] == "House4"  # Before: House1.
    assert houses["Moon"] == "House6"  # Before: House1.
    assert houses["Sun"] == "House12"  # Before: House3.
    assert houses["Venus"] == "House3"  # Before: House1.


@pytest.mark.parametrize("latitude,date,hsys", POLAR)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_shared_core_and_timing_house_numbers_use_the_same_projection(
    latitude, date, hsys, zodiacal
):
    birth, _, _ = _build_birth_info(
        date_text=date, time_text="00:30", timezone_name="UTC", lat=latitude, lon=0
    )
    core = build_core_chart_payload(
        birth, "chart", hsys=hsys, zodiacal=zodiacal, include_context_geometry=True
    )
    context = {p["id"]: p for p in core["context_geometry"]["objects"]}
    timing = build_native_subject(
        name="polar-test",
        local_datetime=birth.local_datetime,
        latitude=latitude,
        longitude=0,
        timezone_name="UTC",
        house_system=CODES[hsys].decode(),
        zodiac_type="Sidereal" if zodiacal else "Tropic",
    )
    assert timing.calculation_basis["house_position_projection"]["method"] == (
        RC_PLANE_PROJECTION_METHOD
        if CODES[hsys] in (b"R", b"C")
        else (
            TOPOCENTRIC_PROJECTION_METHOD
            if CODES[hsys] == b"T"
            else NATIVE_PROJECTION_METHOD
        )
    )
    for point in core["planets"]:
        assert context[point["id"]]["house"] == f"House{point['house']}"
        assert (
            context[point["id"]]["ecliptic_house_position"]
            == point["ecliptic_house_position"]
        )
        key = (
            "mean_north_lunar_node"
            if point["id"] == "North Node"
            else point["id"].lower()
        )
        assert timing.points[key].house == HOUSE_NAMES[point["house"] - 1]


@pytest.mark.parametrize(
    "cusps",
    [
        [0.0] * 12,
        [float(i * 30) for i in reversed(range(12))],
        [0.0, 60.0, 30.0, *[float(i * 30) for i in range(3, 12)]],
    ],
)
def test_interval_classifier_refuses_to_fabricate_a_partition(cusps):
    assert not is_prograde_house_partition(cusps)
    with pytest.raises(ValueError, match="原生宫位投影"):
        _house_for_longitude(45, 0, "cusps", cusps)


@pytest.mark.parametrize("bad", [0.0, -1.0, 13.0, float("nan"), float("inf")])
def test_native_projection_failure_never_becomes_a_default_house(bad, monkeypatch):
    projection = EclipticHouseProjection(0, 80, 23.4, b"T")
    monkeypatch.setattr(runtime, "ephemeris_call", lambda *args: bad)
    with pytest.raises(ValueError, match="不能钳制"):
        projection.position(90)


def test_native_projection_is_not_advertised_without_the_native_runtime(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    with pytest.raises(ValueError, match="需要Swiss"):
        EclipticHouseProjection(0, 80, 23.4, b"T").position(90)
