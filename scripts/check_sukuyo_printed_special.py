"""Check selected direct-print readings and optionally the inspected image bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo import SU27_ORDER
from fatebridge.core.sukuyo_printed_special import SOURCE, printed_lower_comparison
from fatebridge.core.sukuyo_sources import load_source

FIXTURE = ROOT / "tests/data/sukuyo-wakita-special-primary.json"
ALIASES = str.maketrans("軫畢張參", "轸毕张参")


def verify_printed_special(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    loaded = load_source(SOURCE)
    bundle = loaded.data
    if bundle["source_reference"] != fixture["source_reference"]:
        raise ValueError("Direct printed source metadata changed; revalidate")
    expected_tables = fixture["expected_literal_tables"]
    errors = []
    slots = {(r["label"], r["weekday_index"]): r for r in bundle["rows"]}
    if len(slots) != len(bundle["rows"]) or set(slots) != {
        (label, n) for label in expected_tables for n in range(7)
    }:
        raise ValueError("Direct printed slots are missing or duplicated")
    for (label, weekday), row in slots.items():
        literal = expected_tables[label][weekday]
        if row["literal_mansion"] != literal or row["mansion"] != (
            literal.translate(ALIASES) if literal is not None else None
        ):
            errors.append(["literal_slot", label, weekday])
        if literal is None:
            unresolved = fixture["unaccepted_glyph_slot"]
            if (
                row["source_clause_is_witness_reading"]
                or row["candidate_readings"] != unresolved["candidate_readings"]
                or row["candidate_readings_accepted_as_mansion"]
            ):
                errors.append(["unaccepted_glyph_promoted", label, weekday])
    for name in SU27_ORDER:
        for weekday in range(7):
            result = printed_lower_comparison(name, weekday, [])
            expected = [
                label
                for label, sequence in expected_tables.items()
                if sequence[weekday] is not None
                and sequence[weekday].translate(ALIASES) == name
            ]
            unresolved = any(s[weekday] is None for s in expected_tables.values())
            if (
                result["matched_labels"] != expected
                or result["labels_complete_for_selected_day"] == unresolved
                or result["applied_to_primary"]
                or result["disagrees_with_primary"]
                != (None if unresolved else bool(expected))
            ):
                errors.append(["evaluated_cell", name, weekday])
    checked = []
    reference = fixture["source_reference"]
    if capture_dir is not None:
        for image in reference["images"]:
            path = capture_dir / image["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != image["sha256"]:
                raise ValueError("Direct printed image fingerprint changed")
            checked.append(image["file"])
        if (
            hashlib.sha256(
                (capture_dir / "ndl-817827-manifest.json").read_bytes()
            ).hexdigest()
            != reference["manifest_sha256"]
        ):
            raise ValueError("Direct printed manifest fingerprint changed")
    return {
        "format": "sukuyo_printed_special_primary_check_v1",
        "source_bundle_sha256": loaded.sha256,
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "selected_slots": len(slots),
        "recognized_mansion_readings": sum(
            r["mansion"] is not None for r in slots.values()
        ),
        "unaccepted_glyph_slots": [
            {
                "label": label,
                "weekday_index": weekday,
                "candidate_readings": row["candidate_readings"],
            }
            for (label, weekday), row in slots.items()
            if row["mansion"] is None
        ],
        "mansion_weekday_cells_checked": len(SU27_ORDER) * 7,
        "errors": errors,
        "full_image_bytes_checked": checked,
        "manifest_bytes_checked": capture_dir is not None,
        "selected_runtime_primary_changed": False,
        "activity_rules_changed": False,
        "independent_human_transcription_accepted": False,
        "whole_print_and_apparatus_collated": False,
        "independent_historical_observation": False,
        "ancient_clock_mapping_accepted": False,
        "three_axis_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_printed_special(args.capture_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
