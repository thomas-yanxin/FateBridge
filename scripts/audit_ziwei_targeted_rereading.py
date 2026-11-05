"""Check five rereading disclosures; this does not adjudicate source glyphs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.ziwei_sources import ziwei_day_source_evidence

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "tests/data/ziwei_independent/targeted_rereading_r24_v1"
TARGET = ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-targeted-review-r24.json"


def audit_targeted_rereading() -> dict[str, Any]:
    manifest = json.loads((FROZEN / "manifest.json").read_text())
    for record in manifest["files"]:
        if (
            hashlib.sha256((FROZEN / record["path"]).read_bytes()).hexdigest()
            != record["sha256"]
        ):
            raise ValueError(
                "Targeted rereading source checksum mismatch: " + record["path"]
            )
    report_path = FROZEN / "original-first-reading-frozen.json"
    first = json.loads(report_path.read_text())
    # These branch sets refer to this frozen reading, never to chart positions.
    literal_branches = {
        (2, 21): [],
        (3, 11): [],
        (3, 12): ["辰", "巳"],
        (6, 6): [],
        (6, 8): ["寅", "未"],
    }
    if {(r["bureau"], r["day"]) for r in manifest["target_inputs"]} != set(
        literal_branches
    ) or len(manifest["target_inputs"]) != 5:
        raise ValueError("The five targeted inputs changed")
    rows = []
    for target in manifest["target_inputs"]:
        key = target["bureau"], target["day"]
        branches = literal_branches[key]
        rows.append(
            {
                "bureau": key[0],
                "day": key[1],
                "source_frame": target["frame"],
                "status": (
                    "conflicting_direct_labels"
                    if branches
                    else "not_directly_confirmed_in_targeted_rereading"
                ),
                "direct_label_branches": branches,
                "literal_reading": first["targeted_day_table_transcriptions"][
                    target["report_section"]
                ]["literal_character_finding"],
                "scope": "targeted_same_scan_rereading_not_a_new_witness_or_whole_table_review",
            }
        )
    expected = {
        "id": manifest["id"],
        "source_url": manifest["source_url"],
        "source_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "frozen_manifest_sha256": hashlib.sha256(
            (FROZEN / "manifest.json").read_bytes()
        ).hexdigest(),
        "reviewed_input_count": 5,
        "new_witness_count": 0,
        "external_human_experts": 0,
        "whole_day_table_certified": False,
        "records": rows,
    }
    packaged = json.loads(TARGET.read_text())
    mismatches: list[dict[str, Any]] = []
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
    if canonical(packaged) != canonical(expected):
        mismatches.append({"case": "package_differs_from_frozen_literal_rereading"})
    for row in rows:
        key = row["bureau"], row["day"]
        for branch in "子丑寅卯辰巳午未申酉戌亥":
            actual = ziwei_day_source_evidence(
                bureau=key[0], lunar_day=key[1], actual_branch=branch
            )["targeted_rereading"]
            wanted = {
                **{k: v for k, v in row.items() if k not in {"bureau", "day"}},
                "method_id": expected["id"],
                "source_report_sha256": expected["source_report_sha256"],
                "reviewed_input_count": 5,
                "matches_unique_direct_branch": None,
                "unique_source_confirmation_supported": False,
                "new_witness_count": 0,
                "external_human_experts": 0,
                "whole_day_table_certified": False,
            }
            if canonical(actual) != canonical(wanted):
                mismatches.append(
                    {"case": [*key, branch], "expected": wanted, "actual": actual}
                )
    return {
        "method_id": "ziwei_targeted_rereading_disclosure_r24_v1",
        "targeted_inputs": 5,
        "conditional_receipts_checked": 60,
        "conflicting_direct_inputs": 2,
        "not_directly_confirmed_inputs": 3,
        "new_day_table_witnesses": 0,
        "external_human_experts": 0,
        "whole_day_table_certified": False,
        "mismatches": mismatches,
        "scope": "Integrity and faithful disclosure of five frozen model rereadings; not 60 independently observed charts, new 150-input review, or palaeographic certification.",
    }
