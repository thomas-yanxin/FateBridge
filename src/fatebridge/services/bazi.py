"""
Standalone BaZi tool surfaces for FateBridge.
"""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fatebridge.analysis.career import CareerAnalysis
from fatebridge.analysis.children import ChildrenAnalysis
from fatebridge.analysis.education import EducationAnalysis
from fatebridge.analysis.health import HealthAnalysis
from fatebridge.analysis.marriage import MarriageAnalysis
from fatebridge.analysis.personality import PersonalityAnalysis
from fatebridge.analysis.relatives import RelativesAnalysis
from fatebridge.analysis.romance import RomanceAnalysis
from fatebridge.analysis.wealth import WealthAnalysis
from fatebridge.core.almanac import (
    build_calendar_context,
    current_local_datetime,
    get_solar_terms_for_year,
    localize_datetime,
)
from fatebridge.core.classical import (
    build_classical_overview,
    classical_snapshot_lines,
)
from fatebridge.core.export_parser import parse_export_content
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX, kongwang_for_ganzhi
from fatebridge.services.birth_context import (
    BirthComputationContext,
    build_birth_computation_context,
)
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.structured_snapshot import render_structured_snapshot_text
from fatebridge.services.timing_state import build_current_timing_state
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    get_nayin,
    get_ten_god,
)
from fatebridge.utils.errors import (
    ParameterError,
    calculation_guard,
    handle_calculation_error,
)
from fatebridge.utils.formatting import format_birth_datetime_display

PILLAR_LABELS = {
    "year": "年柱",
    "month": "月柱",
    "day": "日柱",
    "hour": "时柱",
    "taiyuan": "胎元",
    "minggong": "命宫",
    "shengong": "身宫",
}

MONTH_HOUR_ORDER = [
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
    "子",
    "丑",
]

PEACH_BLOSSOM_TARGETS = (
    (("申", "子", "辰"), "酉"),
    (("寅", "午", "戌"), "卯"),
    (("亥", "卯", "未"), "子"),
    (("巳", "酉", "丑"), "午"),
)

TRAVEL_HORSE_TARGETS = (
    (("申", "子", "辰"), "寅"),
    (("寅", "午", "戌"), "申"),
    (("亥", "卯", "未"), "巳"),
    (("巳", "酉", "丑"), "亥"),
)

HUA_GAI_TARGETS = (
    (("申", "子", "辰"), "辰"),
    (("寅", "午", "戌"), "戌"),
    (("亥", "卯", "未"), "未"),
    (("巳", "酉", "丑"), "丑"),
)

TIAN_YI_TARGETS = {
    "甲": ["丑", "未"],
    "戊": ["丑", "未"],
    "庚": ["丑", "未"],
    "乙": ["子", "申"],
    "己": ["子", "申"],
    "丙": ["亥", "酉"],
    "丁": ["亥", "酉"],
    "辛": ["寅", "午"],
    "壬": ["卯", "巳"],
    "癸": ["卯", "巳"],
}

WEN_CHANG_TARGETS = {
    "甲": "巳",
    "乙": "午",
    "丙": "申",
    "丁": "酉",
    "戊": "申",
    "己": "酉",
    "庚": "亥",
    "辛": "子",
    "壬": "寅",
    "癸": "卯",
}

# --- 天德贵人 (Heavenly Virtue Noble) ---
# 按月支查天德所在
TIAN_DE_TARGETS = {
    "子": "巳",
    "丑": "庚",
    "寅": "丁",
    "卯": "申",
    "辰": "壬",
    "巳": "辛",
    "午": "亥",
    "未": "甲",
    "申": "癸",
    "酉": "寅",
    "戌": "丙",
    "亥": "乙",
}

# --- 月德贵人 (Monthly Virtue Noble) ---
# 按月支查月德所在
YUE_DE_TARGETS = {
    "子": "壬",
    "丑": "庚",
    "寅": "丙",
    "卯": "甲",
    "辰": "壬",
    "巳": "庚",
    "午": "丙",
    "未": "甲",
    "申": "壬",
    "酉": "庚",
    "戌": "丙",
    "亥": "甲",
}

# --- 将星 (General Star) ---
JIANG_XING_TARGETS = (
    (("申", "子", "辰"), "子"),
    (("寅", "午", "戌"), "午"),
    (("亥", "卯", "未"), "卯"),
    (("巳", "酉", "丑"), "酉"),
)

# --- 金舆 (Golden Carriage) ---
JIN_YU_TARGETS = {
    "甲": "辰",
    "乙": "巳",
    "丙": "未",
    "丁": "申",
    "戊": "未",
    "己": "申",
    "庚": "戌",
    "辛": "亥",
    "壬": "丑",
    "癸": "寅",
}

# --- 亡神 (Lost Spirit) ---
WANG_SHEN_TARGETS = (
    (("申", "子", "辰"), "亥"),
    (("寅", "午", "戌"), "巳"),
    (("亥", "卯", "未"), "寅"),
    (("巳", "酉", "丑"), "申"),
)

# --- 劫煞 (Robbery Sha) ---
JIE_SHA_TARGETS = (
    (("申", "子", "辰"), "巳"),
    (("寅", "午", "戌"), "亥"),
    (("亥", "卯", "未"), "申"),
    (("巳", "酉", "丑"), "寅"),
)

