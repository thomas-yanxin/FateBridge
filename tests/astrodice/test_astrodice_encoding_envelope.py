"""An alternate input path cannot hide failures or incompatible references."""

import copy
from fractions import Fraction as Q

import pytest

from scripts.astrodice.audit_astrodice_encoding_envelope import QUALIFIED, outcome
from scripts.astrodice.audit_astrodice_local_motion import FAIL, PASS, UNRESOLVED


def inputs():
    qualities = {name: QUALIFIED for name in ["JD", "MJD"]}
    reports = {
        name: {layer: {"status": PASS} for layer in ["position", "rate"]}
        for name in qualities
    }
    intervals = {name: [(Q(0), Q(1)), (Q(2), Q(3))] for name in qualities}
    return qualities, reports, intervals, copy.deepcopy(intervals)


def test_two_qualified_paths_both_participate():
    assert outcome(*inputs()) == PASS


@pytest.mark.parametrize("encoding,layer", [("JD", "position"), ("MJD", "rate")])
def test_one_passing_path_cannot_erase_the_other_numerical_failure(encoding, layer):
    q, reports, intervals, boxes = inputs()
    reports[encoding][layer]["status"] = FAIL
    assert outcome(q, reports, intervals, boxes) == FAIL


def test_a_position_failure_survives_when_that_paths_rate_reference_is_unqualified():
    q, reports, intervals, boxes = inputs()
    q["JD"] = "reference_unavailable"
    intervals.pop("JD")
    reports["JD"]["rate"]["status"] = UNRESOLVED
    reports["JD"]["position"]["status"] = FAIL
    assert outcome(q, reports, intervals, boxes) == FAIL


@pytest.mark.parametrize("which", ["intervals", "center"])
def test_conflicting_references_remain_unresolved_even_when_both_candidates_pass(which):
    q, reports, intervals, boxes = inputs()
    target = intervals if which == "intervals" else boxes
    target["MJD"][0] = (Q(4), Q(5))
    assert outcome(q, reports, intervals, boxes) == UNRESOLVED


def test_no_available_reference_is_not_a_numerical_pass():
    q, reports, _, boxes = inputs()
    q = {name: "reference_unavailable" for name in q}
    assert outcome(q, reports, {}, boxes) == UNRESOLVED


def test_a_single_qualified_reference_does_not_drop_the_unavailable_alternative():
    q, reports, intervals, boxes = inputs()
    q["MJD"] = "reference_unavailable"
    reports["MJD"]["rate"]["status"] = UNRESOLVED
    intervals.pop("MJD")
    assert outcome(q, reports, intervals, boxes) == PASS
    assert q["MJD"] == "reference_unavailable"


def test_removing_an_encoding_is_a_coverage_error():
    q, reports, intervals, boxes = inputs()
    reports.pop("MJD")
    with pytest.raises(ValueError, match="Both declared encodings"):
        outcome(q, reports, intervals, boxes)


def test_a_candidate_error_is_not_removed_by_reference_selection():
    q, reports, intervals, boxes = inputs()
    reports["MJD"]["rate"]["status"] = "candidate_error"
    assert outcome(q, reports, intervals, boxes) == "candidate_error"
