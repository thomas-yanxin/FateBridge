"""Trace all nineteen original disagreements through body/seal and passage facts."""

from __future__ import annotations

import argparse
import gzip
import json
import math
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.utils.data import GENERATION_CYCLE

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_focus_validation_v1"
ORDER = ("year", "month", "day", "hour")
SOURCES = (
    "src/fatebridge/core/strength.py",
    "src/fatebridge/core/classical_force.py",
    "src/fatebridge/core/classical_passage.py",
    "src/fatebridge/core/classical_roots.py",
    "src/fatebridge/core/classical_stages.py",
    "src/fatebridge/core/bazi_evidence.py",
    "src/fatebridge/core/elements.py",
    "src/fatebridge/core/stem_effects.py",
    "src/fatebridge/core/storage_movement.py",
    "src/fatebridge/core/complete_bureaus.py",
    "src/fatebridge/utils/data.py",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> dict[str, Any]:
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen evidence changed: " + str(path))
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def source_manifest() -> dict[str, str]:
    return {name: digest(ROOT / name) for name in SOURCES}


def receipt_totals(assessment: dict[str, Any]) -> dict[str, float]:
    """Independent addition of supplied receipts, not another strength solver."""
    parts: dict[str, list[float]] = {e.value: [] for e in GENERATION_CYCLE}
    for row in assessment["hidden_stem_ledger"]:
        parts[row["element"]].append(row["engineering_energy"])
    for row in assessment["combination_contributions"]:
        phase = assessment["seasonal_phases"][row["element"]]
        factor = (
            1
            + (assessment["seasonal_factors"][phase] - 1)
            * assessment["parameters"]["seasonal_spread"]
        )
        parts[row["element"]].append(row["mass"] * factor)
    for row in assessment["stem_energy_accounting"]["ledger"]:
        parts[row["effective_element"]].append(row["energy"])
    totals = {element: math.fsum(values) for element, values in parts.items()}
    for element, total in totals.items():
        if not math.isclose(
            total,
            assessment["effective_elements_unrounded"][element],
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Unrounded receipt fails to reconcile")
    return totals


def path_conditions(paths: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "observed": len(paths),
        "all_nodes_have_remaining_roots": sum(
            p["all_nodes_have_remaining_roots"] is True for p in paths
        ),
        "all_binding_states_clear": sum(
            all(s == "no_binding_recorded" for s in p["binding_states"]) for p in paths
        ),
        "binding_or_review_recorded": sum(
            any(
                s in {"binding_recorded", "pending_combination_review"}
                for s in p["binding_states"]
            )
            for p in paths
        ),
        "shared_pillar_paths": sum(
            p["position_status"] == "shared_pillar_step" for p in paths
        ),
    }


def audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    for name, expected in protocol["originals"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Original input, counterexample or protocol changed")
    original = frozen(ROOT / "tests/data/bazi_disagreement_review_v1/review.json")
    notes = frozen(FIXTURE / "source-focus-notes.json")
    if [c["id"] for c in original["cases"]] != [c["id"] for c in notes["cases"]]:
        raise ValueError("An original anchor disappeared")
    before = source_manifest()
    rows = []
    for source, note in zip(original["cases"], notes["cases"], strict=True):
        if (
            source["pillars"] != note["pillars"]
            or source["expected_strength"] != note["original_expected_strength"]
        ):
            raise ValueError("Original source input or label changed")
        pillars = dict(zip(ORDER, map(tuple, source["pillars"])))
        model = ElementAnalysis.analyze_day_master_strength(pillars)
        evidence = build_natal_evidence(pillars, model)
        assessment = model["assessment"]
        totals = receipt_totals(assessment)
        force = evidence["force_components"]
        components = force["components"]
        for component in components.values():
            if not math.isclose(
                component["engineering_energy_unrounded"],
                totals[component["element"]],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Body/seal view does not reuse the supplied receipt")
        passage = evidence["classical_passage"]
        rows.append(
            {
                "id": source["id"],
                "pillars": source["pillars"],
                "expected_strength": source["expected_strength"],
                "actual_strength": assessment["strength_level"],
                "matches_original_label": assessment["strength_level"]
                == source["expected_strength"],
                "source_note": note,
                "body_seal": {
                    "body_energy": components["body"]["engineering_energy_unrounded"],
                    "seal_energy": components["seal"]["engineering_energy_unrounded"],
                    "composition": force["engineering_composition"],
                    "body_physical_roots": components["body"]["physical_hidden_roots"],
                    "seal_physical_roots": components["seal"]["physical_hidden_roots"],
                    "body_structural_root_qualifications": assessment[
                        "root_qualifications"
                    ],
                    "classical_adjudication": force["classical_adjudication"],
                },
                "month_command": {
                    "branch_phase": assessment["month_command"],
                    "intra_month_duty": evidence["month_command"]["intra_month_duty"],
                    "source_relative_day": note["day_from_jie_as_printed"],
                    "source_duty_stem": note["duty_stem_as_printed"],
                    "exact_civil_instant": None,
                    "calendar_elapsed_from_four_pillars": "not_recoverable_without_birth_instant",
                },
                "passage": {
                    **{
                        name: path_conditions(passage[name])
                        for name in (
                            "visible_paths",
                            "principal_hidden_paths",
                            "all_hidden_paths",
                            "mixed_paths",
                        )
                    },
                    "effectiveness": "not_adjudicated",
                    "clash_exemptions_added": False,
                },
                "raw_same_calculation": {
                    "assessment": assessment,
                    "evidence": evidence,
                },
            }
        )
    after = source_manifest()
    drift = [n for n in before if before[n] != after[n]]
    if drift:
        raise ValueError("Source changed during focus audit: " + ",".join(drift))
    return {
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "source_notes_sha256": digest(FIXTURE / "source-focus-notes.json"),
        "runner_sha256": digest(Path(__file__)),
        "source_manifest_before": before,
        "source_manifest_after": after,
        "source_drift": drift,
        "original_cases_retained": len(rows),
        "resolved_under_original_labels": [
            r["id"] for r in rows if r["matches_original_label"]
        ],
        "unresolved": [r["id"] for r in rows if not r["matches_original_label"]],
        "explicit_source_relative_days": sum(
            r["source_note"]["day_from_jie_as_printed"] is not None for r in rows
        ),
        "unknown_source_relative_days": sum(
            r["source_note"]["day_from_jie_as_printed"] is None for r in rows
        ),
        "absolute_source_birth_instants": 0,
        "all_unrounded_component_receipts_reconcile": True,
        "rows": rows,
        "production_strength_label_policy_changed": False,
        "candidate_adopted": False,
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
        "authority_certified": False,
        "overall_score": None,
        "scope": "All nineteen exposed source anchors; same-developer reading and arithmetic verification. Full same-calculation paths retained. Conditions, counts and clearer precision do not establish classical force, effective passage, a new independent success rate or reality prediction.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="New gzip JSON report"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the first audit")
    result = audit()
    with args.output.open("xb") as stream:
        with gzip.GzipFile(
            filename="", fileobj=stream, mode="wb", mtime=0
        ) as compressed:
            compressed.write(
                (
                    json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n"
                ).encode()
            )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "original_cases_retained",
                    "resolved_under_original_labels",
                    "unresolved",
                    "explicit_source_relative_days",
                    "unknown_source_relative_days",
                    "all_unrounded_component_receipts_reconcile",
                    "candidate_adopted",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
