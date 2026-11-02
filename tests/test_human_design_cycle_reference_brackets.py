"""Frozen integer clock oracles, full runs, historical replay and forgeries."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.human_design_reference_order import reference_ordering
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "docs/validation/human-design-cycle-reference-brackets-v1"
PLAN_PATH = ROOT / "tests/fixtures/human-design-cycle-reference-brackets.json"
PLAN = json.loads(PLAN_PATH.read_text())
OLD = json.loads(
    gzip.decompress((A / "evidence/original-cycle142-run.json.gz").read_bytes())
)["run"]
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_independent_oracle_and_original_failures_remain_frozen():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "a58fd54c5725c35a286b1d1b3bd95968a41cecb27f57aa345472d5f877406a09"
    )
    original = A / "evidence/original-cycle142-run.json.gz"
    assert (
        hashlib.sha256(original.read_bytes()).hexdigest()
        == PLAN["source_packet_sha256"]
    )
    before = json.loads((A / "evidence/before-summary-checks.json").read_text())
    assert len(PLAN["cases"]) == before["case_count"] == 28
    assert before["failures"] == 14
    assert [r["id"] for r in before["cases"]] == [r["id"] for r in PLAN["cases"]]


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_all_original_reference_clocks_use_exact_order_not_rounded_jd(case):
    context = deepcopy(OLD["cycle_context"])
    label, tt = cycles.reference_epoch(case["reference_utc"])
    context["reference_utc"], context["reference_jd_tt"] = label, tt
    context["reference_ordering"] = reference_ordering(
        OLD["birth_utc"], context["birth_jd_tt"], label, tt
    )
    exact = context["reference_ordering"]["reference"]["exact_jd_tt"]
    # Compare the actual clock proof to the independent integer-Gregorian
    # ratio, without using its already computed relation as the expectation.
    assert int(exact["numerator"]) * int(
        case["exact_reference_tt"]["denominator"]
    ) == int(case["exact_reference_tt"]["numerator"]) * int(exact["denominator"])
    original_summary = cycles.cycle_summary(context, OLD["profile"])
    before = json.loads((A / "evidence/before-summary-checks.json").read_text())
    expected_old = next(r for r in before["cases"] if r["id"] == case["id"])[
        "before_relation"
    ]
    assert (
        next(b for b in original_summary["bodies"] if b["body"] == case["body"])[
            "reference_relation"
        ]
        == expected_old
    )
    context["ruleset"] = cycles.cycle_ruleset()
    current = cycles.cycle_summary(context, OLD["profile"])
    assert (
        next(b for b in current["bodies"] if b["body"] == case["body"])[
            "reference_relation"
        ]
        == case["expected_relation"]
    )
    assert current["reference_contact_ordering"]["physical_accuracy_certified"] is False
    assert current["sixth_line"]["current_phase"] is None


@pytest.fixture(
    scope="module", params=["saturn-0-lower-before", "saturn-0-upper-after"]
)
def complete(request):
    case = next(c for c in PLAN["cases"] if c["id"] == request.param)
    old = json.loads(
        gzip.decompress((A / f"evidence/old-engine-{case['id']}.json.gz").read_bytes())
    )
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        env.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        result = execute_tool(SPEC, SPEC.request_model(**old["input"]))
    return case, old, result


def test_complete_current_run_corrects_relation_without_altering_any_astronomy(
    complete,
):
    case, old, current = complete
    assert old["proof"]["status"] == "verified_fixed_template_reading"
    assert (
        old["run"]["cycle_summary"]["bodies"][0]["reference_relation"]
        == "within_numerical_contact_bracket"
    )
    assert (
        current["cycle_summary"]["bodies"][0]["reference_relation"]
        == case["expected_relation"]
    )
    for key in (
        "activations",
        "bodygraph",
        "variables",
        "design_solver",
        "time_scales",
        "profile",
    ):
        assert current[key] == old["run"][key]
    from scripts.check_human_design_cycle_prefix import original_body_projection

    for new_body, old_body in zip(
        current["cycle_context"]["bodies"],
        old["run"]["cycle_context"]["bodies"],
        strict=True,
    ):
        # Every original root, coordinate and source index remains exact;
        # only declared supplemental fields and extra probes are removed.
        assert original_body_projection(new_body, old_body) == old_body
    assert (
        current["cycle_context"]["source_evidence"]
        == old["run"]["cycle_context"]["source_evidence"]
    )
    assert (
        current["cycle_context"]["reference_ordering"]
        == old["run"]["cycle_context"]["reference_ordering"]
    )
    assert current["cycle_context"]["ruleset"]["version"] == "1.6.0"
    assert (
        current["run_metadata"]["contract_sha256"]
        != old["run"]["run_metadata"]["contract_sha256"]
    )
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier recomputed the sky"),
    ):
        proof = verify_human_design_reading(current)
    assert proof["status"] == "verified_fixed_template_reading", proof
    assert current["validation"]["all_three_axes_full_marks"] is False


def test_original_wrong_complete_receipt_is_now_rejected_not_grandfathered(complete):
    _, original, _ = complete
    assert original["proof"]["status"] == "verified_fixed_template_reading"
    result = verify_human_design_reading(original["run"])
    assert result["status"] == "rejected"
    assert {
        "code": "historical_reference_contact_ordering_loss",
        "path": "cycle_summary.bodies.0.reference_relation",
    } in result["errors"]


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
    _, _, original = complete
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
        value["cycle_context"]["ruleset"] = cycles.cycle_ruleset(
            legacy_reference_relation=True
        )
        value["cycle_summary"] = cycles.cycle_summary(
            value["cycle_context"], value["profile"]
        )
        if mutation == "old_version_unknown_contract":
            value["run_metadata"]["contract_sha256"] = "0" * 64
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    result = verify_human_design_reading(value)
    assert result["status"] == "rejected"
    if mutation in {"old_version", "old_version_unknown_contract"}:
        assert {"code": "incomplete_or_malformed_cycle_witnesses"} in result["errors"]
