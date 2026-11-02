"""T1299's six natal counting positions, separate from transit evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_six_palaces.json"


def six_palace_reference(natal_mansion: Optional[str]) -> dict[str, Any]:
    from fatebridge.core.sukuyo_relations import normalize_mansion

    record = load_source(SOURCE)
    source = record.data
    order = source["mansion_order"]
    if natal_mansion is not None:
        if not isinstance(natal_mansion, str) or len(natal_mansion) != 1:
            raise ValueError("六宫宿须使用已核定的二十七宿本命宿（不含牛）")
        natal_mansion = normalize_mansion(natal_mansion)
        if natal_mansion not in order:
            raise ValueError("六宫宿须使用已核定的二十七宿本命宿（不含牛）")
    start = order.index(natal_mansion) if natal_mansion is not None else None
    return {
        "ruleset_id": source["id"],
        "status": "natal_reference" if start is not None else "natal_mansion_required",
        "natal_mansion": natal_mansion,
        "members": (
            [
                {
                    **row,
                    "mansion": order[(start + row["inclusive_ordinal"] - 1) % 27],
                }
                for row in source["positions"]
            ]
            if start is not None
            else []
        ),
        "counting_basis": source["counting_basis"],
        "source_url": source["source_url"],
        "source_sha256": source["source_sha256"],
        "source_bundle_sha256": record.sha256,
        "locator": source["locator"],
        "counting_excerpt": source["counting_excerpt"],
        "joint_reading_requirement": source["joint_reading_requirement"],
        "seven_luminary_transits_evaluated": False,
        "applied_to_day_assessment": False,
        "scope": source["scope"],
    }
