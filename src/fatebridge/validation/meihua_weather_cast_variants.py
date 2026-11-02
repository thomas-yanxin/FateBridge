"""Frozen candidate-specific weather probes, without forecasting observations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.services.meihua import calculate_meihua_cast


def audit_weather_cast_variants(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_casting.py",
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "data/meihua/explicit-casts-v1.json",
        "data/meihua/weather-v1.json",
        "data/meihua/weather-controls-v1.json",
        "validation/meihua_weather_cast_variants.py",
    ]
    hashes = {n: hashlib.sha256((package / n).read_bytes()).hexdigest() for n in names}
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    case_raw = (directory / "cases.json").read_bytes()
    if hashlib.sha256(case_raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen weather cast-variant probes changed")
    for ref in [*manifest["references"], manifest["scan_manifest"]]:
        path = (directory / ref["file"]).resolve()
        if not path.is_relative_to(directory.parent.resolve()):
            raise ValueError(
                "Weather cast-variant reference escapes fixture collection"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("Frozen weather cast-variant reference changed")
    cases = json.loads(case_raw)["cases"]
    if len(cases) != 7 or manifest["case_count"] != 7:
        raise ValueError("Retain all seven cast-variant probes")
    reports = []
    for case in cases:
        result = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        weather = result["interpretation"]["weather"]
        comparison = weather["casting_comparison"]
        details = {r["line_sum_basis"]: r for r in weather["casting_variant_traces"]}
        rows = {r["line_sum_basis"]: r for r in weather["casting_variants"]}
        expected = case["expected"]
        actual: dict[str, Any] = {
            "comparison_status": comparison["status"],
            "variants": {},
        }
        if "trigram_counts_differ" in expected:
            actual["trigram_counts_differ"] = comparison["trigram_counts_differ"]
        if "base_code" in expected:
            actual["base_code"] = result["meihua"]["base_hexagram"]["binary_code"]
        for basis, wanted in expected["variants"].items():
            detail = details[basis]
            trace = {r["rule_id"]: r for r in detail["rule_trace"]}
            controls = {r["rule_id"]: r["status"] for r in detail["controls"]}
            actual["variants"][basis] = {
                **{
                    key: rows[basis][key]
                    for key in ("moving_line", "changed_code", "mutual_code")
                },
                "six_slots": [r["trigram"] for r in detail["trigram_slots"]],
                "rules": {
                    key: [trace[key]["status"], trace[key]["effective_status"]]
                    for key in wanted["rules"]
                },
                "metal_controls_wood_weather": controls["metal_controls_wood_weather"],
            }
        # A missing or unexpected candidate must not disappear from the denominator.
        candidate_bases_match = set(rows) == set(expected["variants"]) == set(details)
        reports.append(
            {
                "id": case["id"],
                "candidate_bases_match": candidate_bases_match,
                "disagreements": [
                    {"field": k, "expected": value, "actual": actual[k]}
                    for k, value in expected.items()
                    if actual[k] != value
                ],
            }
        )
    if any(
        hashlib.sha256((package / n).read_bytes()).hexdigest() != h
        for n, h in hashes.items()
    ):
        raise ValueError("Weather cast-variant implementation changed during audit")
    return {
        "audit_id": "meihua_weather_cast_variants_v3",
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "implementation_sha256": hashes,
        "selected_checks_passed": all(
            r["candidate_bases_match"] and not r["disagreements"] for r in reports
        ),
        "independent_manual_probe_count": len(cases),
        "cases": reports,
        "original_worked_example_count_added": 0,
        "real_model_semantic_acceptance": "not_tested",
        "real_weather_observation_count": 0,
        "unique_classical_count_convention_established": False,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
