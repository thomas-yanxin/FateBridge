"""Publish five frozen literal rereadings without emending the day table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "tests/fixtures/ziwei_independent/targeted_rereading_r24_v1"
TARGET = ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-targeted-review-r24.json"


def build() -> dict[str, Any]:
    manifest = json.loads((FROZEN / "manifest.json").read_text())
    for record in manifest["files"]:
        if (
            hashlib.sha256((FROZEN / record["path"]).read_bytes()).hexdigest()
            != record["sha256"]
        ):
            raise ValueError(
                "Targeted rereading source checksum mismatch: " + record["path"]
            )
    report_path = FROZEN / manifest["independent_first_reading_report"]
    report = json.loads(report_path.read_text())
    target_inputs = manifest["target_inputs"]
    if {(r["bureau"], r["day"]) for r in target_inputs} != {
        (2, 21),
        (3, 11),
        (3, 12),
        (6, 6),
        (6, 8),
    } or len(target_inputs) != 5:
        raise ValueError("The five targeted inputs changed")
    literal_labels = {
        21: {"二十一", "廿一"},
        11: {"十一"},
        12: {"十二"},
        6: {"初六"},
        8: {"初八"},
    }
    rows = []
    for target in target_inputs:
        reading = report["targeted_day_table_transcriptions"][target["report_section"]]
        cells = reading.get("cells") or [
            {
                "visible_cell_heading": reading["visible_cell_heading"],
                "diplomatic_columns_right_to_left": reading[
                    "diplomatic_cell_columns_right_to_left"
                ],
            }
        ]
        branches = [
            r["visible_cell_heading"]
            for r in cells
            if literal_labels[target["day"]].intersection(
                r["diplomatic_columns_right_to_left"]
            )
        ]
        rows.append(
            {
                "bureau": target["bureau"],
                "day": target["day"],
                "source_frame": target["frame"],
                "status": (
                    "conflicting_direct_labels"
                    if len(branches) > 1
                    else (
                        "not_directly_confirmed_in_targeted_rereading"
                        if not branches
                        else "single_direct_label"
                    )
                ),
                "direct_label_branches": branches,
                "literal_reading": reading["literal_character_finding"],
                "scope": "targeted_same_scan_rereading_not_a_new_witness_or_whole_table_review",
            }
        )
    return {
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.is_file() or TARGET.read_text() != text:
            raise SystemExit("Targeted Ziwei rereading disclosure is stale")
    else:
        TARGET.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
