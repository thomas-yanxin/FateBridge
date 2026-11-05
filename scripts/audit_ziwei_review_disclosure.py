"""Audit disclosure of independent readings; do not adjudicate the glyphs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.ziwei_sources import ziwei_day_source_evidence

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "tests/data/ziwei_independent/independent_readings_r22_v1"
TARGET = ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-days-review-r22.json"


def audit_review_disclosure() -> dict[str, Any]:
    manifest = json.loads((FROZEN / "manifest.json").read_text())
    hashes = {r["path"]: r["sha256"] for r in manifest["files"]}
    for name in ["reports/day-review.json", "reports/day-review-errata-01.json"]:
        if hashlib.sha256((FROZEN / name).read_bytes()).hexdigest() != hashes[name]:
            raise ValueError("Independent reading checksum mismatch: " + name)
    first = json.loads((FROZEN / "reports/day-review.json").read_text())
    erratum = json.loads((FROZEN / "reports/day-review-errata-01.json").read_text())
    rows_by_input = {(r["bureau"], r["day"]): r for r in first["day_to_branch_rows"]}
    correction = erratum["corrected_day_to_branch_row"]
    rows_by_input[(correction["bureau"], correction["day"])] = correction
    if set(rows_by_input) != {(b, d) for b in range(2, 7) for d in range(1, 31)}:
        raise ValueError("Independent reading denominator changed")
    rows = [rows_by_input[key] for key in sorted(rows_by_input)]
    mismatches: list[dict[str, Any]] = []
    packaged = json.loads(TARGET.read_text())
    expected_header = {
        "id": "naj_ming_day_independent_review_r22_corrected_v1",
        "source_report_sha256": hashes["reports/day-review.json"],
        "erratum_sha256": hashes["reports/day-review-errata-01.json"],
        "frozen_manifest_sha256": hashlib.sha256(
            (FROZEN / "manifest.json").read_bytes()
        ).hexdigest(),
        "source_report": "tests/data/ziwei_independent/independent_readings_r22_v1/reports/day-review.json",
        "separate_erratum": "tests/data/ziwei_independent/independent_readings_r22_v1/reports/day-review-errata-01.json",
        "new_edition": False,
        "external_human_experts": 0,
    }
    # JSON provenance must distinguish false/0 and true/1, unlike Python equality.
    if json.dumps(packaged, sort_keys=True, ensure_ascii=False) != json.dumps(
        {**expected_header, "records": rows}, sort_keys=True, ensure_ascii=False
    ):
        mismatches.append(
            {"case": "packaged_reading_differs_from_frozen_report_and_erratum"}
        )
    selected_path = TARGET.parent / "ziwei-naj-ming-days.json"
    if (
        hashlib.sha256(selected_path.read_bytes()).hexdigest()
        != "4f19e3426fd3fcb03e2be94fdf8ad8121de0449f27d4d93cd9f38d308bc0634a"
    ):
        raise ValueError("The retained selected transcription changed")
    selected = {
        (r["bureau"], r["day"]): r["branch"]
        for r in json.loads(selected_path.read_text())["records"]
    }
    unambiguous = 0
    for row in rows:
        direct = row["branches_from_direct_labels"]
        candidates = row.get("candidate_branches_from_unresolved_labels", [])
        unique = len(direct) == 1 and not candidates
        unambiguous += int(unique)
        for branch in "子丑寅卯辰巳午未申酉戌亥":
            actual = ziwei_day_source_evidence(
                bureau=row["bureau"], lunar_day=row["day"], actual_branch=branch
            )["independent_review"]
            wanted = {
                "method_id": expected_header["id"],
                "status": row["status"],
                "direct_label_branches": direct,
                "unresolved_label_candidates": candidates,
                "unambiguous_after_rereading": unique,
                "matches_unique_direct_branch": (
                    branch == direct[0] if len(direct) == 1 else None
                ),
                "agrees_with_selected_branch": (
                    selected[(row["bureau"], row["day"])] == direct[0]
                    if len(direct) == 1
                    and selected[(row["bureau"], row["day"])] is not None
                    else None
                ),
                "source_report_sha256": hashes["reports/day-review.json"],
                "erratum_sha256": hashes["reports/day-review-errata-01.json"],
                "whole_day_table_certified": False,
                "new_edition": False,
                "external_human_experts": 0,
            }
            if json.dumps(actual, sort_keys=True, ensure_ascii=False) != json.dumps(
                wanted, sort_keys=True, ensure_ascii=False
            ):
                mismatches.append(
                    {
                        "case": [row["bureau"], row["day"], branch],
                        "expected": wanted,
                        "actual": actual,
                    }
                )
    return {
        "method_id": "ziwei_independent_reading_disclosure_v1",
        "source_inputs": len(rows),
        "conditional_receipts_checked": len(rows) * 12,
        "unique_direct_inputs": sum(
            len(r["branches_from_direct_labels"]) == 1 for r in rows
        ),
        "unambiguous_after_rereading_inputs": unambiguous,
        "mismatches": mismatches,
        "packaged_review_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "first_failed_reading_retained": True,
        "new_independent_calendar_observations": 0,
        "new_editions": 0,
        "whole_day_table_certified": False,
        "scope": "Integrity and disclosure of the existing R22 reading only; 1800 conditional receipt joins are not 1800 historical charts or independently observed star positions.",
    }
