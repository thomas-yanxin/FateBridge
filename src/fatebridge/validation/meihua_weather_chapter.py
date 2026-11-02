"""Audit selected facsimile integration and frozen seasonal/frequency probes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def audit_weather_chapter(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_casting.py",
        "services/meihua.py",
        "data/meihua/weather-v1.json",
        "data/meihua/weather-controls-v1.json",
        "validation/meihua_weather_chapter.py",
    ]
    implementation = {
        n: hashlib.sha256((package / n).read_bytes()).hexdigest() for n in names
    }
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Frozen weather-chapter oracle or collation changed")
    materials = {}
    for ref in manifest["references"]:
        path = (directory / ref["file"]).resolve()
        if (
            not path.is_relative_to(directory.parent)
            or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]
        ):
            raise ValueError("Frozen weather-chapter source changed")
        materials[ref["id"]] = path.read_bytes()
    collation = json.loads((directory / "collation.json").read_text())
    bundle = json.loads((directory / "cases.json").read_text())
    inventory = json.loads((directory / "inventory.json").read_text())
    if len(bundle["cases"]) != 16 or manifest["mathematical_probe_count"] != 16:
        raise ValueError("Retain all sixteen weather-chapter probes")
    profile = weather_ruleset()
    rules = {r["id"]: r for r in profile["rules"]}
    reviewed_ids = {r["rule_id"] for r in collation["readings"]}
    if len(reviewed_ids) != 35 or not reviewed_ids.issubset(rules):
        raise ValueError("Rule-linked selected witness inventory changed")
    source_checks = []
    fixed = materials["fixed-volume-2"].decode()
    for ref in collation["readings"]:
        rule = rules[ref["rule_id"]]
        witnesses = rule["source_witnesses"]
        primary = [r for r in witnesses if r["source_id"] == "meihua-gen-nlc-1925"]
        matched = len(primary) == 1 and all(
            primary[0][k] == ref[v]
            for k, v in [
                ("selected_span", "nlc_selected_span"),
                ("original_pdf_index", "original_pdf_index"),
                ("section", "section"),
            ]
        )
        if "subject_status" in ref:
            matched = matched and rule["textual_status"] == ref["subject_status"]
        elif "fixed_transcription_selected_span" in ref:
            matched = (
                matched
                and rule["textual_status"]
                == "fixed_transcription_with_facsimile_variants"
                and rule["fixed_transcription_selected_span"]
                == ref["fixed_transcription_selected_span"]
            )
        for other in collation["dejutang_selected_confirmations"]:
            if other["rule_id"] == rule["id"]:
                matched = matched and any(
                    w["source_id"] == "meihua-gen-dejutang"
                    and w["section"] == "天時占第二"
                    and w["selected_span"] == other["selected_span"]
                    for w in witnesses
                )
        source_checks.append(
            {
                "rule_id": rule["id"],
                "fixed_quote_matches_its_own_transcription": rule["quote"] in fixed,
                "selected_witness_integration_matches": matched,
            }
        )
    cases = []
    for case in bundle["cases"]:
        result = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        cast = result["meihua"]
        weather = result["interpretation"]["weather"]
        expected = case["expected"]
        trace = next(
            row
            for row in weather["rule_trace"]
            if row["rule_id"] == expected["rule_id"]
        )
        actual = {
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "moving_line": cast["seed"]["moving_line"],
            "six_slots": [r["trigram"] for r in weather["trigram_slots"]],
            "rule_id": trace["rule_id"],
            "status": trace["status"],
            "effective_status": trace["effective_status"],
            "counts": (
                None
                if expected["counts"] is None
                else [
                    r["count"]
                    for r in trace["frequency_assessment"]["counting_variants"]
                ]
            ),
        }
        cases.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": k, "expected": v, "actual": actual[k]}
                    for k, v in expected.items()
                    if actual[k] != v
                ],
            }
        )
    if any(
        hashlib.sha256((package / n).read_bytes()).hexdigest() != h
        for n, h in implementation.items()
    ):
        raise ValueError("Weather-chapter implementation changed during audit")
    return {
        "audit_id": "meihua_weather_chapter_v5",
        "ruleset": profile["id"] + "@" + profile["version"],
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "selected_checks_passed": all(not c["disagreements"] for c in cases)
        and all(
            c["fixed_quote_matches_its_own_transcription"]
            and c["selected_witness_integration_matches"]
            for c in source_checks
        ),
        "literal_mathematical_probe_count": 16,
        "rule_linked_selected_reading_count": len(source_checks),
        "current_profile_rule_count": len(rules),
        "current_rules_not_reviewed_by_this_v5_corpus": sorted(
            set(rules) - reviewed_ids
        ),
        "unique_nlc_selected_spans": len(
            {r["nlc_selected_span"] for r in collation["readings"]}
        ),
        "source_checks": source_checks,
        "cases": cases,
        "chapter_inventory": inventory,
        "selected_span_scope": "A match verifies integration with assistant-read frozen spans, not their truth, a full critical edition or independent expert approval.",
        "source_review_adjudication": json.loads(
            (directory / "adjudications.json").read_text()
        ),
        "independent_human_expert_review": "not_performed",
        "primary_transcription_truth_automatically_proved": False,
        "complete_chapter_character_collation_established": False,
        "complete_chapter_semantic_conformance_established": False,
        "full_classical_conformance_established": False,
        "actual_model_runs": 0,
        "prospective_weather_observations_added": 0,
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
