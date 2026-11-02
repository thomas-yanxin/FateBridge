"""Audit a fixed printed witness without treating agreement as acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from fatebridge.core.sukuyo import SU27_ORDER
from fatebridge.core.sukuyo_calendar_text import month_table_variant
from fatebridge.core.sukuyo_koya import SOURCE, printed_month_reference
from fatebridge.core.sukuyo_profiles import select_profile
from fatebridge.core.sukuyo_sources import load_source


def verify_printed(image_directory: Optional[Path] = None) -> dict[str, Any]:
    source = load_source(SOURCE)
    bundle = source.data
    image_checks = []
    if image_directory is not None:
        for item in bundle["source_images"]:
            p = image_directory / f"upper-frame{item['frame']:02d}.jpg"
            if hashlib.sha256(p.read_bytes()).hexdigest() != item["image_sha256"]:
                raise ValueError("printed source image fingerprint changed")
            image_checks.append(p.name)
    rows = []
    for day in range(1, 31):
        for month in range(1, 13):
            selection = select_profile(
                month,
                day,
                False,
                SU27_ORDER,
                profile="t1299_fullmoon27",
                leap_policy="unresolved",
                day_part=None,
                previous_lunar=None,
            )
            host = selection["host_calculation"]
            upper = month_table_variant(month, day, host["direct_mansion"])
            ref = printed_month_reference(host, upper, selection, False)
            rows.append(
                {
                    "month": month,
                    "day": day,
                    "printed_literal": ref["printed_literal_mansion"],
                    "candidate_literals": ref["candidate_literal_mansions"],
                    "candidate_comparisons": ref["candidate_comparisons"],
                    "host_mansion": host["direct_mansion"],
                    "taisho_upper_literal": upper["literal_mansion"],
                    "matches_host": ref["matches_unsplit_host"],
                    "matches_taisho_upper": ref["matches_taisho_upper_literal"],
                }
            )
    return {
        "source_bundle_sha256": source.sha256,
        "printed_cells_compared": len(rows),
        "host_disagreements": [r for r in rows if r["matches_host"] is False],
        "unresolved_readings": [r for r in rows if r["matches_host"] is None],
        "agreed_model_readings": sum(r["printed_literal"] is not None for r in rows),
        "taisho_upper_disagreement_count": sum(
            r["matches_taisho_upper"] is False for r in rows
        ),
        "all_comparisons": rows,
        "full_image_bytes_rechecked": image_checks,
        "independent_human_transcription_accepted": False,
        "full_critical_edition_accepted": False,
        "modern_clock_mapping_accepted": False,
        "leap_short_month_priority_established": False,
        "real_world_samples_added": 0,
        "original_domain_or_criteria_reduced": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_printed(args.image_directory)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
