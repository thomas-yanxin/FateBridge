"""Check selected manuscript controls without calling them a complete edition."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/sukuyo-t2465-kyoto-primary.json"


def verify_primary(
    manuscript_image: Path | None = None, manifest_path: Path | None = None
) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    data = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_t2465_critical.json").read_bytes()
    )
    primary = fixture["primary"]
    if primary != data["selected_primary"]:
        raise ValueError("Selected manuscript readings differ from the source fixture")
    if manuscript_image is not None:
        raw = manuscript_image.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != primary["image_sha256"]
            or len(raw) != primary["image_bytes"]
        ):
            raise ValueError("Manuscript image fingerprint changed")
    if manifest_path is not None:
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != primary["manifest_sha256"]:
            raise ValueError("Manuscript manifest fingerprint changed")
        manifest = json.loads(raw)
        canvas = manifest["items"][primary["canvas_index_one_based"] - 1]
        service = canvas["items"][0]["items"][0]["body"]["service"][0]["id"]
        if (
            len(manifest["items"]) != primary["canvas_count"]
            or canvas["id"] != primary["canvas_id"]
            or primary["image_url"] != service + "/full/max/0/default.jpg"
        ):
            raise ValueError("Selected canvas is not bound to the captured image URL")
    source = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_t1299_calendar_profiles.json").read_bytes()
    )["hinoo_addendum"]["downloaded_primary_edition"]
    if data["taisho_calendar_windows"] != source["downloaded_calendar_windows"]:
        raise ValueError("Taisho comparison quotations changed")
    span = data["apparatus_span_reference"]
    clean = re.sub(r"[。･、\s]+", "", data["taisho_calendar_windows"][0]["text"])
    selected = span["normalized_candidate_span"]
    if len(selected) != 16 or clean.count(selected) != 1:
        raise ValueError("Sixteen-character apparatus span does not match")
    shorter = span["shorter_sentence_boundary_candidate"]
    return {
        "format": "sukuyo_hinoo_critical_primary_check_v1",
        "selected_manuscript_fragments_checked": len(primary["observations"]),
        "month_day_controls": fixture["expected_month_day_mansions"],
        "retained_taisho_manuscript_disagreement": {
            "month": 12,
            "day": 30,
            "taisho": "星",
            "kyoto_selected_black_text": "室",
        },
        "apparatus_span_characters": len(selected),
        "shorter_sentence_boundary_candidate_characters": len(shorter),
        "apparatus_span_reference": span,
        "full_image_bytes_rechecked": manuscript_image is not None,
        "full_manifest_bytes_rechecked": manifest_path is not None,
        "independent_human_transcription_accepted": False,
        "complete_manuscript_collation": False,
        "copy_identified_as_taisho_ko": False,
        "classical_clock_mapping_established": False,
        "intercalation_short_month_priority_established": False,
        "calendar_algorithm_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript-image", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_primary(args.manuscript_image, args.manifest)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
