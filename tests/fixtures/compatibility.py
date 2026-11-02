"""Independent, versioned score references; never derive expectations from SUT."""

import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

REFERENCE = json.loads(
    (Path(__file__).parent / "compatibility-score-reference.json").read_text(
        encoding="utf-8"
    )
)
CURRENT_VERSION = "source_conditions_v2_v6"
# Preserve every historical input and numerical ledger. The v5 record changes
# method provenance for this pair, whose numeric rule terms remain unchanged.
# v6 repairs unrounded binding; neither fixed input has a binding stem pair.
CURRENT_STRENGTH_METHOD_ID = "season_root_revelation_relations_v6"
CURRENT_RESOLUTION_POLICY = "source_conditions_before_preference_v3"
# The fixed pair does not enter the from-child screen. Keep all frozen v2
# ledgers and profiles intact; current provenance separately reports v3.


def reference_dimensions(kind="general", version=CURRENT_VERSION):
    reference = REFERENCE["versions"][version]
    values = {
        name: min(100, max(0, sum(terms)))
        for name, terms in reference["dimension_ledgers"].items()
    }
    values["ten_gods_relationship"] = min(
        100, max(0, sum(reference["ten_gods_ledgers"][kind]))
    )
    return values


def reference_total(kind="general", version=CURRENT_VERSION):
    dimensions = reference_dimensions(kind, version)
    total = sum(
        Decimal(str(score)) * Decimal(str(REFERENCE["weights"][kind][name]))
        for name, score in dimensions.items()
    )
    return float(
        min(Decimal(100), max(Decimal(0), total)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_EVEN
        )
    )


def assert_score_reference(summary, detailed_analysis=None, kind="general"):
    receipt = summary["scoring"]
    assert receipt["method_id"] == REFERENCE["compatibility_method_id"]
    expected_dimensions = reference_dimensions(kind)
    assert {
        name: entry["score"] for name, entry in receipt["dimensions"].items()
    } == expected_dimensions
    assert {
        name: entry["weight"] for name, entry in receipt["dimensions"].items()
    } == REFERENCE["weights"][kind]
    for name, entry in receipt["dimensions"].items():
        expected_contribution = Decimal(str(expected_dimensions[name])) * Decimal(
            str(REFERENCE["weights"][kind][name])
        )
        assert Decimal(str(entry["weighted_score"])) == expected_contribution
        if detailed_analysis is not None:
            assert detailed_analysis[name]["score"] == expected_dimensions[name]
    assert summary["overall_score"] == reference_total(kind)
    for name in ("person1", "person2"):
        assert (
            receipt["input_methods"][name]["strength_method_id"]
            == CURRENT_STRENGTH_METHOD_ID
        )
        assert (
            receipt["input_methods"][name]["useful_resolution_policy"]
            == CURRENT_RESOLUTION_POLICY
        )