# --- 孤辰 (Lonely Star) ---
GU_CHEN_TARGETS = {
    "子": "寅",
    "丑": "寅",
    "寅": "巳",
    "卯": "巳",
    "辰": "巳",
    "巳": "申",
    "午": "申",
    "未": "申",
    "申": "亥",
    "酉": "亥",
    "戌": "亥",
    "亥": "寅",
}

# --- 寡宿 (Widow Star) ---
GUA_SU_TARGETS = {
    "子": "戌",
    "丑": "戌",
    "寅": "丑",
    "卯": "丑",
    "辰": "丑",
    "巳": "辰",
    "午": "辰",
    "未": "辰",
    "申": "未",
    "酉": "未",
    "戌": "未",
    "亥": "戌",
}

# --- 红鸾 (Red Phoenix) ---
HONG_LUAN_TARGETS = {
    "子": "卯",
    "丑": "寅",
    "寅": "丑",
    "卯": "子",
    "辰": "亥",
    "巳": "戌",
    "午": "酉",
    "未": "申",
    "申": "未",
    "酉": "午",
    "戌": "巳",
    "亥": "辰",
}

# --- 天喜 (Heavenly Joy) ---
TIAN_XI_TARGETS = {
    "子": "酉",
    "丑": "申",
    "寅": "未",
    "卯": "午",
    "辰": "巳",
    "巳": "辰",
    "午": "卯",
    "未": "寅",
    "申": "丑",
    "酉": "子",
    "戌": "亥",
    "亥": "戌",
}

# --- 学堂 (Study Hall) ---
XUE_TANG_TARGETS = {
    "甲": "亥",
    "乙": "午",
    "丙": "寅",
    "丁": "酉",
    "戊": "寅",
    "己": "酉",
    "庚": "巳",
    "辛": "子",
    "壬": "申",
    "癸": "卯",
}

# --- 词馆 (Literary Hall) ---
CI_GUAN_TARGETS = {
    "甲": "寅",
    "乙": "卯",
    "丙": "巳",
    "丁": "午",
    "戊": "巳",
    "己": "午",
    "庚": "申",
    "辛": "酉",
    "壬": "亥",
    "癸": "子",
}


def _resolve_analysis_date(
    analysis_year: Optional[int],
    analysis_month: Optional[int],
    analysis_day: Optional[int],
    *,
    timezone_name: Optional[str] = None,
) -> datetime:
    now = (
        current_local_datetime(timezone_name)
        if timezone_name is not None
        else current_local_datetime()
    )
    year = analysis_year if analysis_year is not None else now.year
    month = analysis_month if analysis_month is not None else now.month
    day = analysis_day if analysis_day is not None else now.day
    if all(
        value is not None for value in (analysis_year, analysis_month, analysis_day)
    ):
        return datetime(year, month, day)
    # Clamp the day to the resolved month so a partial date (e.g. only
    # analysis_day=31) combined with the current month never raises a
    # clock-dependent "day is out of range" error.
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day))


def _cycle_stem(stem: str, steps: int) -> str:
    return HEAVENLY_STEMS[(HEAVENLY_STEMS.index(stem) + steps) % len(HEAVENLY_STEMS)]


def _palace_stem(year_stem: str, position: int) -> str:
    """五虎遁: 给定年干, 取第 ``position`` 宫 (寅=1 … 丑=12) 的天干。

    命宫 / 身宫 的天干随宫位由年干起五虎遁定 (寅宫起干 = (年干序+1)*2),
    而非由月柱「相对位移」推导——后者把地支 mod-12 的位移直接喂给天干
    mod-10 的循环, 在宫位环绕到月支之前时会漏掉 ``12 mod 10 = 2`` 而偏 +2。
    """
    year_gan_index = HEAVENLY_STEMS.index(year_stem)
    gan_index = (year_gan_index + 1) * 2 + position
    while gan_index > 10:
        gan_index -= 10
    return HEAVENLY_STEMS[gan_index - 1]


def _build_origin_payload(
    *,
    label_key: str,
    stem: str,
    branch: str,
    day_stem: str,
) -> Dict[str, Any]:
    return {
        "label": PILLAR_LABELS[label_key],
        "stem": stem,
        "branch": branch,
        "pillar": f"{stem}{branch}",
        "nayin": get_nayin(stem, branch),
        "hidden_stems": BRANCH_HIDDEN_STEMS.get(branch, []),
        "ten_god": get_ten_god(day_stem, stem).value,
    }


