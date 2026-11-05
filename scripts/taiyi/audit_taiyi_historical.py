"""Compare all ten independently published historical phase observations.

These are numerical references, not evidence that historical events were
predicted prospectively. A mismatch retains both values and makes exit 1.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import cyclic_core, yearly_core

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v4"
YEARS = {-202, 403, 404, 424, 430, 441, 465, 466, 474, 477}
FIELDS = ("yuan_ju", "taiyi_number", "kook_year")


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    if "historical-cases.json" not in {s["file"] for s in manifest["source_files"]}:
        raise ValueError("历史独立参照不得移除")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("冻结历史参照指纹不符：" + item["file"])
    data = json.loads((corpus / "historical-cases.json").read_text())
    cases = data["cases"]
    years = {c.get("year_ce", -c.get("year_bce", 0)) for c in cases}
    if (
        len(cases) != 10
        or years != YEARS
        or any(not set(FIELDS) <= c.keys() for c in cases)
    ):
        raise ValueError("必须完整核对10条历史参照及每条3项，不得删去失败字段")
    differences = []
    results = []
    for case in cases:
        if "year_ce" in case:
            core = yearly_core(case["year_ce"])
        else:
            # The public calendar adapter is not used or extended. Historical
            # 1 BCE is astronomical year 0; there is no civil historical year 0.
            astro_year = 1 - case["year_bce"]
            core = cyclic_core(1937281 + astro_year - 724)
            core["kook_year"] = ("理天", "理地", "理人")[(core["accumulation"] - 1) % 3]
        actual = {
            "yuan_ju": (core["accumulation"] - 1) % 360 + 1,
            "taiyi_number": core["taiyi_number"],
            "kook_year": core["kook_year"],
        }
        matching = 0
        for field in FIELDS:
            if actual[field] == case[field]:
                matching += 1
            else:
                differences.append(
                    {
                        "historical_label": case["historical_label"],
                        "field": field,
                        "source_value": case[field],
                        "rule_derived_value": actual[field],
                        "status": "published_reading_confirmed_disagreement_retained",
                    }
                )
        results.append(
            {
                "historical_label": case["historical_label"],
                "matching_fields": matching,
                "actual": actual,
            }
        )
    return {
        "source": data["source"],
        "oracle_kind": "independent_published_historical_phase_list",
        "total_cases": 10,
        "checked_fields": 30,
        "matching_fields": 30 - len(differences),
        "cases": results,
        "disagreements": differences,
        "historical_reference_acceptance_passed": not differences,
        "whole_book_conformance": "not_established",
        "scope": data["scope"],
        "calendar_adapter_validated_for_ancient_dates": False,
        "real_world_efficacy": "not_tested",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "src/fatebridge/core/metaphysics/taiyi_year.py").read_bytes()
        ).hexdigest(),
    }
