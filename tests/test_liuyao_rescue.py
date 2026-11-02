"""Same-position back support qualifies actions without erasing other gates."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_liuyao_conditions import conditional_case

REFERENCE = Path(__file__).parent / "fixtures/liuyao_rescue_v12"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]


def current_control_expectation(case):
    base = REFERENCE.parent / "liuyao_growth_v18"
    path = base / "prior-case-adjudication.json"
    update = json.loads(path.read_text())
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == json.loads((base / "prior-case-adjudication-freeze.json").read_text())[
            "sha256"
        ]
    )
    assert (
        hashlib.sha256((REFERENCE / "cases.json").read_bytes()).hexdigest()
        == update["original_fixture_sha256"]
    )
    assert (
        hashlib.sha256((base / "profile.json").read_bytes()).hexdigest()
        == update["source_profile_sha256"]
    )
    if case["id"] != update["case_id"]:
        return case["expected_control"]
    assert case == update["original_case"]
    assert case["expected_control"] is update["previous"]
    return update["current"]


def test_rescue_source_and_cases_remain_frozen():
    from fatebridge.core.liuyao_rescue import PROFILE
    from scripts.build_liuyao_rescue_profile import build

    assert build() == PROFILE
    for name, digest in json.loads((REFERENCE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_back_generation_and_source_versioned_control_gates(case):
    result = conditional_case(case)
    support = result["back_generation_conditions"]["sources"][
        case["source_position"] - 1
    ]
    assert support["condition_match"] is case["expected_back_generation"]
    control = next(
        c
        for c in result["control_conditions"]["controls"]
        if (c["source_position"], c["target_position"])
        == (case["source_position"], case["target_position"])
    )
    assert control["condition_match"] is current_control_expectation(case)
    assert (
        control["source_back_generation_condition"] is case["expected_back_generation"]
    )
    assert control["back_generation_source_path"] == support["source_path"]
    assert control["status"] and support["status"]
    assert [r["branch"] for r in result["classical_assessment"]["lines"]] == case[
        "mounted_branches"
    ]


def test_original_calendar_harm_is_retained_when_back_support_qualifies_control():
    result = conditional_case(CASES[0])
    control = next(
        c
        for c in result["control_conditions"]["controls"]
        if (c["source_position"], c["target_position"]) == (6, 4)
    )
    assert control["source_calendar_supported"] is False
    assert any(h["location"] == "day" for h in control["source_calendar_oppositions"])
    assert control["source_rescue_used"] is True
    assert (
        result["classical_assessment"]["lines"][5]["strength"]["is_supported"] is None
    )


def test_static_line_cannot_borrow_the_changed_chart_at_its_position():
    result = conditional_case(CASES[12])
    support = result["back_generation_conditions"]["sources"][4]
    assert support["is_actual_moving"] is False
    assert support["changed_branch"] is None
    assert support["condition_match"] is False


def test_back_supported_helper_is_shared_with_dark_activity_qualification():
    frozen = json.loads((REFERENCE / "activity-freeze.json").read_text())
    for name, digest in frozen["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    case = json.loads((REFERENCE / "activity-case.json").read_text())["case"]
    result = conditional_case(case)
    assert result["lines"][3]["activity_condition_match"] is case["expected_activity"]
    # Actual source qualification can coexist with unresolved control of another
    # active source; do not certify global strength or order the two motions.
    controls = {
        (c["source_position"], c["target_position"]): c
        for c in result["control_conditions"]["controls"]
    }
    assert controls[(5, 2)]["condition_match"] is True
    assert controls[(6, 4)]["condition_match"] is None
