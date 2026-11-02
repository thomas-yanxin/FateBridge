"""Literal Hall and row-preservation tests before new control responses."""

import itertools
import json
from fractions import Fraction as Q

import pytest

from scripts.astrodice_epoch_neighborhood import (
    expand_plan,
    parse_rows,
    perfect_matching,
)
from scripts.verify_astrodice_epoch_neighborhood import (
    expand_expected,
    hall_matching,
    raw_rows,
)


@pytest.mark.parametrize(
    "adjacency,slots,expected",
    [
        ([[0, 1], [0, 1]], 2, True),
        ([[0], [0]], 2, False),
        ([[0, 1], [1, 2], [0, 2]], 3, True),
        ([[0, 1], [0, 1], [0, 1]], 3, False),
        ([[0]], 2, False),
        ([], 0, True),
    ],
)
def test_literal_perfect_matching_and_hall_deficiency(adjacency, slots, expected):
    assert perfect_matching(adjacency, slots) is expected
    assert hall_matching(adjacency, slots) is expected


def test_exhaustive_three_by_three_graphs_use_distinct_matching_algorithms():
    for bits in itertools.product((False, True), repeat=9):
        adjacency = [[j for j in range(3) if bits[i * 3 + j]] for i in range(3)]
        assert perfect_matching(adjacency, 3) == hall_matching(adjacency, 3)


def test_invalid_request_slot_cannot_be_a_label_witness():
    for matcher in (perfect_matching, hall_matching):
        with pytest.raises(ValueError):
            matcher([[1]], 1)


def test_nine_fixed_ulp_offsets_and_two_group_batches_preserve_every_input():
    aux = {
        "id": "aux",
        "role": "auxiliary_not_primary",
        "nominal_JD": "2451545",
        "intended_ET_hex": (0.0).hex(),
    }
    cases = [aux]
    for i in range(3):
        raw = float.fromhex("0x1p40") + 86400 * i
        cases.append(
            {
                "id": "case-" + str(i),
                "role": "source_argument_probe",
                "nominal_JD": str(Q(2451545) + Q(raw) / 86400),
                "intended_ET_hex": raw.hex(),
            }
        )
    baseline = {
        "queries": [
            {
                "id": "q",
                "encoding": "JD",
                "parameters": {"TLIST": "original"},
                "cases": cases,
            }
        ]
    }
    p = {
        "neighborhood_case_groups_per_batch": 2,
        "input_ET_ULP_offsets": list(range(-4, 5)),
    }
    actual = expand_plan(baseline, p)
    assert actual == expand_expected(baseline, p)
    assert [len(q["wire_epochs"]) for q in actual["queries"]] == [19, 10]
    first = [e for e in actual["queries"][0]["wire_epochs"] if e["case_id"] == "case-0"]
    assert [(Q(e["epoch_JD"]) - Q(cases[1]["nominal_JD"])) * 86400 for e in first] == [
        Q(k, 4096) for k in range(-4, 5)
    ]
    assert len({e["label"] for e in first}) == 9


def fixture():
    text = """Target body name: Earth (399) {source: DE441}
Center body name: Solar System Barycenter (0) {source: DE441}
Output units : AU-D
Reference frame : ICRF
Output type : GEOMETRIC cartesian states
Calendar mode : Gregorian
JDTDB
$$SOE
2451545.0, A.D. 2000-Jan-01 12:00:00.0000, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0,
2451545.0, A.D. 2000-Jan-01 12:00:00.0000, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0,
$$EOE
"""
    q = {
        "body": "Earth",
        "cases": [{"id": "literal", "nominal_JD": "2451545"}],
        "wire_epochs": [
            {"case_id": "literal", "epoch_JD": str(Q(2451545) + Q(k, 10**10))}
            for k in (-1, 1)
        ],
    }
    p = {
        "row_assignment_radius_seconds": "1",
        "returned_label_match_budget_days": "1/1000000000",
    }
    return text, q, p


def test_repeated_printed_labels_remain_two_distinct_unassigned_response_rows():
    text, q, p = fixture()
    raw = json.dumps({"result": text}).encode()
    rows = parse_rows(raw, q, p)
    assert rows == raw_rows(raw, q, p)
    assert [r["row_index"] for r in rows] == [0, 1]
    assert [r["compatible_request_slots"] for r in rows] == [[0, 1], [0, 1]]
    assert perfect_matching([r["compatible_request_slots"] for r in rows], 2)


@pytest.mark.parametrize(
    "before,after",
    [
        ("JDTDB", "JDTT"),
        ("Earth (399)", "Earth (3)"),
        ("GEOMETRIC cartesian states", "LT CORRECTED cartesian states"),
    ],
)
def test_wrong_time_or_state_definition_is_rejected(before, after):
    text, q, p = fixture()
    raw = json.dumps({"result": text.replace(before, after)}).encode()
    for parser in (parse_rows, raw_rows):
        with pytest.raises(ValueError):
            parser(raw, q, p)
