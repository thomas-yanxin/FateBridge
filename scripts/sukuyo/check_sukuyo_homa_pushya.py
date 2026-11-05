"""Verify retained capture bytes and selected Homa date readings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.sukuyo.check_sukuyo_commentarial_clock import check_literal_days

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/fatebridge/data/sukuyo_homa_pushya_manuscript.json"
FIXTURE = ROOT / "tests/data/sukuyo-homa-pushya-primary.json"


def verify_primary(
    images: dict[int, Path] | None = None, manifest_path: Path | None = None
) -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    fixture = json.loads(FIXTURE.read_bytes())
    if hashlib.sha256(raw).hexdigest() != fixture["source_bundle_sha256"]:
        raise ValueError("护摩读录资料指纹不一致")
    rows = source["monthly_day_observations"]
    literal_days = [{k: row[k] for k in ("month", "day", "literal")} for row in rows]
    if literal_days != fixture["literal_days"]:
        raise ValueError("护摩月日与固定读录不一致")
    # Reuse the numeral binding, not a second independently maintained parser.
    check_literal_days(
        {
            "sources": [
                {
                    "id": "T2216",
                    "selected_quotations": [
                        {"literal": "。".join(row["literal"] for row in rows)}
                    ],
                }
            ],
            "monthly_pushya_reference": {
                "literal_days": [{k: row[k] for k in ("month", "day")} for row in rows]
            },
        }
    )
    expected = {
        row["canvas_index_one_based"]: row
        for row in source["source_reference"]["images"]
    }
    checked = []
    for number, path in (images or {}).items():
        if number not in expected:
            raise ValueError("未登记的护摩影像")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[number]["sha256"]:
            raise ValueError("护摩影像字节指纹不一致")
        checked.append(number)
    if manifest_path is not None:
        data = manifest_path.read_bytes()
        if (
            hashlib.sha256(data).hexdigest()
            != source["source_reference"]["manifest_sha256"]
        ):
            raise ValueError("护摩清单字节指纹不一致")
        canvases = json.loads(data)["sequences"][0]["canvases"]
        for number, row in expected.items():
            canvas = canvases[number - 1]
            if (
                canvas["@id"] != row["canvas_id"]
                or canvas["images"][0]["resource"]["@id"] != row["url"]
            ):
                raise ValueError("清单未绑定所选护摩影像")
    return {
        "source_bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "selected_month_day_controls": len(rows),
        "literal_dates_bound_to_numeric_controls": True,
        "actual_image_bytes_rechecked": sorted(checked),
        "actual_manifest_bytes_rechecked": manifest_path is not None,
        "unique_star_name_glyph_accepted": False,
        "independent_palaeographic_reading_performed_by_script": False,
        "identified_as_T2216_cited_exemplar": False,
        "historical_clock_or_rule_priority_established": False,
        "scope": "Byte identity and selected reading binding only. Does not read glyphs or certify quoted exemplar, dates, lineage, full book or efficacy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", default=[], metavar="NUMBER=PATH")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    images = {}
    for argument in args.image:
        number, path = argument.split("=", 1)
        index = int(number)
        if index in images:
            raise ValueError("重复影像")
        images[index] = Path(path)
    print(
        json.dumps(verify_primary(images, args.manifest), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
