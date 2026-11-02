"""Seven explicitly sourced 德禄马 anchors and their actual Liu Ren seats.

The source's 月序 is indexed with the calculated month-building branch.
Stars name heaven branches: locate them by inverting the earth-to-sky board.
This is deliberately a set of placement facts, not a comprehensive verdict.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import GUI_REN_SEQUENCE, sexagenary_index_for
from .liureng_life_stages import build_life_stages
from .ren_evidence import xun_dun_stems

MONTH_ORDER = "寅卯辰巳午未申酉戌亥子丑"
HEAVEN_DE = dict(
    zip(
        MONTH_ORDER,
        "丁未 坤申 壬亥 辛戌 乾亥 甲寅 癸丑 艮寅 丙巳 乙辰 巽巳 庚申".split(),
    )
)
MONTH_DE = dict(zip(MONTH_ORDER, ["丙巳", "甲寅", "壬亥", "庚申"] * 3))
DAY_DE = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅申巳亥巳寅申巳亥巳"))
BRANCH_DE = dict(zip(EARTHLY_BRANCHES, "巳午未申酉戌亥子丑寅卯辰"))
DAY_HORSE = dict(zip(EARTHLY_BRANCHES, "寅亥申巳寅亥申巳寅亥申巳"))
HEAVEN_HORSE = dict(zip(MONTH_ORDER, "午申戌子寅辰午申戌子寅辰"))
MONTH_BASIS = "按本次计算的节换月月建，寅至丑对应名义月序一至十二；这是软件输入约定，不以农历月份或月将代替月建。"


def build_auxiliary_stars(
    *,
    day_ganzhi: str,
    month_branch: str,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
    lessons: list[dict[str, Any]],
    transmissions: list[str],
) -> dict[str, Any]:
    if len(day_ganzhi) != 2:
        raise ValueError("德禄马需要有效日干支")
    try:
        sexagenary_index_for(day_ganzhi)
    except KeyError as exc:
        raise ValueError("德禄马需要有效日干支") from exc
    if month_branch not in MONTH_ORDER or len(month_branch) != 1:
        raise ValueError("德禄马需要有效月建")
    stages = build_life_stages(day_ganzhi[0], sky_by_earth)
    branches = set(EARTHLY_BRANCHES)
    if set(god_by_sky) != branches or set(god_by_sky.values()) != set(GUI_REN_SEQUENCE):
        raise ValueError("德禄马需要完整且不重复的天将对应")
    if (
        len(lessons) != 4
        or [l.get("index") for l in lessons] != [1, 2, 3, 4]
        or any(l.get("upper_branch") not in branches for l in lessons)
    ):
        raise ValueError("德禄马需要四课上神")
    if len(transmissions) != 3 or any(t not in branches for t in transmissions):
        raise ValueError("德禄马需要完整三传")
    stem, day_branch = day_ganzhi[0], day_ganzhi[1]
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    dun = xun_dun_stems(day_ganzhi)
    stars = []
    for star_id, name, category, token, pages in (
        ("heaven_de", "天德", "month_building", HEAVEN_DE[month_branch], [90]),
        ("month_de", "月德", "month_building", MONTH_DE[month_branch], [90, 91]),
        ("day_de", "日德", "day_stem", DAY_DE[stem], [91]),
        ("branch_de", "日支德", "day_branch", BRANCH_DE[day_branch], [91]),
        ("day_lu", "日禄", "day_stem", stages["linguan_branch"], [94, 104]),
        ("day_horse", "驿马", "day_branch", DAY_HORSE[day_branch], [97]),
        ("heaven_horse", "天马", "month_building", HEAVEN_HORSE[month_branch], [87]),
    ):
        branch = token[-1]
        earth = earth_by_sky[branch]
        stars.append(
            {
                "id": star_id,
                "name": name,
                "category": category,
                "source_token": token,
                "branch": branch,
                "original_pdf_pages": pages,
                "earth_branch": earth,
                "god": god_by_sky[branch],
                "dun_stem": dun.get(branch),
                "ganzhi": f"{dun[branch]}{branch}" if branch in dun else None,
                "xun_kong": branch not in dun,
                "seated_kong": earth not in dun,
                "day_stem_life_stage": stages["stage_by_branch"][branch],
                "lesson_indices": [
                    l["index"] for l in lessons if l["upper_branch"] == branch
                ],
                "transmission_positions": [
                    label
                    for label, value in zip(
                        ("initial", "middle", "final"), transmissions
                    )
                    if value == branch
                ],
                "on_day_stem": lessons[0]["upper_branch"] == branch,
                "on_day_branch": lessons[2]["upper_branch"] == branch,
            }
        )
    return {
        "ruleset_id": "tanyuan_auxiliary_stars_v1",
        "source_title": "大六壬探原·论德、论年命、论墓、论冲及论占事（德禄马定位）",
        "source_url": TANYUAN_SOURCE,
        "source_sha256": TANYUAN_SCAN_SHA256,
        "original_pdf_pages": [87, 90, 91, 94, 97, 104],
        "day_ganzhi": day_ganzhi,
        "month_building_branch": month_branch,
        "nominal_month": MONTH_ORDER.index(month_branch) + 1,
        "month_basis": MONTH_BASIS,
        "stars": stars,
        "complete_classical_conformance": False,
        "scope": "仅列所选七项德禄马的支位、天将、空亡及入课入传事实；德与禄各依明文，不以禄替代阴干日德或天德寄支。尚非完整神煞体系、整书符合性或综合吉凶判断，不据此保证现实结果。",
    }
