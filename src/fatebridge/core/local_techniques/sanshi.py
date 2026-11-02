"""
San Shi United (三式合一：奇门 + 太乙 + 六壬/金口 综合) board.

Pure relocation from the package facade.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fatebridge.core.almanac import DAY_GANZHI_STRATEGY_STANDARD
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.sanshi_correspondences import (
    correspondence_text,
    palace_correspondences,
)
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_dangshi import (
    noble_source_assessment,
    noble_source_text,
)
from fatebridge.core.metaphysics.taiyi_long_cycles import long_cycle_text
from fatebridge.core.metaphysics.taiyi_year import evidence_text
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE

from .chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _build_qimen_palace_overview_lines,
    _join_lines,
    _normalize_date_text,
    _normalize_time_text,
    _render_qimen_palace_sections,
    _render_snapshot_text,
)
from .qimen import (
    _qimen_stem_context_lines,
    _render_qimen_pattern_line,
    _render_qimen_source_disagreements,
    build_qimen_with_options,
)


def _build_taiyi_with_options(
    seed: MetaphysicsSeed, options: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    normalized = dict(options or {})
    unknown = set(normalized) - {
        "accNum",
        "acc_num",
        "rotation",
        "calculation_mode",
        "hour_profile",
        "month_profile",
        "year_profile",
    }
    if unknown:
        raise ValueError("未实现的太乙选项：" + ", ".join(sorted(unknown)))
    for key in ("accNum", "acc_num"):
        if key in normalized and (
            type(normalized[key]) is not int or normalized[key] != 0
        ):
            raise ValueError(
                "太乙accNum任意积数偏移没有原典算法依据；仅支持0，请用实际日期起盘"
            )
    if "rotation" in normalized and (
        not isinstance(normalized["rotation"], str)
        or normalized["rotation"] not in {"顺布", "順布", "forward"}
    ):
        raise ValueError("太乙阴阳遁由所选计法及日期决定，rotation不能覆盖计算")
    mode = normalized.get("calculation_mode", "year")
    if not isinstance(mode, str) or mode not in {"year", "month", "day", "hour"}:
        raise ValueError("太乙calculation_mode仅支持year、month、day、hour")
    if mode in {"day", "hour"} and "rotation" in normalized:
        raise ValueError("太乙日/时计阴阳遁由至点决定，不接受rotation覆盖")
    profile = normalized.get("hour_profile")
    if "hour_profile" in normalized and not isinstance(profile, str):
        raise ValueError("hour_profile必须是已发布时计配置名称")
    month_profile = normalized.get("month_profile")
    if "month_profile" in normalized and not isinstance(month_profile, str):
        raise ValueError("month_profile必须是已发布月计配置名称")
    year_profile = normalized.get("year_profile")
    if "year_profile" in normalized and not isinstance(year_profile, str):
        raise ValueError("year_profile必须是已发布年计配置名称")
    return build_taiyi_board(
        seed,
        gender="未知",
        calculation_mode=mode,
        hour_profile=profile,
        month_profile=month_profile,
        year_profile=year_profile,
    )


def _source_profiles(qimen: Dict[str, Any], liureng: Dict[str, Any]) -> Dict[str, Any]:
    """Keep source identities in a first view without copying whole audits."""
    result: Dict[str, Any] = {"qimen": [], "liureng": []}
    raw = [("qimen", f"qimen.rulesets.{i}", r) for i, r in enumerate(qimen["rulesets"])]
    raw.append(("liureng", "liureng.ruleset", liureng["ruleset"]))
    for technique, path, ruleset in raw:
        profile = {
            key: ruleset[key]
            for key in (
                "id",
                "version",
                "author",
                "classical_author",
                "source",
                "source_urls",
                "classical_conformance",
                "classical_acceptance_passed",
                "real_world_efficacy",
            )
            if key in ruleset
        }
        profile.update(
            source_path=path,
            source_title=ruleset.get("source_title", ruleset.get("title", "")),
            unresolved_count=len(ruleset.get("unresolved", [])),
        )
        result[technique].append(profile)
    return result


def _build_sanshi_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    qimen_seed: Optional[MetaphysicsSeed],
    qimen: Dict[str, Any],
    taiyi: Dict[str, Any],
    liureng: Dict[str, Any],
    correspondences: Dict[str, Any],
    noble_assessment: Dict[str, Any],
) -> str:
    qimen_display_seed = qimen_seed or seed
    palace_lines = _build_qimen_palace_overview_lines(qimen)
    taiyi_mark_lines = [
        f"{item.get('palace', '宫位')}：{'、'.join(item.get('markers', []) or []) or '无'}"
        for item in taiyi.get("palace_marks", []) or []
        if isinstance(item, dict)
    ]
    liureng_four_lesson_lines = [
        f"第{lesson.get('index', 0)}课：{lesson.get('text', '无')}（{lesson.get('relation', '无')}）"
        for lesson in liureng.get("four_lessons", []) or []
        if isinstance(lesson, dict)
    ]
    liureng_transmission_lines = []
    transmissions = (
        liureng.get("three_transmissions", {}) if isinstance(liureng, dict) else {}
    )
    for label, title in (("initial", "初传"), ("middle", "中传"), ("final", "末传")):
        item = transmissions.get(label, {}) if isinstance(transmissions, dict) else {}
        liureng_transmission_lines.append(
            f"{title}：{item.get('branch', '无')} / {item.get('relation', '无')} / {item.get('god', '无')}"
        )
    big_pattern = next(
        (item for item in liureng.get("patterns", []) or [] if isinstance(item, dict)),
        {},
    )
    month_general = (
        liureng.get("month_general", {}) if isinstance(liureng, dict) else {}
    )
    sections = [
        (
            "起盘信息",
            _join_lines(
                [
                    (
                        "时间上下文农历：未扩展；太乙历史历表日期见太乙规则依据（仅太乙年计使用）。"
                        if (taiyi.get("calendar_rules") or {}).get(
                            "historical_calendar"
                        )
                        else f"时间上下文农历：{(seed.calendar_context.get('lunar_calendar') or {}).get('display') or '未提供'}（父级钟面上下文，太乙年计日期见太乙规则依据）"
                    ),
                    f"奇门输入钟时：{qimen_display_seed.input_datetime.isoformat()}；时区：{qimen_display_seed.timezone}",
                    f"奇门计算钟面：{qimen_display_seed.calendar_context['solar_datetime']}",
                    f"四柱：{qimen_display_seed.pillars['year'][0]}{qimen_display_seed.pillars['year'][1]}年/{qimen_display_seed.pillars['month'][0]}{qimen_display_seed.pillars['month'][1]}月/{qimen_display_seed.pillars['day'][0]}{qimen_display_seed.pillars['day'][1]}日/{qimen_display_seed.pillars['hour'][0]}{qimen_display_seed.pillars['hour'][1]}时",
                    (
                        "时间算法：真太阳时 + 本地节气换月"
                        if qimen_display_seed.applied_true_solar
                        else "时间算法：直接时间 + 本地节气换月"
                    ),
                    "换日：按各子盘注明的实际口径",
                    f"月将：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"年命：{seed.pillars['year'][1]}",
                ]
            ),
        ),
        (
            "概览",
            _join_lines(
                [
                    f"盘型：{qimen.get('dun_type', '无')}{qimen.get('ju_number', '无')}局",
                    f"旬首：{qimen.get('xun_head', '无')}",
                    f"空亡：{qimen.get('kongwang', '无')}",
                    f"值符：{(qimen.get('zhifu') or {}).get('star', '无')}在{(qimen.get('zhifu') or {}).get('palace', '无')}",
                    f"值使：{(qimen.get('zhishi') or {}).get('door', '无')}在{(qimen.get('zhishi') or {}).get('palace', '无')}",
                    f"八神口径：{qimen['rule_profiles']['god']['title']}（{qimen['god_profile']}）",
                    f"九星旺衰口径：{qimen['rule_profiles']['season']['title']}（{qimen['season_profile']}）",
                    *_qimen_stem_context_lines(qimen),
                    f"伏使卦：{(qimen.get('fushi_hexagram') or {}).get('name', '无')}",
                    "奇门格局按条件读取；下列结构不等于现实成败判断：",
                    *_render_qimen_source_disagreements(qimen),
                    *[_render_qimen_pattern_line(p) for p in qimen.get("patterns", [])],
                ]
            ),
        ),
        (
            "太乙",
            _join_lines(
                [
                    taiyi.get("style_label", "无"),
                    taiyi.get("accumulation_label", "无"),
                    taiyi.get("rotation", "无"),
                    taiyi.get("life_method", "无"),
                    taiyi.get("big_pattern", ""),
                    taiyi.get("small_pattern", ""),
                    (taiyi.get("core_board") or {}).get("main_calculation", "无"),
                    (taiyi.get("core_board") or {}).get("taiyi_position", "无"),
                    (taiyi.get("core_board") or {}).get("wenchang_position", "无"),
                    f"{taiyi['core_board'].get('ruler_label', '岁君')}：{taiyi['core_board'].get('ruler_branch', taiyi['core_board'].get('suijun', '无'))}",
                    f"合神：{(taiyi.get('core_board') or {}).get('heshen', '无')}",
                ]
            ),
        ),
        ("太乙十六宫", _join_lines(taiyi_mark_lines) or "无"),
        ("太乙中宫", "、".join(taiyi["center_marks"]["markers"]) or "无星标"),
        ("太乙规则依据", evidence_text(taiyi)),
        ("太乙年运十神", long_cycle_text(taiyi.get("long_cycles"))),
        ("三式宫位对应", correspondence_text(correspondences)),
        ("三式贵人来源对照", noble_source_text(noble_assessment)),
        (
            "合参范围",
            f"太乙采用{taiyi['life_method']}；奇门、六壬为本次时刻盘。尚未完成共同事件的全套合参断法，不能合成胜率或把三式视为三份独立证据。",
        ),
        (
            "神煞",
            _join_lines(
                [
                    f"月将：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"布盘：{liureng.get('board_order', '无')}",
                    f"课体：{liureng.get('board_style', '无')}",
                    f"旬首：{liureng.get('xun_head', '无')}",
                    f"空亡：{liureng.get('kongwang', '无')}",
                    f"贵人体系：{liureng.get('guiren_system', '无')}",
                ]
            ),
        ),
        ("大六壬", _join_lines(liureng_four_lesson_lines) or "无"),
        (
            "六壬大格",
            _join_lines(
                [
                    big_pattern.get("name", "无"),
                    f"依据：{big_pattern.get('basis', '无')}",
                ]
            ),
        ),
        ("六壬小局", _join_lines(liureng_transmission_lines) or "无"),
        ("六壬参考", _join_lines(liureng.get("overview", [])) or "无"),
        ("六壬概览", _join_lines(liureng.get("overview", [])) or "无"),
        ("八宫详解", _join_lines(palace_lines) or "无"),
        *_render_qimen_palace_sections(qimen),
    ]
    return _render_snapshot_text(sections)


def build_sanshiunited_result(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    qimen_options: Optional[Dict[str, Any]] = None,
    taiyi_options: Optional[Dict[str, Any]] = None,
    liureng_yue: Optional[str] = None,
    liureng_is_diurnal: Optional[bool] = None,
    liureng_guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
    use_true_solar_time: bool = False,
) -> Dict[str, Any]:
    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time),
        "zone": zone or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "qimen_options": qimen_options or {},
        "taiyi_options": taiyi_options or {},
        "liureng_yue": liureng_yue,
        "liureng_is_diurnal": liureng_is_diurnal,
        "liureng_guiren_profile": liureng_guiren_profile,
        "use_true_solar_time": bool(use_true_solar_time),
    }
    seed = _build_metaphysics_seed(
        date_text=input_normalized["date"],
        time_text=input_normalized["time"],
        timezone_name=input_normalized["zone"],
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        use_true_solar_time=bool(use_true_solar_time),
    )
    qimen_seed = _build_metaphysics_seed(
        date_text=input_normalized["date"],
        time_text=input_normalized["time"],
        timezone_name=input_normalized["zone"],
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        use_true_solar_time=bool(use_true_solar_time),
        day_pillar_strategy=DAY_GANZHI_STRATEGY_STANDARD,
    )
    qimen = build_qimen_with_options(qimen_seed, qimen_options)
    taiyi = _build_taiyi_with_options(seed, taiyi_options)
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, month_general_override=liureng_yue
    )
    liureng = build_liureng_board(
        seed,
        gender="未知",
        month_general_override=liureng_yue,
        is_diurnal_override=liureng_is_diurnal,
        guiren_profile=liureng_guiren_profile,
    )

    correspondences = palace_correspondences(taiyi, qimen, liureng)
    noble_assessment = noble_source_assessment(
        seed.pillars["day"][0],
        liureng,
        taiyi_mode=taiyi["calendar_summary"]["calculation_mode"],
    )
    snapshot_text = _build_sanshi_snapshot_text(
        seed=seed,
        qimen_seed=qimen_seed,
        qimen=qimen,
        taiyi=taiyi,
        liureng=liureng,
        correspondences=correspondences,
        noble_assessment=noble_assessment,
    )
    analysis_context = _build_metaphysics_analysis_context(seed)
    four_pillars = create_pillar_dict(seed.pillars)
    qimen_analysis_context = _build_metaphysics_analysis_context(qimen_seed)
    qimen_four_pillars = create_pillar_dict(qimen_seed.pillars)
    subresults = {
        "qimen": {
            "analysis_type": "奇门遁甲",
            "analysis_context": qimen_analysis_context,
            "four_pillars": qimen_four_pillars,
            "calendar_context": qimen_seed.calendar_context,
            "pan": qimen,
        },
        "taiyi": {
            "analysis_type": "太乙神数",
            "analysis_context": analysis_context,
            "four_pillars": four_pillars,
            "calendar_context": seed.calendar_context,
            "pan": taiyi,
        },
        "liureng_gods": {
            "analysis_type": "大六壬起课",
            "analysis_context": analysis_context,
            "four_pillars": four_pillars,
            "calendar_context": seed.calendar_context,
            "liureng": liureng,
        },
    }

    return {
        "analysis_type": "三式合一",
        "analysis_context": analysis_context,
        "input_normalized": input_normalized,
        "qimen": qimen,
        "taiyi": taiyi,
        "liureng": liureng,
        "subresults": subresults,
        "synthesis": {
            "source_profiles": _source_profiles(qimen, liureng),
            "method": "scoped_evidence_aggregation_v1",
            "status": "parallel_boards_without_validated_joint_prediction",
            "time_scopes": {
                "taiyi": taiyi["ruleset"]["time_granularity"],
                "qimen": "casting_time",
                "liureng": "casting_time",
            },
            "common_input": {
                "date": input_normalized["date"],
                "time": input_normalized["time"],
                "timezone": input_normalized["zone"],
            },
            "facts": [
                {
                    "technique": "taiyi",
                    "field": "taiyi.core_board.main_calculation",
                    "value": taiyi["core_board"]["main_calculation"],
                },
                {
                    "technique": "qimen",
                    "field": "qimen.ju_text",
                    "value": qimen["ju_text"],
                },
                {
                    "technique": "liureng",
                    "field": "liureng.patterns",
                    "value": liureng.get("patterns", []),
                },
            ],
            "palace_correspondences": correspondences,
            "noble_source_assessment": noble_assessment,
            "agreement": "not_assessed_without_shared_event_and_adjudication_rule",
            "independent_evidence_count": None,
            "real_world_efficacy": "not_tested",
            "limitations": [
                (
                    (
                        "共用民用输入；太乙年计另用所选齐梁史历表，502年闰标分歧保留；奇门/六壬仍用各自现代适配，未认证三式共同古历时刻，也不能假设统计独立。"
                        if (taiyi.get("calendar_rules") or {}).get("year_profile")
                        == "jinjing_year_qiliang_table_v1"
                        else "共用民用输入；太乙年计另用所选历史晋历表，奇门/六壬仍用各自现代适配，未认证三式共同古历时刻，也不能假设统计独立。"
                    )
                    if (taiyi.get("calendar_rules") or {}).get("historical_calendar")
                    else "各盘共用输入及历法，不能假设统计独立。"
                ),
                "各术原典符合度须独立验收；本次太乙规则修正不认证奇门或六壬。",
                "太乙各计法按实际时间层解释；时计至点和时辰边界采用已声明的现代时钟适配，不能外推分钟级事件应验。",
            ],
        },
        "sources": {
            "four_pillars": four_pillars,
            "calendar_context": seed.calendar_context,
        },
        "snapshot_text": snapshot_text,
        "summary": (
            f"已运行本地三式合一聚合算法。"
            f"奇门：{qimen['dun_type']}{qimen['ju_number']}局。"
            f"太乙：{(taiyi.get('core_board') or {}).get('main_calculation', '无')}。"
            f"六壬：{next((item.get('name') for item in liureng.get('patterns', []) if isinstance(item, dict)), '无')}。"
        ),
    }
