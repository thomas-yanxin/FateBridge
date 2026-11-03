"""Manual rational controls for the explicitly limited time-branch projection."""

from copy import deepcopy
from fractions import Fraction

import pytest
from pydantic import ValidationError

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_timing import TimingInteractions
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.core.timing_strength import StrengthProjectionBaseline


def calculate(branches, timing):
    natal = dict(
        zip(
            ("year", "month", "day", "hour"),
            (("甲" if b in "子寅辰午申戌" else "乙", b) for b in branches),
        )
    )
    a = ElementAnalysis.analyze_day_master_strength(natal)["assessment"]
    baseline = StrengthProjectionBaseline(
        method_id=a["method_id"],
        strength_level=a["strength_level"],
        numerical_label=a["threshold_arithmetic"]["numerical_label"],
        support_share_exact=a["threshold_arithmetic"]["share_exact"],
        energies_exact=a["threshold_arithmetic"]["energies_exact"],
        parameters=a["parameters"],
        seasonal_phases=a["seasonal_phases"],
        seasonal_factors=a["seasonal_factors"],
        relations=a["relations"],
    )
    before = deepcopy((natal, timing, baseline))
    result = analyze_timing_interactions(natal, timing, strength_baseline=baseline)
    TimingInteractions.model_validate(result)
    assert (natal, timing, baseline) == before
    return result["strength_projection"], a


def mass(layer, element):
    return sum(
        Fraction(r["remaining_mass_exact"])
        for r in layer["hidden_roots"]
        if r["element"] == element
    )


def test_clash_uses_original_month_budget_and_does_not_add_time_fire_to_natal_energy():
    result, a = calculate("子子子子", {"liunian": {"stem": "庚", "branch": "午"}})
    layer = result["layers"][0]
    assert layer["status"] == "projected"
    # Four original 子: budgets 2+4+2+2=10. 午 contributes comparison-only
    # 火4/3 土2/3. Water wins; retain .9 once, so original水roots total9.
    assert layer["comparison_powers_exact"]["水"] == "10"
    assert layer["comparison_powers_exact"]["火"] == "4/3"
    assert mass(layer, "水") == 9
    assert layer["energies_exact"]["火"] == layer["energies_exact"]["土"] == "0"
    assert set(r["pillar"] for r in layer["hidden_roots"]) == {
        "year",
        "month",
        "day",
        "hour",
    }
    assert result["month_command_node_id"] == "natal.month"
    assert result["full_timing_strength_status"] == "not_adjudicated"
    assert result["baseline"]["parameters"] == a["parameters"]


def test_existing_self_punishment_and_new_clash_do_not_multiply_retention():
    result, a = calculate("午午午午", {"dayun": {"stem": "壬", "branch": "子"}})
    layer = result["layers"][0]
    assert layer["status"] == "projected"
    # Initial火:10*(2/3), native repeated午 already retains.9 =>6.
    assert mass(layer, "火") == 6
    assert layer["energies_exact"] == a["threshold_arithmetic"]["energies_exact"]


def test_complete_zi_mao_punishment_retains_nine_tenths_once_per_physical_root():
    result, _ = calculate("卯卯卯卯", {"liunian": {"stem": "壬", "branch": "子"}})
    row = result["layers"][0]
    assert row["status"] == "projected"
    assert len(row["effect_relation_ids"]) == 4
    assert mass(row, "木") == 9


def test_two_branch_punishment_fragment_and_harm_do_not_mechanically_remove_roots():
    result, a = calculate("寅寅寅寅", {"liunian": {"stem": "丁", "branch": "巳"}})
    row = result["layers"][0]
    assert row["status"] == "projected" and row["effect_relation_ids"] == []
    assert row["energies_exact"] == a["threshold_arithmetic"]["energies_exact"]


