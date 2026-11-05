"""Verify literal membership sets; image bytes do not authenticate a reading."""

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
from fatebridge.core.sukuyo_kenyu_pairs import SOURCE
from fatebridge.core.sukuyo_sources import load_source


def verify_pairs(materials: Path | None = None) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    source = loaded.data
    fixture = json.loads(
        (ROOT / "tests/data/sukuyo-kenyu-ndl-pairs-primary.json").read_bytes()
    )
    translation = str.maketrans(source["normalization"])

    def members(rows: dict[str, list[str]]) -> dict[str, set[str]]:
        return {k: {n.translate(translation) for n in v} for k, v in rows.items()}

    generator = fixture["generator_raw_selected_object"]
    reviewer = fixture["reviewer_raw_selected_object"]
    first = members(
        {r["weekday_glyph"]: r["mansion_glyphs"] for r in generator["table_readings"]}
    )
    second = members(
        {r["luminary"]: r["upper"] + r["lower"] for r in reviewer["table"]}
    )
    expected = members(source["memberships"])
    errors: list[str] = []
    if not first == second == expected:
        errors.append("literal_membership_sets")
    if sum(map(len, expected.values())) != 27 or len(expected["月"]) != 3:
        errors.append("readable_membership_count")
    if materials is not None:
        required = {
            "ndl-manifest.json": source["manifest_sha256"],
            "ndl-14487241-frame6.jpg": source["source_image"]["sha256"],
            **{r["file"]: r["sha256"] for r in source["model_reading_receipts"]},
        }
        for name, digest in required.items():
            raw = (materials / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                errors.append(name + ":digest")
            if name.startswith("generator-"):
                objects = json.loads(raw)["selected_diplomatic_readings"]
                if generator not in objects:
                    errors.append("generator_fragment")
            elif name.startswith("reviewer-"):
                frame = next(
                    r
                    for r in json.loads(raw)["selected_diplomatic_readings"]
                    if r.get("frame") == 6
                )
                if reviewer not in frame["readings"]:
                    errors.append("reviewer_fragment")
    return {
        "format": "sukuyo_kenyu_pair_source_check_v1",
        "source_bundle_sha256": loaded.sha256,
        "readable_memberships_checked": sum(map(len, expected.values())),
        "literal_model_reads_compared": 2,
        "cell_order_or_topology_compared": False,
        "original_image_and_model_read_bytes_checked": materials is not None,
        "independent_human_image_acceptance": False,
        "no_fourth_monday_member_inserted": True,
        "adjacent_twenty_eight_claim_retained": source["adjacent_stated_mansions"],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_pairs(args.materials)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
