"""Check selected printed readings, preserving failed and unresolved readings."""

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

from fatebridge.core.sukuyo_printed_special import KYOTO_ENPO_SOURCE
from fatebridge.core.sukuyo_sources import load_source


def verify_kyoto_enpo(captures: Path | None = None) -> dict[str, Any]:
    loaded = load_source(KYOTO_ENPO_SOURCE)
    source = loaded.data
    reference = source["source_reference"]
    fixture_path = ROOT / "tests/fixtures/sukuyo-kyoto-enpo-primary.json"
    fixture = json.loads(fixture_path.read_bytes())
    rows = source["rows"]
    errors = []
    groups = [
        [r["literal_mansion"] for r in rows if r["label"] == label]
        for label in ["甘露", "金刚峰", "罗刹"]
    ]
    if groups != fixture["accepted_rows_by_group"]:
        errors.append("accepted_rows_changed")
    accepted = sum(r["mansion"] is not None for r in rows)
    if len(rows) != 21 or accepted != 20:
        errors.append("selected_positions_or_unresolved_slot_lost")
    earth = next(r for r in rows if r["label"] == "金刚峰" and r["weekday_index"] == 6)
    if (
        earth["literal_mansion"] is not None
        or earth["mansion"] is not None
        or earth["literal_mansion_candidates"] != ["元", "亢"]
    ):
        errors.append("unresolved_earth_glyph_promoted")
    clock = source["clock_reference"]
    if (
        clock["accepted_complete_diplomatic_transcription"] is not None
        or clock["modern_clock_mapping_established"]
        or clock["leap_short_month_priority_established"]
        or clock["identified_as_taisho_ming_witness"]
        or clock["source_efficacy_claim_is_empirical_evidence"]
    ):
        errors.append("selected_reference_promoted")
    images = {r["file"]: r["sha256"] for r in reference["images"]}
    if (
        images != fixture["source_images_sha256"]
        or reference["manifest_sha256"] != fixture["manifest_sha256"]
        or reference["raw_reading_files_sha256"] != fixture["raw_reading_files_sha256"]
    ):
        errors.append("source_binding_changed")
    checked = 0
    if captures:
        files = {
            "kyoto-RB00017017-manifest.json": reference["manifest_sha256"],
            **images,
            **reference["raw_reading_files_sha256"],
        }
        for name, expected in files.items():
            if hashlib.sha256((captures / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Selected Kyoto evidence bytes changed: {name}")
            checked += 1
        manifest = json.loads(
            (captures / "kyoto-RB00017017-manifest.json").read_bytes()
        )
        if len(manifest["items"]) != 80:
            errors.append("manifest_extent_changed")
        for row in reference["images"]:
            canvas = manifest["items"][row["frame"] - 1]
            body = canvas["items"][0]["items"][0]["body"]
            if (
                canvas["id"] != row["canvas"]
                or body["service"][0]["id"] + "/full/max/0/default.jpg" != row["url"]
            ):
                errors.append(["image_not_bound_to_manifest_service", row["frame"]])
    return {
        "format": "sukuyo_kyoto_enpo_selected_check_v1",
        "source_bundle_sha256": loaded.sha256,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "selected_mansion_slots": 21,
        "accepted_mansion_readings": accepted,
        "unresolved_mansion_slots": len(rows) - accepted,
        "initial_generator_wrong_cells_retained": fixture[
            "initial_generator_rejected_readings"
        ],
        "actual_evidence_files_hashed": checked,
        "all_eighty_frames_collated": False,
        "human_or_independent_provider_acceptance": False,
        "ancient_clock_or_precedence_admitted": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_kyoto_enpo(args.captures)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
