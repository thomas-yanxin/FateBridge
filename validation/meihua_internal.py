"""Frozen selected-source examples, arithmetic and direct-control fidelity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua.meihua_countercontrol import internal_control_ruleset
from fatebridge.services.meihua import calculate_meihua_cast
from validation.meihua_scans import read_frozen_artifact
from validation.meihua_source_guard import capture_current_implementation


def _resolve(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def audit_internal_controls(directory: Path) -> dict[str, Any]:

    directory = directory.resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Frozen internal-control reference changed")
        else:
            pass
    sources = json.loads((directory / "sources.json").read_text())
    for record in sources.values():
        read_frozen_artifact(
            directory, record["file"], record["sha256"], root=directory.parent
        )
    names = [
        "core/divination.py",
        "core/meihua/meihua.py",
        "core/meihua/meihua_countercontrol.py",
        "core/meihua/meihua_seasonal_reading.py",
        "data/meihua/seasonal-reading-nlc1925-v1.json",
        "core/meihua/meihua_casting.py",
        "core/meihua/meihua_general_variants.py",
        "core/meihua/meihua_topics.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "data/meihua/explicit-casts-v1.json",
        "data/meihua/internal-control-nlc1925-v1.json",
        "validation/meihua_scans.py",
        "validation/meihua_internal.py",
    ]
    hashes = capture_current_implementation(names)
    frozen = json.loads((directory / "readings.json").read_text())
    profile = internal_control_ruleset()
    source_checks = {
        "selected_source_matches": profile["source"] == frozen["source"],
        "two_selected_clauses_match": profile["rules"] == frozen["rules"],
        "worked_qualifying_snippets_match": profile["worked_snippets"]
        == frozen["worked_snippets"],
    }
    cases = json.loads((directory / "cases.json").read_text())
    errata = json.loads((directory / "oracle-errata.json").read_text())
    declared_errata = {r["case_id"]: r for r in errata["corrections"]}
    reports = []
    for case in [*cases["cases"], *cases["synthetic_probes"]]:
        result = calculate_meihua_cast(casting=case["casting"])
        cast = result["meihua"]
        control = result["interpretation"]["internal_countercontrol"]
        original_expected = case["expected"]
        expected = dict(original_expected)
        correction = declared_errata.get(case["id"])
        if correction is not None:
            if (
                case.get("kind") == "source_worked_calculation_not_observation"
                or expected[correction["field"]] != correction["frozen_original"]
            ):
                raise ValueError(
                    "Declared erratum no longer matches the frozen synthetic oracle"
                )
            else:
                pass
            expected[correction["field"]] = correction["corrected"]
        else:
            pass
        actual = {
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "body": cast["body_trigram"]["name"],
            "use": cast["use_trigram"]["name"],
            "relations": [r["relation"] for r in cast["stage_relations"]],
        }
        if case.get("kind") == "source_worked_calculation_not_observation":
            actual.update(
                {
                    k: cast["seed"][k]
                    for k in [
                        "raw_upper_number",
                        "raw_lower_number",
                        "line_sum",
                        "moving_line",
                    ]
                }
            )
        else:
            pass
        checks = {k: actual[k] == v for k, v in expected.items()}
        checks["five_role_occurrences_only"] = len(control["nodes"]) == 5 and [
            n["role"] for n in control["nodes"]
        ] == ["body", "use", "body_mutual", "use_mutual", "changed_use"]
        checks["all_node_fact_paths_resolve"] = all(
            (
                _resolve(result, n["fact_path"])["name"],
                _resolve(result, n["fact_path"])["element"],
            )
            == (n["trigram"], n["element"])
            for n in control["nodes"]
        )
        checks["no_outcome_invented"] = (
            "success_probability" not in control
            and control["net_verdict"] is control["event_time"] is None
            and not control["recursive_cancellation_applied"]
            and not control["seasonal_strength_used_to_disable_control"]
        )
        edge = case.get("expected_partial_relief_edge")
        relief = [
            q
            for q in control["qualifications"]
            if q["qualification"] == "partial_relief"
        ]
        if "expected_partial_relief_edge" in case:
            checks["source_countercontrolled_attacker"] = (
                not relief
                if edge is None
                else any(
                    q["role"] == edge[1] and edge[0] in q["incoming_controller_roles"]
                    for q in relief
                )
            )
        else:
            pass
        if "support_target" in case:
            q = next(
                q
                for q in control["qualifications"]
                if q["role"] == case["support_target"]
            )
            checks["support_controlled_by_own_three_roles"] = (
                q["qualification"] == "support_constrained"
                and q["incoming_controller_roles"] == case["incoming_controller_roles"]
            )
        else:
            pass
        reports.append(
            {
                "id": case["id"],
                "kind": case.get("kind", "synthetic_mathematical_probe"),
                "checks": checks,
                "original_oracle_disagreements": [
                    k for k, v in original_expected.items() if actual[k] != v
                ],
                "declared_erratum": correction,
                "disagreements": [k for k, v in checks.items() if not v],
            }
        )
    if capture_current_implementation(hashes) != hashes:
        raise ValueError(
            "Mei Hua internal-control files changed during audit; rerun a stable snapshot"
        )
    else:
        pass
    return {
        "audit_id": "meihua_internal_v1",
        "implementation_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_checks": source_checks,
        "cases": reports,
        "selected_checks_passed": all(source_checks.values())
        and all(not r["disagreements"] for r in reports),
        "source_worked_calculation_count": 3,
        "synthetic_probe_count": 1,
        "independent_human_expert_review": False,
        "actual_model_runs": 0,
        "prospective_observation_count": 0,
        "source_stories_are_outcome_observations": False,
        "oracle_errata": errata,
        "original_oracle_all_checks_passed": all(
            not r["original_oracle_disagreements"] for r in reports
        ),
        "whole_book_conformance_established": False,
        "predictive_efficacy_established": False,
    }
