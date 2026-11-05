"""Verify the captured named witness, without authenticating its clock policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fatebridge.core.sukuyo_kenyu import SOURCE, lookup_printed_hour
from fatebridge.core.sukuyo_sources import load_source
from scripts.sukuyo.audit_sukuyo_t2465_primary import SATQuotationParser


def verify_kenyu(captures: Path | None = None) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    source = loaded.data
    table = source["clock_selected"]
    if len(table["table_rows"]) != 8 or any(
        len(r["luminaries"]) != 7 for r in table["table_rows"]
    ):
        raise ValueError("Printed matrix must retain all 56 cells")
    for example in table["source_prose_examples"]:
        part = {"上": "upper", "下": "lower", None: None}[example["part"]]
        actual = lookup_printed_hour(example["day_luminary"], example["branch"], part)
        if actual["selected_hour_luminary"] != example["hour_luminary"]:
            raise ValueError("Printed table differs from an explicit prose example")
    checked = []
    if captures is not None:
        for name, expected in [
            ("nijl-100159236-manifest.json", source["manifest_sha256"]),
            ("sat-t2216-0058.html", source["commentary_selected"]["html_sha256"]),
            *[
                (f"nijl-100159236-frame{r['frame']}.jpg", r["sha256"])
                for r in source["images"]
            ],
            *[(r["file"], r["sha256"]) for r in source["model_reading_receipts"]],
        ]:
            raw = (captures / name).read_bytes()
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != expected:
                raise ValueError(f"Captured source bytes changed: {name}")
            checked.append({"name": name, "bytes": len(raw), "sha256": actual_sha})
        manifest = json.loads((captures / "nijl-100159236-manifest.json").read_bytes())
        canvases = manifest["sequences"][0]["canvases"]
        if len(canvases) != source["catalogue"]["manifest_canvas_count"]:
            raise ValueError("Manifest canvas count changed")
        for row in source["images"]:
            canvas = canvases[row["frame"] - 1]
            if (
                canvas["@id"] != row["canvas"]
                or canvas["images"][0]["resource"]["@id"] != row["url"]
            ):
                raise ValueError("Captured image is not bound to its manifest canvas")
        parser = SATQuotationParser()
        parser.feed((captures / "sat-t2216-0058.html").read_text(encoding="utf-8"))
        text = "".join("".join(line) for line in parser.lines.values())
        for passage in source["commentary_selected"]["passages"]:
            if passage["literal"] not in text:
                raise ValueError(f"Selected commentary changed: {passage['locator']}")
    return {
        "source_bundle_sha256": loaded.sha256,
        "captured_bytes_rechecked": captures is not None,
        "checked_captures": checked,
        "printed_cells": 56,
        "explicit_prose_lookups": len(table["source_prose_examples"]),
        "day_branch_rows": 8,
        "night_branch_pairs": 4,
        "modern_clock_conversion_established": False,
        "unique_t1299_interpretation_established": False,
        "leap_short_month_priority_established": False,
        "human_full_collation_complete": False,
        "real_world_samples": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_kenyu(args.captures)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
