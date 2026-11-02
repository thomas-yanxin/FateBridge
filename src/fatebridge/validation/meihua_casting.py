"""Frozen non-time casting examples and unresolved textual semantics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_casting import explicit_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def audit_explicit_casts(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    files = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_countercontrol.py",
        "core/meihua_seasonal_reading.py",
        "data/meihua/seasonal-reading-nlc1925-v1.json",
        "data/meihua/internal-control-nlc1925-v1.json",
        "core/meihua_casting.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "validation/meihua_casting.py",
        "core/zhouyi.py",
        "data/classical/zhouyi.json",
        "data/meihua/time-v1.json",
        "data/meihua/explicit-casts-v1.json",
    ]
    implementation = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in files
    }
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    cases_path = directory / "cases.json"
    case_bytes = cases_path.read_bytes()
    if hashlib.sha256(case_bytes).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen explicit-casting oracle changed")
    materials = {}
    for reference in manifest["references"]:
        path = (directory / reference["file"]).resolve()
        if not path.is_relative_to(directory.parent.resolve()):
            raise ValueError("Source escapes the fixture collection")
        source_bytes = path.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != reference["sha256"]:
            raise ValueError("Frozen primary source changed")
        materials[reference["id"]] = source_bytes.decode("utf-8")
    bundle = json.loads(case_bytes)
    if (
        len(bundle["cases"]) != 13
        or sum(c["kind"] == "classical_worked_example" for c in bundle["cases"]) != 9
    ):
        raise ValueError("The v1 corpus must retain all nine examples and four probes")
    reports = []
    for case in bundle["cases"]:
        result = calculate_meihua_cast(casting=case["input"])
        if "error" in result:
            reports.append(
                {
                    "id": case["id"],
                    "kind": case["kind"],
                    "error": result["error_code"],
                    "disagreements": [{"field": "calculation", "actual": "error"}],
                }
            )
            continue
        cast = result["meihua"]
        stages = {row["role"]: row for row in cast["stage_relations"]}
        actual = {
            **{
                key: cast["seed"][key]
                for key in ["upper_number", "lower_number", "moving_line"]
            },
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "body": cast["body_trigram"]["name"],
            "use": cast["use_trigram"]["name"],
            "relation": cast["body_use_relation"],
            **{
                role + "_relation": stages[role]["relation"]
                for role in ["body_mutual", "use_mutual", "changed_use"]
            },
        }
        if set(actual) != set(case["expected"]):
            raise ValueError("Incomplete explicit-casting oracle fields")
        reports.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "disagreements": [
                    {"field": key, "expected": expected, "actual": actual[key]}
                    for key, expected in case["expected"].items()
                    if actual[key] != expected
                ],
            }
        )
    quotes = [
        {
            "rule_id": rule["id"],
            "matched": rule["quote"] in materials[rule["source_id"]],
        }
        for rule in explicit_ruleset()["rules"]
        if "quote" in rule
    ]
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != value
        for name, value in implementation.items()
    ):
        raise ValueError(
            "Mei Hua engine files changed during audit; rerun against a stable snapshot"
        )
    return {
        "audit_id": "meihua_explicit_casts_v1",
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "selected_calculation_checks_passed": all(
            not r["disagreements"] for r in reports
        )
        and all(q["matched"] for q in quotes),
        "original_worked_example_count": 9,
        "independent_rule_probe_count": 4,
        "cases": reports,
        "quote_checks": quotes,
        "semantic_findings": bundle["semantic_findings"],
        "reference_findings_scope": "Frozen reference creation state. Later facsimile readings and object-count probes have a separate meihua_scan_v1 audit; these historical notes are not the current capability inventory.",
        "full_classical_conformance_established": False,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_efficacy": "not_tested",
        "real_world_prospective_sample_count": 0,
        "authority_certified": False,
        "unresolved": bundle["unresolved"],
    }