def _build_three_origins(
    pillars: Dict[str, Tuple[str, str]],
) -> Dict[str, Dict[str, Any]]:
    year_stem = pillars["year"][0]
    month_stem, month_branch = pillars["month"]
    day_stem = pillars["day"][0]
    hour_branch = pillars["hour"][1]

    taiyuan = _build_origin_payload(
        label_key="taiyuan",
        stem=_cycle_stem(month_stem, 1),
        branch=EARTHLY_BRANCHES[
            (EARTHLY_BRANCHES.index(month_branch) + 3) % len(EARTHLY_BRANCHES)
        ],
        day_stem=day_stem,
    )

    # 月支按寅起 (寅=1 … 丑=12)。
    month_order = MONTH_HOUR_ORDER.index(month_branch) + 1

    # 命宫: 月支序 + 时支序 (时支同样寅起), 和 ≥14 用 26 减, 否则 14 减;
    # 余数即命宫宫位 (寅=1)，天干由年干起五虎遁定。
    ming_hour_order = MONTH_HOUR_ORDER.index(hour_branch) + 1
    ming_position = month_order + ming_hour_order
    ming_position = 26 - ming_position if ming_position >= 14 else 14 - ming_position
    ming_branch = MONTH_HOUR_ORDER[ming_position - 1]
    ming_stem = _palace_stem(year_stem, ming_position)

    # 身宫: 月支序 (寅起) + 时支序 (子起), 和 >12 减 12; 天干同样年干起五虎遁。
    shen_hour_order = EARTHLY_BRANCHES.index(hour_branch) + 1
    shen_position = month_order + shen_hour_order
    if shen_position > 12:
        shen_position -= 12
    shen_branch = MONTH_HOUR_ORDER[shen_position - 1]
    shen_stem = _palace_stem(year_stem, shen_position)

    return {
        "taiyuan": taiyuan,
        "minggong": _build_origin_payload(
            label_key="minggong",
            stem=ming_stem,
            branch=ming_branch,
            day_stem=day_stem,
        ),
        "shengong": _build_origin_payload(
            label_key="shengong",
            stem=shen_stem,
            branch=shen_branch,
            day_stem=day_stem,
        ),
    }


def _find_group_target(
    source_branch: str, mappings: tuple[tuple[tuple[str, ...], str], ...]
) -> Optional[str]:
    for group, target in mappings:
        if source_branch in group:
            return target
    return None


def _collect_branch_hits(
    target_branches: List[str],
    positions: Dict[str, str],
) -> List[str]:
    hits: List[str] = []
    for key, branch in positions.items():
        if branch in target_branches:
            hits.append(f"{PILLAR_LABELS[key]}{branch}")
    return hits


def _collect_stem_or_branch_hits(
    target: str,
    stem_positions: Dict[str, str],
    branch_positions: Dict[str, str],
) -> List[str]:
    """Collect hits for a target that can be either a stem or a branch."""
    from fatebridge.utils.data import HEAVENLY_STEMS

    hits: List[str] = []
    if target in HEAVENLY_STEMS:
        for key, stem in stem_positions.items():
            if stem == target:
                hits.append(f"{PILLAR_LABELS[key]}{stem}")
    else:
        for key, branch in branch_positions.items():
            if branch == target:
                hits.append(f"{PILLAR_LABELS[key]}{branch}")
    return hits


