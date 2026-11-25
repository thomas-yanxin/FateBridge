"""Source arithmetic does not certify or replace the selected progression key."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

RECORD = (
    Path(__file__).resolve().parents[2]
    / "data/knowledge/witte1923-constant-source.json"
)
RECORD_SHA256 = "ccfdbaf79be14b5f5a4fef04728584c2b48175ca66382962d29ac5dffd1b5256"


def _time_seconds(parts: list[int]) -> int:
    if len(parts) != 3 or any(type(part) is not int for part in parts):
        raise ValueError("Source time angles require three integer parts")
    hours, minutes, seconds = parts
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError("Source time angle is out of range")
    return hours * 3600 + minutes * 60 + seconds


def progression_key_source_comparison() -> Dict[str, Any]:
    """Audit printed operands; never adjust a present chart to the printed sum.

    The source's arithmetic residuals are measured in seconds of time angle.
    They are neither errors in the user's birth clock nor corrections to an
    ecliptic longitude. The actual 365.25-day key remains a FateBridge choice.
    """
    raw = RECORD.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise RuntimeError("Witte1923 progression-constant source checksum mismatch")
    record = json.loads(raw)
    operations = []
    for row in record["operations"]:
        actual = 0
        for term in row["terms"]:
            if type(term["sign"]) is not int or term["sign"] not in (-1, 1):
                raise ValueError("Source time-angle term requires sign +1 or -1")
            actual += term["sign"] * _time_seconds(term["hms"])
        printed = _time_seconds(row["printed_result_hms"])
        operations.append(
            {
                "id": row["id"],
                "section": row["section"],
                "computed_time_seconds": actual,
                "printed_time_seconds": printed,
                "printed_minus_computed_time_seconds": printed - actual,
                "arithmetic_matches_print": printed == actual,
            }
        )
    consistent = all(row["arithmetic_matches_print"] for row in operations)
    source = record["source"]
    return {
        "status": "original_source_not_accepted",
        "ruleset_id": "witte1923_constant_source_arithmetic_v1",
        "author": "FateBridge",
        "version": "1",
        "selected_key_id": "fatebridge_julian_36525_v1",
        "selected_key_from_compared_source": False,
        "computed_for_current_chart": False,
        "comparison_unit": "seconds of time angle; not ecliptic arcseconds or measured birth-clock error",
        "source_record_sha256": RECORD_SHA256,
        "source": {
            "id": source["id"],
            "author": source["author"],
            "title": source["title"],
            "url": source["url"],
            "source_sha256": source["source_pdf_sha256"],
            "sections": source["sections"],
            "scope": record["scope"],
        },
        "operations": operations,
        "printed_arithmetic_consistent": consistent,
        "inconsistent_operation_ids": [
            row["id"] for row in operations if not row["arithmetic_matches_print"]
        ],
        "clock_label_status": "civil-night and noon-based astronomical date labels not independently resolved",
        "residuals_applied_as_corrections": False,
        "original_progression_time_key_accepted": False,
        "full_original_rulebook_accepted": False,
        "scope": "One historical printed example only. These operands are not computed for the user's chart; no original time-key or event forecast is supplied.",
    }
