"""Engineering accounting probes, not independent classical validation."""

from copy import deepcopy
from fractions import Fraction
from math import fsum

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate, assess_strength
from fatebridge.utils.data import STEM_ELEMENTS, Element


def evaluate(text, mode="non_day_transformation_v1"):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))
    return _evaluate(
        pillars,
        ElementAnalysis.seasonal_phases(pillars["month"][1]),
        DEFAULT_POLICY,
        stem_effect_mode=mode,
    )


@pytest.mark.parametrize(
    "text,target",
    [
        ("己酉 甲戌 戊辰 丙辰", "土"),
        ("庚辰 乙酉 辛酉 癸巳", "金"),
        ("辛酉 丙子 壬辰 庚子", "水"),
        ("丁卯 壬寅 甲子 乙亥", "木"),
        ("癸丑 戊午 丙午 壬辰", "火"),
    ],
)
def test_one_physical_budget_per_stem_with_separate_effect_element(text, target):
    result = evaluate(text)
    effects = result["stem_effects"]
    decision = effects["decisions"][0]
    assert decision["status"] == "conditioned_transformation"
    assert all(decision["conditions"].values())
    rows = effects["ledger"]
    assert [r["pillar"] for r in rows] == ["year", "month", "hour"]
    assert fsum(r["initial_budget"] for r in rows) == 3
    assert fsum(r["available_budget"] for r in rows) == 3
    assert [r["effective_element"] for r in rows[:2]] == [target, target]
    # The equation is checked from independent receipt quantities, not a snapshot.
    for row in rows:
        root = fsum(
            h["remaining_mass"]
            for h in result["hidden_stem_ledger"]
            if h["element"] == row["effective_element"]
        )
        assert row["energy"] == pytest.approx(
            (0.25 + 0.75 * min(1, root)) * row["seasonal_factor"]
        )
    assert fsum(effects["energies"].values()) == pytest.approx(
        fsum(r["energy"] for r in rows)
    )


def test_real_root_blocks_conversion_and_binding_uses_unrounded_energy():
    result = evaluate("癸亥 戊午 壬午 己酉")
    effects = result["stem_effects"]
    decision = effects["decisions"][0]
    assert decision["status"] == "binding"
    assert decision["anchored_opposing_roots"]
    for row in effects["ledger"][:2]:
        assert row["effective_element"] == row["physical_element"]
        assert row["available_budget"] == 0.85
        assert row["energy"] == pytest.approx(
            0.85 * row["activation"] * row["seasonal_factor"]
        )


@pytest.mark.parametrize("text", ["丙子 戊戌 癸酉 丁巳", "甲子 己巳 甲子 丁卯"])
def test_day_master_and_contested_pairs_require_review(text):
    result = evaluate(text)
    assert all(
        d["status"] == "day_master_or_contested_review"
        for d in result["stem_effects"]["decisions"]
    )
    assert all(r["available_budget"] == 1 for r in result["stem_effects"]["ledger"])


def test_effects_preserve_physical_branch_and_stem_facts():
    text = "癸丑 戊午 丙午 壬辰"
    base = evaluate(text, "legacy_v5")
    precise = evaluate(text, "precise_binding_only_v1")
    candidate = evaluate(text)
    for key in (
        "hidden_stem_ledger",
        "branch_budgets",
        "roots",
        "combination_contributions",
    ):
        assert base[key] == precise[key] == candidate[key]
    assert [r["stem"] for r in base["revealed_stems"]] == [
        r["stem"] for r in candidate["revealed_stems"]
    ]
    assert not any(
        d["status"] == "conditioned_transformation"
        for d in precise["stem_effects"]["decisions"]
    )
    assert candidate["support_strength"] > precise["support_strength"]
    assert precise["relations"] == base["relations"]
    assert all(
        r["root_activation_policy"] == "remaining_physical_hidden_stems_only_v1"
        for r in precise["revealed_stems"]
    )


def test_invalid_mode_and_order_independence():
    pillars = dict(
        zip(("year", "month", "day", "hour"), map(tuple, "癸丑 戊午 丙午 壬辰".split()))
    )
    saved = deepcopy(pillars)
    phases = ElementAnalysis.seasonal_phases("午")
    with pytest.raises(ValueError, match="Unknown stem effect"):
        _evaluate(pillars, phases, DEFAULT_POLICY, stem_effect_mode="guess")
    assert _evaluate(
        pillars, phases, DEFAULT_POLICY, stem_effect_mode="non_day_transformation_v1"
    ) == _evaluate(
        dict(reversed(list(pillars.items()))),
        phases,
        DEFAULT_POLICY,
        stem_effect_mode="non_day_transformation_v1",
    )
    assert pillars == saved


def test_no_synthetic_stem_identity_or_root_activation():
    effects = evaluate("癸丑 戊午 丙午 壬辰")["stem_effects"]
    for row in effects["ledger"]:
        assert row["physical_element"] == STEM_ELEMENTS[row["physical_stem"]][0].value
        assert row["effective_element"] in {e.value for e in Element}
    assert [r["physical_stem"] for r in effects["ledger"]] == ["癸", "戊", "壬"]


def test_production_binding_has_closed_form_fraction_without_display_rounding():
    pillars = dict(
        zip(("year", "month", "day", "hour"), map(tuple, "癸丑 戊午 丙午 壬辰".split()))
    )
    result = assess_strength(pillars, ElementAnalysis.seasonal_phases("午"))
    receipt = result["stem_energy_accounting"]
    # Independent hand derivation: 癸根丑4/7 + 辰2/7 = 6/7;
    # activation 1/4 + 3/4*6/7 = 25/28; summer water factor1/2;
    # binding17/20 gives85/224. The hour壬 is unbound25/56.
    assert receipt["ledger"][0]["energy"] == pytest.approx(
        float(Fraction(85, 224)), abs=1e-15
    )
    assert receipt["ledger"][1]["energy"] == pytest.approx(
        float(Fraction(51, 40)), abs=1e-15
    )
    assert receipt["ledger"][2]["energy"] == pytest.approx(
        float(Fraction(25, 56)), abs=1e-15
    )
    assert result["effective_elements"]["水"] == round(float(Fraction(305, 224)), 6)
    # Raw weighted-energy accounting closes before display rounding.
    assert result["support_strength"] + result["weaken_strength"] == pytest.approx(
        fsum(r["engineering_energy"] for r in result["hidden_stem_ledger"])
        + fsum(r["energy"] for r in receipt["ledger"]),
        abs=1e-13,
    )
    assert result["method_id"] == "season_root_revelation_relations_v10"
    assert result["strength_level"] == "中和"  # no unaccepted conversion promotion
    assert "stem_effects" not in result
    assert all(
        r["physical_element"] == r["effective_element"] for r in receipt["ledger"]
    )
