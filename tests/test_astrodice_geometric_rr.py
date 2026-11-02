"""Literal calendar and analytic monotone-grid tests before any new probes."""

import json
import math
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts import astrodice_geometric_rr as producer
from scripts.astrodice_clock_interval import A, I
from scripts.verify_astrodice_geometric_rr import label, raw_rows


@pytest.mark.parametrize(
    "jd,text",
    [
        ("2451545", "2000ad-Jan-01 12:00:00.000000"),
        ("2440587.5", "1970ad-Jan-01 00:00:00.000000"),
        ("1721425.5", "1ad-Jan-01 00:00:00.000000"),
    ],
)
def test_literal_calendar_epoch_identity(jd, text):
    assert producer.epoch_label(Q(jd), "CAL") == label(Q(jd), "CAL") == text


def test_exact_microsecond_rounding_across_midnight():
    epoch = Q("2451544.5") - Q(1, 86400 * 10**7)
    assert (
        producer.epoch_label(epoch, "CAL")
        == label(epoch, "CAL")
        == "2000ad-Jan-01 00:00:00.000000"
    )
    assert (
        producer.epoch_label(Q(2451545), "MJD") == label(Q(2451545), "MJD") == "51544.5"
    )


@pytest.mark.parametrize(
    "target,strict,index",
    [(Q(-10), False, 0), (Q(2), False, 2), (Q(2), True, 3), (Q(20), True, 4)],
)
def test_monotone_integer_search_keeps_inclusive_and_strict_boundaries(
    target, strict, index
):
    assert (
        producer.lower_bound([Q(0), Q(1), Q(2), Q(3)], lambda x: x, target, strict)
        == index
    )


def analytic_clock(monkeypatch, shift=False, limit=4096):
    raw = float.fromhex("0x1p40")
    epoch0 = Q(2451545) + Q(raw) / 86400

    class Reader:
        def __init__(self, *args):
            pass

        def state(self, t, body):
            return [(t - epoch0) * 86400 + 123, A(0), A(0), A(86400), A(0), A(0)]

    def axis(source, window, epoch, body, index):
        return lambda t: (t - epoch0) * 86400 + 123

    def exact(source, window, epoch, body):
        return [(epoch - epoch0) * 86400 + 123, Q(0), Q(0), Q(86400), Q(0), Q(0)]

    monkeypatch.setattr(producer, "Reader", Reader)
    monkeypatch.setattr(producer, "exact_axis", axis)
    monkeypatch.setattr(producer, "exact_state", exact)
    value = "123.000244140625000" if shift else "123.000000000000000"
    row = {
        "printed_state": [
            value,
            "0.000000000000000",
            "0.000000000000000",
            "86400.000000000000000",
            "0.000000000000000",
            "0.000000000000000",
        ]
    }
    case = {"nominal_JD": str(epoch0), "window_index": 0, "intended_ET_hex": raw.hex()}
    plan = {
        "geometry_clock_search_radius_seconds": "1/1000",
        "maximum_lattice_points_per_model": limit,
        "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
    }
    return producer.diagnose(Path("."), case, row, "Earth", "printing_only", plan), raw


def test_exact_grid_inverse_finds_the_intended_literal_point(monkeypatch):
    result, raw = analytic_clock(monkeypatch)
    assert result["status"] == "complete" and result["unique_at_intended_epoch"]
    assert result["all_six_grid_matches"] == [raw.hex()]
    assert not result["physical_time_model_certified"]


def test_neighbor_clock_is_found_but_cannot_qualify_transfer(monkeypatch):
    result, raw = analytic_clock(monkeypatch, shift=True)
    assert result["status"] == "complete" and not result["unique_at_intended_epoch"]
    assert result["all_six_grid_matches"] == [math.nextafter(raw, math.inf).hex()]


def test_clock_grid_budget_keeps_unknown_without_selecting_a_subset(monkeypatch):
    result, raw = analytic_clock(monkeypatch, limit=2)
    assert result["status"] == "enumeration_limit" and len(result["grid_hex"]) == 2
    assert "candidates" not in result and "unique_at_intended_epoch" not in result


def test_radial_projection_distinguishes_tangential_speed():
    value = producer.projection([I(v) for v in (3, 4, 0, -4, 3, 0)])
    assert value.bounds() == (Q(0), Q(0))


def table():
    text = """Target body name: Earth (399) {source: DE441}
Center body name: Solar System Barycenter (0) {source: DE441}
Output units : AU-D
Reference frame : ICRF
Output type : GEOMETRIC cartesian states
Calendar mode : Gregorian
JDTDB
$$SOE
2451545.0, A.D. 2000-Jan-01 12:00:00.0000, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0,
$$EOE
"""
    q = {"body": "Earth", "cases": [{"id": "literal", "nominal_JD": "2451545"}]}
    plan = {
        "row_assignment_radius_seconds": "1",
        "returned_label_match_budget_days": "1/1000000000",
    }
    return text, q, plan


def test_both_parsers_preserve_tdb_body_units_and_population():
    text, q, p = table()
    raw = json.dumps({"result": text}).encode()
    assert producer.parse_geometry(raw, q, p) == raw_rows(raw, q, p)
    assert producer.parse_geometry(raw, q, p)[0]["case_id"] == "literal"


@pytest.mark.parametrize(
    "old,new",
    [
        ("JDTDB", "JDTT"),
        ("Earth (399)", "Earth (3)"),
        ("GEOMETRIC cartesian states", "LT CORRECTED cartesian states"),
    ],
)
def test_wrong_time_body_or_correction_is_rejected(old, new):
    text, q, p = table()
    raw = json.dumps({"result": text.replace(old, new)}).encode()
    for parser in (producer.parse_geometry, raw_rows):
        with pytest.raises(ValueError):
            parser(raw, q, p)
