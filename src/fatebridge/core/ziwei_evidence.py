"""Chart geometry and explicit palace identities, without event predictions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from fatebridge.utils.data import ZIWEI_BRANCH_SEQUENCE

ZIWEI_MAJOR_STARS = frozenset(
    {
        "紫微",
        "天机",
        "太阳",
        "武曲",
        "天同",
        "廉贞",
        "天府",
        "太阴",
        "贪狼",
        "巨门",
        "天相",
        "天梁",
        "七杀",
        "破军",
    }
)


def horoscope_natal_prerequisites(chart: Dict[str, Any]) -> Dict[str, Any]:
    """Carry the actual natal derivation used by this horoscope, without reruns.

    A horoscope's bureau/starting age depends on natal inputs. Expose their
    existing trace so a consumer need not infer a natal stem from target time or
    manufacture another birth run. Source comparisons retain their own scope.
    """
    required = (
        "lunar_month_for_placement",
        "ming_shen_month_hour",
        "wuhu_dun_nayin_ju",
    )
    traces = chart["rule_trace"]
    if any(sum(t["rule_id"] == name for t in traces) != 1 for name in required):
        raise ValueError("紫微运限本命前置链缺少或重复必要规则回执")
    return {
        "schema_version": "ziwei_horoscope_natal_prerequisites_v1",
        "origin": "same_calculation_internal_natal_chart",
        "ruleset": {
            key: chart["ruleset"][key]
            for key in ("id", "version", "sihua_source")
            if key in chart["ruleset"]
        },
        **{
            key: deepcopy(chart[key])
            for key in (
                "lunar_date",
                "year_stem",
                "hour_branch",
                "ming_gong",
                "shen_gong",
                "wuxing_ju",
            )
        },
        "rule_trace": [
            deepcopy(next(t for t in traces if t["rule_id"] == name))
            for name in required
        ],
        "separate_birth_run": False,
        "classical_birth_year_boundary_verified": False,
    }


def natal_reading_view(palaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lossless star facts and geometry references for a bounded first response.

    Null star attributes have one explicit encoding policy; related stars are
    joined by branch in this same twelve-palace view, rather than copied four
    times per palace. The full palace evidence remains available separately.
    """
    return {
        "schema_version": "ziwei_natal_reading_v1",
        "star_occurrence_count": sum(len(p["stars_detail"]) for p in palaces),
        "distinct_star_count": len(
            {s["name"] for p in palaces for s in p["stars_detail"]}
        ),
        "null_star_fields_omitted": ["brightness", "mutagen"],
        "sanfang_branch_order": ["本宫", "三合", "三合", "对宫"],
        "palaces": [
            {
                "name": p["name"],
                "ganzhi": p["ganzhi"],
                "stars": [
                    {
                        key: star[key]
                        for key in ("name", "brightness", "mutagen")
                        if star[key] is not None
                    }
                    for star in p["stars_detail"]
                ],
                "major_stars": list(p["structural_evidence"]["major_stars"]),
                "sanfang_sizheng_branches": [
                    r["branch"] for r in p["structural_evidence"]["sanfang_sizheng"]
                ],
                "changsheng12": p["changsheng12"],
                "boshi12": p["boshi12"],
                "daxian": p["daxian"],
            }
            for p in palaces
        ],
    }


def palace_structural_evidence(
    palace: Dict[str, Any], palaces: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """本宫 + 两个三合宫 + 对宫；空宫不搬移或复制对宫星曜。"""
    by_branch = {p["ganzhi"][1]: p for p in palaces}
    index = ZIWEI_BRANCH_SEQUENCE.index(palace["ganzhi"][1])
    related = []
    for offset, relation in ((0, "本宫"), (4, "三合"), (8, "三合"), (6, "对宫")):
        branch = ZIWEI_BRANCH_SEQUENCE[(index + offset) % 12]
        p = by_branch[branch]
        related.append(
            {
                "relation": relation,
                "natal_palace_name": p["name"],
                "natal_palace_ganzhi": p["ganzhi"],
                "branch": branch,
                "stars_detail": deepcopy(p["stars_detail"]),
            }
        )
    major = [
        s["name"] for s in palace["stars_detail"] if s["name"] in ZIWEI_MAJOR_STARS
    ]
    return {
        "major_stars": major,
        "is_empty_main_palace": not major,
        "sanfang_sizheng": related,
        "opposite_stars_relocated": False,
    }


def scope_palace_map(
    ming_branch: str,
    palaces: List[Dict[str, Any]],
    palace_sequence: List[str],
) -> List[Dict[str, Any]]:
    """Rotate functional names from this scope's Ming; retain natal stems/stars.

    This does not calculate flowing auxiliary stars, new palace stems, flying
    palace-stem transformations, or a composite school's complete dynamic chart.
    """
    by_branch = {p["ganzhi"][1]: p for p in palaces}
    index = ZIWEI_BRANCH_SEQUENCE.index(ming_branch)
    result = []
    for offset, role in enumerate(palace_sequence):
        branch = ZIWEI_BRANCH_SEQUENCE[(index + offset) % 12]
        natal = by_branch[branch]
        result.append(
            {
                "scope_palace_name": role,
                "branch": branch,
                "natal_palace_name": natal["name"],
                "natal_palace_ganzhi": natal["ganzhi"],
                "natal_stars_detail": deepcopy(natal["stars_detail"]),
            }
        )
    return result
