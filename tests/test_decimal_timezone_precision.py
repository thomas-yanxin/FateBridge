"""Exact decimal-hour offsets must not be rounded to integer seconds."""

import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from random import Random

import pytest

from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

FIXTURE = Path(__file__).parent / "data/human_design/decimal_offset"
PLAN = json.loads((FIXTURE / "plan.json").read_text())


def test_declared_decimal_sofa_cohort_keeps_all_inputs_and_tolerance():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert PLAN["tolerance_seconds"] == 0.0002
    assert len(PLAN["valid_cases"]) == len(reference["cases"]) == 24
    assert len(PLAN["reject_cases"]) == 7
    assert reference["independent_generator_imports_fatebridge"] is False


@pytest.mark.parametrize("case", PLAN["valid_cases"], ids=lambda c: c["id"])
def test_all_frozen_decimal_offsets_retain_exact_integer_microseconds(case):
    params = case["input"]
    zone = parse_timezone_name(params["birth_timezone"])
    delta = zone.utcoffset(None)
    assert (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds == case[
        "expected_offset_microseconds"
    ]
    assert timezone_rules_metadata(params["birth_timezone"]) == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }


@pytest.mark.parametrize("case", PLAN["reject_cases"], ids=lambda c: c["offset"])
def test_all_original_provisional_rejections_preserve_the_prior_input_scope(case):
    # Retain all seven original inputs. Only the original magnitude contract
    # rejects inputs; the withdrawn exact-microsecond restriction is not a gate.
    hours = Fraction(case["offset"])
    if abs(hours) > 15:
        with pytest.raises(ValueError, match="Invalid birth timezone"):
            parse_timezone_name(case["offset"])
    else:
        value = parse_timezone_name(case["offset"]).utcoffset(None)
        ticks = (value.days * 86400 + value.seconds) * 1000000 + value.microseconds
        assert ticks == round(hours * 3600000000)
        assert abs(Fraction(ticks) - hours * 3600000000) <= Fraction(1, 2)
        assert (
            timezone_rules_metadata(case["offset"])["rounding_error_bound_seconds"]
            == "0.0000005"
        )


def test_seeded_integer_microsecond_roundtrips_across_the_full_offset_range():
    # Multiples of9us have terminating decimal hours. Expected ticks are chosen
    # first; independent Decimal formatting does not use the production parser.
    random = Random(20261025)
    with localcontext() as context:
        context.prec = 60
        for _ in range(1000):
            expected = 9 * random.randint(-6_000_000_000, 6_000_000_000)
            text = format(Decimal(expected) / Decimal(3600000000), "f")
            value = parse_timezone_name(text).utcoffset(None)
            assert (
                value.days * 86400 + value.seconds
            ) * 1000000 + value.microseconds == expected


def test_trailing_zero_padding_does_not_discard_valid_precision():
    assert parse_timezone_name("  +5.500010000000000000000000  ").utcoffset(
        None
    ) == parse_timezone_name("5.50001").utcoffset(None)
    tiny = "0." + "0" * 5000 + "1"
    assert parse_timezone_name(tiny).utcoffset(None).total_seconds() == 0
    assert (
        timezone_rules_metadata(tiny)["decimal_hour_rounding"]
        == "nearest_microsecond_ties_even"
    )
