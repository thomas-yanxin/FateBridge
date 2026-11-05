"""Derived classifications and selection precede display rounding.

The supplied doubles are the numerical inputs; these checks do not claim
better ephemeris, birth-clock accuracy or predictive validity. The harmonic
product is also documented by the software publisher:
https://www.esotech.com.au/SFHelp/casting_an_harmonic_transform_antiscia_or_analogue_chart.htm
"""

import asyncio
import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astrology_lifespan import (
    _house_containing,
    build_age_point_payload,
    build_harmonic_payload,
    build_persian_directed_payload,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest


def test_harmonic_product_keeps_the_supplied_coordinate_on_its_side_of_each_sign():
    with localcontext() as context:
        context.prec = 100
        for harmonic in range(1, 361):
            for boundary in range(30, 361, 30):
                value = boundary / harmonic
                for longitude in (
                    math.nextafter(value, -math.inf),
                    value,
                    math.nextafter(value, math.inf),
                ):
                    exact = Decimal.from_float(longitude) * harmonic % 360
                    result = build_harmonic_payload(
                        {"sun": {"absolute_degree": longitude}},
                        harmonic=harmonic,
                        orb=2,
                    )
                    displayed = result["positions"]["sun"]["absolute_degree"]
                    assert 0 <= displayed < 360
                    assert int(displayed // 30) == int(exact // 30)


def test_harmonic_conjunction_orb_uses_the_product_before_float_display():
    # 1.6 is a binary double above the exact decimal; the exact separation
    # of these supplied values times20 exceeds2, although float products tie.
    result = build_harmonic_payload(
        {"sun": {"absolute_degree": 1.5}, "moon": {"absolute_degree": 1.6}},
        harmonic=20,
        orb=2,
    )
    assert result["resonant_conjunctions"] == []


def test_harmonic_contacts_are_ordered_before_rounding_four_decimal_labels():
    result = build_harmonic_payload(
        {
            "sun": {"absolute_degree": 0},
            "moon": {"absolute_degree": 1.00004},
            "mercury": {"absolute_degree": 1.00001},
        },
        harmonic=1,
        orb=2,
    )
    assert [row["points"] for row in result["resonant_conjunctions"]] == [
        ["Moon", "Mercury"],
        ["Sun", "Mercury"],
        ["Sun", "Moon"],
    ]


@pytest.mark.parametrize("ascendant", [0, 1, 3.038038378856752, 60, 120])
def test_age_point_keeps_the_preceding_float_in_the_preceding_house(ascendant):
    cusps = [(ascendant + index * 30) % 360 for index in range(12)]
    for house, cusp in enumerate(cusps):
        assert _house_containing(cusp, cusps)[0] == house
        containing, fraction = _house_containing(math.nextafter(cusp, -math.inf), cusps)
        assert containing == (house - 1) % 12
        assert 0 < fraction < 1


def test_age_point_orders_near_cycle_end_before_the_exact_cycle_closure():
    cusps = [1 + index * 30 for index in range(12)]
    result = build_age_point_payload(
        {"Sun": 1, "Moon": math.nextafter(1.0, -math.inf)},
        cusps,
        max_age_years=72,
    )
    assert [row["body"] for row in result["contacts"]] == ["Moon", "Sun"]


def test_age_point_year_annotation_does_not_round_the_contact_twice():
    # Equal30-degree houses advance5degrees/year:12.505degrees is2.501years.
    # Its two-decimal label2.50 must not promote the actual contact to age2.
    result = build_age_point_payload(
        {"Sun": 12.505}, [index * 30 for index in range(12)], max_age_years=6
    )
    assert result["contacts"][0]["age"] == 2.5
    assert result["points"][2]["aspect_to"] is None
    assert result["points"][3]["aspect_to"] == "Sun"


def test_persian_hit_limit_keeps_the_first_actual_age_with_equal_display_labels():
    result = build_persian_directed_payload(
        {"Sun": 0, "Uranus": 1.004, "Neptune": 1.001},
        [],
        max_age_years=2,
        limit=1,
    )
    assert result["hit_count"] == 1
    assert result["hits"][0]["age"] == 1
    assert result["hits"][0]["significator"] == "Neptune"


@pytest.mark.parametrize(
    ("tool", "field", "options"),
    [
        ("astro_harmonic", "harmonic_chart", {"harmonic": 7}),
        ("astro_agepoint", "age_point", {"max_age_years": 72}),
        ("astro_persiandirected", "persian_directed", {"max_age_years": 90}),
    ],
)
def test_derived_calculations_reach_all_three_transports(
    rest, tmp_path, capsys, tool, field, options
):
    spec = SPECS[tool]
    inputs = {
        "birth_year": 2000,
        "birth_month": 12,
        "birth_day": 10,
        "birth_hour": 9,
        "birth_minute": 55,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 120.45,
        "birth_latitude": 32.54,
        **options,
    }
    fields = [field]
    query = [("fields", field), ("strict_fields", "true")]
    query += [("include_snapshot_text", "false"), ("response_char_limit", 0)]
    http = rest.post(spec.rest_path, json=inputs, params=query)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, ["--fields", *fields])
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    assert field in outputs[0]