def _build_shensha_entries(
    *,
    pillars: Dict[str, Tuple[str, str]],
    three_origins: Dict[str, Dict[str, Any]],
) -> List[Dict[str, str]]:
    branch_positions = {
        "year": pillars["year"][1],
        "month": pillars["month"][1],
        "day": pillars["day"][1],
        "hour": pillars["hour"][1],
        "taiyuan": three_origins["taiyuan"]["branch"],
        "minggong": three_origins["minggong"]["branch"],
        "shengong": three_origins["shengong"]["branch"],
    }
    stem_positions = {
        "year": pillars["year"][0],
        "month": pillars["month"][0],
        "day": pillars["day"][0],
        "hour": pillars["hour"][0],
        "taiyuan": three_origins["taiyuan"]["stem"],
        "minggong": three_origins["minggong"]["stem"],
        "shengong": three_origins["shengong"]["stem"],
    }
    day_stem = pillars["day"][0]
    year_branch = pillars["year"][1]
    day_branch = pillars["day"][1]

    entries: List[Dict[str, str]] = []
    for key, (stem, branch) in pillars.items():
        entries.append(
            {
                "label": f"{PILLAR_LABELS[key]}纳音",
                "value": get_nayin(stem, branch),
            }
        )
    for origin_key, origin in three_origins.items():
        entries.append(
            {
                "label": f"{PILLAR_LABELS[origin_key]}纳音",
                "value": origin["nayin"],
            }
        )

    year_peach = _find_group_target(year_branch, PEACH_BLOSSOM_TARGETS)
    day_peach = _find_group_target(day_branch, PEACH_BLOSSOM_TARGETS)
    year_horse = _find_group_target(year_branch, TRAVEL_HORSE_TARGETS)
    day_horse = _find_group_target(day_branch, TRAVEL_HORSE_TARGETS)
    year_huagai = _find_group_target(year_branch, HUA_GAI_TARGETS)
    day_huagai = _find_group_target(day_branch, HUA_GAI_TARGETS)
    year_jiangxing = _find_group_target(year_branch, JIANG_XING_TARGETS)
    day_jiangxing = _find_group_target(day_branch, JIANG_XING_TARGETS)
    year_wangshen = _find_group_target(year_branch, WANG_SHEN_TARGETS)
    day_wangshen = _find_group_target(day_branch, WANG_SHEN_TARGETS)
    year_jiesha = _find_group_target(year_branch, JIE_SHA_TARGETS)
    day_jiesha = _find_group_target(day_branch, JIE_SHA_TARGETS)

    month_branch = pillars["month"][1]
    tian_de_target = TIAN_DE_TARGETS.get(month_branch)
    yue_de_target = YUE_DE_TARGETS.get(month_branch)

    rule_rows: List[Tuple[str, List[str]]] = [
        ("年支桃花", [year_peach] if year_peach else []),
        ("日支桃花", [day_peach] if day_peach else []),
        ("年支驿马", [year_horse] if year_horse else []),
        ("日支驿马", [day_horse] if day_horse else []),
        ("年支华盖", [year_huagai] if year_huagai else []),
        ("日支华盖", [day_huagai] if day_huagai else []),
        ("日主天乙贵人", TIAN_YI_TARGETS.get(day_stem, [])),
        (
            "日主文昌",
            [WEN_CHANG_TARGETS[day_stem]] if day_stem in WEN_CHANG_TARGETS else [],
        ),
        ("年支将星", [year_jiangxing] if year_jiangxing else []),
        ("日支将星", [day_jiangxing] if day_jiangxing else []),
        ("日主金舆", [JIN_YU_TARGETS[day_stem]] if day_stem in JIN_YU_TARGETS else []),
        ("年支亡神", [year_wangshen] if year_wangshen else []),
        ("日支亡神", [day_wangshen] if day_wangshen else []),
        ("年支劫煞", [year_jiesha] if year_jiesha else []),
        ("日支劫煞", [day_jiesha] if day_jiesha else []),
        (
            "日支孤辰",
            [GU_CHEN_TARGETS[day_branch]] if day_branch in GU_CHEN_TARGETS else [],
        ),
        (
            "日支寡宿",
            [GUA_SU_TARGETS[day_branch]] if day_branch in GUA_SU_TARGETS else [],
        ),
        (
            "年支红鸾",
            (
                [HONG_LUAN_TARGETS[year_branch]]
                if year_branch in HONG_LUAN_TARGETS
                else []
            ),
        ),
        (
            "年支天喜",
            [TIAN_XI_TARGETS[year_branch]] if year_branch in TIAN_XI_TARGETS else [],
        ),
        (
            "日主学堂",
            [XUE_TANG_TARGETS[day_stem]] if day_stem in XUE_TANG_TARGETS else [],
        ),
        (
            "日主词馆",
            [CI_GUAN_TARGETS[day_stem]] if day_stem in CI_GUAN_TARGETS else [],
        ),
        (
            "年柱空亡",
            list(kongwang_for_ganzhi(f"{pillars['year'][0]}{pillars['year'][1]}")),
        ),
        ("日柱空亡", list(kongwang_for_ganzhi(f"{day_stem}{day_branch}"))),
    ]

    for label, targets in rule_rows:
        hits = _collect_branch_hits(targets, branch_positions) if targets else []
        entries.append(
            {
                "label": label,
                "value": "、".join(hits) if hits else "未触发",
            }
        )

    # 天德/月德需要同时检查天干和地支位置
    if tian_de_target:
        tian_de_hits = _collect_stem_or_branch_hits(
            tian_de_target, stem_positions, branch_positions
        )
        entries.append(
            {
                "label": "天德",
                "value": "、".join(tian_de_hits) if tian_de_hits else "未触发",
            }
        )
    else:
        entries.append({"label": "天德", "value": "未触发"})
    if yue_de_target:
        yue_de_hits = _collect_stem_or_branch_hits(
            yue_de_target, stem_positions, branch_positions
        )
        entries.append(
            {
                "label": "月德",
                "value": "、".join(yue_de_hits) if yue_de_hits else "未触发",
            }
        )
    else:
        entries.append({"label": "月德", "value": "未触发"})

    return entries


