"""Check documentary placement and curated facsimile provenance, not image meaning."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_documentary import JAPANESE, LAYERS
from fatebridge.core.sukuyo_sources import load_source


def paragraph_layers(raw: str) -> tuple[str, list[dict[str, str]]]:
    node = ET.fromstring(raw)
    notes = []
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] == "note":
            notes.append(
                {
                    "place": child.get("place", ""),
                    "text": "".join(child.itertext()).strip(),
                }
            )
            child.text = None
            for nested in list(child):
                child.remove(nested)
    return "".join(node.itertext()).replace("\n", "").strip(), notes


def verify_documentary_primary(
    xml_path: Path | None = None, capture_dir: Path | None = None
) -> dict[str, Any]:
    fixture = json.loads(
        (ROOT / "tests/data/sukuyo-text-layers-primary.json").read_bytes()
    )
    layers = load_source(LAYERS)
    japanese = load_source(JAPANESE)
    curated = json.loads(
        (ROOT / "tests/data/sukuyo-japanese-selected-primary.json").read_bytes()
    )
    errors: list[Any] = []
    if japanese.data != curated:
        errors.append("facsimile_curation_changed")
    if layers.data["rule_passages"] != fixture["rule_passages"]:
        errors.append("rule_passage_binding_changed")
    if set(layers.data["passages"]) != set(fixture["raw_selected_xml_paragraphs"]):
        errors.append("paragraph_selection_changed")
    full_xml = None
    if xml_path:
        raw = xml_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["source_sha256"]:
            raise ValueError("Documentary full source bytes changed")
        full_xml = raw.decode()
    for identifier, raw in fixture["raw_selected_xml_paragraphs"].items():
        main, notes = paragraph_layers(raw)
        actual = layers.data["passages"][identifier]
        if main != actual["main_text"] or notes != actual["inline_notes"]:
            errors.append([identifier, "placement_or_text"])
        if full_xml is not None and raw not in full_xml:
            errors.append([identifier, "fragment_missing_from_full_source"])
    checked_images = []
    ref = japanese.data["source_reference"]
    if capture_dir:
        manifest_bytes = (capture_dir / "nijl-100223664-manifest.json").read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != ref["manifest_sha256"]:
            raise ValueError("Facsimile manifest bytes changed")
        manifest = json.loads(manifest_bytes)
        canvases = manifest["sequences"][0]["canvases"]
        if len(canvases) != ref["manifest_canvas_count"]:
            errors.append("canvas_count")
        for image in ref["images"]:
            # Captures retain institutional files privately; no images in package.
            matches = [
                p
                for p in capture_dir.glob("nijl-100223664-*.jpg")
                if hashlib.sha256(p.read_bytes()).hexdigest() == image["sha256"]
            ]
            if len(matches) != 1 or matches[0].stat().st_size != image["bytes"]:
                raise ValueError("Selected facsimile image bytes changed or missing")
            canvas = canvases[image["canvas_index_one_based"] - 1]
            if canvas["@id"] != image["canvas_id"]:
                errors.append("selected_canvas_identity")
            checked_images.append(image["canvas_index_one_based"])
    differences = []
    for day in range(1, 31):
        result = calendar_day_evidence(day)
        comparison = result["japanese_selected_reference"]
        if any(
            r["favorable_list_membership_differs"]
            for r in comparison["primary_general_day_comparison"]
        ):
            differences.append(day)
        if (
            result["clock_evaluation_status"] != "not_computed"
            or comparison["applied_to_primary"]
            or comparison["leap_short_month_priority_established"]
        ):
            errors.append(["comparison_promoted_to_policy", day])
    if differences != [9, 10, 16, 24, 25]:
        errors.append(["favorable_membership_differences", differences])
    return {
        "format": "sukuyo_documentary_primary_check_v1",
        "layer_bundle_sha256": layers.sha256,
        "japanese_bundle_sha256": japanese.sha256,
        "selected_paragraphs": 17,
        "bound_direction_rules": 16,
        "bound_opposing_wall_rule": 1,
        "full_xml_bytes_and_fragments_checked": full_xml is not None,
        "selected_private_facsimile_canvases_checked": checked_images,
        "body_day_entries": 13,
        "body_time_phase_entries": 8,
        "weekday_labels": 8,
        "weekday_independent_controls_added": 0,
        "favorable_membership_difference_days": differences,
        "unchanged_clock_controls": 30,
        "independent_image_transcription_or_human_collation": False,
        "facsimile_check_scope": "Checks captured bytes and frozen curation; does not independently recognize image text.",
        "ancient_day_or_leap_priority_admitted": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-path", type=Path)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_documentary_primary(args.xml_path, args.capture_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
