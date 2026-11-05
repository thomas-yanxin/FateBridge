"""Independent Fraction controls for the bounded existing-stem budget change."""

from copy import deepcopy
from fractions import Fraction as Q

import pytest
from pydantic import ValidationError

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_timing import TimingInteractions
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.core.timing_strength import StrengthProjectionBaseline
from tests.support.bazi_strength_reference_v3 import (
    PHASE_FACTORS,
    reconstruct,
    seasonal_phases,
)

ORDER = ("year", "month", "day", "hour")
STEMS = "甲乙丙丁戊己庚辛壬癸"
ELEMENT = dict(zip(STEMS, "木木火火土土金金水水"))
GENERATES = dict(zip("木火土金水", "火土金水木"))


def projection(values, timing):
    natal = dict(zip(ORDER, map(tuple, values)))
    a = ElementAnalysis.analyze_day_master_strength(natal)["assessment"]
    exact = a["threshold_arithmetic"]
    baseline = StrengthProjectionBaseline(
        method_id=a["method_id"],
        strength_level=a["strength_level"],
        numerical_label=exact["numerical_label"],
        support_share_exact=exact["share_exact"],
        energies_exact=exact["energies_exact"],
        parameters=a["parameters"],
        seasonal_phases=a["seasonal_phases"],
        seasonal_factors=a["seasonal_factors"],
        relations=a["relations"],
    )
    before = deepcopy((natal, timing, baseline))
    full = analyze_timing_interactions(natal, timing, strength_baseline=baseline)
    TimingInteractions.model_validate(full)
    assert (natal, timing, baseline) == before
    return full["strength_projection"], a


def test_unique_time_stem_changes_only_the_existing_month_stem_budget():
    result, baseline = projection(
        ("乙卯", "己卯", "辛卯", "癸卯"),
        {"dayun": {"stem": "甲", "branch": "寅"}},
    )
    row = result["layers"][0]
    assert row["status"] == "projected"
    assert row["effect_relation_ids"] == ["stem_combination:natal.month+timing.dayun"]
    # Baseline wood27, earth1/8, water1/4 => metal support1/219.
    # Unrooted己 has activation1/4, spring earth死1/2. Its existing1/8
    # receives the declared17/20 binding multiplier =>17/160. No time甲
    # or time寅 root is added: total4377/160 and support share17/4377.
    assert baseline["threshold_arithmetic"]["share_exact"] == "1/219"
    assert row["stem_retention_factors_exact"] == {
        "year": "1",
        "month": "17/20",
        "hour": "1",
    }
    assert row["energies_exact"] == {
        "木": "27",
        "火": "0",
        "土": "17/160",
        "金": "0",
        "水": "1/4",
    }
    assert row["support_share_exact"] == "17/4377"
    assert all(r["stem"] == "乙" for r in row["hidden_roots"])
    assert sum(Q(r["remaining_mass_exact"]) for r in row["hidden_roots"]) == 10
    assert result["full_timing_strength_status"] == "not_adjudicated"
    assert result["baseline"]["parameters"]["binding"] == 0.85
    assert (
        result["stem_binding_source"]["source_sha256"]
        == "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
    )


