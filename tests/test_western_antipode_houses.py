"""Exact derived node versus displayed node in the unchanged house models."""

import asyncio
import math
from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest
from mpmath import mp

from fatebridge.core.astro import chart as core_chart
from fatebridge.core.astro.context_geometry import build_context_geometry
from fatebridge.core.astro.geometry import combine_longitudes
from fatebridge.core.astro.house_positions import build_ecliptic_house_projection
from fatebridge.core.astro.time_scales import ephemeris_time
from tests.test_agentic_nested_outputs import SPECS, business, call_cli
from tests.test_agentic_nested_outputs import inputs as representative_inputs
from tests.test_agentic_nested_outputs import native, rest


def decimal_house(source, cusps):
    with localcontext() as context:
        context.prec = 1200
        point = (Decimal.from_float(source) + 180) % 360
        continuous = []
        for cusp in cusps:
            value = Decimal.from_float(cusp) % 360
            while continuous and value <= continuous[-1]:
                value += 360
            continuous.append(value)
        while point < continuous[0]:
            point += 360
        ends = continuous[1:] + [continuous[0] + 360]
        return next(
            i + 1 for i, (a, b) in enumerate(zip(continuous, ends)) if a <= point < b
        )


@pytest.mark.parametrize("offset", [0.0, 15.0, 29.99996, 358.72338217449254])
def test_exact_context_antipode_uses_all_half_open_cusps(offset):
    cusps = [(offset + i * 30) % 360 for i in range(12)]
    for cusp in cusps:
        source = float((Fraction(cusp) - 180) % 360)
        for north in (
            math.nextafter(source, -math.inf),
            source,
            math.nextafter(source, math.inf),
        ):
            if not 0 <= north < 360:
                continue
            result = build_context_geometry(
                {"North Node": {"longitude": north}},
                ["North Node"],
                ascendant=cusps[0],
                midheaven=270,
                house_system="equal",
                house_cusps=cusps,
                ayanamsha=0,
                chart_sect="day",
            )
            south = next(p for p in result["objects"] if p["id"] == "South Node")
            assert south["house"] == f"House{decimal_house(north, cusps)}"


def projector(code):
    day = "2024-03-20" if code == b"T" else "2024-06-21"
    scales = ephemeris_time(datetime.fromisoformat(f"{day}T00:30:00+00:00"))
    return build_ecliptic_house_projection(
        julian_day_ut1=scales.jd_ut1,
        julian_day_tt=scales.jd_tt,
        geographic_latitude=80.0,
        geographic_longitude=0.0,
        house_code=code,
    )


def vector_house(projection, source):
    """Independent dot products in the actual equatorial angle model.

    R/C use the named plane phase; T uses the positive-to-negative root's
    boundary residual in its actual physical quadrant. No cusp interpolation.
    """
    ctx = mp.clone()
    ctx.dps = 120
    exact = (Fraction(source) + 180) % 360
    lam = ctx.mpf(exact.numerator) / exact.denominator * ctx.pi / 180
    phi, theta, eps = [
        ctx.mpf(v) * ctx.pi / 180
        for v in (projection.geographic_latitude, projection.armc, projection.obliquity)
    ]
    p = (ctx.cos(lam), ctx.cos(eps) * ctx.sin(lam), ctx.sin(eps) * ctx.sin(lam))
    east_axis = (-ctx.sin(theta), ctx.cos(theta), ctx.mpf(0))
    meridian_axis = (ctx.cos(theta), ctx.sin(theta), ctx.mpf(0))
    up_axis = (
        ctx.cos(phi) * ctx.cos(theta),
        ctx.cos(phi) * ctx.sin(theta),
        ctx.sin(phi),
    )
    east = ctx.fsum(a * b for a, b in zip(east_axis, p))
    meridian = ctx.fsum(a * b for a, b in zip(meridian_axis, p))
    up = ctx.fsum(a * b for a, b in zip(up_axis, p))
    offset = ctx.mpf(1) / 3600000
    if projection.house_code == b"R":
        phase = (ctx.atan2(ctx.cos(phi) * east, up) * 180 / ctx.pi - 90 + offset) % 360
    elif projection.house_code == b"C":
        phase = (ctx.atan2(-up, east) * 180 / ctx.pi + offset) % 360
    else:
        # Both selected T examples flank phase30; below horizon, reflected west.
        assert projection.house_code == b"T" and up < 0 and east > 0
        root = (60 + offset) * ctx.pi / 180
        cp, sp = ctx.cos(phi), ctx.sin(phi)
        residual = (
            cp * east * ctx.cos(root)
            + cp * meridian * ctx.sin(root)
            + sp * p[2] * root / (ctx.pi / 2)
        )
        derivative = (
            -cp * east * ctx.sin(root)
            + cp * meridian * ctx.cos(root)
            + sp * p[2] / (ctx.pi / 2)
        )
        assert derivative < 0
        return 2 if residual < 0 else 1
    return int(ctx.floor(phase / 30)) + 1


