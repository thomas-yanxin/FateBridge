"""Same-receipt body/seal arithmetic must stay coherent without filling gaps."""

import gzip
import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_classical_force import (
    ClassicalForceComponents,
    EngineeringForceComposition,
    ForceComponent,
)

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "docs/validation/bazi-force-coherence-files-v1"


@pytest.mark.parametrize("share", ["0", "1/2", "1"])
def test_zero_exact_total_cannot_have_a_defined_body_share(share):
    with pytest.raises(ValidationError):
        EngineeringForceComposition.model_validate(
            {
                "body_energy_exact": "0",
                "seal_energy_exact": "0",
                "body_seal_energy_relation": "equal",
                "body_within_support_exact": share,
            }
        )


def force(body, seal, basis="unrounded_same_assessment", **composition):
    key = (
        "engineering_energy_unrounded"
        if basis.startswith("unrounded")
        else "engineering_energy"
    )
    return {
        "components": {"body": {key: body}, "seal": {key: seal}},
        "engineering_composition": {"ratio_basis": basis, **composition},
    }


@pytest.mark.parametrize("share", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    "basis", ["unrounded_same_assessment", "rounded_legacy_assessment"]
)
def test_zero_recorded_float_total_cannot_have_a_defined_body_share(share, basis):
    with pytest.raises(ValidationError):
        ClassicalForceComponents.model_validate(
            force(0.0, 0.0, basis, body_within_support_share=share)
        )


@pytest.mark.parametrize(
    "basis", ["unrounded_same_assessment", "rounded_legacy_assessment"]
)
@pytest.mark.parametrize(
    "fault",
    [
        {"body_within_support_share": 0.75},
        {"legacy_float_body_seal_energy_relation": "body_greater"},
        {"legacy_float_body_seal_energy_relation": "equal"},
        {"body_seal_energy_relation": "body_greater"},
    ],
)
def test_supplied_composition_cannot_contradict_its_own_recorded_float_components(
    basis, fault
):
    with pytest.raises(ValidationError):
        ClassicalForceComponents.model_validate(
            force(1.0, 3.0, basis, comparison_basis=basis, **fault)
        )


@pytest.mark.parametrize(
    "key,value",
    [
        ("engineering_energy", float("nan")),
        ("engineering_energy", float("inf")),
        ("engineering_energy", -1.0),
        ("engineering_energy_unrounded", float("inf")),
    ],
)
def test_budget_energy_facts_must_be_finite_and_nonnegative(key, value):
    with pytest.raises(ValidationError):
        ForceComponent.model_validate({key: value})


@pytest.mark.parametrize(
    "context,force_value",
    [
        (
            {"method_id": "current"},
            {"engineering_composition": {"strength_method_id": "stale"}},
        ),
        (
            {"strength_level": "弱"},
            {"engineering_composition": {"strength_level": "强"}},
        ),
        (
            {"threshold_arithmetic": {"day_element": "水"}},
            {"components": {"body": {"element": "火"}}},
        ),
        (
            {"threshold_arithmetic": {"day_element": "水"}},
            {"components": {"seal": {"element": "土"}}},
        ),
        (
            {
                "threshold_arithmetic": {
                    "day_element": "水",
                    "energies_exact": {"水": "4"},
                }
            },
            {"engineering_composition": {"body_energy_exact": "3"}},
        ),
        (
            {
                "threshold_arithmetic": {
                    "day_element": "水",
                    "energies_exact": {"金": "1"},
                }
            },
            {"engineering_composition": {"seal_energy_exact": "4"}},
        ),
    ],
)
def test_known_same_chain_strength_receipt_and_force_facts_cannot_be_mixed(
    context, force_value
):
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(
            {"strength_context": context, "force_components": force_value}
        )


def test_correct_zero_positive_and_float_exact_disagreements_survive():
    for basis in ["unrounded_same_assessment", "rounded_legacy_assessment"]:
        ClassicalForceComponents.model_validate(
            force(
                0.0,
                0.0,
                basis,
                body_within_support_share=None,
                legacy_float_body_seal_energy_relation="equal",
            )
        )
        ClassicalForceComponents.model_validate(
            force(
                0.0,
                3.0,
                basis,
                body_within_support_share=0.0,
                legacy_float_body_seal_energy_relation="seal_greater",
            )
        )
        ClassicalForceComponents.model_validate(
            force(
                1.0,
                3.0,
                basis,
                body_within_support_share=0.25,
                legacy_float_body_seal_energy_relation="seal_greater",
            )
        )
    b, s = 0.1, 0.10000000000000002
    # The old floating evidence is retained even when exact arithmetic ties.
    ClassicalForceComponents.model_validate(
        force(
            b,
            s,
            body_within_support_share=b / (b + s),
            legacy_float_body_seal_energy_relation="seal_greater",
            comparison_basis="exact_rational_same_assessment",
            body_energy_exact="1/10",
            seal_energy_exact="1/10",
            body_within_support_exact="1/2",
            body_seal_energy_relation="equal",
        )
    )


def test_projection_subsets_keep_missing_unknown_and_never_insert_facts():
    paths = [
        ("components", "body", "engineering_energy_unrounded"),
        ("components", "seal", "engineering_energy_unrounded"),
        ("engineering_composition", "ratio_basis"),
        ("engineering_composition", "body_within_support_share"),
        ("engineering_composition", "legacy_float_body_seal_energy_relation"),
    ]
    complete = force(
        1.0,
        3.0,
        body_within_support_share=0.25,
        legacy_float_body_seal_energy_relation="seal_greater",
    )
    for flags in itertools.product([False, True], repeat=len(paths)):
        value = {}
        for use, path in zip(flags, paths):
            if not use:
                continue
            src = complete
            dst = value
            for part in path[:-1]:
                src = src[part]
                dst = dst.setdefault(part, {})
            dst[path[-1]] = src[path[-1]]
        before = deepcopy(value)
        ClassicalForceComponents.model_validate(value)
        assert value == before
    # A missing seal can be positive; zero body alone does not establish 0/0.
    for value in [
        {"body_energy_exact": "0", "body_within_support_exact": "0"},
        {"seal_energy_exact": "0", "body_within_support_exact": "1"},
    ]:
        EngineeringForceComposition.model_validate(value)
    ClassicalForceComponents.model_validate(
        {
            "components": {"body": {"engineering_energy_unrounded": 0.0}},
            "engineering_composition": {
                "ratio_basis": "unrounded_same_assessment",
                "body_within_support_share": 0.0,
            },
        }
    )


def test_all408_frozen_complete_chains_and_original19_uncertainties_survive():
    total = original = unresolved = zero = 0
    with gzip.open(FILES / "all408-before-first.jsonl.gz", "rt") as handle:
        for line in handle:
            row = json.loads(line)
            before = deepcopy(row)
            BaziEvidenceChain.model_validate(row["natal"])
            assert row == before
            comp = row["natal"]["force_components"]["engineering_composition"]
            if comp["body_energy_exact"] == comp["seal_energy_exact"] == "0":
                assert (
                    comp["body_within_support_exact"] is None
                    and comp["body_within_support_share"] is None
                )
                zero += 1
            if row["case"].get("is_original_nineteen"):
                original += 1
                unresolved += (
                    row["case"]["expected_strength"]
                    != row["strength"]["strength_level"]
                )
                assert set(
                    row["natal"]["force_components"]["classical_adjudication"].values()
                ) == {"not_adjudicated"}
                assert (
                    row["natal"]["month_command"]["intra_month_duty"]["selected_stem"]
                    is None
                )
            total += 1
    assert (total, original, unresolved, zero) == (408, 19, 17, 3)
