"""Frozen selected facsimile readings and independently hand-drawn probes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def reference_bundle(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    required = {
        "collation.json",
        "object-count-cases.json",
        "sources/nlc-1925.pdf",
        "sources/nlc-1925-retrieval.json",
        "sources/dejutang-selected.pdf",
        "sources/dejutang-selection.json",
        "sources/dejutang-retrieval.json",
    }
    if {r["file"] for r in manifest["artifacts"]} != required:
        raise ValueError("The selected scan corpus must retain every frozen artifact")
    for record in manifest["artifacts"]:
        path = (directory / record["file"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Scan reference escapes its frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Frozen scan reference changed: {record['file']}")
    return manifest  # type: ignore[no-any-return]


def audit_scanned_rules(directory: Path) -> dict[str, Any]:
    from fatebridge.core.meihua_casting import explicit_ruleset
    from fatebridge.services.meihua import calculate_meihua_cast

    reference_bundle(directory)
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_casting.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "data/meihua/explicit-casts-v1.json",
        "validation/meihua_scans.py",
    ]
    implementation = {
        n: hashlib.sha256((package / n).read_bytes()).hexdigest() for n in names
    }
    collation = json.loads((directory / "collation.json").read_text(encoding="utf-8"))
    cases = json.loads(
        (directory / "object-count-cases.json").read_text(encoding="utf-8")
    )["cases"]
    if len(collation["readings"]) != 7 or len(cases) != 5:
        raise ValueError("Retain all seven selected readings and five manual probes")
    rule = next(r for r in explicit_ruleset()["rules"] if r["id"] == "object_count")
    span = next(r["span"] for r in collation["readings"] if r["id"] == "object-count")
    normalized_quote = re.sub(r"[，。\s]", "", rule["quote"])
    reports = []
    for case in cases:
        result = calculate_meihua_cast(casting=case["input"])
        if "error" in result:
            reports.append(
                {
                    "id": case["id"],
                    "disagreements": [
                        {"field": "calculation", "actual": result["error_code"]}
                    ],
                }
            )
            continue
        cast = result["meihua"]
        seed = cast["seed"]
        stages = {r["role"]: r for r in cast["stage_relations"]}
        actual = {
            **{
                k: seed[k]
                for k in ("upper_number", "lower_number", "moving_line", "line_sum")
            },
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "body": cast["body_trigram"]["name"],
            "use": cast["use_trigram"]["name"],
            "relation": cast["body_use_relation"],
            **{
                k + "_relation": stages[k]["relation"]
                for k in ("body_mutual", "use_mutual", "changed_use")
            },
        }
        if set(actual) != set(case["expected"]):
            raise ValueError(
                "The manual probe must retain its complete declared fields"
            )
        reports.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": k, "expected": v, "actual": actual[k]}
                    for k, v in case["expected"].items()
                    if actual[k] != v
                ],
            }
        )
    if any(
        hashlib.sha256((package / n).read_bytes()).hexdigest() != d
        for n, d in implementation.items()
    ):
        raise ValueError(
            "Implementation changed during scan audit; use a stable snapshot"
        )
    return {
        "audit_id": "meihua_selected_scans_and_object_count_v1",
        "profile": f"{explicit_ruleset()['id']}@{explicit_ruleset()['version']}",
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(
            (directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "selected_calculation_checks_passed": all(
            not r["disagreements"] for r in reports
        )
        and normalized_quote == span,
        "runtime_quote_matches_frozen_manual_reading": normalized_quote == span,
        "manual_facsimile_readings": collation["readings"],
        "manual_reading_authentication": "reviewable_images_and_locators_not_automated_proof_of_transcription_truth",
        "independent_rule_probe_count": len(cases),
        "cases": reports,
        "new_historical_worked_examples": 0,
        "real_world_observations": 0,
        "full_text_conformance_established": False,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_efficacy_established": False,
        "authority_certified": False,
        "unresolved": [
            "物數占超八时卦數指原数量或上卦卦序数尚未唯一裁定，保留两套结果。",
            "單組聲音的加時配數句義仍待裁定，不能静默當作物數占。",
            "少年與牛例的互字範圍仍未唯一裁定；七畫是兩本所載，不等於規範字形七畫已證明。",
            "尚未完成全书校勘、外应、精确应期或独立现实效力验收。",
        ],
    }
