"""Bind the selected Zentsuji readings to their captured manifest and image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fatebridge/data/sukuyo_t2465_zentsuji.json"
FIXTURE = ROOT / "tests/data/sukuyo-zentsuji-hinoo-primary.json"


def verify_primary(
    manuscript_image: Path | None = None, manifest_path: Path | None = None
) -> dict[str, Any]:
    source = json.loads(SOURCE.read_bytes())
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    if (
        hashlib.sha256(raw).hexdigest() != source["transcription_receipt_sha256"]
        or fixture["observations"] != source["observations"]
        or fixture["original_image_sha256"] != source["image_sha256"]
    ):
        raise ValueError("善通寺所选读录与比较前记录不一致")
    observations = source["observations"]
    if len({r["id"] for r in observations}) != len(observations):
        raise ValueError("善通寺所选读录出现重复")
    if manuscript_image is not None:
        image_bytes = manuscript_image.read_bytes()
        if (
            hashlib.sha256(image_bytes).hexdigest() != source["image_sha256"]
            or len(image_bytes) != source["image_bytes"]
        ):
            raise ValueError("善通寺原图指纹不一致")
    if manifest_path is not None:
        raw_manifest = manifest_path.read_bytes()
        if hashlib.sha256(raw_manifest).hexdigest() != source["manifest_sha256"]:
            raise ValueError("善通寺manifest指纹不一致")
        manifest = json.loads(raw_manifest)
        canvases = manifest["sequences"][0]["canvases"]
        selected = canvases[source["canvas_one_based"] - 1]
        image = selected["images"][0]["resource"]
        if (
            len(canvases) != source["canvas_count"]
            or selected["@id"] != source["selected_canvas_id"]
            or image["@id"] != source["image_url"]
            or [selected["width"], selected["height"]] != source["image_dimensions"]
            or manifest["attribution"] != source["source_attribution"]
        ):
            raise ValueError("善通寺所选画布、原图或归属不一致")
    return {
        "format": "sukuyo_zentsuji_hinoo_selected_check_v1",
        "source_id": source["id"],
        "source_bundle_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "selected_fragments_checked_against_prior_record": len(observations),
        "observed_month_day_mansions": [
            {key: row[key] for key in ("month", "day", "mansion")}
            for row in observations
            if "month" in row
        ],
        "full_image_bytes_rechecked": manuscript_image is not None,
        "full_manifest_bytes_rechecked": manifest_path is not None,
        "independent_palaeographic_reading_performed_by_script": False,
        "complete_manuscript_collation": False,
        "witness_identity_or_physical_copy_date_established": False,
        "intercalation_short_month_priority_established": False,
        "classical_clock_mapping_established": False,
        "calendar_algorithm_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript-image", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_primary(args.manuscript_image, args.manifest)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
