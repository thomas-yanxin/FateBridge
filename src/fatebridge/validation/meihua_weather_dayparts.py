"""Frozen daypart diagrams and scope comparisons, without real weather claims."""

from __future__ import annotations

import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

from fatebridge.core.divination import build_mutual_hexagram
from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.core.meihua_weather_time_scope import compare_weather_time_scopes
from fatebridge.services.meihua import calculate_meihua_cast

NEW_RULES = ("li_above_gen_morning_clear", "li_above_gen_evening_rain")


def synthetic_scope_traces(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn explicitly fictional symbols into qualified comparison inputs."""
    return [
        {
            "rule_id": row["id"],
            "status": "matched",
            "time_scope": row["scope"],
            "tags": row["tags"],
            "effective_tags": [
                t for t in row["tags"] if t not in row.get("controlled", [])
            ],
            "conditional_tags": row.get("conditional", []),
            "controlled_tags": row.get("controlled", []),
        }
        for row in rows
    ]


def _geometry(cast: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    traces = {r["rule_id"]: r for r in weather["rule_trace"]}
    states = [traces[name]["status"] for name in NEW_RULES]
    if len(set(states)) != 1:
        raise ValueError(
            "The two halves of one daypart clause must share its pair condition"
        )
    return {
        "moving_line": cast.get("moving_line", cast.get("seed", {}).get("moving_line")),
        "changed_code": cast["changed_hexagram"]["binary_code"],
        "mutual_code": cast["mutual_hexagram"]["binary_code"],
        "six_slots": [r["trigram"] for r in weather["trigram_slots"]],
        "new_clause_status": states[0],
    }


def audit_weather_dayparts(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/divination.py",
        "core/meihua_casting.py",
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/meihua_weather_cast_variants.py",
        "services/meihua.py",
        "data/meihua/weather-v1.json",
        "validation/meihua_weather_dayparts.py",
    ]
    implementation = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in names
    }
    raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(
                "Frozen daypart diagrams, comparison cases or readings changed"
            )
    materials = {}
    for ref in manifest["references"]:
        path = (directory / ref["file"]).resolve()
        if (
            not path.is_relative_to(directory.parent)
            or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]
        ):
            raise ValueError("Frozen daypart source changed")
        materials[ref["id"]] = path.read_bytes()
    cases = json.loads((directory / "cases.json").read_text())["cases"]
    scope_cases = json.loads((directory / "scope-cases.json").read_text())["cases"]
    collation = json.loads((directory / "collation.json").read_text())
    baseline = json.loads((directory / "baseline-profile.json").read_text())
    profile = weather_ruleset()
    if (
        len(cases) != 16
        or manifest["mathematical_case_count"] != 16
        or len(scope_cases) != 6
        or manifest["synthetic_scope_case_count"] != 6
    ):
        raise ValueError("Retain all sixteen diagrams and six scope comparisons")
    if len(profile["rules"]) != 40 or profile["rules"][:38] != baseline["rules"]:
        raise ValueError("The previous38 rules must remain unchanged")
    rules = {r["id"]: r for r in profile["rules"]}
    source_checks = []
    for rule_id, scope in zip(NEW_RULES, ["morning", "evening"]):
        rule = rules[rule_id]
        witness = rule["source_witnesses"][0]
        source_checks.append(
            {
                "rule_id": rule_id,
                "fixed_quote_matches": rule["quote"] == collation["fixed_quote"]
                and rule["quote"] in materials["fixed-volume-2"].decode(),
                "selected_witness_integrated": witness["selected_span"]
                == collation["selected_span"]
                and witness["original_pdf_index"] == 64,
                "source_daypart_matches": rule["time_scope"] == scope,
            }
        )
    case_results = []
    for case in cases:
        result = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        cast, weather = result["meihua"], result["interpretation"]["weather"]
        actual = {
            "base_code": cast["base_hexagram"]["binary_code"],
            **_geometry(cast, weather),
        }
        trace = next(r for r in weather["rule_trace"] if r["rule_id"] == NEW_RULES[0])
        actual["matching_hexagram_keys"] = [
            p.split(".")[-1]
            for c in trace["conditions"]
            for p in c.get("matched_paths", [])
        ]
        expected = case["expected"]
        if "variants" in expected:
            geometries, signatures = {}, []
            for index, (candidate, detail) in enumerate(
                zip(cast["counting_variants"], weather["casting_variant_traces"])
            ):
                geometries[candidate["line_sum_basis"]] = _geometry(candidate, detail)
                signatures.append(
                    {
                        r["rule_id"]: {
                            k: r[k]
                            for k in [
                                "status",
                                "effective_status",
                                "controlled_tags",
                                "conditional_tags",
                                "effective_tags",
                            ]
                        }
                        for r in detail["rule_trace"]
                        if r["rule_id"] not in NEW_RULES
                    }
                )
            actual["variants"] = geometries
            actual["baseline_38_rule_signatures_equal"] = signatures[0] == signatures[1]
            actual["changed_rule_ids"] = weather["casting_comparison"][
                "changed_rule_ids"
            ]
        case_results.append(
            {
                "id": case["id"],
                "actual": actual,
                "disagreements": [
                    {"field": key, "expected": value, "actual": actual[key]}
                    for key, value in expected.items()
                    if actual[key] != value
                ],
            }
        )
    scope_results = []
    for case in scope_cases:
        comparison = compare_weather_time_scopes(synthetic_scope_traces(case["rows"]))
        actual = {
            "legacy_conflicts": len(comparison["unspecified_time_conflicts"]),
            "same_daypart_conflicts": len(comparison["same_daypart_conflicts"]),
            "separated_pairs": len(comparison["separated_daypart_pairs"]),
            "unresolved_pairs": len(comparison["unresolved_time_relations"]),
        }
        if "morning_qualified_tags" in case["expected"]:
            actual["morning_qualified_tags"] = next(
                g["qualified_tags"]
                for g in comparison["groups"]
                if g["time_scope"] == "morning"
            )
        scope_results.append(
            {
                "id": case["id"],
                "actual": actual,
                "disagreements": [
                    {"field": key, "expected": value, "actual": actual[key]}
                    for key, value in case["expected"].items()
                    if actual[key] != value
                ],
            }
        )
    diagrams = json.loads((directory / "mutual-diagrams.json").read_text())
    mutual_codes = sorted(
        {
            build_mutual_hexagram({"lines": list(bits)})["binary_code"]
            for bits in product((0, 1), repeat=6)
        }
    )
    mutual_matches = (
        mutual_codes == diagrams["expected_codes"]
        and (diagrams["traveller_code"] in mutual_codes)
        == diagrams["traveller_admissible_as_plain_mutual"]
    )
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != digest
        for name, digest in implementation.items()
    ):
        raise ValueError("Daypart implementation changed during audit")
    return {
        "audit_id": "meihua_weather_dayparts_v7",
        "ruleset": profile["id"] + "@" + profile["version"],
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "selected_checks_passed": all(
            all(value for key, value in row.items() if key != "rule_id")
            for row in source_checks
        )
        and not any(r["disagreements"] for r in [*case_results, *scope_results])
        and mutual_matches,
        "mathematical_diagram_cases": 16,
        "synthetic_scope_cases": 6,
        "source_checks": source_checks,
        "cases": case_results,
        "scope_cases": scope_results,
        "mutual_codes": mutual_codes,
        "mutual_diagram_check_passed": mutual_matches,
        "following_clause_parse_adjudicated": False,
        "source_clock_bounds_or_target_dates_defined": False,
        "independent_human_expert_review": "not_performed",
        "complete_classical_conformance_established": False,
        "actual_model_runs": 0,
        "real_weather_observations": 0,
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
