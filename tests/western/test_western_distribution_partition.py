"""Bound walks partition the supplied zodiacal arc without epsilon jumps.

Expected Aries boundaries are the unchanged selected Egyptian table. The exposed
ordinary birth case and independent 100-place Decimal intersection reference
are retained under /tmp/fatebridge-unmet-audit-20261103/astrology/.
"""

import math
from fractions import Fraction

import pytest

from fatebridge.core.astrology_lifespan import (
    _bound_segments_from,
    build_distributions_payload,
)
from tests.support.transports import SPECS, business, rest, surface_calls

ASCENDANT = 3.038038378856752
SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)


def test_ordinary_origin_does_not_skip_mars_and_saturn_bound_periods():
    segments = _bound_segments_from(ASCENDANT, 90)
    aries = [row for row in segments if row["sign"] == "Aries"]
    assert [row["bound"]["bound_lord"] for row in aries] == [
        "Jupiter",
        "Venus",
        "Mercury",
        "Mars",
        "Saturn",
    ]
    for row, boundary in zip(aries, [6, 12, 20, 25, 30]):
        assert row["exit_arc"] == Fraction(boundary) - Fraction(ASCENDANT)
    assert aries[3]["exit_arc"] - aries[3]["enter_arc"] == 5
    assert aries[4]["exit_arc"] - aries[4]["enter_arc"] == 5


def test_body_on_a_bound_boundary_belongs_to_the_entered_half_open_period():
    value = build_distributions_payload(
        {"ascendant": {"absolute_degree": ASCENDANT}, "sun": {"absolute_degree": 20.0}},
        time_key="Ptolemy",
        max_age_years=30,
    )
    containing = [
        row
        for row in value["periods"]
        if any(p["planet"] == "Sun" for p in row["participants"])
    ]
    assert len(containing) == 1
    assert containing[0]["distributor"] == "Mars"
    assert containing[0]["start_age_years"] == round(20 - ASCENDANT, 3)


def test_a_positive_initial_remainder_is_never_replaced_with_the_rest_of_the_sign():
    asc = math.nextafter(6.0, 0.0)
    rows = _bound_segments_from(asc, 2)
    assert rows[0]["bound"]["bound_lord"] == "Jupiter"
    assert rows[0]["exit_arc"] == Fraction(6) - Fraction(asc) > 0
    assert rows[1]["bound"]["bound_lord"] == "Venus"


@pytest.mark.parametrize("sign_index", range(12))
def test_all_sign_origins_have_contiguous_nonempty_cells_and_correct_midpoint_labels(
    sign_index,
):
    origin = Fraction(sign_index * 30 + ASCENDANT)
    rows = _bound_segments_from(float(origin), 90)
    assert rows[0]["enter_arc"] == 0 and rows[-1]["exit_arc"] == 90
    for index, row in enumerate(rows):
        left, right = row["enter_arc"], row["exit_arc"]
        assert left < right
        if index:
            assert rows[index - 1]["exit_arc"] == left
        midpoint = (origin + (left + right) / 2) % 360
        assert row["sign"] == SIGNS[int(midpoint // 30)]
        assert (
            row["bound"]["segment_start_degree"]
            <= midpoint % 30
            < row["bound"]["segment_end_degree"]
        )
        assert (
            right - left
            <= row["bound"]["segment_end_degree"] - row["bound"]["segment_start_degree"]
        )


@pytest.mark.parametrize("time_key", ["Ptolemy", "Naibod"])
def test_correct_bound_sequence_reaches_rest_mcp_cli(time_key, surface_calls):
    spec = SPECS["astro_distributions"]
    inputs = dict(
        birth_year=2001,
        birth_month=5,
        birth_day=22,
        birth_hour=2,
        birth_minute=8,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        time_key=time_key,
        max_age_years=90,
    )
    fields = ["distributions", "natal_reference.ascendant.absolute_degree"]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http, protocol, code, cli = surface_calls(
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
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        aries = [
            row for row in value["distributions"]["periods"] if row["sign"] == "Aries"
        ]
        assert [row["distributor"] for row in aries] == [
            "Jupiter",
            "Venus",
            "Mercury",
            "Mars",
            "Saturn",
        ]
        rate = value["distributions"]["rate_deg_per_year"]
        assert aries[3]["start_age_years"] == round(
            (20 - value["natal_reference"]["ascendant"]["absolute_degree"]) / rate, 3
        )
