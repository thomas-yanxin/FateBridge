"""Supplied-coordinate antipodes, independently classified before display.

These controls make no astronomical-precision or traditional-source claim.
Run in the existing fresh native test worker for source-seam monkeypatches.
"""

import asyncio
import math
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from fatebridge.core import jyotish
from fatebridge.core.astro import chart as core_chart
from fatebridge.core.astro import runtime
from fatebridge.core.astro.context_geometry import build_context_geometry
from fatebridge.core.astro.reference import NAKSHATRAS
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.jyotish_vargas import varga_coordinates, varga_longitude
from fatebridge.core.local_techniques.chart import _build_birth_info
from tests.test_agentic_nested_outputs import SPECS, business, call_cli
from tests.test_agentic_nested_outputs import inputs as representative_inputs
from tests.test_agentic_nested_outputs import native, rest


@pytest.mark.parametrize("boundary", range(0, 360, 30))
def test_context_antipodes_keep_each_thirty_degree_boundary_and_neighbors(boundary):
    source = float((boundary - 180) % 360)
    for longitude in (
        math.nextafter(source, -math.inf),
        source,
        math.nextafter(source, math.inf),
    ):
        with localcontext() as context:
            context.prec = 1200
            opposite = (Decimal.from_float(longitude) + 180) % 360
            sign = int(opposite // 30)
        result = build_context_geometry(
            {"North Node": {"longitude": longitude}},
            ["North Node"],
            ascendant=0,
            midheaven=270,
            house_system="whole_sign",
            house_cusps=[float(i * 30) for i in range(12)],
            ayanamsha=0,
            chart_sect="day",
        )
        south = next(p for p in result["objects"] if p["id"] == "South Node")
        assert south["sign"] == SIGNS[sign], (longitude, opposite, south)
        assert south["house"] == f"House{sign + 1}"
        assert 0 <= south["lon"] < 360 and 0 <= south["signlon"] < 30


def reference_varga(longitude, division):
    """Decimal partition index and unchanged declared destination mapping."""
    sign = int(longitude // 30)
    degree = longitude - sign * 30
    if division == 1:
        return sign
    if division == 30:
        bounds, destinations = (
            ([5, 10, 18, 25, 30], [0, 10, 8, 2, 6])
            if sign % 2 == 0
            else ([5, 12, 20, 25, 30], [1, 5, 11, 9, 7])
        )
        return next(d for end, d in zip(bounds, destinations) if degree < end)
    part = int(degree * division // 30)
    if division == 2:
        return ([4, 3] if sign % 2 == 0 else [3, 4])[part]
    if division == 3:
        return (sign + 4 * part) % 12
    if division == 7:
        return (sign + (0 if sign % 2 == 0 else 6) + part) % 12
    if division == 9:
        return ([0, 9, 6, 3][sign % 4] + part) % 12
    if division == 10:
        return (sign + (0 if sign % 2 == 0 else 8) + part) % 12
    return (sign + part) % 12  # D12


def antipode_matrix_sources():
    sources = set()
    with localcontext() as context:
        context.prec = 1200
        boundaries = [
            Decimal(k) * 30 / division
            for division in (1, 2, 3, 7, 9, 10, 12)
            for k in range(12 * division)
        ]
        boundaries += [Decimal(k) * 360 / 108 for k in range(108)]
        for boundary in boundaries:
            source = float((boundary - 180) % 360)
            if source < 0:
                source += 360
            for longitude in (
                math.nextafter(source, -math.inf),
                source,
                math.nextafter(source, math.inf),
            ):
                if 0 <= longitude < 360:
                    sources.add(longitude)
    return sorted(sources)


def test_exact_antipode_matrix_all_supported_vargas_nakshatras_and_padas():
    sources = antipode_matrix_sources()
    assert len(sources) == 1151
    with localcontext() as context:
        context.prec = 1200
        for source in sources:
            expected = (Decimal.from_float(source) + 180) % 360
            exact = (Fraction(source) + 180) % 360
            for division in (1, 2, 3, 7, 9, 10, 12, 30):
                sign, _ = varga_coordinates(exact, division)
                assert sign == reference_varga(expected, division), (source, division)
                if division != 30:
                    assert int(varga_longitude(exact, division) // 30) == sign
            star = jyotish.nakshatra(exact)
            index = int(expected * 27 // 360)
            pada = int(expected * 108 // 360) % 4 + 1
            assert star["index"] == index + 1 and star["name"] == NAKSHATRAS[index]
            assert star["pada"] == pada


def test_hand_given_raw_ketu_is_not_implicitly_rebuilt():
    raw = {
        "ascendant": 0.0,
        "longitudes": {planet: 0.0 for planet in jyotish.GRAHAS},
    }
    # This standalone geometric fixture supplies Ketu independently of Rahu.
    raw["longitudes"]["Ketu"] = 123.0
    result = jyotish.divisional_chart(raw, 1)
    ketu = next(p for p in result["planets"] if p["id"] == "Ketu")
    assert ketu["longitude"] == 123.0 and ketu["sign"] == "Leo"


@pytest.mark.native_engine_fault
def test_india_sample_grid_uses_exact_antipodes_for_vargas_nakshatra_and_pada(
    monkeypatch,
):
    birth, _, _ = _build_birth_info(
        date_text="2024-03-20",
        time_text="06:30:00",
        timezone_name="UTC",
        lat="0",
        lon="0",
    )
    center = ephemeris_time(birth.require_utc_datetime).jd_tt
    source = math.nextafter(20.0, -math.inf)
    original = runtime.ephemeris_call

    def controlled(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == runtime.swe.MEAN_NODE:
            coordinates, returned_flags = result
            coordinates = list(coordinates)
            coordinates[0] = source if args[0] == center else 20.0
            return tuple(coordinates), returned_flags
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", controlled)
    result = jyotish.build_india(
        birth, divisions=[3, 9, 12], birth_time_uncertainty_minutes=0.5
    )
    sampled = result["birth_time_sensitivity"]
    assert sampled["sample_count"] == 3
    with localcontext() as context:
        context.prec = 1200
        targets = [(Decimal.from_float(source) + 180) % 360, Decimal(200)]
        for division in (3, 9, 12):
            expected = {SIGNS[reference_varga(target, division)] for target in targets}
            alternatives = sampled["alternatives"][f"D{division}"]["Ketu"]
            assert {point["sign"] for point in alternatives} == expected
        expected_stars = {
            (int(target * 27 // 360) + 1, int(target * 108 // 360) % 4 + 1): count
            for target, count in zip(targets, [1, 2])
        }
    assert {
        (star["index"], star["pada"]): star["sample_count"]
        for star in sampled["nakshatra_alternatives"]["Ketu"]
    } == expected_stars


@pytest.mark.native_engine_fault
def test_public_otherbu_exact_node_antipode_through_three_transports(
    monkeypatch, rest, tmp_path, capsys
):
    original = core_chart._build_planet_states
    source = math.nextafter(180.0, -math.inf)

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
        "date": "2024-03-20",
        "time": "06:30:00",
        "zone": "UTC",
        "lat": "0",
        "lon": "0",
        "hsys": 0,
        "zodiacal": 0,
    }
    fields = ["chart.chart.objects"]
    query = [("fields", field) for field in fields]
    query += [("strict_fields", "true"), ("include_snapshot_text", "false")]
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
        points = {p["id"]: p for p in value["chart"]["chart"]["objects"]}
        assert points["North Node"]["lon"] == source
        assert points["South Node"]["sign"] == "Pisces"
        assert points["South Node"]["house"] == "House12"


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("tool", ["astro_india", "astro_chart"])
@pytest.mark.parametrize(
    "source", [math.nextafter(v, -math.inf) for v in (15.0, 20.0, 180.0)]
)
def test_public_india_partitions_preserve_the_exact_derived_ketu(
    monkeypatch, rest, tmp_path, capsys, tool, source
):
    original = runtime.ephemeris_call

    def controlled(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] in {
            runtime.swe.MEAN_NODE,
            runtime.swe.TRUE_NODE,
        }:
            coordinates, returned_flags = result
            coordinates = list(coordinates)
            coordinates[0] = source
            return tuple(coordinates), returned_flags
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", controlled)
    spec = SPECS[tool]
    divisions = [2, 3, 7, 9, 10, 12, 30]
    inputs = {**representative_inputs(spec), "divisions": divisions}
    if tool == "astro_chart":
        inputs["chart_variant"] = "india_chart"
    fields = ["india.charts", "india.nakshatras"]
    query = [("fields", field) for field in fields]
    query += [("strict_fields", "true"), ("include_snapshot_text", "false")]
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
    with localcontext() as context:
        context.prec = 1200
        opposite = (Decimal.from_float(source) + 180) % 360
        for value in values:
            charts = value["india"]["charts"]
            for division in [1, *divisions]:
                ketu = next(
                    p for p in charts[f"D{division}"]["planets"] if p["id"] == "Ketu"
                )
                assert ketu["sign"] == SIGNS[reference_varga(opposite, division)]
            star = value["india"]["nakshatras"]["Ketu"]
            assert star["index"] == int(opposite * 27 // 360) + 1
            assert star["pada"] == int(opposite * 108 // 360) % 4 + 1
