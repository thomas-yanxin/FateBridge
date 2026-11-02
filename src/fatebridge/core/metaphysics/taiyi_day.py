"""The Key's daily count, using explicit modern dates and midnight boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fatebridge.core.almanac import (
    get_day_ganzhi,
    localize_datetime,
)
from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES, SOURCES

from .common import SEXAGENARY_INDEX, MetaphysicsSeed
from .taiyi_clock import validate_seed_civil_clock
from .taiyi_hour import KEY_SOURCE
from .taiyi_origin_selection import winter_origin_selection
from .taiyi_periods import SOLAR_ANCHOR_SCOPE, _clock, _previous_term
from .taiyi_ten_jing import attach_ten_jing
from .taiyi_year import assemble_board, calendar_summary, cyclic_core

KEY_DAY_PROFILE = "key_day_winter_jiazi_v1"


def key_day_origin(winter_clock: datetime, target_clock: datetime) -> dict[str, Any]:
    if winter_clock.tzinfo is not None or target_clock.tzinfo is not None:
        raise ValueError("日计须先确定所选钟面，再传无时区钟面")
    winter_day = winter_clock.date()
    winter_ganzhi = get_day_ganzhi(winter_day.year, winter_day.month, winter_day.day)
    origin_ordinal = winter_day.toordinal() - SEXAGENARY_INDEX[winter_ganzhi]
    if origin_ordinal < 1:
        raise ValueError("冬至前甲子超出可表达日历范围")
    origin = datetime.fromordinal(origin_ordinal)
    target = target_clock.date()
    count = target.toordinal() - origin_ordinal + 1
    if count < 1:
        raise ValueError("日计日期早于冬至前甲子")
    return {
        "source": KEY_SOURCE,
        "winter_clock": winter_clock.isoformat(),
        "winter_day_ganzhi": winter_ganzhi,
        "origin_effective_date": origin.date().isoformat(),
        "target_effective_date": target.isoformat(),
        "target_day_ganzhi": get_day_ganzhi(target.year, target.month, target.day),
        "accumulation": count,
        "day_boundary": "00:00_selected_clock_modern_convention",
        "same_day_jiazi_included": True,
        "same_day_selection_adjudicated": False,
        "alternative_strict_previous_count": (
            count + 60 if winter_ganzhi == "甲子" else None
        ),
        "scope": "取冬至所属日或此前甲子日；同日纳入与零时日界均为明示现代约定。日计差60日会改变72局相位，不套用时计720时相位不变的结论。",
    }


def key_day_numeric_board(count: int, ruler: str, yin: bool) -> dict[str, Any]:
    """The same numeric chain used by the date adapter and source audit."""
    from .taiyi_gates import attach_gate_board

    core = cyclic_core(count, yin=yin)
    if ruler != BRANCHES[(count - 1) % 12]:
        raise ValueError("从甲子起计的积日与所给日支不一致")
    core.update(
        ruler_branch=ruler,
        ruler_label="日支",
        heshen=BRANCHES[(1 - BRANCHES.index(ruler)) % 12],
    )
    board = assemble_board(core, calculation_mode="day")
    board.update(
        rotation="逆布" if yin else "顺布",
        calendar_rules={
            "calculation_mode": "day",
            "day_profile": KEY_DAY_PROFILE,
            "counter": count,
            "palace_day_number": (count - 1) % 3 + 1,
        },
    )
    attach_gate_board(board, "day")
    attach_ten_jing(board)
    board["day_source_comparisons"] = []
    if not yin and (count - 44) % 72 == 0:
        board["day_source_comparisons"] = [
            {
                "field": "main_count",
                "source_value": 32,
                "rule_derived_value": core["main_count"],
                "scope": "图43课式，正文图40作33；阳局相位参照；是否匹配原例日期另见calendar_rules.historical_date_reference，完整古历时实未复原。",
                "source": KEY_SOURCE,
            },
            {
                "field": "heshen",
                "source_value": "艮",
                "rule_derived_value": core["heshen"],
                "scope": "图43课式写三宫，正文图41以日支未合午；同相位参照，历史日期对照另列。",
                "source": KEY_SOURCE,
            },
        ]
    return board


def build_key_day_board(seed: MetaphysicsSeed, gender: str) -> dict[str, Any]:
    from .taiyi_historical import source_date_reference

    instant = localize_datetime(seed.input_datetime, seed.timezone)
    validate_seed_civil_clock(seed)
    anchor = _previous_term(instant, ("冬至", "夏至"))
    winter = _previous_term(instant, ("冬至",))
    target_clock = _clock(instant, seed)
    origin = key_day_origin(_clock(winter.moment, seed), target_clock)
    origin.update(
        winter_anchor_utc=winter.moment.astimezone(timezone.utc).isoformat(),
        winter_anchor_provider=winter.resolution_provider,
    )
    count = origin["accumulation"]
    ruler = origin["target_day_ganzhi"][1]
    board = key_day_numeric_board(count, ruler, anchor.name == "夏至")
    board.update(
        style_label="太乙金钥匙续集·日计现代日期适配",
        accumulation_label=f"日计冬至前甲子积日：{count}",
        rotation="逆布" if anchor.name == "夏至" else "顺布",
        life_method="金钥匙日计（性别不参与定局）",
        solar_anchors={
            "boundary": anchor.as_dict(),
            "winter_origin": winter.as_dict(),
        },
        solar_anchor_scope=SOLAR_ANCHOR_SCOPE,
        calendar_rules={
            "input_calendar": "proleptic_gregorian",
            "calculation_mode": "day",
            "day_profile": KEY_DAY_PROFILE,
            "day_origin": origin,
            "civil_datetime": instant.isoformat(),
            "timezone": seed.timezone,
            "anchor_name": anchor.name,
            "anchor_utc": anchor.moment.astimezone(timezone.utc).isoformat(),
            "anchor_provider": anchor.resolution_provider,
            "counter": count,
            "palace_day_number": (count - 1) % 3 + 1,
            "clock_basis": (
                "local_apparent_solar"
                if seed.applied_true_solar
                else "civil_wall_clock"
            ),
            "target_clock": target_clock.isoformat(),
            "boundary_instant_basis": "civil_utc_instant",
            "ruler_branch_basis": "selected_clock_midnight_day_ganzhi",
            "heshen_branch_basis": "selected_clock_midnight_day_ganzhi",
            "pillars_role": "共用四柱依其原有边界；本日计日支独立取day_origin所示零时所属日，不把共用日柱代换入本盘。",
            "counter_rule_source": KEY_SOURCE,
            "counter_formula": "target_selected_date_ordinal - winter_previous_Jiazi_date_ordinal + 1",
            "modern_conventions": "现代定气实刻换遁，所选钟面零时换日；同日甲子纳入起点，非完整古历复原，日数不乘十二。",
        },
        ruleset={
            "id": KEY_DAY_PROFILE,
            "version": "1.1.0",
            "author": "FateBridge contributors",
            "classical_author": "《太乙金钥匙续集》底本题署，作者未独立考定",
            "source_title": "太乙金钥匙续集·日计（NLC892-411999021066-66022）",
            "source_kind": "facsimile_with_explicit_modern_calendar_adapter",
            "sources": {
                "key": KEY_SOURCE,
                "shared_count_rules": SOURCES["2"],
                "shared_relation_rules": SOURCES["3"],
            },
            "time_granularity": "selected_clock_day",
            "classical_conformance": "partial_with_source_and_calendar_questions",
            "classical_acceptance_passed": False,
            "real_world_efficacy": "not_tested",
            "unresolved": [
                "零时/同日甲子是现代约定；选定课例日期另有独立历表对照，完整古历未复原。",
                "图43主算32、合神三宫与正文33、午不合，双方保留。",
                "十精天时采十二支通则并有年度补证，日例坤宫仍不符；八风异数、太乙数宫位语义未决，阴局中五不强作对冲。",
                "计神按前文明列阴局起申；末段阴阳差异概括未提计神，仍待完整阴局古例。",
                "三门主体、完整断法及夏至完整古例待验收；空间关系与五将条件另标金镜来源。",
            ],
        },
        interpretation_scope={
            "calculation": "日数、阴阳局、二目主客与定计、直门及分源十精",
            "traditional_interpretation": "只解释实际规则事实和未决范围，不生成未实现的事件或天气断语",
            "gender_used": False,
            "real_world_prediction": "不返回事件概率或权威认证",
        },
        long_cycles={
            "status": "not_computed_for_selected_mode",
            "time_granularity": "year",
            "reason": "金镜年度十神不作为金钥匙日计十精。",
        },
        long_cycle_summary={"status": "not_computed_for_selected_mode"},
        extra_palace_marks=[],
    )
    reference = source_date_reference(
        target_clock.date(), "day", count, origin["target_day_ganzhi"]
    )
    if reference:
        board["calendar_rules"]["historical_date_reference"] = reference
    board["calendar_summary"] = calendar_summary(board)
    board["winter_origin_selection"] = winter_origin_selection(
        origin,
        board["solar_anchors"]["winter_origin"],
        board["calendar_rules"]["clock_basis"],
    )
    return board
