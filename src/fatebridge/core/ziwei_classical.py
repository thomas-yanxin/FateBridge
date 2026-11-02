"""Pinned-text facts joined to computed Ziwei placements, without predictions."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, cast

from fatebridge.core.ziwei_rulesets import QUANSHU_SOURCE
from fatebridge.utils.data import EARTHLY_BRANCHES


@lru_cache(maxsize=1)
def _symbolic_source() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-quanshu-v2-stars.json")
            .read_text(encoding="utf-8")
        ),
    )


def symbolic_properties(palaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Quote the selected text separately from the actual natal 四化 marker.

    For example, 武曲「化财」and 天相「化印」are textual symbolic phrases,
    not additional 禄/权/科/忌 assignments. Water/metal in 天同 and fire/metal
    in 七杀 are retained as written, rather than resolved to a software norm.
    """
    source = _symbolic_source()
    records = []
    for entry in source["entries"]:
        for i, palace in enumerate(palaces):
            for j, star in enumerate(palace["stars_detail"]):
                if star["name"] != entry["star"]:
                    continue
                records.append(
                    {
                        "star": entry["star"],
                        "source_name": entry["source_name"],
                        "elements_as_written": list(entry["elements"]),
                        "source_quote": entry["quote"],
                        "source_section": entry["section"],
                        "natal_palace_name": palace["name"],
                        "natal_branch": palace["ganzhi"][1],
                        "natal_brightness": star["brightness"],
                        "natal_mutagen": star["mutagen"],
                        "calculation_path": f"ziwei_birth.palaces.{i}.stars_detail.{j}",
                    }
                )
    return {
        "method_id": source["id"],
        "source": source["source_url"],
        "source_status": "pinned_transcription_quotes_with_element_only_scan_crosscheck",
        "element_collation_source": source["element_collation_source"],
        "element_collation_frames": source["element_collation_frames"],
        "element_collation_scope": source["element_collation_scope"],
        "scope": source["scope"],
        "textual_hua_terms_are_sihua": False,
        "multi_element_text_retained": True,
        "records": records,
    }


def annual_text_stars(
    scope_palaces: List[Dict[str, Any]], *, year_branch: str
) -> List[Dict[str, Any]]:
    """Annual virtues/four flying stars, not the natal same-name stars."""
    year_index = EARTHLY_BRANCHES.index(year_branch)
    result = []
    for star, offset, system, rule in (
        ("天德", 9, "annual_virtues", "annual_tiande_yuede"),
        ("月德", 0, "annual_virtues", "annual_tiande_yuede"),
        ("丧门", 2, "annual_four_flying_stars", "annual_sangmen_four"),
        ("吊客", -2, "annual_four_flying_stars", "annual_sangmen_four"),
        ("白虎", 8, "annual_four_flying_stars", "annual_sangmen_four"),
        ("官府", 4, "annual_four_flying_stars", "annual_sangmen_four"),
    ):
        branch = EARTHLY_BRANCHES[(year_index + offset) % 12]
        palace = next(p for p in scope_palaces if p["branch"] == branch)
        result.append(
            {
                "star": star,
                "scope": "流年",
                "system_id": system,
                "branch": branch,
                "scope_palace_name": palace["scope_palace_name"],
                "natal_palace_name": palace["natal_palace_name"],
                "rule_id": rule,
                "year_branch": year_branch,
                "source": QUANSHU_SOURCE,
                "natal_stars_relocated": False,
            }
        )
    return result


def annual_three_sha(year_branch: str) -> Dict[str, Any]:
    """The text gives a branch set; it does not pair each named sha to it."""
    groups = (
        ("寅午戌", ["亥", "卯", "未"]),
        ("申子辰", ["巳", "酉", "丑"]),
        ("巳酉丑", ["寅", "午", "戌"]),
        ("亥卯未", ["申", "子", "辰"]),
    )
    branches = next(target for group, target in groups if year_branch in group)
    return {
        "rule_id": "annual_flying_three_sha",
        "scope": "流年",
        "year_branch": year_branch,
        "names_as_written": ["奏书", "将军", "直符"],
        "branches": list(branches),
        "individual_name_positions": None,
        "individual_assignment_status": "not_explicit_in_selected_text",
        "source": QUANSHU_SOURCE,
        "distinct_from_boshi_cycle": True,
    }
