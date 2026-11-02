"""Compare an exposed, frozen strength expansion without rewriting its labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.elements import ElementAnalysis

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/bazi_strength_expansion_v1/reference.json"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def input_consistency(values: list[str]) -> dict[str, Any]:
    """Check transcription consistency; do not repair a source or invent dates.

    月干 uses the 寅-month start of 五虎遁. Hour checks the recorded day stem
    under 五鼠遁; a 子时 statement does not resolve historical day boundaries.
    """
    positions = [(STEMS.index(p[0]), BRANCHES.index(p[1])) for p in values]
    year, month, day, hour = positions
    return {
        "sexagenary_pairs": all(s % 2 == b % 2 for s, b in positions),
        "month_stem_matches_year": month[0]
        == (2 * (year[0] % 5) + 2 + (month[1] - 2) % 12) % 10,
        "hour_stem_matches_recorded_day": hour[0] == (2 * (day[0] % 5) + hour[1]) % 10,
        "zi_hour_boundary_unresolved": hour[1] == 0,
        "scope": "四柱录文内在一致性；不证明历史日期、出生钟或子时换日口径正确。",
    }


def audit() -> dict[str, Any]:
    raw = REFERENCE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REFERENCE.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen source labels changed")
    reference = json.loads(raw)
    rows = []
    for case in reference["cases"]:
        chart = dict(zip(("year", "month", "day", "hour"), map(tuple, case["pillars"])))
        actual = ElementAnalysis.analyze_day_master_strength(chart)["assessment"]
        rows.append(
            {
                "id": case["id"],
                "source_pdf_page": case["source_pdf_page"],
                "expected_strength": case["expected_strength"],
                "actual_strength": actual["strength_level"],
                "support_share": actual["support_share"],
                "matched": actual["strength_level"] == case["expected_strength"],
                "input_consistency": input_consistency(case["pillars"]),
                "roots": actual["roots"],
                "relations": actual["relations"],
            }
        )
    candidate = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in reference["candidate_before_first_comparison"]
    }
    return {
        "method_id": "ziping_strength_expansion_audit_v1",
        "reference_sha256": digest,
        "source_sha256": reference["source_sha256"],
        "protocol": reference["protocol"],
        "matched": sum(r["matched"] for r in rows),
        "total": len(rows),
        "cases": rows,
        "candidate_fingerprints": candidate,
        "candidate_equals_first_comparison": candidate
        == reference["candidate_before_first_comparison"],
        "scope": "Current comparison to two source labels; both are exposed after their first comparison and are not reusable blind trials. Input inconsistency is retained, never silently repaired or filtered out.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Source strength expansion: {result['matched']}/{result['total']}")
    return 0 if result["matched"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
