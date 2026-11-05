"""Manufactured clock inversions and reference identity failure controls."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice.astrodice_vector_clock import (
    clock_hypotheses,
    inverse,
    parse,
    tube,
)


@pytest.mark.parametrize("increasing", [True, False])
def test_inverse_brackets_two_boundaries_without_observed_axis_selection(increasing):
    sign = 1 if increasing else -1
    result = inverse(
        lambda t: sign * 3 * t + 7,
        Q(10),
        (Q(36), Q(38)) if increasing else (Q(-24), Q(-22)),
        increasing,
        Q(1),
        48,
    )
    assert result["status"] == "bracketed"
    for pair, target in zip(result["boundary_brackets_JD"], [Q(29, 3), Q(31, 3)]):
        lo, hi = map(Q, pair)
        assert lo <= target <= hi
        assert hi - lo == Q(2, 2**48)


def test_inverse_rejects_unbracketed_support_instead_of_extending_it():
    assert inverse(lambda t: t, Q(0), (Q(2), Q(3)), True, Q(1), 48) == {
        "status": "unbracketed"
    }


def test_printing_and_extra_ulps_remain_separate_uncertified_profiles():
    assert tube("1.234E-03", 0) == (Q(".001233"), Q(".001235"))
    lo, hi = tube("1.234E-03", 64)
    assert lo < Q(".001233") and hi > Q(".001235")


def test_numeric_representation_models_keep_exact_rationals_distinct():
    epoch = Q(4680826) + Q(1, 86400)
    values = clock_hypotheses(epoch)
    assert values["exact_nominal_TDB"] == epoch
    assert values["binary64_absolute_JD"] != epoch
    assert values["binary64_seconds_from_J2000"] == epoch


def raw_vector(epoch="4680826.000000002", timescale="TDB"):
    import json

    prefix = f"""Target body name: Venus (299) {{source: DE441}}
Center body name: Solar System Barycenter (0)
Output units : AU-D
Reference frame : ICRF
Output type : GEOMETRIC cartesian states
JD{timescale}
"""
    return json.dumps(
        {
            "result": prefix
            + "$$SOE\n"
            + epoch
            + ", A.D. 8103-Jul-26, 1, 2, 3, 4, 5, 6,\n$$EOE"
        }
    ).encode()


def test_structural_assignment_does_not_relax_original_label_budget():
    rows = parse(
        raw_vector(),
        {"time_type": "TDB"},
        [{"id": "one", "nominal_JD": "4680826"}],
        {
            "row_assignment_radius_seconds": "1",
            "returned_label_match_budget_days": "1/1000000000",
        },
    )
    assert len(rows) == 1 and rows[0]["original_label_budget_pass"] is False


@pytest.mark.parametrize(
    "raw",
    [
        raw_vector(timescale="TT"),
        raw_vector(epoch="4680827"),
        b'{"error":"service failed"}',
    ],
)
def test_wrong_time_type_missing_case_and_service_error_are_rejected(raw):
    with pytest.raises(ValueError):
        parse(
            raw,
            {"time_type": "TDB"},
            [{"id": "one", "nominal_JD": "4680826"}],
            {
                "row_assignment_radius_seconds": "1",
                "returned_label_match_budget_days": "1/1000000000",
            },
        )
