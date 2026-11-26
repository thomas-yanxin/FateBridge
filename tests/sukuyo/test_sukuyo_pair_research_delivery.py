"""Pair summaries preserve the same adverse reference without borrowing a month."""

import json
from pathlib import Path

import pytest

from fatebridge.services.divination import calculate_sukuyo_compatibility
from tests.unit_test.fixtures.sukuyo_transports import (
    assert_sukuyo_transport_parity as _check_surfaces,
)

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/sukuyo-pair-research-before-code-v89.json"
    ).read_text()
)


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["case_id"])
def test_pair_delivers_complete_pre_edit_reference(case) -> None:
    result = calculate_sukuyo_compatibility(**case["input_pair"])
    assert result["fixed_host_research_scope"] == REFERENCE["scope"]
    assert "274相合、52不同、1未知" in result["summary"]
    assert "未知行号为263，作者横杠未补成不进" in result["summary"]
    assert "双方本次历日分别交付" in result["summary"]


def test_pair_reference_mutation_does_not_remove_next_calls_adverse_rows() -> None:
    result = calculate_sukuyo_compatibility(**REFERENCE["cases"][0]["input_pair"])
    result["fixed_host_research_scope"]["unknown_direction_rows"].clear()
    following = calculate_sukuyo_compatibility(**REFERENCE["cases"][1]["input_pair"])
    assert following["fixed_host_research_scope"] == REFERENCE["scope"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["case_id"])
def test_pair_reference_across_actual_protocols(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case
) -> None:
    _check_surfaces(
        monkeypatch,
        capsys,
        "sukuyo_compatibility",
        case["input_pair"],
        [
            "fixed_host_research_scope",
            "interpretation_contract.research_reference",
            "person1.calendar",
            "person2.calendar",
            "summary",
        ],
    )
