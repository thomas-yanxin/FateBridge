"""Source-local conditional roles, never 38 independent charts or fortune labels."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.classical_stages import twelve_life_stage
from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.output_timing import TimingInteractions
from fatebridge.core.output_timing_carriers import TimingCarrier
from fatebridge.core.timing_carriers import describe_timing_carrier
from fatebridge.core.timing_interactions import analyze_timing_interactions

NATAL = dict(
    zip(("year", "month", "day", "hour"), map(tuple, "乙未 戊子 庚辰 丁丑".split()))
)
FIXTURE = (
    Path(__file__).parents[1] / "data/bazi_timing_carriers_v1/source-examples.json"
)
REFERENCE = json.loads(FIXTURE.read_text())


def test_source_transcription_and_all_38_conditional_examples():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == FIXTURE.with_suffix(".sha256").read_text().strip()
    )
    assert len(REFERENCE["cases"]) == 38
    for case in REFERENCE["cases"]:
        row = describe_timing_carrier("timing.dayun", *case["pillar"], NATAL)
        if case["desired_component"] == "branch":
            assert row["branch_principal_element"] == case["desired_element"]
            assert row["branch_covered_if_desired"] is True, case["id"]
        else:
            assert row["stem_element"] == case["desired_element"]
            assert row["stem_pressure_if_desired"] is True, case["id"]
        assert row["effective_force_status"] == "not_adjudicated"


def test_own_seat_is_not_replaced_by_external_natal_roots():
    row = describe_timing_carrier("timing.dayun", "乙", "酉", NATAL)
    assert row["principal_relation"] == "branch_overcomes_stem"
    assert row["own_hidden_roots"] == [] and row["own_hidden_root_present"] is False
    assert {r["position"] for r in row["external_natal_roots"]} == {"year", "day"}
    assert row["stem_pressure_if_desired"] is True
    assert row["branch_covered_if_desired"] is False


def test_reference_yin_growth_name_does_not_invent_an_actual_fire_root():
    assert twelve_life_stage("丁", "酉") == "长生"
    row = describe_timing_carrier("timing.liunian", "丁", "酉", NATAL)
    assert row["own_hidden_roots"] == [] and not row["own_hidden_root_present"]
    assert row["principal_relation"] == "stem_overcomes_branch"
    # Two conditional perspectives coexist; neither is the actual desired god.
    assert row["branch_covered_if_desired"] and row["stem_pressure_if_desired"]


def test_actual_root_does_not_erase_a_contrary_principal_relation():
    row = describe_timing_carrier("timing.dayun", "戊", "寅", NATAL)
    assert row["own_hidden_root_present"]
    assert row["own_hidden_roots"] == [{"stem": "戊", "rank": 3, "exact_stem": True}]
    assert row["principal_relation"] == "branch_overcomes_stem"
    assert row["stem_pressure_if_desired"]


def test_generation_is_separate_from_an_actual_root_and_no_false_pressure():
    row = describe_timing_carrier("timing.liunian", "甲", "子", NATAL)
    assert row["principal_relation"] == "branch_generates_stem"
    assert not row["own_hidden_root_present"]
    assert not row["stem_pressure_if_desired"] and not row["branch_covered_if_desired"]
    row = describe_timing_carrier("timing.dayun", "己", "未", NATAL)
    assert (
        row["principal_relation"] == "same_element" and row["own_hidden_root_present"]
    )
    assert not row["stem_pressure_if_desired"]


def test_all_sixty_legal_pillars_validate_without_mutating_natal_facts():
    before = deepcopy(NATAL)
    for pair in SEXAGENARY_CYCLE:
        row = describe_timing_carrier("timing.dayun", *pair, NATAL)
        TimingCarrier.model_validate(row)
        assert (
            describe_timing_carrier(
                "timing.dayun", *pair, dict(reversed(list(NATAL.items())))
            )
            == row
        )
    assert NATAL == before
    with pytest.raises(ValueError, match="六十甲子"):
        describe_timing_carrier("timing.dayun", "甲", "丑", NATAL)


def test_shared_interactions_align_the_two_receipts_without_relabeling_existing_roots():
    result = analyze_timing_interactions(
        NATAL,
        {
            "dayun": {"stem": "乙", "branch": "酉"},
            "liunian": {"stem": "癸", "branch": "酉"},
        },
    )
    assert result["method_id"] == "natal_timing_relations_v2"
    assert len(result["pillar_carriers"]) == len(result["ten_god_context"]) == 2
    for row, old in zip(
        result["pillar_carriers"], result["ten_god_context"], strict=True
    ):
        assert row["node_id"] == old["node_id"]
        assert row["external_natal_roots"] == old["natal_same_element_roots"]
    assert any(
        e["rule_id"] == "stem_combination"
        and set(e["participants"]) == {"natal.month", "timing.liunian"}
        and e["transformation"] == "not_assessed"
        for e in result["relations"]
    )


def test_partial_contract_and_false_root_or_unconditional_role_are_rejected():
    TimingCarrier.model_validate({"own_hidden_root_present": False})
    with pytest.raises(ValidationError, match="本柱实根"):
        TimingCarrier.model_validate(
            {"own_hidden_roots": [], "own_hidden_root_present": True}
        )
    with pytest.raises(ValidationError, match="盖头条件"):
        TimingCarrier.model_validate(
            {
                "principal_relation": "branch_generates_stem",
                "branch_covered_if_desired": True,
            }
        )


def test_summary_cannot_change_an_actual_receipt():
    result = analyze_timing_interactions(
        NATAL, {"dayun": {"stem": "乙", "branch": "酉"}}
    )
    TimingInteractions.model_validate(result)
    wrong = deepcopy(result)
    wrong["pillar_carrier_summary"][0]["own_hidden_root_present"] = True
    with pytest.raises(ValidationError, match="同次明细"):
        TimingInteractions.model_validate(wrong)
    wrong = deepcopy(result)
    wrong["pillar_carrier_summary"][0]["external_natal_root_count"] = 3
    with pytest.raises(ValidationError, match="原局根明细"):
        TimingInteractions.model_validate(wrong)
