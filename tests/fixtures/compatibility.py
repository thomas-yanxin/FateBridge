"""Independent, versioned score references; never derive expectations from SUT."""

import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

REFERENCE = json.loads(
    (Path(__file__).parent / "compatibility-score-reference.json").read_text(
        encoding="utf-8"
    )
)
CURRENT_VERSION = "season_root_v2"


def reference_dimensions(kind="general", version=CURRENT_VERSION):
    reference = REFERENCE["versions"][version]
    values = {
        name: sum(terms) for name, terms in reference["dimension_ledgers"].items()
    }
    values["ten_gods_relationship"] = sum(reference["ten_gods_ledgers"][kind])
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
            == REFERENCE["versions"][CURRENT_VERSION]["strength_method_id"]
        )
        assert (
            receipt["input_methods"][name]["useful_resolution_policy"]
            == REFERENCE["resolution_policy"]
        )
