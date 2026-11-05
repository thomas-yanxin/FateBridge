"""Preserve adverse research evidence independently of current model applicability."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_dayan_reconstruction import (
    reconstruction_scope_lines,
    reconstruction_scope_reference,
)

FIXTURE = Path(__file__).parent / "data/sukuyo-research-direction-before-code-v89.json"


def frozen_scope():
    return json.loads(FIXTURE.read_text())["existing_fixed_host_research_scope"]


def test_complete_fixed_host_reference_matches_pre_edit_scientific_outputs():
    reference = reconstruction_scope_reference()
    assert reference["fixed_host_research_scope"] == frozen_scope()
    assert reference["applies_to_every_input_or_calendar"] is False
    scope = reference["fixed_host_research_scope"]
    assert [
        len(scope[k])
        for k in (
            "same_direction_rows",
            "different_direction_rows",
            "unknown_direction_rows",
        )
    ] == [274, 52, 1]
    assert scope["unknown_direction_rows"] == [263]


def test_modern_input_explains_adverse_reference_without_applying_model():
    lines = reconstruction_scope_lines(reconstruction_scope_reference(), {})
    assert any("没有应用该大衍名义模型" in line for line in lines)
    assert any("274相合、52不同、1未知" in line for line in lines)
    assert any("不把它应用成现代本次历日" in line for line in lines)
    assert any("作者横杠未补成不进" in line for line in lines)


def test_scope_copies_do_not_mutate_cached_reference():
    first = reconstruction_scope_reference()
    first["fixed_host_research_scope"]["different_direction_rows"].clear()
    assert (
        reconstruction_scope_reference()["fixed_host_research_scope"] == frozen_scope()
    )


@pytest.mark.parametrize(
    "key", ["research_scope_delivery_round", "fixed_host_research_scope"]
)
def test_current_reference_cannot_silently_downgrade_when_one_key_is_missing(key):
    reference = reconstruction_scope_reference()
    del reference[key]
    with pytest.raises(ValueError, match="全表研究方向"):
        reconstruction_scope_lines(reference, {})


@pytest.mark.parametrize("key", ["different_direction_rows", "unknown_direction_rows"])
def test_omitted_adverse_or_unknown_rows_are_rejected(key):
    reference = deepcopy(reconstruction_scope_reference())
    reference["fixed_host_research_scope"][key] = []
    with pytest.raises(ValueError, match="全表研究方向"):
        reconstruction_scope_lines(reference, {})


def test_archived_reference_does_not_claim_later_research_delivery():
    reference = reconstruction_scope_reference()
    del reference["research_scope_delivery_round"]
    del reference["fixed_host_research_scope"]
    assert not any(
        "274相合、52不同、1未知" in line
        for line in reconstruction_scope_lines(reference, {})
    )
