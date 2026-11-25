"""The six explicit childhood-age palaces, separate from decade substitution."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-childhood.json")
            .read_text(encoding="utf-8")
        ),
    )


def childhood_limit(chart: dict[str, Any], age: int) -> dict[str, Any]:
    """Compute a literal age row and join actual natal facts, never a new 四化.

    This is an independent childhood method. Returning it does not certify
    the software's use of a childhood palace in the pre-decade slot.
    """
    if age < 1:
        raise ValueError("童限需要正整数岁序")
    source = _source()
    row = next((r for r in source["ordinal_rows"] if r["age"] == age), None)
    palace = (
        next(p for p in chart["palaces"] if p["name"] == row["modern_palace_name"])
        if row is not None
        else None
    )
    return {
        "method_id": source["id"],
        "version": source["version"],
        "status": "computed_given_age_ordinal" if palace else "unresolved_from_source",
        "given_age_ordinal": age,
        "source_palace_label": row["source_palace"] if row else None,
        "natal_palace_name": palace["name"] if palace else None,
        "natal_branch": palace["ganzhi"][1] if palace else None,
        "natal_palace_ganzhi": palace["ganzhi"] if palace else None,
        "natal_stars_detail": (
            [dict(s) for s in palace["stars_detail"]] if palace else []
        ),
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "frame": source["frame"],
        "source_section": source["section"],
        "source_reading": source["quote"],
        "source_reading_caveat": source["tail_glyph_note"],
        "age_boundary_rule_verified": False,
        "pre_decade_substitution_verified": False,
        "childhood_sihua_supported": False,
        "natal_stars_are_not_childhood_transformations": True,
        "unresolved_reason": (
            None
            if palace
            else "本批只据明文确定一至六岁；后半句未得唯一排法，不据此推定当前岁序宫位"
        ),
    }
