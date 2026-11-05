"""Earth-center source identity and analytic paired-clock edge conditions."""

from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_batch_binding import (
    matching_time_batches,
    require_matching_time_batches,
)
from scripts.astrodice_clock_interval import A
from scripts.astrodice_earth_clock import exact_axis, pair
from scripts.verify_astrodice_emission_epoch import exact_position


@pytest.mark.parametrize("body", ["Earth", "Venus"])
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_source_axes_equal_independent_original_coefficients(body, axis):
    source = (
        Path(__file__).parent / "data/astrodice/reference_sets/fixture-de441-records-v1"
    )
    epoch = Q("5166012.3")
    evaluate = exact_axis(source, 6, epoch, body, axis)
    for t in [epoch - Q(1, 86400), epoch, epoch + Q(1, 86400)]:
        assert evaluate(t) == exact_position(source, 6, t, body)[axis]
    with pytest.raises(ValueError, match="cell"):
        evaluate(epoch + 100)


def synthetic(interval, compatible=True):
    return {
        "profiles": {
            "printing_only": {
                "status": "bracketed",
                "effective_JD": list(map(str, interval)),
                "all_six_compatible": compatible,
            }
        },
        "printed_state": ["1.00000000000000"] * 6,
    }


class ConstantReader:
    def state(self, epoch, body):
        return [A(1)] * 6


PLAN = {"numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}}}


def test_touching_closed_clock_intervals_keep_the_exact_common_point():
    result = pair(
        ConstantReader(), synthetic([1, 2]), synthetic([2, 3]), "printing_only", PLAN
    )
    assert result["status"] == "intersecting" and result["common_JD"] == ["2", "2"]
    assert result["joint_necessary_not_refuted"]
    assert result["Earth_minus_Venus_seconds"] == ["-172800", "0"]


def test_disjoint_clocks_have_no_common_receiver_even_if_each_body_fits():
    result = pair(
        ConstantReader(), synthetic([1, 2]), synthetic([3, 4]), "printing_only", PLAN
    )
    assert result["status"] == "disjoint" and "common_JD" not in result


def test_component_failure_survives_an_intersecting_clock_interval():
    result = pair(
        ConstantReader(),
        synthetic([1, 2], False),
        synthetic([1, 2]),
        "printing_only",
        PLAN,
    )
    assert result["status"] == "intersecting"
    assert result["joint_necessary_not_refuted"] is False


def test_unknown_single_clock_is_not_a_false_disjoint_or_usable_common_clock():
    result = pair(
        ConstantReader(),
        {"profiles": {"printing_only": {"status": "unbracketed"}}},
        synthetic([1, 2]),
        "printing_only",
        PLAN,
    )
    assert result == {"status": "calibration_unknown"}


def time_query():
    return {
        "parameters": {
            "TIME_TYPE": "'TT'",
            "CAL_TYPE": "'GREGORIAN'",
            "TIME_DIGITS": "'FRACSEC'",
            "CAL_FORMAT": "'BOTH'",
            "TLIST_TYPE": "'JD'",
            "TLIST": "'2243796'\n'5166012.3'",
        }
    }


def test_equal_primary_epoch_cannot_bind_a_different_companion_time_batch():
    original, other = time_query(), time_query()
    assert matching_time_batches(original, other)
    require_matching_time_batches(original, other)
    other["parameters"]["TLIST"] += "\n'5166012.4'"
    assert matching_time_batches(original, other) is False
    with pytest.raises(ValueError, match="Cross-batch"):
        require_matching_time_batches(original, other)


@pytest.mark.parametrize(
    "key", ["TIME_TYPE", "CAL_TYPE", "TIME_DIGITS", "CAL_FORMAT", "TLIST_TYPE", "TLIST"]
)
def test_time_batch_contract_does_not_ignore_missing_or_changed_fields(key):
    original, other = time_query(), time_query()
    other["parameters"][key] += " changed"
    with pytest.raises(ValueError, match="Cross-batch"):
        require_matching_time_batches(original, other)
    other["parameters"].pop(key)
    with pytest.raises(ValueError, match="Incomplete"):
        require_matching_time_batches(original, other)
