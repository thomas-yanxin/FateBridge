"""Separate hand ledgers for declared full and source-unadjudicated inputs."""

import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

REFERENCE = json.loads(
    (Path(__file__).parent / "data/compatibility/score-ledger.json").read_text()
)
# New source-case arithmetic is self-contained. The detailed primary hand
# ledger is checked separately by a local-data test; there is no IO fallback.
SOURCE_CONDITION_REFERENCE = {
    "case_id": "published_pair_unadjudicated_first_preferences_v12",
    "source_premises": {
        "first": {
            "strength": "强",
            "numerical_strength": "弱",
            "support_share_exact": "276/709",
            "ordinary_fuyi_requires_review": True,
            "useful": [],
            "avoid": [],
            "conditional": ["火", "土", "水"],
            "neutral": ["木", "金"],
            "useful_ten_gods": [],
            "month_path": "killer_seal",
            "chosen_path_id": None,
            "force_conditions": "unknown",
        },
        "second": "Same independently declared pillars/distribution/profile as "
        "score-ledger.json person2; no first-person preference conclusion is "
        "borrowed from its strong label.",
    },
    "dimension_ledgers": {
        "element_balance": [65, 5, -4, 3],
        "favorable_synergy": [60, 7, 10],
        "pattern_synergy": [68, -4, -4, -4, -4],
        "traditional_analysis": [50, -2, -2, -2, -5],
    },
    "ten_gods_ledgers": {
        "general": [65, 12, 2, 10, 4, 1, -2, -2],
        "marriage": [65, 14, 2, 11, 4, 2, -2, -2],
        "friendship": [65, 12, 4, 10, 4, 1, -2, -2],
        "business": [65, 15, 4, 13, -5, 6, 1, -2, -2, -5],
        "family": [65, 12, 2, 10, 4, 1, -2, -2],
    },
    "unresolved_dimensions": [
        "element_balance",
        "favorable_synergy",
        "pattern_synergy",
    ],
    "unresolved_harmonies": [
        "申辰半合水局",
        "寅午半合火局",
        "巳丑半合金局",
        "巳申六合",
    ],
    "tension_events": ["寅申六冲", "丑午六害", "寅巳六害", "寅巳申三刑"],
}
CURRENT_STRENGTH_METHOD_ID = "season_root_revelation_relations_v12"
CURRENT_COMPATIBILITY_METHOD_ID = "compatibility_weighted_rules_v3"


def current_reference_dimensions(kind="general"):
    values = {
        name: min(100, max(0, sum(terms)))
        for name, terms in REFERENCE["dimension_ledgers"].items()
    }
    values["ten_gods_relationship"] = min(
        100, max(0, sum(REFERENCE["ten_gods_ledgers"][kind]))
    )
    return values


def current_reference_total(kind="general"):
    values = current_reference_dimensions(kind)
    total = sum(
        (
            Decimal(str(score)) * Decimal(str(REFERENCE["weights"][kind][name]))
            for name, score in values.items()
        ),
        Decimal(0),
    )
    return float(total.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN))


def source_condition_reference_dimensions(kind="general"):
    values = {
        name: min(100, max(0, sum(terms)))
        for name, terms in SOURCE_CONDITION_REFERENCE["dimension_ledgers"].items()
    }
    values["ten_gods_relationship"] = min(
        100, max(0, sum(SOURCE_CONDITION_REFERENCE["ten_gods_ledgers"][kind]))
    )
    return values


def source_condition_reference_total(kind="general"):
    values = source_condition_reference_dimensions(kind)
    total = sum(
        (
            Decimal(str(score)) * Decimal(str(REFERENCE["weights"][kind][name]))
            for name, score in values.items()
        ),
        Decimal(0),
    )
    return float(total.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN))


def assert_score_reference(summary, detailed_analysis=None, kind="general"):
    """Original finite-rule ledger, conditional on its explicitly full profiles."""
    _assert_scoring(
        summary,
        detailed_analysis,
        kind,
        current_reference_dimensions(kind),
        current_reference_total(kind),
    )


def assert_source_condition_score_reference(
    summary, detailed_analysis=None, kind="general"
):
    """Current published case after independently checked unadjudicated inputs."""
    _assert_scoring(
        summary,
        detailed_analysis,
        kind,
        source_condition_reference_dimensions(kind),
        source_condition_reference_total(kind),
    )
    assert summary["status"] == summary["scoring"]["status"] == "partial"
    assert set(summary["scoring"]["unresolved_dimensions"]) == set(
        SOURCE_CONDITION_REFERENCE["unresolved_dimensions"]
    )
    assert "未裁定" in summary["compatibility_level"]
    if detailed_analysis is not None:
        balance = detailed_analysis["element_balance"]
        assert balance["assessment_status"] == "partial"
        assert {
            (row["person"], row["element"], row["state"])
            for row in balance["control_evidence"]
        } == {("第一人", "火", "conditional"), ("第二人", "金", "useful")}
        favorable = detailed_analysis["favorable_synergy"]
        assert favorable["assessment_status"] == "partial"
        assert favorable["score_evidence"]["base_score_is_support_evidence"] is False
        assert favorable["useful_ten_gods_support"] == []
        pattern = detailed_analysis["pattern_synergy"]
        assert pattern["assessment_status"] == "partial"
        assert pattern["supportive_patterns"] == pattern["risk_patterns"] == []
        assert {row["label"] for row in pattern["unresolved_patterns"]} == set(
            SOURCE_CONDITION_REFERENCE["unresolved_harmonies"]
        )
        assert {row["label"] for row in pattern["tension_patterns"]} == set(
            SOURCE_CONDITION_REFERENCE["tension_events"]
        )


def _assert_scoring(summary, detailed_analysis, kind, expected, total):
    receipt = summary["scoring"]
    assert receipt["method_id"] == CURRENT_COMPATIBILITY_METHOD_ID
    assert {
        name: entry["score"] for name, entry in receipt["dimensions"].items()
    } == expected
    assert {
        name: entry["weight"] for name, entry in receipt["dimensions"].items()
    } == REFERENCE["weights"][kind]
    for name, entry in receipt["dimensions"].items():
        contribution = Decimal(str(expected[name])) * Decimal(
            str(REFERENCE["weights"][kind][name])
        )
        assert Decimal(str(entry["weighted_score"])) == contribution
        if detailed_analysis is not None:
            assert detailed_analysis[name]["score"] == expected[name]
    exact_sum = sum(
        (
            Decimal(str(expected[name])) * Decimal(str(weight))
            for name, weight in REFERENCE["weights"][kind].items()
        ),
        Decimal(0),
    )
    assert Decimal(str(receipt["unrounded_score"])) == exact_sum
    assert summary["overall_score"] == total
    for person in ("person1", "person2"):
        assert (
            receipt["input_methods"][person]["strength_method_id"]
            == CURRENT_STRENGTH_METHOD_ID
        )
        assert (
            receipt["input_methods"][person]["useful_resolution_policy"]
            == "source_conditions_before_preference_v3"
        )