@pytest.mark.parametrize("pair", ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"])
@pytest.mark.parametrize("reverse", [False, True])
def test_all_five_pairs_both_directions_match_independent_existing_budget_math(
    pair, reverse
):
    target, incoming = pair[::-1] if reverse else pair
    other = next(s for s in STEMS if s not in pair)

    def pillar(s):
        return s + ("子" if STEMS.index(s) % 2 == 0 else "卯")

    values = [pillar(other), pillar(target), pillar(other), pillar(other)]
    timing_branch = "寅" if STEMS.index(incoming) % 2 == 0 else "巳"
    result, baseline = projection(
        values, {"dayun": {"stem": incoming, "branch": timing_branch}}
    )
    row = result["layers"][0]
    assert row["status"] == "projected"
    assert row["effect_relation_ids"] == ["stem_combination:natal.month+timing.dayun"]
    expected = reconstruct(values, baseline["relations"])["energies"]
    # These fictional controls contain only子/卯 physical roots. If both
    # occur every root is in an actual子卯 punishment, retaining9/10 once.
    branches = [v[1] for v in values]
    retention = Q(9, 10) if set(branches) == {"子", "卯"} else Q(1)
    roots = sum(
        (Q(4) if p == "month" else Q(2)) * retention
        for p, branch in zip(ORDER, branches)
        if ELEMENT[target] == ("水" if branch == "子" else "木")
    )
    activation = Q(1, 4) + Q(3, 4) * min(Q(1), roots)
    factor = PHASE_FACTORS[seasonal_phases(branches[1])[ELEMENT[target]]]
    expected[ELEMENT[target]] -= Q(3, 20) * activation * factor
    assert {e: Q(v) for e, v in row["energies_exact"].items()} == expected
    body = ELEMENT[other]
    seal = next(e for e, child in GENERATES.items() if child == body)
    share = (expected[body] + expected[seal]) / sum(expected.values())
    assert Q(row["support_share_exact"]) == share
    assert row["residual_natal_numerical_label"] == (
        "强" if share > Q(3, 5) else "弱" if share < Q(2, 5) else "中和"
    )


@pytest.mark.parametrize(
    "values,incoming",
    [
        (("乙卯", "己卯", "辛卯", "癸卯"), "丙"),
        (("己卯", "己卯", "辛卯", "癸卯"), "甲"),
        (("甲子", "己卯", "辛卯", "癸卯"), "甲"),
    ],
)
def test_day_match_repeated_partner_and_existing_combination_remain_blocked(
    values, incoming
):
    result, _ = projection(values, {"dayun": {"stem": incoming, "branch": "寅"}})
    row = result["layers"][0]
    assert row["status"] == "blocked" and row["blocker_relation_ids"]
    assert row["energies_exact"] == row["stem_retention_factors_exact"] == {}
    assert row["support_share_exact"] is None
    if values[0] == "甲子":
        assert any(
            r.startswith("natal.relations:") for r in row["blocker_relation_ids"]
        )


def test_time_layers_do_not_compete_or_accumulate_into_a_fifth_natal_column():
    values = ("乙卯", "己卯", "辛卯", "癸卯")
    first, _ = projection(values, {"dayun": {"stem": "甲", "branch": "寅"}})
    both, _ = projection(
        values,
        {
            "dayun": {"stem": "甲", "branch": "寅"},
            "liunian": {"stem": "甲", "branch": "寅"},
        },
    )
    assert first["layers"][0] == both["layers"][0]
    assert both["layers"][1]["status"] == "blocked"
    assert both["layers"][1]["energies_exact"] == {}


@pytest.mark.parametrize("layer", ["liunian", "liuyue", "liuri", "liushi"])
def test_dayun_source_is_not_extended_to_other_time_scales(layer):
    result, _ = projection(
        ("乙卯", "己卯", "辛卯", "癸卯"),
        {layer: {"stem": "甲", "branch": "寅"}},
    )
    row = result["layers"][0]
    assert row["status"] == "blocked"
    assert row["blocker_relation_ids"] == [
        f"stem_combination:natal.month+timing.{layer}"
    ]
    assert row["stem_retention_factors_exact"] == row["energies_exact"] == {}
    assert result["stem_binding_source"]["supported_layer"] == "dayun"


def test_stem_retention_contract_rejects_invented_negative_or_excess_budget():
    result, _ = projection(
        ("乙卯", "己卯", "辛卯", "癸卯"), {"dayun": {"stem": "甲", "branch": "寅"}}
    )
    for value in ("-1", "21/20", "nan"):
        changed = deepcopy(result)
        changed["layers"][0]["stem_retention_factors_exact"]["month"] = value
        with pytest.raises(ValidationError):
            TimingInteractions.model_validate({"strength_projection": changed})
    changed = deepcopy(result)
    changed["layers"][0]["stem_retention_factors_exact"]["day"] = "17/20"
    with pytest.raises(ValidationError):
        TimingInteractions.model_validate({"strength_projection": changed})
