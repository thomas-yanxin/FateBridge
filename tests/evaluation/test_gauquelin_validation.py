"""No named person's outcome is a test oracle for the geometry or parser."""

import math
from datetime import datetime

import pytest

from fatebridge.validation.gauquelin import (
    FIELDS,
    LIMITS,
    clock_coherence,
    decode_final3,
    parse_line,
    sector12,
    semiarc_sector,
    source_datetime,
)


def line(**changes):
    values = dict(
        zip(
            FIELDS,
            (
                "Synthetic",
                "A",
                "F",
                "FICTIONAL Person",
                "1900 01 01",
                "f",
                "03 00",
                "PARIS",
                "75001",
                "-02.34",
                "+48.86",
                "1900 01 01",
                "02 51",
                "1",
            ),
        )
    )
    values.update(changes)
    return "".join(
        values[k].ljust(b - a) for k, a, b in zip(FIELDS, LIMITS, LIMITS[1:])
    ).encode()


def test_west_positive_is_negated_once_and_original_value_retained():
    row = parse_line(line(), 1066)
    assert row["issues"] == []
    assert row["longitude_east"] == 2.34
    assert row["raw"]["longitude_west"] == "-02.34"
    assert row["cohort"] == "published_1066"
    assert parse_line(line(longitude_west="+04.48"), 1067)["longitude_east"] == -4.48
    assert parse_line(line(), 1067)["cohort"] == "supplementary_54"


def test_only_2400_rolls_the_printed_day_and_invalid_2401_is_rejected():
    value, rolled = source_datetime("1941 04 06", "24 00")
    assert value == datetime(1941, 4, 7)
    assert rolled is True
    with pytest.raises(ValueError):
        source_datetime("1941 04 06", "24 01")
    assert source_datetime("1900 01 01", "00 00")[0] == datetime(1900, 1, 1)


@pytest.mark.parametrize(
    "changes,issue",
    [
        ({"universal_time": ""}, "universal:"),
        ({"local_date": "1900 02 29"}, "local:"),
        ({"longitude_west": ""}, "longitude_west:"),
        ({"latitude": "+91.00"}, "latitude:"),
        ({"mars12": "0"}, "missing_or_invalid_source_sector"),
        ({"mars12": "13"}, "missing_or_invalid_source_sector"),
        ({"regime": "x"}, "unknown_time_regime"),
    ],
)
def test_invalid_fields_are_retained_without_imputation(changes, issue):
    row = parse_line(line(**changes), 1)
    assert row["case_id"] == "CF-1"
    assert any(s.startswith(issue) for s in row["issues"])
    assert clock_coherence(row)["status"] == "not_checked_invalid_input"


def test_hash_pinning_rejects_changed_or_subset_source():
    with pytest.raises(ValueError, match="hash_mismatch"):
        decode_final3(line() + b"\n")
    assert parse_line(line()[:-1], 7)["issues"] == ["invalid_fixed_width"]


def test_partial_clock_check_uses_full_day_difference_and_keeps_unknowns():
    row = parse_line(line(), 1)
    assert clock_coherence(row)["status"] == "coherent_at_source_resolution"
    row = parse_line(line(local_date="1900 01 02"), 1)
    assert clock_coherence(row)["status"] == "unreconciled"
    for regime in ("o", "a"):
        assert (
            clock_coherence(parse_line(line(regime=regime), 1))["status"]
            == "not_checked_regime"
        )
    modern = parse_line(line(local_date="1940 01 01", universal_date="1940 01 01"), 1)
    assert clock_coherence(modern)["status"] == "not_checked_date"
    lmt = parse_line(
        line(
            local_date="1830 01 01",
            universal_date="1830 01 01",
            longitude_west="-06.92",
            universal_time="02 32",
        ),
        1,
    )
    assert clock_coherence(lmt)["expected_offset_seconds"] == pytest.approx(1660.8)


@pytest.mark.parametrize("hour,expected", [(-90, 1), (0, 10), (90, 19), (180, 28)])
def test_equatorial_rise_upper_set_lower_anchors(hour, expected):
    result = semiarc_sector(hour, 0, 0, 0)
    assert result["sector36"] == expected


def test_clockwise_motion_and_geographic_symmetry():
    # Declination zero makes both semiarcs90 degrees at any nonpolar latitude.
    for lat in (-89, -45, 0, 45, 89):
        for hour in range(-90, 270, 10):
            result = semiarc_sector(123 + hour, lat, 123, 0)
            assert result["sector36"] == pytest.approx(1 + (hour + 90) / 10)
    north = semiarc_sector(20, 45, 15, 23.4)
    south = semiarc_sector(20, -45, 15, -23.4)
    assert north == south


@pytest.mark.parametrize(
    "latitude,declination", [(80, 60), (80, -60), (-80, 60), (-80, -60)]
)
def test_circumpolar_points_do_not_receive_an_invented_sector(latitude, declination):
    result = semiarc_sector(0, latitude, 10, declination)
    assert result == {"status": "no_two_horizon_crossings", "sector36": None}


@pytest.mark.parametrize("args", [(0, 90, 0, 0), (0, -90, 0, 0), (0, 0, 0, 90)])
def test_poles_are_underdetermined(args):
    assert semiarc_sector(*args)["status"] == "underdetermined_pole"


def test_twelve_sector_mapping_has_explicit_half_open_boundaries():
    for k in range(12):
        cusp = 1.0 + k * 3
        assert sector12(cusp) == k + 1
        assert sector12(math.nextafter(cusp, math.inf)) == k + 1
        if k:
            assert sector12(math.nextafter(cusp, -math.inf)) == k
    for bad in (0, 37, True, float("nan"), float("inf"), "1"):
        with pytest.raises(ValueError):
            sector12(bad)


@pytest.mark.parametrize(
    "args", [(True, 0, 0, 0), (0, 91, 0, 0), (0, 0, 0, float("nan"))]
)
def test_geometry_rejects_invalid_inputs(args):
    with pytest.raises(ValueError):
        semiarc_sector(*args)


def test_documented_native_boundary_bias_is_separate_from_raw_geometry_gate():
    from scripts.evaluation.audit_gauquelin_cfepp import geometry_comparison

    for point in (1.0, 3.5, 10.0, 19.0, 28.0, 36.5):
        native = 1 + ((point - 1 - 1 / 36_000_000) % 36)
        result = geometry_comparison(native, point)
        assert result["raw_numeric_agreement"] is False
        assert result["documented_policy_agreement"] is True
        assert result["policy_error_sector_units"] == 0
    assert geometry_comparison(11, 10)["documented_policy_agreement"] is False


def test_source_and_diagnostic_protocols_are_separately_pinned():
    import hashlib
    import json

    from scripts.evaluation.audit_gauquelin_cfepp import (
        POLICY,
        POLICY_SHA256,
        PROTOCOL,
        PROTOCOL_SHA256,
    )

    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert hashlib.sha256(POLICY.read_bytes()).hexdigest() == POLICY_SHA256
    initial = json.loads(PROTOCOL.read_text())
    supplemental = json.loads(POLICY.read_text())
    assert initial["predictive_acceptance"] is False
    assert supplemental["primary_protocol_sha256"] == PROTOCOL_SHA256