def test_original_fragment_fixture_now_retains_its_unresolved_repeated_stem_match():
    # Preserve the original 己巳 control: its four甲 partners include the day
    # stem, so the new combined-budget scope cannot choose a binding winner.
    result, _ = calculate("寅寅寅寅", {"liunian": {"stem": "己", "branch": "巳"}})
    row = result["layers"][0]
    assert row["status"] == "blocked"
    assert (
        len(
            [
                r
                for r in row["blocker_relation_ids"]
                if r.startswith("stem_combination:")
            ]
        )
        == 4
    )


def test_completed_earth_punishment_cannot_override_existing_stronger_water_loss():
    result, a = calculate("丑未丑未", {"liunian": {"stem": "戊", "branch": "戌"}})
    row = result["layers"][0]
    assert row["status"] == "projected" and row["effect_relation_ids"]
    assert all(r.startswith("branch_punishment:") for r in row["effect_relation_ids"])
    assert row["energies_exact"] == a["threshold_arithmetic"]["energies_exact"]


def test_storage_movement_keeps_earth_and_reduces_only_water_beyond_old_self_punishment():
    result, _ = calculate("辰辰辰辰", {"liunian": {"stem": "甲", "branch": "戌"}})
    layer = result["layers"][0]
    assert layer["status"] == "projected"
    assert mass(layer, "土") == Fraction(36, 7)
    assert mass(layer, "木") == Fraction(18, 7)
    assert mass(layer, "水") == Fraction(15, 14)


def test_new_time_combination_blocks_numeric_projection_instead_of_claiming_resolution():
    result, _ = calculate("子子子子", {"liunian": {"stem": "乙", "branch": "丑"}})
    row = result["layers"][0]
    assert row["status"] == "blocked" and row["blocker_relation_ids"]
    assert row["hidden_roots"] == [] and row["support_share_exact"] is None
    assert row["residual_natal_numerical_label"] is None


def test_clash_on_old_combination_blocks_reusing_its_prior_transfer():
    result, _ = calculate("寅午戌子", {"liunian": {"stem": "庚", "branch": "申"}})
    row = result["layers"][0]
    assert row["status"] == "blocked"
    assert any(r.startswith("natal.relations:") for r in row["blocker_relation_ids"])


def test_layers_are_separate_and_a_new_wood_branch_does_not_create_a_natal_root():
    first, a = calculate("子子子子", {"dayun": {"stem": "庚", "branch": "午"}})
    both, _ = calculate(
        "子子子子",
        {
            "dayun": {"stem": "庚", "branch": "午"},
            "liunian": {"stem": "甲", "branch": "寅"},
        },
    )
    assert first["layers"][0] == both["layers"][0]
    assert mass(both["layers"][1], "木") == 0
    assert (
        both["layers"][1]["energies_exact"]
        == a["threshold_arithmetic"]["energies_exact"]
    )


def test_blocked_receipt_cannot_publish_a_force_label_and_projections_stay_optional():
    result, _ = calculate("子子子子", {"liunian": {"stem": "乙", "branch": "丑"}})
    result["layers"][0]["residual_natal_numerical_label"] = "强"
    with pytest.raises(ValidationError, match="未解会合"):
        TimingInteractions.model_validate({"strength_projection": result})
    TimingInteractions.model_validate(
        {"strength_projection": {"full_timing_strength_status": "not_adjudicated"}}
    )


@pytest.mark.parametrize(
    "fault",
    ["negative", "nonfinite", "retention_over_one", "wrong_grade", "wrong_method"],
)
def test_present_budget_and_threshold_receipts_cannot_contradict_the_baseline(fault):
    result, _ = calculate("子子子子", {"liunian": {"stem": "庚", "branch": "午"}})
    row = result["layers"][0]
    if fault == "negative":
        row["hidden_roots"][0]["remaining_mass_exact"] = "-1"
    elif fault == "nonfinite":
        row["support_share_exact"] = "nan"
    elif fault == "retention_over_one":
        row["retention_factors_exact"]["year"]["水"] = "11/10"
    elif fault == "wrong_grade":
        row["residual_natal_numerical_label"] = "弱"
    else:
        result["baseline_method_id"] = "unrelated"
    with pytest.raises(ValidationError):
        TimingInteractions.model_validate({"strength_projection": result})
