"""Place 年命 on the earth plate, then read the existing heaven plate."""

from typing import Any, Dict, Optional

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from .common import (
    EARTHLY_BRANCHES,
    SEXAGENARY_INDEX,
    branch_element_text,
    liuqin_against_day,
    sexagenary_text,
    stem_element_text,
)
from .ren_evidence import xun_dun_stems


def natal_year_ganzhi(birth_lunar_year: int) -> str:
    """Use the declared civil-lunar birth year, not the birth pillar year."""
    if type(birth_lunar_year) is not int:
        raise ValueError("本命需要有效的出生农历年")
    return sexagenary_text(birth_lunar_year - 4)


def build_year_fate(
    board: Dict[str, Any],
    *,
    day_ganzhi: str,
    birth_lunar_year: int,
    runyear_ganzhi: Optional[str],
    runyear_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Never invert earth/heaven lookup or reuse 年命 stems as 旬遁 stems."""
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("年命上神需要有效的占日干支")
    rows = board["twelve_board"]
    if (
        len(rows) != 12
        or {row["earth_branch"] for row in rows} != set(EARTHLY_BRANCHES)
        or {row["sky_branch"] for row in rows} != set(EARTHLY_BRANCHES)
    ):
        raise ValueError("年命上神需要完整且不重复的天地盘")
    by_earth = {row["earth_branch"]: row for row in rows}
    dun = xun_dun_stems(day_ganzhi)
    day_element = stem_element_text(day_ganzhi[0])

    def placement(subject: Optional[str]) -> Dict[str, Any]:
        if subject is None:
            return {
                "status": "not_calculated",
                "subject_ganzhi": None,
                "earth_branch": None,
                "sky_branch": None,
                "god": None,
                "upper_dun_stem": None,
                "upper_ganzhi": None,
                "upper_relation": None,
                "upper_xun_kong": None,
                "earth_xun_kong": None,
                "reason": runyear_reason or "行年未计算",
            }
        if subject not in SEXAGENARY_INDEX:
            raise ValueError("年命落盘需要有效干支")
        earth = subject[1]
        row = by_earth[earth]
        sky = row["sky_branch"]
        stem = dun.get(sky)
        return {
            "status": "calculated",
            "subject_ganzhi": subject,
            "earth_branch": earth,
            "sky_branch": sky,
            "god": row["god"],
            "upper_dun_stem": stem,
            "upper_ganzhi": f"{stem}{sky}" if stem else None,
            "upper_relation": liuqin_against_day(day_element, branch_element_text(sky)),
            "upper_xun_kong": sky not in dun,
            "earth_xun_kong": earth not in dun,
            "reason": None,
        }

    return {
        "ruleset_id": "tanyuan_year_fate_v1",
        "source_title": "袁树珊大六壬探原·卷上推演篇·年命",
        "source_url": TANYUAN_SOURCE,
        "source_sha256": TANYUAN_SCAN_SHA256,
        "original_pdf_pages": [70, 71, 72, 73],
        "birth_year_basis": "出生民用日期的农历年；沿用既有换岁口径，不取出生四柱年柱",
        "placement_basis": "本命与行年干支均书地盘，以其支读取同一课天盘上神及所乘天将",
        "day_ganzhi": day_ganzhi,
        "guiren_profile": board["meta"]["guiren_profile"],
        "natal": placement(natal_year_ganzhi(birth_lunar_year)),
        "annual": placement(runyear_ganzhi),
        "scope": "年命落盘事实；年命干支与上神旬遁干支分列，不据单一六亲作整体吉凶或现实预测",
    }
