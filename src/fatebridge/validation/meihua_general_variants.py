"""Frozen literal probes of general counting-candidate interpretation fidelity."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_casting import explicit_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def _normalized(text: str) -> str:
    return "".join(
        c
        for c in text
        if unicodedata.category(c)[0] not in {"P", "S", "Z"} and not c.isspace()
    )


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def audit_general_casting_readings(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    package = Path(__file__).resolve().parents[1]
    files = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_countercontrol.py",
        "core/meihua_seasonal_reading.py",
        "data/meihua/seasonal-reading-nlc1925-v1.json",
        "data/meihua/internal-control-nlc1925-v1.json",
        "core/meihua_casting.py",
        "core/meihua_general_variants.py",
        "services/meihua.py",
        "core/zhouyi.py",
        "data/meihua/time-v1.json",
        "data/meihua/explicit-casts-v1.json",
        "data/classical/zhouyi.json",
        "validation/meihua_general_variants.py",
    ]
    implementation = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in files
    }
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Frozen general-candidate source or oracle changed")
    materials = []
    for reference in manifest["meihua_sources"]:
        path = (directory / reference["file"]).resolve()
        if (
            not path.is_relative_to(directory.parent)
            or hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]
        ):
            raise ValueError("Frozen general-candidate Mei Hua source changed")
        materials.append(path.read_text())
    primary = {}
    for source in manifest["primary_chapters"]:
        parser = _Text()
        parser.feed((directory / source["file"]).read_text())
        primary[source["chapter"]] = _normalized("".join(parser.parts))
    bundle = json.loads((directory / "cases.json").read_text())
    if (
        len(bundle["cases"]) != manifest["oracle_case_count"]
        or manifest["oracle_case_count"] != 9
    ):
        raise ValueError("The general-candidate corpus must retain all nine probes")
    reports = []
    source_checks = []
    for case in bundle["cases"]:
        result = calculate_meihua_cast(
            casting=case["casting"], season_month_branch=case["season_month_branch"]
        )
        readings = result["interpretation"]["casting_readings"]
        expected = case["expected"]
        checks = {
            "candidate_count": len(readings) == expected["candidate_count"],
            "comparison_status": result["interpretation"]["casting_comparison"][
                "status"
            ]
            == expected["comparison_status"],
        }
        candidates = {row["line_sum_basis"]: row for row in readings}
        for reference in expected["candidates"]:
            row = candidates[reference["basis"]]
            prefix = reference["basis"] + "."
            for key in (
                "moving_line",
                "base_code",
                "changed_code",
                "mutual_code",
                "body",
                "use",
            ):
                checks[prefix + key] = row[key] == reference[key]
            checks[prefix + "relations"] = [
                r["relation"] for r in row["stage_relations"]
            ] == reference["relations"]
            checks[prefix + "role_trigrams"] = [
                row["body"],
                *[r["trigram"] for r in row["stage_relations"]],
            ] == reference["role_trigrams"]
            seasonal = row["seasonal_strength"]
            checks[prefix + "season"] = (
                None
                if seasonal is None
                else {r["role"]: r["strength"] for r in seasonal["trigrams"]}
            ) == reference["seasonal_strengths"]
            verse = row["classical_text_reference"]["moving_yaoci"]
            checks[prefix + "verse_position"] = (
                verse["position"] == reference["moving_line"]
            )
            checks[prefix + "verse_text"] = _normalized(verse["text"]) == _normalized(
                reference["yaoci"]
            )
            source_checks.append(
                {
                    "case_id": case["id"],
                    "basis": reference["basis"],
                    "chapter": reference["chapter"],
                    "matched": _normalized(reference["yaoci"])
                    in primary[reference["chapter"]],
                }
            )
        reports.append(
            {
                "id": case["id"],
                "checks": checks,
                "disagreements": [
                    name for name, passed in checks.items() if not passed
                ],
            }
        )
    quotes = [
        {"rule_id": r["id"], "matched": any(r["quote"] in text for text in materials)}
        for r in explicit_ruleset()["rules"]
        if "quote" in r
    ]
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != digest
        for name, digest in implementation.items()
    ):
        raise ValueError("General-candidate engine changed during audit")
    return {
        "audit_id": "meihua_general_counting_readings_v2",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "implementation_sha256": implementation,
        "selected_checks_passed": all(not row["disagreements"] for row in reports)
        and all(r["matched"] for r in source_checks + quotes),
        "cases": reports,
        "verse_source_checks": source_checks,
        "meihua_quote_checks": quotes,
        "literal_mathematical_probe_count": 9,
        "original_worked_example_count_added": 0,
        "oracle_builder": bundle["oracle_policy"]["builder"],
        "independent_human_expert_review": "not_performed",
        "full_classical_conformance_established": False,
        "unique_classical_count_convention_established": False,
        "actual_model_runs": 0,
        "prospective_observation_count": 0,
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
