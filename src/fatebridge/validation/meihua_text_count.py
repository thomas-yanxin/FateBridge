"""Audit frozen text-count witnesses and mathematical probes, not prediction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_casting import cast_explicit_meihua, explicit_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def audit_text_count(directory: Path) -> dict[str, Any]:
    base = directory.resolve()
    manifest_raw = (base / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    for group in ["files", "references"]:
        for name, digest in manifest[group].items():
            path = (base / name).resolve()
            if (
                not path.is_relative_to(base.parent)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                raise ValueError("Frozen text-count witness or hand oracle changed")
    cases = json.loads((base / "cases.json").read_text())["cases"]
    if len(cases) != 6 or [c["count"] for c in cases] != [11, 17, 32, 100, 101, 113]:
        raise ValueError("All six frozen boundary probes must remain")
    collation = json.loads((base / "collation.json").read_text())
    transcription = (base / "../meihua_v1/sources/volume-1.txt").read_text()
    if collation["witnesses"][0]["quote"] not in transcription:
        raise ValueError("Fixed text-count transcription quote is not preserved")
    reports = []
    for case in cases:
        for basis, expected_key in [
            ("raw_counts", "raw"),
            ("trigram_numbers", "reduced"),
        ]:
            output = calculate_meihua_cast(
                casting={
                    "method": "text_count",
                    "character_count": case["count"],
                    "text_basis": case["text_basis"],
                    "line_sum_basis": basis,
                }
            )
            cast = output["meihua"]
            expected = {
                "upper": case["upper"],
                "lower": case["lower"],
                "base": case["base"],
                **case[expected_key],
            }
            actual = {
                "upper": cast["seed"]["upper_number"],
                "lower": cast["seed"]["lower_number"],
                "line": cast["seed"]["moving_line"],
                "base": cast["base_hexagram"]["binary_code"],
                "changed": cast["changed_hexagram"]["binary_code"],
                "mutual": cast["mutual_hexagram"]["binary_code"],
                "body": cast["body_trigram"]["name"],
                "use": cast["use_trigram"]["name"],
            }
            reports.append(
                {
                    "case": case["id"],
                    "line_sum_basis": basis,
                    "expected": expected,
                    "actual": actual,
                    "disagreements": [
                        name
                        for name, value in expected.items()
                        if actual[name] != value
                    ],
                    "textual_extent_status": cast["seed"]["text_count_basis"][
                        "range_status"
                    ],
                }
            )
    mismatches = []
    changed90 = changed189 = 0
    for n in range(11, 200):
        upper, lower = n // 2, n - n // 2
        raw = n % 6 or 6
        reduced = ((upper % 8 or 8) + (lower % 8 or 8)) % 6 or 6
        changed189 += raw != reduced
        changed90 += n <= 100 and raw != reduced
        for basis, line in [("raw_counts", raw), ("trigram_numbers", reduced)]:
            result, _ = cast_explicit_meihua(
                {
                    "method": "text_count",
                    "character_count": n,
                    "text_basis": (
                        "fixed_transcription_2690596"
                        if n <= 100
                        else "nlc1925_selected_span"
                    ),
                    "line_sum_basis": basis,
                }
            )
            if result["seed"]["moving_line"] != line:
                mismatches.append({"count": n, "basis": basis})
    return {
        "audit_id": "meihua_text_count_boundaries_v1",
        "ruleset_id": explicit_ruleset()["id"],
        "ruleset_version": explicit_ruleset()["version"],
        "fixture_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "hand_derived_probe_count": 6,
        "formula_contexts_from_hand_probes": 12,
        "hand_probes": reports,
        "selected_hand_arithmetic_checks_passed": all(
            not r["disagreements"] for r in reports
        ),
        "working_counts11through199": 189,
        "exhaustive_declared_arithmetic_contexts": 378,
        "arithmetic_mismatches": mismatches,
        "working_counts_with_distinct_moving_lines": changed189,
        "old11through100_counts_with_distinct_moving_lines": changed90,
        "selected_transcription_quote_preserved": True,
        "facsimile_reading_scope": "assistant visual selected spans with original PDF and rendered-image hashes; not independent expert or whole-book authentication",
        "exact_facsimile_upper_bound_adjudicated": False,
        "raw_or_reduced_count_uniquely_classical": False,
        "software_extension_is_source_range_certification": False,
        "original_worked_examples_added": 0,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_prospective_sample_count": 0,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
