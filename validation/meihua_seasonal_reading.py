"""Frozen text/diagram probes of the selected month-strength reading layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua.meihua_seasonal_reading import seasonal_reading_ruleset
from fatebridge.services.meihua import calculate_meihua_cast
from validation.meihua_scans import read_frozen_artifact
from validation.meihua_source_guard import capture_current_implementation


def _resolve(result: dict[str, Any], path: str) -> Any:
    value: Any = result
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def audit_seasonal_reading(directory: Path) -> dict[str, Any]:

    directory = directory.resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Frozen seasonal-reading reference changed")
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
        "core/meihua/meihua_strength_exceptions.py",
        "core/meihua/meihua_general_variants.py",
        "core/meihua/meihua_topics.py",
        "data/meihua/seasonal-reading-nlc1925-v1.json",
        "data/meihua/strength-exceptions-nlc1925-v1.json",
        "validation/meihua_scans.py",
        "validation/meihua_seasonal_reading.py",
    ]
    hashes = capture_current_implementation(names)
    frozen = json.loads((directory / "readings.json").read_text())
    runtime = seasonal_reading_ruleset()
    source_checks = {
        k: runtime[k] == frozen[k]
        for k in [
            "selected_source",
            "section",
            "rules",
            "unresolved_clause",
            "same_book_comparison",
        ]
    }
    comparison = runtime["same_book_comparison"]
    source_checks["comparison_quote_in_fixed_volume3"] = (
        comparison["quote"]
        in (directory / sources["fixed_volume3"]["file"]).read_text()
    )
    reports = []
    for case in json.loads((directory / "cases.json").read_text())["diagrams"]:
        for context in case["months"]:
            out = calculate_meihua_cast(
                casting=case["casting"], season_month_branch=context["month"]
            )
            c = out["interpretation"]["seasonal_qualification"]
            checks = {
                "changed_code": out["meihua"]["changed_hexagram"]["binary_code"]
                == case["changed_code"],
                "mutual_code": out["meihua"]["mutual_hexagram"]["binary_code"]
                == case["mutual_code"],
                "role_trigrams": [r["trigram"] for r in c["roles"]]
                == case["role_trigrams"],
                "original_relations": [r["relation_to_body"] for r in c["roles"][1:]]
                == case["relations"],
                "strengths": [r["strength"] for r in c["roles"]]
                == context["strengths"],
                "joint_statuses": [r["status"] for r in c["condition_checks"]]
                == context["joint_statuses"],
                "preference_statuses": [r["status"] for r in c["preferences"]]
                == context["preference_statuses"],
                "unknown_not_replaced": all(
                    r["strength_status"] != "known_selected_label"
                    for r in c["roles"]
                    if r["strength"] in {None, "原文未定"}
                ),
                "trigram_paths_resolve": all(
                    _resolve(out, r["fact_path"])["name"] == r["trigram"]
                    for r in c["roles"]
                ),
                "strength_paths_resolve": all(
                    _resolve(out, r["strength_fact_path"]) == r["strength"]
                    for r in c["roles"]
                    if r["strength_fact_path"] is not None
                ),
                "relation_paths_resolve": all(
                    _resolve(out, r["relation_fact_path"]) == r["relation_to_body"]
                    for r in c["roles"][1:]
                ),
                "unresolved_repeated_control_not_guessed": c["repeated_control_clause"][
                    "status"
                ]
                == "not_adjudicated",
                "no_joint_preference_gate": not c[
                    "preference_matches_are_joint_necessary_conditions"
                ],
                "no_net_verdict": "success_probability" not in c
                and c["net_verdict"] is c["event_time"] is None,
            }
            reports.append(
                {
                    "id": case["id"],
                    "month": context["month"],
                    "checks": checks,
                    "disagreements": [k for k, v in checks.items() if not v],
                }
            )
    if capture_current_implementation(hashes) != hashes:
        raise ValueError(
            "Seasonal-reading source changed during audit; rerun a stable snapshot"
        )
    else:
        pass
    return {
        "audit_id": "meihua_seasonal_reading_v1",
        "implementation_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_checks": source_checks,
        "cases": reports,
        "selected_checks_passed": all(source_checks.values())
        and all(not r["disagreements"] for r in reports),
        "unique_hand_diagrams": 4,
        "month_context_checks": len(reports),
        "selected_source_clauses": 6,
        "original_worked_forecasts_added": 0,
        "actual_model_runs": 0,
        "predictive_observation_count": 0,
        "independent_human_expert_review": False,
        "full_chapter_or_book_conformance_established": False,
        "predictive_efficacy_established": False,
    }
