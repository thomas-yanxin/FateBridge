"""Independent exact reference clocks and current complete-result controls."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.human_design_reference_order import reference_ordering
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading
from tests.support.human_design_current import complete_run

PLAN = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/human-design-cycle-reference-brackets.json"
    ).read_text()
)


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_all_reference_clocks_use_exact_order_against_declared_intervals(case):
    label, tt = cycles.reference_epoch(case["reference_utc"])
    birth_label, birth_tt = cycles.reference_epoch("1980-01-01T00:00:00Z")
    ordering = reference_ordering(birth_label, birth_tt, label, tt)
    exact = ordering["reference"]["exact_jd_tt"]
    ratio = Fraction(int(exact["numerator"]), int(exact["denominator"]))
    assert ratio == Fraction(
        int(case["exact_reference_tt"]["numerator"]),
        int(case["exact_reference_tt"]["denominator"]),
    )
    grouped = {}
    for row in PLAN["cases"]:
        if row["body"] == case["body"]:
            endpoints = grouped.setdefault(row["contact_index"], {})
            old = endpoints.setdefault(row["endpoint"], row["endpoint_tt"])
            assert old == row["endpoint_tt"]
    contacts = [
        {"bracket_jd_tt": [ends["lower"], ends["upper"]]}
        for _, ends in sorted(grouped.items())
    ]
    assert (
        cycles.reference_contact_relation(
            {"status": "sampled_search_completed", "contacts": contacts}, ratio
        )
        == case["expected_relation"]
    )


@pytest.fixture(
    scope="module", params=["saturn-0-lower-before", "saturn-0-upper-after"]
)
def complete(request):
    case = next(c for c in PLAN["cases"] if c["id"] == request.param)
    return case, complete_run(
        birth_year=1980,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        cycle_reference_datetime=case["reference_utc"],
    )


def test_current_complete_run_uses_the_exact_reference_relation(complete):
    case, current = complete
    assert (
        current["cycle_summary"]["bodies"][0]["reference_relation"]
        == case["expected_relation"]
    )
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier recalculated sky"),
    ):
        assert (
            verify_human_design_reading(current)["status"]
            == "verified_fixed_template_reading"
        )
    assert not current["validation"]["all_three_axes_full_marks"]


@pytest.mark.parametrize(
    "mutation",
    [
        "rounded_relation",
        "changed_exact_reference",
        "false_physical",
        "missing_basis",
        "old_version",
        "old_version_unknown_contract",
    ],
)
def test_fresh_hash_cannot_hide_wrong_order_or_downgrade(complete, mutation):
    _, original = complete
    value = deepcopy(original)
    if mutation == "rounded_relation":
        value["cycle_summary"]["bodies"][0][
            "reference_relation"
        ] = "within_numerical_contact_bracket"
    elif mutation == "changed_exact_reference":
        ratio = value["cycle_context"]["reference_ordering"]["reference"]["exact_jd_tt"]
        ratio["numerator"] = str(int(ratio["numerator"]) + 1)
    elif mutation == "false_physical":
        value["cycle_summary"]["reference_contact_ordering"][
            "physical_accuracy_certified"
        ] = True
    elif mutation == "missing_basis":
        del value["cycle_summary"]["reference_contact_ordering"]
    else:
        value["cycle_context"]["ruleset"]["version"] = "unsupported"
        if mutation == "old_version_unknown_contract":
            value["run_metadata"]["contract_sha256"] = "0" * 64
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    result = verify_human_design_reading(value)
    assert result["status"] == "rejected"
    if mutation in {"old_version", "old_version_unknown_contract"}:
        assert {"code": "incomplete_or_malformed_cycle_witnesses"} in result["errors"]