def _build_timing_overview(
    *,
    birth_context: BirthComputationContext,
    analysis_date: datetime,
    analysis_calendar_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    timing_state = build_current_timing_state(
        birth_context,
        analysis_date=analysis_date,
    )
    dayun_result = timing_state["dayun_analysis"]
    liunian_result = timing_state["liunian_analysis"]
    liuyue_result = timing_state["liuyue_analysis"]
    liuri_result = timing_state["liuri_analysis"]
    liushi_result = timing_state["liushi_analysis"]

    dayun_payload: Dict[str, Any]
    if "dayun_info" in dayun_result:
        dayun_payload = {
            "pillar": dayun_result["dayun_info"]["pillar"],
            "start_age": dayun_result["age_info"]["start_age"],
            "dayun_age": dayun_result["age_info"]["dayun_age"],
            "years_in_period": dayun_result["age_info"]["years_in_period"],
            "summary": dayun_result.get("summary", ""),
        }
    else:
        dayun_payload = {
            "pillar": None,
            "summary": dayun_result.get("error", "大运信息不可用"),
        }

    liuyue_info = liuyue_result["liuyue_info"]
    liuri_info = liuri_result["liuri_info"]
    liushi_info = liushi_result["liushi_info"]

    current_solar_term_name = (
        (analysis_calendar_context or {})
        .get("current_solar_term", {})
        .get("name", "未知")
    )
    next_solar_term_name = (
        (analysis_calendar_context or {}).get("next_solar_term", {}).get("name", "未知")
    )

    return {
        "analysis_date": analysis_date.strftime("%Y-%m-%d"),
        "dayun": dayun_payload,
        "liunian": {
            "pillar": liunian_result["liunian_info"]["pillar"],
            "summary": liunian_result.get("summary", ""),
        },
        "liuyue": {
            "pillar": liuyue_info["pillar"],
            "summary": liuyue_result.get("summary", ""),
            "start_term": liuyue_info["solar_term_window"]["start_term"]["name"],
            "end_term": liuyue_info["solar_term_window"]["next_term"]["name"],
        },
        "liuri": {
            "pillar": liuri_info["pillar"],
            "summary": liuri_result.get("summary", ""),
            "weekday": liuri_info["weekday"],
        },
        "liushi": {
            "pillar": liushi_info["pillar"],
            "summary": liushi_result.get("summary", ""),
            "hour": liushi_info["hour"],
            "shichen": liushi_info["shichen"],
        },
        "current_jieqi": liuyue_info["solar_term_window"]["start_term"]["name"],
        "next_jieqi": liuyue_info["solar_term_window"]["next_term"]["name"],
        "current_solar_term_name": current_solar_term_name,
        "next_solar_term_name": next_solar_term_name,
    }


def _format_pillar_line(label: str, stem: str, branch: str, day_stem: str) -> str:
    hidden_stems = "、".join(BRANCH_HIDDEN_STEMS.get(branch, [])) or "无"
    return (
        f"{label}：{stem}{branch}；"
        f"纳音：{get_nayin(stem, branch)}；"
        f"十神：{get_ten_god(day_stem, stem).value}；"
        f"藏干：{hidden_stems}"
    )


def _format_origin_line(origin: Dict[str, Any]) -> str:
    hidden_stems = "、".join(origin.get("hidden_stems") or []) or "无"
    return (
        f"{origin['label']}：{origin['pillar']}；"
        f"纳音：{origin['nayin']}；"
        f"十神：{origin['ten_god']}；"
        f"藏干：{hidden_stems}"
    )


def _build_snapshot_text(
    *,
    person: PersonInfo,
    normalized_birth_datetime: datetime,
    input_birth_datetime: datetime,
    timezone_name: str,
    longitude: Optional[float],
    applied_true_solar: bool,
    calendar_context: Dict[str, Any],
    pillars: Dict[str, Tuple[str, str]],
    three_origins: Dict[str, Dict[str, Any]],
    shensha_entries: List[Dict[str, str]],
    timing_overview: Dict[str, Any],
    classical_overview: Dict[str, Any],
    analysis_calendar_context: Optional[Dict[str, Any]] = None,
) -> str:
    include_minutes = (
        person.birth_minute != 0
        or applied_true_solar
        or input_birth_datetime.minute != 0
        or normalized_birth_datetime.minute != 0
    )
    day_stem = pillars["day"][0]
    lunar_calendar = calendar_context.get("lunar_calendar") or {}

    acc_solar_term = (
        (analysis_calendar_context or {}).get("current_solar_term", {}).get("name")
    )
    acc_next_term = (
        (analysis_calendar_context or {}).get("next_solar_term", {}).get("name")
    )

    birth_context_lines = [
        f"姓名：{person.name or '未提供'}",
        f"性别：{person.gender or '未知'}",
        f"出生时间：{format_birth_datetime_display(input_birth_datetime, include_minutes=include_minutes)}",
        f"校正时间：{format_birth_datetime_display(normalized_birth_datetime, include_minutes=True)}",
        f"出生地：{person.birth_place or '未提供'}",
        f"时区：{timezone_name}",
        f"经度：{longitude if longitude is not None else '未提供'}",
        f"时间算法：{'真太阳时' if applied_true_solar else '直接时间'}",
        f"农历：{lunar_calendar.get('display', '未知')}",
        f"出生节气：{calendar_context['current_solar_term']['name']}",
        f"出生后节气：{calendar_context['next_solar_term']['name']}",
    ]
    if acc_solar_term and acc_next_term:
        birth_context_lines.append(
            f"当下节气：{acc_solar_term}，后续节气：{acc_next_term}"
        )
    sections = [
        (
            "起盘信息",
            "\n".join(birth_context_lines).strip(),
        ),
        (
            "四柱与三元",
            "\n".join(
                [
                    _format_pillar_line("年柱", *pillars["year"], day_stem),
                    _format_pillar_line("月柱", *pillars["month"], day_stem),
                    _format_pillar_line("日柱", *pillars["day"], day_stem),
                    _format_pillar_line("时柱", *pillars["hour"], day_stem),
                    _format_origin_line(three_origins["taiyuan"]),
                    _format_origin_line(three_origins["minggong"]),
                    _format_origin_line(three_origins["shengong"]),
                ]
            ).strip(),
        ),
        (
            "格局调候",
            "\n".join(classical_snapshot_lines(classical_overview)).strip(),
        ),
        (
            "流年行运概略",
            "\n".join(
                [
                    f"分析日期：{timing_overview['analysis_date']}",
                    (
                        "当前大运："
                        f"{timing_overview['dayun']['pillar'] or '未进入稳定大运'}；"
                        f"{timing_overview['dayun']['summary']}"
                    ),
                    f"流年：{timing_overview['liunian']['pillar']}；{timing_overview['liunian']['summary']}",
                    (
                        f"流月：{timing_overview['liuyue']['pillar']}；"
                        f"节气窗口：{timing_overview['liuyue']['start_term']}→{timing_overview['liuyue']['end_term']}；"
                        f"{timing_overview['liuyue']['summary']}"
                    ),
                    (
                        f"流日：{timing_overview['liuri']['pillar']}；"
                        f"星期：{timing_overview['liuri']['weekday']}；"
                        f"{timing_overview['liuri']['summary']}"
                    ),
                    (
                        f"流时：{timing_overview['liushi']['pillar']}；"
                        f"{timing_overview['liushi']['hour']}时 / "
                        f"{timing_overview['liushi']['shichen']}时；"
                        f"{timing_overview['liushi']['summary']}"
                    ),
                    f"当下节气：{timing_overview['current_solar_term_name']}（月令：{timing_overview['current_jieqi']}）",
                    f"后续节气：{timing_overview['next_solar_term_name']}（月令：{timing_overview['next_jieqi']}）",
                ]
            ).strip(),
        ),
        (
            "神煞（四柱与三元）",
            "\n".join(
                f"{item['label']}：{item['value']}" for item in shensha_entries
            ).strip(),
        ),
    ]

    blocks: List[str] = []
    for title, body in sections:
        blocks.append(f"[{title}]")
        if body:
            blocks.append(body)
        blocks.append("")
    return "\n".join(blocks).strip()


def _build_base_bazi_payload(
    *,
    person: PersonInfo,
    analysis_date: datetime,
) -> Dict[str, Any]:
    birth_context = build_birth_computation_context(person)
    normalized_birth_time = birth_context.normalized_birth_time
    input_birth_datetime = normalized_birth_time.input_datetime
    normalized_birth_datetime = normalized_birth_time.corrected_datetime
    base_analysis = build_destiny_payload(birth_context)
    three_origins = _build_three_origins(birth_context.birth_pillars)
    shensha_entries = _build_shensha_entries(
        pillars=birth_context.birth_pillars,
        three_origins=three_origins,
    )
    classical_overview = build_classical_overview(birth_context.birth_pillars)
    timezone_name = normalized_birth_time.timezone
    analysis_pillars = birth_context.birth_pillars
    analysis_calendar_context = build_calendar_context(
        analysis_date,
        timezone_name=timezone_name,
        pillars=analysis_pillars,
    )
    timing_overview = _build_timing_overview(
        birth_context=birth_context,
        analysis_date=analysis_date,
        analysis_calendar_context=analysis_calendar_context,
    )
    snapshot_text = _build_snapshot_text(
        person=person,
        normalized_birth_datetime=normalized_birth_datetime,
        input_birth_datetime=input_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        longitude=normalized_birth_time.longitude,
        applied_true_solar=normalized_birth_time.applied,
        calendar_context=birth_context.birth_calendar_context,
        pillars=birth_context.birth_pillars,
        three_origins=three_origins,
        shensha_entries=shensha_entries,
        timing_overview=timing_overview,
        classical_overview=classical_overview,
        analysis_calendar_context=analysis_calendar_context,
    )
    return {
        "input_birth_datetime": input_birth_datetime,
        "normalized_birth_datetime": normalized_birth_datetime,
        "normalized_birth_time": normalized_birth_time,
        "calendar_context": birth_context.birth_calendar_context,
        "analysis_calendar_context": analysis_calendar_context,
        "base_analysis": base_analysis,
        "three_origins": three_origins,
        "shensha_entries": shensha_entries,
        "classical_overview": classical_overview,
        "timing_overview": timing_overview,
        "snapshot_text": snapshot_text,
    }


@calculation_guard("八字命盘")
def calculate_bazi_birth(
    person: PersonInfo,
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    analysis_date = _resolve_analysis_date(analysis_year, analysis_month, analysis_day)
    payload = _build_base_bazi_payload(person=person, analysis_date=analysis_date)
    base_analysis = payload["base_analysis"]
    snapshot_text = payload["snapshot_text"]
    snapshot_export = parse_export_content(
        technique="bazi",
        content=snapshot_text,
        selected_sections=selected_sections,
    )

    return {
        "analysis_type": "八字命盘",
        "bazi_birth": {
            "engine": "fatebridge-offline",
            "time_algorithm": (
                "真太阳时" if payload["normalized_birth_time"].applied else "直接时间"
            ),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "person_info": base_analysis["person_info"],
            "four_pillars": base_analysis["four_pillars"],
            "three_origins": payload["three_origins"],
            "day_master": base_analysis["day_master"],
            "element_distribution": base_analysis["element_distribution"],
            "favorable_elements": base_analysis["favorable_elements"],
            "structure_profile": base_analysis["structure_profile"],
            "ten_gods": base_analysis["ten_gods"],
            "patterns": base_analysis["patterns"],
            "calendar_context": base_analysis["calendar_context"],
            "analysis_calendar_context": payload["analysis_calendar_context"],
            "timing_overview": payload["timing_overview"],
            "shensha": payload["shensha_entries"],
            "classical": payload["classical_overview"],
        },
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


# =============================================================================
# 八字专项分析服务（财运 / 健康 / 子女 / 学业）
#
# 每个服务从出生信息构建四柱，调用对应分析模块，返回统一结构：
#   {"analysis_type": ..., "<dim>_analysis": {...}}
# 同时支撑 FastAPI 端点与 FastMCP 工具，避免重复构盘逻辑。
# =============================================================================


def _parse_pillar_str(
    pillar_str: Optional[str], field_name: str = "pillar"
) -> Optional[Tuple[str, str]]:
    """Only absent overrides default; explicit invalid pillars are rejected."""
    if pillar_str is None:
        return None
    if not isinstance(pillar_str, str) or pillar_str not in SEXAGENARY_INDEX:
        raise ParameterError(
            "覆盖柱必须为六十甲子中的完整两字干支",
            [{"path": field_name, "code": "invalid_sexagenary_pillar"}],
        )
    return (pillar_str[0], pillar_str[1])


def _derive_current_pillars(
    birth_context: BirthComputationContext,
    analysis_date: datetime,
) -> Tuple[Optional[Tuple[str, str]], Optional[Tuple[str, str]], Dict[str, Any]]:
    """从命盘 + 分析日期内部推算当前大运、流年柱（用户无需自己知道大运）。"""
    state = build_current_timing_state(birth_context, analysis_date=analysis_date)
    dayun_result = state.get("dayun_analysis", {}) or {}
    liunian_result = state.get("liunian_analysis", {}) or {}
    dayun_pillar_str = (dayun_result.get("dayun_info") or {}).get("pillar")
    liunian_pillar_str = (liunian_result.get("liunian_info") or {}).get("pillar")
    timezone_name = birth_context.normalized_birth_time.timezone
    anchor = localize_datetime(analysis_date, timezone_name)
    # Date-only dimension APIs retain their historical midnight anchor. Expose
    # the boundary rather than treating an arbitrary clock time as equivalent.
    year_boundaries = [
        term
        for term in get_solar_terms_for_year(anchor.year, timezone_name)
        if term.name == "立春" and term.moment.date() == anchor.date()
    ]
    context = {
        "analysis_date": analysis_date.strftime("%Y-%m-%d"),
        "analysis_datetime": anchor.isoformat(),
        "timezone": timezone_name,
        "input_granularity": "date",
        "anchor_policy": "local_midnight",
        "year_boundary_policy": "lichun_exact_moment",
        "boundary_status": (
            "year_boundary_day" if year_boundaries else "not_year_boundary_day"
        ),
        "boundaries_on_date": [term.as_dict() for term in year_boundaries],
        "boundary_scope": "只核验流年立春年界，不代表已扫描大运或全年时段边界。",
        "hourly_evidence": {
            "tool": "timing_analysis",
            "fields": ["personal_info.analysis_datetime", "liunian_analysis"],
            "when": "问题涉及交节当日钟时或跨工具时点比较时，按实际目标analysis_hour/minute补证；不把本零点锚点当作全天结果。",
        },
        "dayun_pillar": dayun_pillar_str,
        "liunian_pillar": liunian_pillar_str,
        "dayun_age": (dayun_result.get("age_info") or {}).get("dayun_age"),
        "source": "auto-derived",
    }
    return (
        _parse_pillar_str(dayun_pillar_str),
        _parse_pillar_str(liunian_pillar_str),
        context,
    )


def _run_bazi_dimension_analysis(
    person: PersonInfo,
    *,
    analyzer: Callable[..., Dict[str, Any]],
    analysis_type: str,
    result_key: str,
    error_label: str,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    dayun_pillar: Optional[str] = None,
    liunian_pillar: Optional[str] = None,
) -> Dict[str, Any]:
    """通用八字专项分析执行器。

    大运、流年默认由命盘 + 分析日期（默认今天，或 analysis_year/month/day）内部推算，
    用户无需自己知道大运；如显式传入 dayun_pillar / liunian_pillar 则作为覆盖。
    """
    try:
        # Validate explicit overrides before any birth/timing work. A typo must
        # not silently turn into an automatically calculated pillar.
        dayun = _parse_pillar_str(dayun_pillar, "dayun_pillar")
        liunian = _parse_pillar_str(liunian_pillar, "liunian_pillar")
        birth_context = build_birth_computation_context(person)
        pillars = birth_context.birth_pillars

        timing_context: Optional[Dict[str, Any]] = None
        if dayun is None or liunian is None:
            analysis_date = _resolve_analysis_date(
                analysis_year,
                analysis_month,
                analysis_day,
                timezone_name=birth_context.normalized_birth_time.timezone,
            )
            auto_dayun, auto_liunian, timing_context = _derive_current_pillars(
                birth_context, analysis_date
            )
            timing_context["overridden"] = {
                "dayun_pillar": dayun is not None,
                "liunian_pillar": liunian is not None,
            }
            if dayun is None:
                dayun = auto_dayun
            if liunian is None:
                liunian = auto_liunian
            timing_context["dayun_pillar"] = "".join(dayun) if dayun else None
            timing_context["liunian_pillar"] = "".join(liunian) if liunian else None
            if timing_context["overridden"]["dayun_pillar"]:
                # Keep the published fractional-year reference projectable,
                # without presenting it as the age of the override pillar.
                timing_context["dayun_age_basis"] = (
                    "auto_derived_reference_not_override_pillar_age"
                )
        else:
            # Explicit pillars still have a provenance contract. They do not
            # have an automatically derived age/date; do not invent those.
            timing_context = {
                "dayun_pillar": "".join(dayun),
                "liunian_pillar": "".join(liunian),
                "source": "explicit_pillar_overrides",
                "overridden": {"dayun_pillar": True, "liunian_pillar": True},
            }

        analysis = analyzer(
            pillars,
            gender=person.gender,
            dayun_pillar=dayun,
            liunian_pillar=liunian,
        )
        if isinstance(analysis, dict) and timing_context is not None:
            analysis = {**analysis, "timing_context": timing_context}
        snapshot_text = render_structured_snapshot_text(analysis, title=analysis_type)
        snapshot_export = parse_export_content(
            technique="generic", content=snapshot_text
        )
        return {
            "analysis_type": analysis_type,
            result_key: analysis,
            "snapshot_text": snapshot_text,
            "snapshot_export": snapshot_export,
        }
    except ParameterError as exc:
        return exc.as_result()
    except Exception as exc:
        return handle_calculation_error(exc, error_label)


def _make_bazi_dimension_service(
    *,
    analyzer: Callable[..., Dict[str, Any]],
    analysis_type: str,
    result_key: str,
    doc: str,
) -> Callable[..., Dict[str, Any]]:
    """生成一个八字专项分析服务。

    九个维度（婚姻/事业/财运/健康/子女/学业/性格/六亲/桃花）此前各自重复同一段透传
    外壳，仅 analyzer / analysis_type / result_key / 文档串不同。这里统一生成，签名与
    返回结构与逐个手写的版本完全一致；error_label 在所有九个维度均等于 analysis_type。
    """

    def service(
        person: PersonInfo,
        *,
        analysis_year: Optional[int] = None,
        analysis_month: Optional[int] = None,
        analysis_day: Optional[int] = None,
        dayun_pillar: Optional[str] = None,
        liunian_pillar: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _run_bazi_dimension_analysis(
            person,
            analyzer=analyzer,
            analysis_type=analysis_type,
            result_key=result_key,
            error_label=analysis_type,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
            dayun_pillar=dayun_pillar,
            liunian_pillar=liunian_pillar,
        )

    service.__doc__ = doc
    return service


calculate_bazi_marriage = _make_bazi_dimension_service(
    analyzer=MarriageAnalysis.analyze_marriage,
    analysis_type="八字婚姻分析",
    result_key="marriage_analysis",
    doc="八字婚姻分析：配偶星、配偶宫、婚姻质量、婚期与婚姻风险。",
)

calculate_bazi_career = _make_bazi_dimension_service(
    analyzer=CareerAnalysis.analyze_career,
    analysis_type="八字事业分析",
    result_key="career_analysis",
    doc="八字事业分析：适合行业、事业格局、创业倾向与事业时机。",
)

calculate_bazi_wealth = _make_bazi_dimension_service(
    analyzer=WealthAnalysis.analyze_wealth,
    analysis_type="八字财运分析",
    result_key="wealth_analysis",
    doc="八字财运分析：财星定位、财富格局、墓库财、求财方式与财运时机。",
)

calculate_bazi_health = _make_bazi_dimension_service(
    analyzer=HealthAnalysis.analyze_health,
    analysis_type="八字健康分析",
    result_key="health_analysis",
    doc="八字健康分析：体质、脏腑强弱、易患疾病与健康风险时机。",
)

calculate_bazi_children = _make_bazi_dimension_service(
    analyzer=ChildrenAnalysis.analyze_children,
    analysis_type="八字子女分析",
    result_key="children_analysis",
    doc="八字子女分析：子女星、子女宫、缘分厚薄与生育时机。",
)

calculate_bazi_education = _make_bazi_dimension_service(
    analyzer=EducationAnalysis.analyze_education,
    analysis_type="八字学业分析",
    result_key="education_analysis",
    doc="八字学业分析：印星食伤、学历层次、文昌、学科方向与考试时机。",
)

calculate_bazi_personality = _make_bazi_dimension_service(
    analyzer=PersonalityAnalysis.analyze_personality,
    analysis_type="八字性格分析",
    result_key="personality_analysis",
    doc="八字性格分析：日主心性、主导十神、刚柔内外向与优劣势。",
)

calculate_bazi_relatives = _make_bazi_dimension_service(
    analyzer=RelativesAnalysis.analyze_relatives,
    analysis_type="八字六亲分析",
    result_key="relatives_analysis",
    doc="八字六亲分析：父母星、兄弟姐妹星、六亲宫位与贵人助力。",
)

calculate_bazi_romance = _make_bazi_dimension_service(
    analyzer=RomanceAnalysis.analyze_romance,
    analysis_type="八字正缘桃花分析",
    result_key="romance_analysis",
    doc="八字正缘桃花分析：桃花咸池、红鸾天喜、异性缘星与正缘时机。",
)