@pytest.mark.parametrize(
    "code,sources",
    [
        (b"R", [153.68892576934772, math.nextafter(153.68892576934772, math.inf)]),
        (b"T", [39.97519004038387, math.nextafter(39.97519004038387, -math.inf)]),
    ],
)
def test_same_float_opposites_keep_distinct_projected_houses_in_both_orders(
    code, sources
):
    projection = projector(code)
    displays = [combine_longitudes(source, 180.0) for source in sources]
    assert displays[0] == displays[1]
    expected = [vector_house(projection, source) for source in sources]
    assert expected[0] != expected[1]
    for index in (0, 1, 1, 0):
        exact = (Fraction(sources[index]) + 180) % 360
        got = projection.position(displays[index], exact_longitude=exact)
        assert int(got) == expected[index]
        check = projection.metadata()["precision"]["checks"][-1]
        assert check["exact_tropical_longitude_ratio"] == list(exact.as_integer_ratio())
        assert isinstance(check["tropical_longitude"], float)


def test_campanus_exact_derived_input_keeps_the_existing_plane_model():
    projection = projector(b"C")
    for source in [15.0, math.nextafter(15.0, -math.inf), 153.68892576934772]:
        exact = (Fraction(source) + 180) % 360
        got = projection.position(
            combine_longitudes(source, 180.0), exact_longitude=exact
        )
        assert int(got) == vector_house(projection, source)
        assert (
            projection.metadata()["method"]
            == "fatebridge_rc_plane_zero_ecliptic_latitude_v1"
        )


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("case", ["regular", "R", "T"])
def test_public_otherbu_exact_node_house_membership_through_three_transports(
    monkeypatch, rest, tmp_path, capsys, case
):
    if case == "regular":
        source, date, time, latitude, hsys = (
            28.72338217449254,
            "2024-03-20",
            "06:30:00",
            51.5,
            5,
        )
    elif case == "R":
        source, date, time, latitude, hsys = (
            153.68892576934772,
            "2024-06-21",
            "00:30:00",
            80.0,
            2,
        )
    else:
        source, date, time, latitude, hsys = (
            39.97519004038387,
            "2024-03-20",
            "00:30:00",
            80.0,
            6,
        )
    original = core_chart._build_planet_states

    def controlled(*args, **kwargs):
        result = original(*args, **kwargs)
        result[0]["North Node"]["longitude"] = source
        return result

    monkeypatch.setattr(core_chart, "_build_planet_states", controlled)
    spec = SPECS["otherbu"]
    inputs = {
        **representative_inputs(spec),
        "planet": "Mercury",
        "sign": "Virgo",
        "house": 6,
        "date": date,
        "time": time,
        "zone": "UTC",
        "lat": str(latitude),
        "lon": "0",
        "hsys": hsys,
        "zodiacal": 0,
    }
    fields = ["chart.chart.objects", "chart.chart.houses", "chart.params"]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
    ]
    http = rest.post(spec.rest_path, json=inputs, params=query)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, ["--fields", *fields])
    mcp = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        chart = value["chart"]["chart"]
        points = {p["id"]: p for p in chart["objects"]}
        assert points["North Node"]["lon"] == source
        if case == "regular":
            cusps = [house["lon"] for house in chart["houses"]]
            expected = decimal_house(source, cusps)
            assert (
                expected == 7
                and "housePositionProjection" not in value["chart"]["params"]
            )
        else:
            expected = vector_house(projector(case.encode()), source)
            policy = value["chart"]["params"]["housePositionProjection"]
            assert (
                policy["precision"]["boundary_policy"]
                == "geometric_phase_plus_forward_offset_not_longitude_cusp_snap"
            )
            assert policy["method"] == (
                "fatebridge_rc_plane_zero_ecliptic_latitude_v1"
                if case == "R"
                else "fatebridge_topocentric_zero_ecliptic_latitude_v1"
            )
        assert points["South Node"]["house"] == f"House{expected}"
