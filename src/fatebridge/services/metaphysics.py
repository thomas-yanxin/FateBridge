"""
Chinese metaphysics services for FateBridge.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fatebridge.core.almanac import (
    DAY_GANZHI_STRATEGY_STANDARD,
    GAN,
    build_calendar_context,
    get_lunar_context,
    localize_datetime,
)
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.local_techniques.qimen import (
    build_qimen_snapshot_text,
    build_qimen_with_options,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from fatebridge.core.metaphysics.jinkou_natal_course import (
    build_natal_course,
    natal_course_trace,
)
from fatebridge.core.metaphysics.jinkou_year_fate import (
    build_jinkou_year_fate,
    confirmed_natal_branch,
)
from fatebridge.core.metaphysics.liureng import (
    build_liureng_board,
    build_liureng_runyear,
)
from fatebridge.core.metaphysics.liureng_god_yin import add_year_fate_membership
from fatebridge.core.metaphysics.liureng_year_fate import build_year_fate
from fatebridge.core.metaphysics.ren_calendar import (
    require_ren_calendar,
    resolve_runyear_birth_clock,
    resolve_runyear_birth_zone,
)
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_clock import civil_clock_resolution
from fatebridge.core.metaphysics.taiyi_long_cycles import long_cycle_text
from fatebridge.core.metaphysics.taiyi_year import evidence_text as taiyi_evidence_text
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei_calendar import basis_text, calendar_basis, context_basis
from fatebridge.core.ziwei_rulesets import DEFAULT_ZIWEI_PROFILE
from fatebridge.core.ziwei_time_input import birth_clock_receipt
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    resolve_civil_clock,
    utc_instant,
)
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import (
    create_pillar_dict,
    format_birth_datetime_display,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    calculate_solar_time_adjustment,
    normalize_birth_time,
)
from fatebridge.utils.solar_time_provenance import solar_time_receipt


def _build_analysis_seed(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    utc_offset_field: str = "analysis_utc_offset",
    analysis_longitude: Optional[float] = None,
    # 紫微运限把「读盘日期」(流年/大限 calendar progression)交给本函数，且刻意不传
    # analysis_longitude，所以它的 use_true_solar_time 默认关。式占(奇门/六壬)则以
    # 起局时刻为盘，默认开（请求模型层）。无经度时按显式性区分：显式要求→报错，
    # 吃默认→降级为钟表时间（time_algorithm 字段透出「直接时间」即为提示）。
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = True,
    day_pillar_strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
) -> MetaphysicsSeed:
    timezone_name = analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    input_datetime = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
        analysis_second,
    )
    # Validate the physical civil instant in both clock modes. Apparent-solar
    # labels are not civil times and must not receive this DST gap/fold check.
    resolved_clock = resolve_civil_clock(
        input_datetime,
        timezone_name,
        analysis_utc_offset,
        offset_field=utc_offset_field,
    )
    if analysis_utc_offset is not None:
        input_datetime = resolved_clock
    corrected_datetime = input_datetime
    total_correction_minutes = 0.0
    applied_true_solar = use_true_solar_time
    solar_adjustment_evidence = None

    if use_true_solar_time and analysis_longitude is None:
        if true_solar_explicit:
            raise ValueError("真太阳时修正需要 analysis_longitude")
        # 默认开但无经度可用 → 降级为钟表时间（不报错）。
        applied_true_solar = False

    if applied_true_solar:
        # Invariant: the graceful branch above zeroes applied_true_solar whenever
        # analysis_longitude is None, so reaching here guarantees a longitude.
        assert analysis_longitude is not None
        adjustment = calculate_solar_time_adjustment(
            input_datetime,
            timezone_name,
            analysis_longitude,
            strategy=SOLAR_TIME_STRATEGY_APPARENT,
        )
        total_correction_minutes = adjustment["total_correction_minutes"]
        corrected_datetime = input_datetime.replace(tzinfo=None) + timedelta(
            minutes=total_correction_minutes
        )
        if analysis_utc_offset is not None:
            corrected_datetime = localize_datetime(corrected_datetime, timezone_name)
        solar_adjustment_evidence = solar_time_receipt(
            civil_instant=resolved_clock,
            corrected_label=corrected_datetime,
            timezone_name=timezone_name,
            longitude=analysis_longitude,
            adjustment=adjustment,
        )

    pillars = BaZiCalendar.get_four_pillars(
        corrected_datetime,
        timezone_name=timezone_name,
        day_pillar_strategy=day_pillar_strategy,
        civil_datetime=input_datetime,
    )
    calendar_context = build_calendar_context(
        corrected_datetime,
        timezone_name=timezone_name,
        pillars=pillars,
        civil_datetime=input_datetime,
    )
    return MetaphysicsSeed(
        input_datetime=input_datetime,
        corrected_datetime=corrected_datetime,
        timezone=timezone_name,
        longitude=analysis_longitude,
        applied_true_solar=applied_true_solar,
        total_correction_minutes=total_correction_minutes,
        pillars=pillars,
        calendar_context=calendar_context,
        solar_time_adjustment=solar_adjustment_evidence,
    )


def _build_person_seed(
    person: PersonInfo, *, birth_utc_offset: Optional[str] = None
) -> MetaphysicsSeed:
    # 紫微斗数命盘的真太阳时校正采用 APPARENT 口径（经度差 + 均时差），与八字
    # 引擎保持一致。此前用 LONGITUDE_ONLY（仅经度差、不含均时差），导致同一出生
    # 时间在八字与紫微下校正结果相差一个均时差量（最大约 ±16 分钟），跨体系合参
    # 时会在时辰边界附近落入不同的 hour pillar。真太阳时的严格定义本就含均时差。
    normalized_birth_time = normalize_birth_time(
        person,
        solar_time_strategy=SOLAR_TIME_STRATEGY_APPARENT,
        birth_utc_offset=birth_utc_offset,
    )
    corrected_datetime = normalized_birth_time.corrected_datetime
    pillars = BaZiCalendar.get_four_pillars(
        corrected_datetime,
        timezone_name=normalized_birth_time.timezone,
        day_pillar_strategy=DAY_GANZHI_STRATEGY_STANDARD,
        civil_datetime=normalized_birth_time.input_datetime,
    )
    calendar_context = build_calendar_context(
        corrected_datetime,
        timezone_name=normalized_birth_time.timezone,
        pillars=pillars,
        civil_datetime=normalized_birth_time.input_datetime,
    )
    return MetaphysicsSeed(
        input_datetime=normalized_birth_time.input_datetime,
        corrected_datetime=corrected_datetime,
        timezone=normalized_birth_time.timezone,
        longitude=normalized_birth_time.longitude,
        applied_true_solar=normalized_birth_time.applied,
        total_correction_minutes=normalized_birth_time.total_correction_minutes,
        pillars=pillars,
        calendar_context=calendar_context,
        birth_time_normalization=birth_clock_receipt(person, normalized_birth_time),
    )


def _analysis_context_payload(seed: MetaphysicsSeed) -> Dict[str, Any]:
    lunar_context = seed.calendar_context.get("lunar_calendar") or {}
    return {
        "input_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_datetime": seed.corrected_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": seed.timezone,
        "longitude": seed.longitude,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "total_correction_minutes": round(seed.total_correction_minutes, 2),
        "current_jieqi": seed.calendar_context["current_solar_term"]["name"],
        "next_jieqi": seed.calendar_context["next_solar_term"]["name"],
        "lunar_display": lunar_context.get("display"),
    }


def _join_snapshot_lines(lines: List[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def _build_taiyi_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    taiyi: Dict[str, Any],
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    calendar_rules = taiyi.get("calendar_rules") or {}
    historical = calendar_rules.get("historical_calendar")
    civil_lunar = calendar_rules.get("civil_lunar_calendar")
    lunar_display = (
        historical["display"] + "（历史历表，太乙专用）"
        if historical
        else (
            civil_lunar["display"]
            if civil_lunar
            else lunar_calendar.get("display") or "未提供"
        )
    )
    mark_lines = [
        f"{item.get('palace', '宫位')}：{'、'.join(item.get('markers', []) or []) or '无'}"
        for item in taiyi.get("palace_marks", []) or []
        if isinstance(item, dict)
    ]
    sections = [
        (
            "起盘信息",
            _join_snapshot_lines(
                [
                    f"{'年计所用农历' if historical or civil_lunar else '时间上下文农历'}：{lunar_display}",
                    f"输入钟时：{seed.input_datetime.isoformat()}；时区：{seed.timezone}",
                    f"计算钟面：{seed.calendar_context['solar_datetime']}；{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                    (
                        f"时间上下文农历：{lunar_calendar.get('display') or '未提供'}（校正钟面上下文，不替代年计所用农历）"
                        if historical or civil_lunar
                        else ""
                    ),
                    (
                        f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                ]
            ),
        ),
        (
            "太乙盘",
            _join_snapshot_lines(
                [
                    taiyi.get("style_label", "无"),
                    taiyi.get("accumulation_label", "无"),
                    f"布盘方向：{taiyi.get('rotation', '无')}",
                    f"计法：{taiyi.get('life_method', '无')}",
                    (taiyi.get("core_board") or {}).get("main_calculation", "无"),
                    (taiyi.get("core_board") or {}).get("taiyi_position", "无"),
                    (taiyi.get("core_board") or {}).get("wenchang_position", "无"),
                    f"{taiyi['core_board'].get('ruler_label', '岁君')}：{taiyi['core_board'].get('ruler_branch', taiyi['core_board'].get('suijun', '无'))}",
                    f"合神：{(taiyi.get('core_board') or {}).get('heshen', '无')}",
                ]
            ),
        ),
        ("十六宫标记", _join_snapshot_lines(mark_lines) or "无"),
        ("中宫标记", "、".join(taiyi["center_marks"]["markers"]) or "无星标"),
        ("规则依据", taiyi_evidence_text(taiyi)),
        ("年运十神", long_cycle_text(taiyi.get("long_cycles"))),
    ]
    return _render_snapshot_text(sections)


def _ren_calendar_snapshot_lines(policy: Dict[str, Any]) -> list[str]:
    if policy.get("mode") != "civil_instant_checked":
        return ["历法依据：符号推演，未核验真实民用时刻"]
    providers = sorted({term["provider"] for term in policy["solar_term_dependencies"]})
    models = sorted(
        {
            term.get("ephemeris_model", "unknown")
            for term in policy["solar_term_dependencies"]
        }
    )
    future = any(
        term.get("future_leap_seconds_assumed_unchanged")
        for term in policy["solar_term_dependencies"]
    )
    lines = [
        f"输入民用时间：{policy['civil_datetime']}",
        f"日时取用钟：{policy['corrected_clock']}（{'真太阳钟' if policy['day_hour_clock'] == 'apparent_solar' else '民用钟'}）",
        f"换日约定：{policy['day_boundary']}子初；日柱归属日期：{policy['effective_day_date']}（{policy['effective_day_ganzhi']}）",
        "年/月柱以民用瞬间交节换界；月将以民用瞬间中气换界",
        f"交气提供者：{'、'.join(providers)}；提供者状态不代替独立精度核验",
        f"实际交气星历模型：{'、'.join(models)}；依据各交气的模型与来源回执，未据此认证完整精度",
        "交气以TT求解后转换民用时间；小数秒仅为数值分辨率",
        (
            "未来闰秒：依冻结表末值保持不变的假设"
            if future
            else "未来闰秒假设未触发；历史时刻按所列UT1或历史UTC政策处理"
        ),
    ]
    lines.append(
        "香港天文台逐日表仅核对固定UTC+08日期；相符不认证交气时刻，冲突不改计算交界"
    )
    for term in policy["solar_term_dependencies"]:
        ref = term["published_date_reference"]
        if ref["status"] == "outside_published_range":
            lines.append(
                f"{term['role']} {term['name']}：计算+08日期{ref['computed_hko_date']}；超出官方1901—2100逐日表范围，未比较"
            )
        else:
            lines.append(
                f"{term['role']} {term['name']}：计算+08日期{ref['computed_hko_date']}；天文台刊载{ref['published_date']}；{'日期相符' if ref['dates_equal'] else '日期不一致'}"
            )
    resolution = policy.get("civil_clock_resolution")
    if resolution:
        selection = (
            f"重复钟时第{resolution['fold'] + 1}次"
            if resolution["was_ambiguous"]
            else "明确偏移已核对"
        )
        lines.insert(
            1,
            f"民用钟消歧：{resolution['timezone']} {resolution['resolved_utc_offset']}，"
            f"{selection}；对应UTC {resolution['instant_utc']}",
        )
    return lines


def _build_liureng_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    liureng: Dict[str, Any],
    runyear: Optional[Dict[str, Any]] = None,
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    month_general = (
        liureng.get("month_general", {}) if isinstance(liureng, dict) else {}
    )
    transmissions = (
        liureng.get("three_transmissions", {}) if isinstance(liureng, dict) else {}
    )
    auxiliary = liureng["auxiliary_stars"]
    auxiliary_lines: Dict[str, List[str]] = {
        "day_stem": [],
        "day_branch": [],
        "month_building": [],
    }
    for star in auxiliary["stars"]:
        lesson_text = "、".join(str(i) for i in star["lesson_indices"]) or "无"
        transmission_text = (
            "、".join(
                {"initial": "初传", "middle": "中传", "final": "末传"}[p]
                for p in star["transmission_positions"]
            )
            or "无"
        )
        auxiliary_lines[star["category"]].append(
            f"{star['name']}：{star['branch']}临{star['earth_branch']}乘{star['god']}；"
            f"旬遁{star['ganzhi'] or '无'}；旬空{'是' if star['xun_kong'] else '否'}；"
            f"坐空{'是' if star['seated_kong'] else '否'}；课序{lesson_text}；入传{transmission_text}；"
            f"临干{'是' if star['on_day_stem'] else '否'}；临支{'是' if star['on_day_branch'] else '否'}"
        )
    pattern_lines = [
        f"{item.get('name', '无')}：{item.get('basis', '无')}"
        for item in liureng.get("patterns", []) or []
        if isinstance(item, dict)
    ]
    board_lines = [
        (
            f"{item.get('earth_branch', '无')}位："
            f"天盘{item.get('sky_branch', '无')}；"
            f"贵神{item.get('god', '无')}"
        )
        for item in liureng.get("twelve_board", []) or []
        if isinstance(item, dict)
    ]
    lesson_lines = []
    for lesson in liureng.get("four_lessons", []) or []:
        if not isinstance(lesson, dict):
            continue
        lesson_lines.append(
            (
                f"第{lesson.get('index', 0)}课：{lesson.get('text', '无')}；"
                f"六亲：{lesson.get('relation', '无')}；"
                f"上下：{lesson.get('upper_lower_relation', '无')}；"
                f"上神对日干十二运：{lesson.get('upper_day_stem_life_stage', '未计算')}；"
                f"与日：{(lesson.get('relations') or {}).get('with_day_branch', '无')}；"
                f"与下：{(lesson.get('relations') or {}).get('with_lower_branch', '无')}"
                + ("；发用候选" if lesson.get("use_candidate") else "")
            )
        )
    transmission_lines = [
        f"取传法：{transmissions.get('method', '无')}",
        (
            f"初传：{(transmissions.get('initial') or {}).get('branch', '无')} / "
            f"{(transmissions.get('initial') or {}).get('relation', '无')} / "
            f"{(transmissions.get('initial') or {}).get('god', '无')}"
        ),
        (
            f"中传：{(transmissions.get('middle') or {}).get('branch', '无')} / "
            f"{(transmissions.get('middle') or {}).get('relation', '无')} / "
            f"{(transmissions.get('middle') or {}).get('god', '无')}"
        ),
        (
            f"末传：{(transmissions.get('final') or {}).get('branch', '无')} / "
            f"{(transmissions.get('final') or {}).get('relation', '无')} / "
            f"{(transmissions.get('final') or {}).get('god', '无')}"
        ),
    ]
    for index, key in enumerate(("initial", "middle", "final"), start=1):
        item = transmissions.get(key) or {}
        transmission_lines[index] += (
            f"；旬遁：{item.get('ganzhi') or '旬空无遁干'}"
            f"；本空：{'是' if item.get('xun_kong') else '否'}"
            f"；坐空：{'是' if item.get('seated_kong') else '否'}"
            f"；日干十二运：{item.get('day_stem_life_stage', '未计算')}"
            f"；所坐地盘对日干：{item.get('seated_day_stem_life_stage', '未计算')}"
        )
    progression = liureng["transmission_progression"]
    progression_lines = [
        "依据：探原PDF110–111，三传连茹与间断",
        f"初中末支序：{'、'.join(progression['branches'])}；模十二步长：{progression['steps']}",
        f"支序结构：{progression['kind'] or '未合所列连茹、间断'}；支序方向：{progression['sequence_direction'] or '无所列方向'}",
        f"支神本空：{progression['branch_xun_kong']}；{progression['empty_assumption']}",
        f"在上述假设下原文条件释读：{progression['raw_branch_empty_conditional_reading'] or '无所列释读'}；条件方向：{progression['raw_branch_empty_conditional_direction'] or '未定'}",
        "综合有效进退：未裁定；综合判断：未裁定",
        progression["scope"],
    ]
    empty = liureng["emptiness_evidence"]
    seasonal = liureng["seasonal_evidence"]
    seasonal_lines = [
        "依据：探原PDF84、86、89–90；支神、天将、地盘五行分别定位",
        f"月建{seasonal['month_branch']}；季节分组{seasonal['season_partition']}；{seasonal['month_partition_basis']}",
        "五态表：" + "、".join(f"{p}{v}" for p, v in seasonal["phase_powers"].items()),
        f"日干{seasonal['day_ganzhi'][0]}{seasonal['day_stem_element']}为{seasonal['day_stem_seasonal_power']}；日干状态不替换支神或天将状态",
    ]
    for row in seasonal["rows"]:
        positions = "、".join(
            label
            for label, key in [
                ("初传", "initial"),
                ("中传", "middle"),
                ("末传", "final"),
            ]
            if transmissions[key]["branch"] == row["sky_branch"]
        )
        seasonal_lines.append(
            f"地盘{row['earth_branch']}{row['earth_element']}{row['earth_seasonal_power']}；天盘支神{row['sky_branch']}{row['sky_element']}{row['sky_seasonal_power']}；"
            f"天将{row['god']}{row['god_element']}{row['god_seasonal_power']}；支神本空{row['sky_xun_kong']}；"
            f"{row['sky_empty_seasonal_condition'] or '未入本空，不套真半'}；传位{positions or '无'}；调整后真半及有效空亡未裁定"
        )
    seasonal_lines.append(seasonal["scope"])
    god_yin = liureng["god_yin"]
    god_yin_lines = [f"来源：{god_yin['source_title']}，PDF87–88。"]
    for row in god_yin["rows"]:
        method = (
            "昼夜贵人互取"
            if row["derivation"] == "opposite_noble_start"
            else "所乘支上神"
        )
        appears = {True: "已见", False: "未见", None: "年命缺项未定"}[
            row["appears_in_roles"]
        ]
        god_yin_lines.append(
            f"{row['god']}乘{row['riding_branch']}临{row['riding_earth_branch']}：阴神{row['yin_branch']}（{method}）；"
            f"课传年命范围{appears}；本支旬空{'是' if row['yin_branch_xun_kong'] else '否'}，名义五态{row['nominal_seasonal_power']}。"
        )
    god_yin_lines.append(god_yin["scope"])
    empty_by_sky = {r["sky_branch"]: r for r in empty["rows"]}
    empty_lines = [
        "依据：探原卷下论空亡，PDF84–85；本空与综合有效空亡分列",
        f"本次日干寄宫：{empty['day_stem_house']}；占时{empty['hour_branch']}本空：{empty['hour_branch_xun_kong']}",
        "角色条件："
        + "；".join(
            f"{r['role']}{r['branch']}本空{r['branch_xun_kong']}"
            for r in empty["role_conditions"]
        ),
    ]
    for label, position in (("初传", "initial"), ("中传", "middle"), ("末传", "final")):
        r = empty_by_sky[transmissions[position]["branch"]]
        empty_lines.append(
            f"{label}天盘{r['sky_branch']}本空{r['sky_xun_kong']}；地盘{r['earth_branch']}落底本空{r['earth_xun_kong']}；"
            f"日干寄宫地盘例外{r['earth_stem_house_exception']}；天盘角色{'、'.join(r['sky_authority_roles']) or '无所列角色'}；综合有效空亡未裁定"
        )
    empty_lines.append(empty["scope"])
    runyear_lines = ["无"]
    relation_evidence = liureng["transmission_relations"]
    course = relation_evidence["course_conditions"]
    transmission_lines.extend(
        [
            "三传关系依据：探原卷下论三传、论十二天将、论合（所选结构）",
            *(
                f"{ {'initial':'初传','middle':'中传','final':'末传'}[r['position']]}：支神{r['branch']}{r['element']}，天将{r['god']}{r['god_element']}；将对神{r['god_to_spirit']}，{r['war'] or '无内外战'}；六亲仍按支神为{r['day_relation']}"
                for r in relation_evidence["rows"]
            ),
            "三传结构："
            + (
                "、".join(r["name"] for r in relation_evidence["rules"] if r["matched"])
                or "所列九条条件无命中"
            ),
            *(
                f"三合{'、'.join(t['branches'])}支齐，名义{t['nominal_element']}局体对日干为{t['nominal_day_relation']}；未裁合化，不改各支本六亲"
                for t in relation_evidence["trines"]
                if t["branches_complete"]
            ),
            relation_evidence["scope"],
            "传序课体（探原PDF114–115，按初中末）："
            + "—".join(relation_evidence["named_structures"]["branches"])
            + "；"
            + (
                "、".join(
                    r["name"]
                    for r in relation_evidence["named_structures"]["evaluations"]
                    if r["matched"]
                )
                or "所列三条传序条件无命中"
            ),
            f"课体纲要条件（探原PDF112、114–115）：占日{course['day_ganzhi']}，初传{course['branches'][0]}乘{course['initial_god']}、临{course['initial_earth_branch']}，日干十二运{course['initial_stage']}；"
            + "、".join(
                r["name"]
                for group in (
                    "stage_god_patterns",
                    "god_patterns",
                    "structural_patterns",
                )
                for r in course[group]
                if r["matched"]
            )
            + "；仅结构条件，非寿命、临床、灾祸或现实结局判断",
            course["scope"],
            "配将必要条件（两表、昼夜、顺逆8种配置）："
            + "、".join(
                r["name"]
                for r in course["stage_god_patterns"]
                if not r["compatible_in_any_supported_noble_layout"]
            )
            + "的日干十二运与天将支位不能同时满足；字面判据保留，非占事吉凶",
        ]
    )
    branch_evidence = liureng.get("branch_relations") or {}
    branch_lines = []
    branch_names = {
        "same_branch": "同支",
        "liuhe": "六合",
        "liuchong": "六冲",
        "liuhai": "六害",
        "liupo": "六破",
        "left_xing_right": "前支刑后支",
        "right_xing_left": "后支刑前支",
    }
    for item in branch_evidence.get("rows", []):
        matched = [label for key, label in branch_names.items() if item["facts"][key]]
        if matched:
            annotation = item["facts"]["harmony_annotation"]
            branch_lines.append(
                f"{item['id']}：{item['left_role']}{item['left_branch']}／"
                f"{item['right_role']}{item['right_branch']}，{'、'.join(matched)}"
                + (f"；原文{annotation}" if annotation else "")
            )
    branch_lines += [
        f"依据：{branch_evidence.get('source_title', '无')}；PDF91、92、95–97。",
        "逐项布尔值见47条结构化依据；本节仅列有匹配项。六合与刑破可以并存，不据合独断成局；首课寄宫支关系不替代日干五行。",
        branch_evidence.get("scope", ""),
    ]
    if runyear:
        runyear_lines = [
            f"年龄：{runyear.get('age', '无')}",
            f"行年：{runyear.get('ganzhi') or '未计算'}",
            f"性别：{runyear.get('gender', '无')}",
            f"虚岁依据：{runyear.get('age_basis', '无')}",
            f"规则依据：{runyear.get('source_section', '无')}",
            *([f"说明：{runyear['reason']}"] if runyear.get("reason") else []),
        ]
        if birth_clock := runyear.get("birth_civil_clock"):
            runyear_lines += [
                f"出生民用时刻：{birth_clock['wall_datetime']}{birth_clock['resolved_utc_offset']}（{birth_clock['timezone']}，fold={birth_clock['fold']}）",
                f"出生UTC瞬间：{birth_clock['instant_utc']}；先后核对使用民用瞬间，出生时间未做太阳钟偏移。",
            ]
            runyear_lines.append(
                f"出生时区来源：{birth_clock.get('timezone_source', '未列')}"
                f"（{birth_clock.get('timezone_resolved_place') or '未使用地名解析'}）；"
                f"默认假设：{'是' if birth_clock.get('timezone_assumed') else '否'}。"
            )
            if birth_clock.get("timezone_resolution_advisory"):
                runyear_lines.append(birth_clock["timezone_resolution_advisory"])
        if age_calendar := runyear.get("age_calendar"):
            runyear_lines += [
                f"虚岁参考时区：{age_calendar['timezone']}；分析瞬间在该区：{age_calendar['analysis_civil_datetime']}。",
                f"虚岁农历年：出生{age_calendar['birth_lunar_year']}、分析{age_calendar['analysis_lunar_year']}；两端同区，正月初一00:00换岁。",
            ]
        if year_fate := runyear.get("year_fate"):
            for key, label in (("natal", "本命"), ("annual", "行年")):
                item = year_fate[key]
                if item["status"] == "not_calculated":
                    runyear_lines.append(f"{label}落盘：未计算；{item['reason']}")
                    continue
                runyear_lines.append(
                    f"{label}干支{item['subject_ganzhi']}书地盘{item['earth_branch']}；"
                    f"上见{item['sky_branch']}乘{item['god']}，对占日为{item['upper_relation']}；"
                    f"上神旬遁：{item['upper_ganzhi'] or '旬空无遁干'}；"
                    f"上神旬空：{'是' if item['upper_xun_kong'] else '否'}；"
                    f"地盘旬空：{'是' if item['earth_xun_kong'] else '否'}。"
                )
            runyear_lines.append(f"年命口径：{year_fate['birth_year_basis']}。")
    sections = [
        (
            "起盘信息",
            _join_snapshot_lines(
                [
                    f"农历：{lunar_calendar.get('display') or '无'}",
                    *_ren_calendar_snapshot_lines(liureng.get("calendar_policy") or {}),
                    (
                        f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                ]
            ),
        ),
        (
            "十二盘式",
            _join_snapshot_lines(
                [
                    f"月将：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"课体：{liureng.get('board_style', '无')}",
                    f"细课体：{liureng.get('board_style_detail', '无')}",
                    f"按总说规则细分：{' / '.join(liureng['classification']['labels'])}",
                    f"细分依据：{liureng['classification']['basis']}",
                    f"盘序：{liureng.get('board_order', '无')}",
                    f"贵人体系：{liureng.get('guiren_system', '无')}",
                ]
            ),
        ),
        ("十二地盘/十二天盘/十二贵神对应", _join_snapshot_lines(board_lines) or "无"),
        ("四课", _join_snapshot_lines(lesson_lines) or "无"),
        ("三传", _join_snapshot_lines(transmission_lines) or "无"),
        ("三传连茹与间断", _join_snapshot_lines(progression_lines)),
        ("季节五态与支神本空条件", _join_snapshot_lines(seasonal_lines)),
        ("类神阴神", _join_snapshot_lines(god_yin_lines)),
        ("空亡分层条件", _join_snapshot_lines(empty_lines)),
        ("支位合冲刑破害", _join_snapshot_lines(branch_lines)),
        ("行年", _join_snapshot_lines(runyear_lines) or "无"),
        (
            "旬日",
            _join_snapshot_lines(
                [
                    f"旬首：{liureng.get('xun_head', '无')}",
                    f"空亡：{liureng.get('kongwang', '无')}",
                ]
            ),
        ),
        (
            "旺衰",
            _join_snapshot_lines(
                [
                    f"月建所属五行：{liureng.get('month_building_element', '无')}",
                    f"昼夜：{'昼占' if (liureng.get('meta') or {}).get('is_diurnal') else '夜占'}",
                    liureng["meta"]["diurnal_evidence"]["basis"],
                    liureng["meta"]["diurnal_evidence"]["scope"],
                    f"发用课序：第{(liureng.get('meta') or {}).get('selected_lesson_index', '无')}课",
                ]
            ),
        ),
        (
            "基础神煞",
            _join_snapshot_lines(
                [
                    f"月将：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"贵人体系：{liureng.get('guiren_system', '无')}",
                    f"盘序：{liureng.get('board_order', '无')}",
                    f"德禄马依据：{auxiliary['source_title']}",
                    auxiliary["scope"],
                ]
            ),
        ),
        (
            "干煞",
            _join_snapshot_lines(
                [
                    f"日干：{seed.pillars['day'][0]}",
                    f"旬首：{liureng.get('xun_head', '无')}",
                    f"空亡：{liureng.get('kongwang', '无')}",
                    *auxiliary_lines["day_stem"],
                ]
            ),
        ),
        (
            "月煞",
            _join_snapshot_lines(
                [
                    f"月将：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"当前节气：{(liureng.get('meta') or {}).get('current_term', '无')}",
                    f"月建所属五行：{liureng.get('month_building_element', '无')}",
                    f"德马月序：月建{auxiliary['month_building_branch']}，名义月序{auxiliary['nominal_month']}",
                    auxiliary["month_basis"],
                    *auxiliary_lines["month_building"],
                ]
            ),
        ),
        (
            "支煞",
            _join_snapshot_lines(
                [
                    f"日支：{seed.pillars['day'][1]}",
                    f"时支：{seed.pillars['hour'][1]}",
                    f"首传所临：{(transmissions.get('initial') or {}).get('branch', '无')}",
                    *auxiliary_lines["day_branch"],
                ]
            ),
        ),
        (
            "岁煞",
            _join_snapshot_lines(
                [
                    f"岁干：{seed.pillars['year'][0]}",
                    f"岁支：{seed.pillars['year'][1]}",
                    f"问占性别：{(liureng.get('meta') or {}).get('questioner_gender', '无')}",
                ]
            ),
        ),
        (
            "十二长生",
            _join_snapshot_lines(
                [
                    f"十二运依据：{liureng['life_stages']['source_title']}；日干{liureng['life_stages']['day_stem']}，{liureng['life_stages']['direction']}行",
                    "、".join(
                        f"{branch}{stage}"
                        for branch, stage in liureng["life_stages"][
                            "stage_by_branch"
                        ].items()
                    ),
                    *[
                        f"{item['name']}：{'命中' if item['matched'] else '未命中'}；天盘{item['sky_branch']}({item['sky_stage']})临地盘{item['earth_branch']}({item['earth_stage']})"
                        for item in liureng["life_stages"]["placements"]
                    ],
                    liureng["life_stages"]["scope"],
                ]
            ),
        ),
        ("大格", _join_snapshot_lines(pattern_lines) or "无"),
        ("小局", _join_snapshot_lines(transmission_lines) or "无"),
        ("参考", _join_snapshot_lines(liureng.get("overview", [])) or "无"),
        (
            "概览",
            _join_snapshot_lines(
                [
                    f"{liureng.get('board_style', '无')}课 / {liureng.get('board_style_detail', '无')}",
                    (
                        f"月将{month_general.get('branch', '无')}({month_general.get('name', '无')})，"
                        f"{liureng.get('board_order', '无')}。"
                    ),
                    f"首传：{(transmissions.get('initial') or {}).get('branch', '无')}",
                ]
            ),
        ),
    ]
    return _render_snapshot_text(sections)


def _build_jinkou_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    jinkou: Dict[str, Any],
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    overview = jinkou.get("overview", {}) if isinstance(jinkou, dict) else {}
    yuejiang = overview.get("yuejiang", {}) if isinstance(overview, dict) else {}
    month_general = (
        overview.get("month_general", {}) if isinstance(overview, dict) else {}
    )
    guishen = overview.get("guishen", {}) if isinstance(overview, dict) else {}
    row_lines = []
    for row in jinkou.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        row_lines.append(
            (
                f"{row.get('label', '四位')}：{row.get('content', '无')}；"
                f"神将：{row.get('shenjiang', '无')}；"
                f"五行：{row.get('element', '无')}；"
                f"四季旺衰：{row.get('seasonal_power', '无')}"
                f"；课内旺衰：{row.get('internal_power') or '未定'}"
                f"；阴阳：{row.get('polarity', '无')}"
                f"；旬空：{'是' if row.get('xun_kong') else '否'}"
                f"；四大空亡：{'是' if row.get('si_da_kong') else '否'}"
            )
        )
    interactions = jinkou["position_interactions"]
    row_lines.extend(
        [
            f"四位位置关系依据：{interactions['source_title']}",
            *(
                f"位置生克：{p['upper_position']}{p['upper_element']}与{p['lower_position']}{p['lower_element']}，"
                f"{p['relation']}（{'相邻' if p['adjacent'] else '隔位'}）"
                for p in interactions["pairs"]
            ),
            *(
                f"位置结构：{r['name']}，{'命中' if r['matched'] else '所列条件未命中'}；"
                + "、".join(
                    f"{c['source_position']}{c['source_element']}{c['relation']}{c['target_position']}{c['target_element']}：{'是' if c['matched'] else '否'}"
                    for c in r["condition_checks"]
                )
                for r in interactions["rule_evaluations"]
            ),
            f"四位任意位置有克：{'是' if interactions['has_any_control'] else '否'}",
            interactions["scope"],
        ]
    )
    stems = jinkou["stem_relations"]
    pair = stems["pair_facts"]
    row_lines.extend(
        [
            f"神将遁干依据：{stems['source_title']}",
            f"贵神固有干支：{stems['guishen_intrinsic_ganzhi']}；当日神干{stems['god']['dun_ganzhi']}、将干{stems['general']['dun_ganzhi']}",
            f"干元类关系：{stems['relation']}；{stems['motion_analogue'] or '无本节克类动象'}，不改四位五动命中",
            f"遁干配对：天干五合{'是' if pair['stem_harmony_matched'] else '否'}；地支六合{'是' if pair['branch_harmony_matched'] else '否'}；干支俱合{'是' if pair['both_harmonies_matched'] else '否'}；候选五行{pair['candidate_element'] or '无'}，合化未裁定",
            f"两遁干支自身旬：{pair['left_ganzhi_xun_head']}／{pair['right_ganzhi_xun_head']}；自身同旬{'是' if pair['same_ganzhi_xun'] else '否'}，不改占日旬首与空亡",
            stems["scope"],
        ]
    )
    shensha_lines = [
        f"{item.get('label', '神煞')}：{item.get('value', '无')}"
        for item in jinkou.get("shensha", []) or []
        if isinstance(item, dict)
    ]
    natal = jinkou.get("natal_course")
    natal_lines = []
    if natal:
        natal_lines = ["京本次客法本命另课：本命支作派生地分，与原地分主课分列。"]
        if natal["course"] is None:
            natal_lines.append("本命支及明确出生年干支均未提供，未另起本命课。")
        else:
            natal_lines += [
                f"本命支{natal['natal_branch']}；来源{natal['natal_branch_source']}；另课四位："
                + "、".join(r["label"] + r["content"] for r in natal["course"]["rows"]),
                f"本命另课阴阳用位：{natal['course']['overview']['use_position']}；综合取用尚未裁定。",
            ]
        natal_lines += [natal["scope"]]
    year_fate = jinkou.get("year_fate")
    year_fate_lines = []
    if year_fate:
        year_fate_lines = [
            "京本行年：出生年干支所属旬起运，男顺女逆；与大六壬通用行年起点分开。"
        ]
        if year_fate["status"] == "calculated":
            year_fate_lines.extend(
                [
                    f"本命{year_fate['birth_year_ganzhi']}属{year_fate['birth_xun']}旬；指定岁序{year_fate['age_ordinal']}，{year_fate['gender']}{year_fate['direction']}行，起点{year_fate['start_ganzhi']}，目标行年{year_fate['ganzhi']}。",
                    "行年另课：以"
                    + year_fate["branch"]
                    + "作地分；"
                    + "、".join(
                        r["label"] + r["content"] for r in year_fate["course"]["rows"]
                    )
                    + "。原问课地分与本课四位保留。",
                ]
            )
        else:
            year_fate_lines.append(
                "行年资料缺失："
                + "、".join(
                    {
                        "birth_year_ganzhi": "出生年干支",
                        "year_fate_age": "一岁起算岁序",
                        "gender": "性别",
                    }[k]
                    for k in year_fate["missing_inputs"]
                )
                + "；未另起行年课。"
            )
        year_fate_lines.extend([year_fate["relation_note"], year_fate["scope"]])
    definitions = jinkou["definition_evidence"]
    route_names = {
        "intrinsic_god": "贵神固有干",
        "daily_god": "日干起神干",
        "daily_general": "日干起将干",
        "human_redun_at_ground": "人元再遁至地分",
    }
    row_lines.extend(
        [
            "课钤疑义校勘：CNTS第二册PDF118–121与早稻田《湖社叢話》第六册p0057–p0059；六条均未裁定命中。",
            *(
                f"{entry['pattern_id']}{entry['name']}：{entry['unresolved_reason']}"
                for entry in definitions["entries"]
            ),
            "同课昼夜条件候选："
            + "；".join(
                f"{'昼' if c['assumed_is_diurnal'] else '夜'}起{c['start_branch']}、地分{c['ground_branch']}见{c['god_name']}（{c['intrinsic_ganzhi']}）"
                for c in definitions["day_night_candidates"]
            ),
            "起丁路径候选："
            + "；".join(
                f"{route_names[r['route_id']]}={r['stem']}{r['element']}，克人元{'是' if r['controls_human'] else '否'}、克地分{'是' if r['controls_ground'] else '否'}"
                for r in definitions["ding_routes"]
            ),
            definitions["scope"],
        ]
    )
    shensha_lines.extend(
        f"{motion['name']}：{motion['basis']}" for motion in jinkou.get("motions", [])
    )
    relations = jinkou.get("relations") or {}
    if relations:
        shensha_lines.extend(
            [
                "四绝："
                + (
                    "；".join(
                        f"{check['basis']}（{check['classification']}）"
                        for check in relations["si_jue"]["checks"]
                        if check["matched"]
                    )
                    or "已算关系无命中"
                ),
                "四败临地分："
                + (
                    "；".join(
                        check["basis"]
                        for check in relations["si_bai"]["checks"]
                        if check["matched"]
                    )
                    or "无命中"
                ),
                "岁日同冲："
                + (
                    "；".join(
                        f"{check['name']}：{check['basis']}"
                        for check in relations["calendar"]["checks"]
                        if check["matched"]
                    )
                    or "已算关系无命中"
                ),
                relations["si_jue"]["natal"]["basis"],
                "四绝依京本书影配对，不套一般十二长生。四败只列临地分一层，不等同于旺衰或现实结局。",
            ]
        )
    stars = jinkou["branch_stars"]
    shensha_lines.append(
        f"京本所选神煞：年支{stars['year_branch']}、月建{stars['month_building_branch']}（名义{stars['nominal_month']}月）、占日{stars['day_ganzhi']}。"
    )
    for check in stars["checks"]:
        anchor_label = {
            "month_building": "月建",
            "year_branch": "年支",
            "season_and_day": "四季与占日",
        }[check["category"]]
        if check["target_kind"] == "day_ganzhi":
            status = "符合占日" if check["matched_day"] else "未合占日"
        else:
            status = "本支相同位置：" + ("、".join(check["matched_positions"]) or "无")
        shensha_lines.append(
            f"{check['name']}：目标{check['target']}，依据{anchor_label}，{status}；原PDF{check['original_pdf_page']}。"
        )
    shensha_lines.append(stars["scope"])
    combination_lines = []
    for trine in jinkou["combinations"]["trines"]:
        if len(trine["present_branches"]) < 2:
            continue
        name = trine["partial_name"] if trine["missing_branches"] else trine["name"]
        combination_lines.append(f"{name}：{trine['basis']}")
        conditions = [
            f"{member['position']}{member['branch']}："
            + "、".join(
                text
                for key, text in (
                    ("day_clash", "日冲"),
                    ("month_break", "月破"),
                    ("xun_kong", "旬空"),
                    ("si_da_kong", "四大空亡"),
                )
                if member[key]
            )
            for member in trine["member_conditions"]
            if any(
                member[k]
                for k in ("day_clash", "month_break", "xun_kong", "si_da_kong")
            )
        ]
        combination_lines.append("；".join(conditions) or "所列成员空破条件无命中。")
        combination_lines.extend(
            f"{stem['position']}遁干{stem['stem']}{stem['element']}克{stem['trine_element']}局；"
            + (
                "符合本节壬癸克火局条件。"
                if stem["explicit_fire_clause"]
                else "仅列五行关系。"
            )
            for stem in trine["controlling_dun_stems"]
        )
    sections = [
        (
            "起盘信息",
            _join_snapshot_lines(
                [
                    f"农历：{lunar_calendar.get('display') or '无'}",
                    *_ren_calendar_snapshot_lines(jinkou.get("calendar_policy") or {}),
                    (
                        f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                ]
            ),
        ),
        (
            "金口诀速览",
            _join_snapshot_lines(
                [
                    f"地分：{overview.get('di_fen', '无')}",
                    f"地分来源：{overview.get('di_fen_source', '无')}",
                    f"月将本位：{month_general.get('branch', '无')}({month_general.get('name', '无')})",
                    f"将神落地分：{yuejiang.get('branch', '无')}({yuejiang.get('name', '无')})",
                    (
                        f"贵神：{guishen.get('branch', '无')}({guishen.get('name', '无')})；"
                        f"贵人起位：{guishen.get('start_branch', '无')}"
                    ),
                    (
                        f"课体：{overview.get('board_style', '无')} / "
                        f"{overview.get('board_style_detail', '无') or '无细课体'}"
                    ),
                    f"取传：{overview.get('transmission_method', '无')}",
                    f"用爻：{overview.get('use_position', '无')}",
                    f"取用依据：{overview.get('use_position_basis', '无')}",
                    overview["diurnal_evidence"]["basis"],
                    overview["diurnal_evidence"]["scope"],
                    f"空亡：{overview.get('kongwang', '无')}",
                    f"四大空亡：{overview.get('si_da_kong', '无')}",
                    f"旺衰依据：{overview.get('power_basis', '无')}",
                    f"位内旺神：{jinkou['internal_strength']['anchor_element'] or '未定'}；{jinkou['internal_strength']['basis']}",
                    jinkou["internal_strength"]["source_evidence"]["note"],
                    f"月建与日辰得气：{jinkou['qi_evidence']['basis']}",
                    f"神将建旺：{jinkou['qi_evidence']['month_building_basis']}",
                    f"阴阳用位条件：受克于{'、'.join(jinkou['use_evidence']['controlled_by']) or '无'}；旬空{jinkou['use_evidence']['xun_kong']}；四大空亡{jinkou['use_evidence']['si_da_kong']}；月破{jinkou['use_evidence']['month_break']}",
                    f"综合取用状态：{jinkou['use_evidence']['status']}；{jinkou['use_evidence']['basis']}",
                    "已列日支生将依据；日下完整五态及综合取用尚未裁定，当前用位仅按阴阳次第五用。",
                    (
                        f"规则来源：{jinkou['ruleset']['source_title']}；"
                        f"{jinkou['ruleset']['id']} / {jinkou['ruleset']['version']}"
                    ),
                    *jinkou["ruleset"]["source_urls"],
                    "局部转录规则，未完成全书验收；现实预测效度未经验证。",
                ]
            ),
        ),
        ("金口诀四位", _join_snapshot_lines(row_lines) or "无"),
        *(
            ([("京本本命另课", _join_snapshot_lines(natal_lines))])
            if natal_lines
            else []
        ),
        *(
            ([("京本行年另课", _join_snapshot_lines(year_fate_lines))])
            if year_fate_lines
            else []
        ),
        (
            "六十四课钤结构",
            _join_snapshot_lines(
                [
                    *(
                        f"{p['name']}（{p['alias']}）：{p['condition']}；{p['basis']}；书影PDF{p['original_pdf_page']}"
                        for p in jinkou["patterns"]["matched"]
                    ),
                    f"已评估{jinkou['patterns']['evaluated_rule_count']}/{jinkou['patterns']['catalog_count']}条结构定义，尚未评估："
                    + "、".join(p["name"] for p in jinkou["patterns"]["unresolved"]),
                    f"本课命中{jinkou['patterns']['evaluation_counts']['matched']}条，"
                    f"所选定义下未命中{jinkou['patterns']['evaluation_counts']['not_matched']}条，"
                    f"疑义未判{jinkou['patterns']['evaluation_counts']['unresolved']}条；未判不等于不成立。",
                    jinkou["patterns"]["scope"],
                ]
            ),
        ),
        (
            "三合与虚一待用",
            _join_snapshot_lines(
                [
                    *(
                        combination_lines
                        or ["神、将、地分未见同组三合的两个不同成员。"]
                    ),
                    jinkou["combinations"]["scope"],
                ]
            ),
        ),
        ("四位神煞", _join_snapshot_lines(shensha_lines) or "无"),
    ]
    return _render_snapshot_text(sections)


def _build_ziwei_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    ziwei_birth: Dict[str, Any],
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    ming_gong = (
        ziwei_birth.get("ming_gong", {}) if isinstance(ziwei_birth, dict) else {}
    )
    shen_gong = (
        ziwei_birth.get("shen_gong", {}) if isinstance(ziwei_birth, dict) else {}
    )
    sihua = ziwei_birth.get("sihua", {}) if isinstance(ziwei_birth, dict) else {}
    palace_lines = []
    for palace in ziwei_birth.get("palaces", []) or []:
        if not isinstance(palace, dict):
            continue
        star_text = (
            "、".join(
                (
                    f"{d['label']}({d['brightness']})"
                    if d.get("brightness")
                    else d["label"]
                )
                for d in palace["stars_detail"]
            )
            or "无"
        )
        palace_lines.append(
            (
                f"{palace.get('name', '宫位')}：{palace.get('ganzhi', '无')}；"
                f"大限：{palace.get('daxian') or '未定（缺少性别）'}；"
                f"十二长生：{palace.get('changsheng12') or '未定'}；博士十二神：{palace.get('boshi12') or '未定'}；"
                f"星曜：{star_text}"
            )
        )
    sections = [
        (
            "起盘信息",
            _join_snapshot_lines(
                [
                    f"农历：{lunar_calendar.get('display') or '无'}",
                    f"输入钟表时间：{seed.input_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"排盘时间：{seed.calendar_context['solar_datetime']}",
                    (
                        f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                    f"生年天干：{ziwei_birth.get('year_stem', '无')}",
                    basis_text(ziwei_birth["calendar_basis"]),
                    f"规则配置：{ziwei_birth['ruleset']['id']}；原典符合范围：{ziwei_birth['ruleset']['classical_conformance']}",
                    *(
                        [
                            "所选四化表：明刊卷三；本命年干原文："
                            + ziwei_birth["sihua_source_comparison"]["source_reading"],
                            "仅切换四化表，其他安星、亮度及岁序按基础配置分别核对",
                        ]
                        if ziwei_birth["ruleset"].get("sihua_source") == "naj_ming_v1"
                        else []
                    ),
                    f"闰月口径：{ziwei_birth['calendar_rules']['leap_month']}",
                    f"亮度来源：{ziwei_birth['ruleset']['brightness_rule']}",
                    "旬空显示："
                    + "、".join(
                        ziwei_birth["void_systems"]["xun"]["displayed_star_branches"]
                    ),
                    "原文的化财、化印等象意与本命禄权科忌分别记录",
                    (
                        "明刊四化异文比较：本年干差异 "
                        f"{len(ziwei_birth['sihua_source_comparison']['differences'])} 项；"
                        "异文未套用于当前盘，不代表其他规则或全书一致"
                    ),
                    f"命主（命宫支）：{ziwei_birth['chart_masters']['life']['star']}；身主（生年支）：{ziwei_birth['chart_masters']['body']['star']}",
                    f"十二长生规则：{ziwei_birth['calendar_cycles']['changsheng_rule']}；标记仅表示传统循环名称",
                    (
                        f"命宫：{ming_gong.get('branch', '无')} / "
                        f"{ming_gong.get('ganzhi', '无')}"
                    ),
                    (
                        f"身宫：{shen_gong.get('branch', '无')} / "
                        f"{shen_gong.get('ganzhi', '无')}"
                    ),
                ]
            ),
        ),
        (
            "宫位总览",
            _join_snapshot_lines(
                [
                    (
                        "四化："
                        f"化禄={sihua.get('化禄', '无')}；"
                        f"化权={sihua.get('化权', '无')}；"
                        f"化科={sihua.get('化科', '无')}；"
                        f"化忌={sihua.get('化忌', '无')}"
                    ),
                    *palace_lines,
                ]
            ),
        ),
    ]
    return _render_snapshot_text(sections)


def _build_ziwei_horoscope_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    target_seed: MetaphysicsSeed,
    horoscope: Dict[str, Any],
) -> str:
    def _mutagen_line(mut: Dict[str, Any]) -> str:
        return (
            f"化禄={mut.get('化禄', '无')}；化权={mut.get('化权', '无')}；"
            f"化科={mut.get('化科', '无')}；化忌={mut.get('化忌', '无')}"
        )

    sections = [
        (
            "起盘信息",
            _join_snapshot_lines(
                [
                    f"出生：{seed.calendar_context['solar_datetime']}",
                    f"目标：{target_seed.calendar_context['solar_datetime']}",
                    f"虚岁：{horoscope.get('nominal_age', '无')}",
                    f"岁序方法：{horoscope['nominal_age_calendar']['method_id']}；参考时区：{horoscope['nominal_age_calendar']['timezone'] or '旧混合时钟'}；原典岁首尚未认证",
                    f"目标时区：{target_seed.timezone}；目标时刻采用钟表时间",
                    "出生" + basis_text(horoscope["calendar_basis"]["birth"]),
                    "目标" + basis_text(horoscope["calendar_basis"]["target"]),
                    *(
                        [
                            f"明文童限（给定岁序{horoscope['nominal_age']}）：本命{horoscope['childhood_limit']['natal_palace_name']}，{horoscope['childhood_limit']['natal_palace_ganzhi']}",
                            "该宫本命星曜："
                            + "、".join(
                                s["label"]
                                for s in horoscope["childhood_limit"][
                                    "natal_stars_detail"
                                ]
                            ),
                            "童限与大限分列；本命四化不是童限四化，岁首与起大限前替代关系未认证",
                        ]
                        if horoscope.get("childhood_limit", {}).get("status")
                        == "computed_given_age_ordinal"
                        else []
                    ),
                    f"规则配置：{horoscope['ruleset']['id']}；原典符合范围：{horoscope['ruleset']['classical_conformance']}",
                    *(
                        [
                            "所选四化表：明刊卷三；各可用层按实际天干查同表，运限复用仍为软件约定，未获原典认证"
                        ]
                        if horoscope["ruleset"].get("sihua_source") == "naj_ming_v1"
                        else []
                    ),
                ]
            ),
        )
    ]
    for s in horoscope.get("scopes", []) or []:
        if s.get("status") == "not_started":
            sections.append(
                (
                    str(s["scope"]),
                    f"按所选五行局起岁，尚未起正式大限（{s['first_age']}岁起）；"
                    "本层宫位、宫干和四化未生成。童限另列，不作为大限替代。",
                )
            )
            continue
        sections.append(
            (
                str(s.get("scope", "运限")),
                _join_snapshot_lines(
                    [
                        f"命宫活动索引所临本命宫：{s.get('natal_palace_name', s.get('palace_name', '无'))}（{s.get('palace_ganzhi', '')}）",
                        f"四化天干：{s.get('stem', '')}",
                        f"天干来源：{s.get('stem_origin', '')}",
                        f"四化：{_mutagen_line(s.get('mutagen', {}) or {})}",
                        *(
                            [
                                "本层流曜："
                                + "；".join(
                                    f"{star['star']}入{star['scope_palace_name']}（{star['branch']}，叠本命{star['natal_palace_name']}）"
                                    for star in s["flowing_stars"]
                                )
                            ]
                            if s.get("flowing_stars")
                            else []
                        ),
                        *(
                            [
                                "飞天三杀位置集合："
                                + "、".join(s["annual_three_sha"]["branches"])
                                + "（所选原文未逐名配对）"
                            ]
                            if s.get("annual_three_sha")
                            else []
                        ),
                        "本层功能宫映射（星位仍为本命）："
                        + "；".join(
                            f"{p['scope_palace_name']}={p['branch']}（本命{p['natal_palace_name']}）"
                            for p in s.get("palace_map", [])
                        ),
                    ]
                ),
            )
        )
    return _render_snapshot_text(sections)


def _build_ziwei_rules_snapshot_text(payload: Dict[str, Any]) -> str:
    rule_catalogue = (
        payload.get("rule_catalogue", {}) if isinstance(payload, dict) else {}
    )
    focused_rules = (
        payload.get("focused_rules", {}) if isinstance(payload, dict) else {}
    )
    palace_sequence = "、".join(rule_catalogue.get("palace_sequence", []) or []) or "无"
    sihua_lines = [
        f"{stem}："
        + "；".join(
            f"{label}={star}"
            for label, star in (mapping.items() if isinstance(mapping, dict) else [])
        )
        for stem, mapping in (
            rule_catalogue.get("sihua_by_year_stem", {}) or {}
        ).items()
        if isinstance(mapping, dict)
    ]
    focused_sihua = (
        focused_rules.get("sihua", {}) if isinstance(focused_rules, dict) else {}
    )
    sections = [
        (
            "规则概览",
            _join_snapshot_lines(
                [
                    f"请求天干：{payload.get('requested_year_stem') or '全部'}",
                    f"引擎：{payload.get('engine', 'fatebridge-offline')}",
                    f"规则配置：{rule_catalogue['ruleset']['id']}；原典符合范围：{rule_catalogue['ruleset']['classical_conformance']}",
                    *(
                        [
                            "所选四化表：明刊卷三原页；仅选四化表，不认证基础配置的其他规则或历法"
                        ]
                        if rule_catalogue["ruleset"].get("sihua_source")
                        == "naj_ming_v1"
                        else []
                    ),
                ]
            ),
        ),
        ("宫位序列", palace_sequence),
        (
            "命身宫规则",
            _join_snapshot_lines(
                [
                    f"命宫：{rule_catalogue.get('ming_gong_method', '无')}",
                    f"身宫：{rule_catalogue.get('shen_gong_method', '无')}",
                ]
            ),
        ),
        ("四化总表", _join_snapshot_lines(sihua_lines) or "无"),
    ]
    if focused_sihua:
        sections.append(
            (
                "当前天干四化",
                _join_snapshot_lines(
                    [
                        f"天干：{focused_rules.get('year_stem', payload.get('requested_year_stem') or '无')}",
                        *[f"{label}：{star}" for label, star in focused_sihua.items()],
                    ]
                ),
            )
        )
    return _render_snapshot_text(sections)


@calculation_guard("紫微斗数命盘")
def calculate_ziwei_birth(
    person: PersonInfo,
    *,
    selected_sections: Optional[List[str]] = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    birth_utc_offset: Optional[str] = None,
) -> Dict[str, Any]:
    seed = _build_person_seed(person, birth_utc_offset=birth_utc_offset)
    ziwei_birth = build_ziwei_chart(
        seed,
        person.gender or "未知",
        rule_profile=rule_profile,
        sihua_source=sihua_source,
    )
    ziwei_birth["engine"] = "fatebridge-offline"
    ziwei_birth["calendar_basis"] = calendar_basis(seed)
    snapshot_text = _build_ziwei_snapshot_text(seed=seed, ziwei_birth=ziwei_birth)
    snapshot_export = _build_snapshot_export(
        technique="ziwei",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "紫微斗数命盘",
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                seed.input_datetime, include_minutes=True
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                seed.corrected_datetime, include_minutes=True
            ),
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": seed.timezone,
            "birth_longitude": seed.longitude,
            "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        },
        "analysis_context": {
            **_analysis_context_payload(seed),
            **context_basis(ziwei_birth["calendar_basis"]),
        },
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "ziwei_birth": ziwei_birth,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("紫微斗数运限")
def calculate_ziwei_horoscope(
    person: PersonInfo,
    *,
    target_year: int,
    target_month: int,
    target_day: int,
    target_hour: int,
    target_minute: int = 0,
    target_timezone: str = "Asia/Shanghai",
    target_utc_offset: Optional[str] = None,
    birth_utc_offset: Optional[str] = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    nominal_age_basis: str = "birth_civil_timezone",
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    seed = _build_person_seed(person, birth_utc_offset=birth_utc_offset)
    chart = build_ziwei_chart(
        seed,
        person.gender or "未知",
        rule_profile=rule_profile,
        sihua_source=sihua_source,
    )
    target_seed = _build_analysis_seed(
        analysis_year=target_year,
        analysis_month=target_month,
        analysis_day=target_day,
        analysis_hour=target_hour,
        analysis_minute=target_minute,
        analysis_timezone=target_timezone,
        analysis_utc_offset=target_utc_offset,
        utc_offset_field="target_utc_offset",
    )
    # Compare actual civil instants, not corrected apparent-solar labels or
    # just lunar years; same-year targets can still precede birth.
    if utc_instant(
        localize_datetime(target_seed.input_datetime, target_seed.timezone)
    ) < utc_instant(localize_datetime(seed.input_datetime, seed.timezone)):
        raise ValueError("紫微运限目标时刻早于出生时刻")
    horoscope = build_ziwei_horoscope(
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
        birth_seed=seed,
        nominal_age_basis=nominal_age_basis,
    )
    horoscope["calendar_basis"] = {
        "birth": calendar_basis(seed),
        "target": calendar_basis(target_seed),
        "nominal_age_rule": horoscope["nominal_age_calendar"]["rule"],
        "age_boundary_classically_verified": False,
    }
    # engine 已由 build_ziwei_horoscope 标记，无需在此重复盖章
    # （与 calculate_ziwei_birth 不同：build_ziwei_chart 不自带 engine）。
    snapshot_text = _build_ziwei_horoscope_snapshot_text(
        seed=seed, target_seed=target_seed, horoscope=horoscope
    )
    snapshot_export = _build_snapshot_export(
        technique="ziwei_horoscope",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "紫微斗数运限",
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                seed.input_datetime, include_minutes=True
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                seed.corrected_datetime, include_minutes=True
            ),
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": seed.timezone,
            "birth_longitude": seed.longitude,
            "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        },
        # Correct the old birth-seed receipt here; preserve it under an explicit
        # birth key. Target civil timezone/minute are independent birth inputs.
        "birth_context": {
            **_analysis_context_payload(seed),
            **context_basis(horoscope["calendar_basis"]["birth"]),
            "context_role": "birth",
        },
        "analysis_context": {
            **_analysis_context_payload(target_seed),
            **context_basis(horoscope["calendar_basis"]["target"]),
            "context_role": "target",
            "analysis_datetime": target_seed.corrected_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "analysis_year": target_seed.corrected_datetime.year,
            "analysis_month": target_seed.corrected_datetime.month,
            "analysis_day": target_seed.corrected_datetime.day,
            "analysis_hour": target_seed.corrected_datetime.hour,
            "analysis_minute": target_seed.corrected_datetime.minute,
        },
        "ziwei_horoscope": horoscope,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("紫微规则库")
def calculate_ziwei_rules(
    year_stem: Optional[str] = None,
    *,
    selected_sections: Optional[List[str]] = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
) -> Dict[str, Any]:
    if year_stem is not None and year_stem not in set(GAN):
        raise ValueError("year_stem 必须是单个天干")
    payload = build_ziwei_rules(
        year_stem, rule_profile=rule_profile, sihua_source=sihua_source
    )
    payload["engine"] = "fatebridge-offline"
    snapshot_text = _build_ziwei_rules_snapshot_text(payload)
    snapshot_export = _build_snapshot_export(
        technique="ziwei_rules",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "紫微规则库",
        **payload,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("大六壬起课")
def calculate_liureng_gods(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    analysis_longitude: Optional[float] = None,
    gender: str = "未知",
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: Optional[List[str]] = None,
    is_diurnal: Optional[bool] = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> Dict[str, Any]:
    seed = _build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    liureng = build_liureng_board(
        seed,
        gender=gender,
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    liureng["engine"] = "fatebridge-offline"
    snapshot_text = _build_liureng_snapshot_text(seed=seed, liureng=liureng)
    snapshot_export = _build_snapshot_export(
        technique="liureng",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "大六壬起课",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "liureng": liureng,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("大六壬行年")
def calculate_liureng_runyear(
    person: PersonInfo,
    *,
    birth_utc_offset: Optional[str] = None,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    analysis_longitude: Optional[float] = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: Optional[List[str]] = None,
    is_diurnal: Optional[bool] = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> Dict[str, Any]:
    # 大六壬行年以「分析时刻」起课，不依赖出生四柱；
    # 出生民用时刻用于先后核对与出生农历年，不构建出生四柱。
    seed = _build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    birth_zone, birth_zone_source = resolve_runyear_birth_zone(
        person.birth_timezone, person.birth_place, person.birth_longitude
    )
    birth_moment, birth_clock = resolve_runyear_birth_clock(
        datetime(
            person.birth_year,
            person.birth_month,
            person.birth_day,
            person.birth_hour,
            person.birth_minute,
            person.birth_second or 0,
        ),
        birth_zone,
        birth_utc_offset,
        recorded_offset=person.birth_utc_offset,
    )
    birth_clock.update(birth_zone_source)
    # A same-zone datetime comparison ignores fold and orders wall labels.
    # Birth/analysis chronology must instead compare physical UTC instants.
    analysis_civil = localize_datetime(seed.input_datetime, seed.timezone)
    if utc_instant(analysis_civil) < utc_instant(birth_moment):
        raise ValueError("行年分析日期不能早于出生日期")
    birth_lunar = get_lunar_context(birth_moment, timezone_name=birth_zone)
    if birth_lunar is None:
        raise ValueError("行年需要出生日期的农历年")
    birth_lunar_year = birth_lunar.get("year")
    if not isinstance(birth_lunar_year, int):
        raise ValueError("行年需要出生日期的农历年")
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    liureng = build_liureng_board(
        seed,
        gender=person.gender or "未知",
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    liureng["engine"] = "fatebridge-offline"
    runyear = build_liureng_runyear(
        seed,
        gender=person.gender or "未知",
        birth_year=person.birth_year,
        birth_lunar_year=birth_lunar_year,
        age_reference_timezone=birth_zone,
    )
    runyear["engine"] = "fatebridge-offline"
    runyear["birth_civil_clock"] = birth_clock
    runyear["year_fate"] = build_year_fate(
        liureng,
        day_ganzhi="".join(seed.pillars["day"]),
        birth_lunar_year=birth_lunar_year,
        runyear_ganzhi=runyear["ganzhi"],
        runyear_reason=runyear.get("reason"),
    )
    add_year_fate_membership(liureng, runyear["year_fate"])
    snapshot_text = _build_liureng_snapshot_text(
        seed=seed,
        liureng=liureng,
        runyear=runyear,
    )
    snapshot_export = _build_snapshot_export(
        technique="liureng",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "大六壬行年",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "runyear": runyear,
        "liureng": liureng,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("奇门遁甲")
def calculate_qimen_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    analysis_longitude: Optional[float] = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    qimen_options: Optional[Dict[str, Any]] = None,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    seed = _build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
        day_pillar_strategy=DAY_GANZHI_STRATEGY_STANDARD,
    )
    qimen = build_qimen_with_options(seed, qimen_options)
    qimen["engine"] = "fatebridge-offline"
    if analysis_utc_offset is not None:
        offset = seed.input_datetime.utcoffset()
        assert offset is not None
        resolution = {
            "method": "explicit_input_offset_checked_against_named_zone",
            "timezone": seed.timezone,
            "input_utc_offset": analysis_utc_offset,
            "resolved_utc_offset": format_utc_offset(offset),
            "fold": seed.input_datetime.fold,
            "instant_utc": utc_instant(seed.input_datetime).isoformat(),
        }
        qimen["calendar_policy"]["civil_clock_resolution"] = resolution
        qimen["rule_trace"].append(
            {
                "rule_id": "civil_clock_resolution",
                "source": "declared UTC offset checked against timezone rules",
                "section": "民用时刻消歧，非原典规则",
                "inputs": {
                    "timezone": seed.timezone,
                    "utc_offset": analysis_utc_offset,
                },
                "outputs": dict(resolution),
                "evidence_paths": ["qimen.calendar_policy.civil_clock_resolution"],
            }
        )
    snapshot_text = build_qimen_snapshot_text(seed=seed, qimen=qimen)
    snapshot_export = _build_snapshot_export(
        technique="qimen",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "奇门遁甲",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "qimen": qimen,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("太乙神数")
def calculate_taiyi_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    analysis_longitude: Optional[float] = None,
    gender: str = "未知",
    calculation_mode: str = "year",
    hour_profile: Optional[str] = None,
    month_profile: Optional[str] = None,
    year_profile: Optional[str] = None,
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = True,
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    seed = _build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    taiyi = build_taiyi_board(
        seed,
        gender=gender,
        calculation_mode=calculation_mode,
        hour_profile=hour_profile,
        month_profile=month_profile,
        year_profile=year_profile,
    )
    if analysis_utc_offset is not None:
        resolution = civil_clock_resolution(seed, analysis_utc_offset)
        taiyi["calendar_rules"]["civil_clock_resolution"] = resolution
        taiyi["calendar_summary"]["civil_clock_resolution"] = dict(resolution)
    taiyi["engine"] = "fatebridge-offline"
    snapshot_text = _build_taiyi_snapshot_text(seed=seed, taiyi=taiyi)
    snapshot_export = _build_snapshot_export(
        technique="taiyi",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "太乙神数",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "taiyi": taiyi,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("金口诀")
def calculate_jinkou_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: Optional[str] = None,
    analysis_utc_offset: Optional[str] = None,
    analysis_longitude: Optional[float] = None,
    gender: str = "未知",
    di_fen: Optional[str] = None,
    natal_branch: Optional[str] = None,
    birth_year_ganzhi: Optional[str] = None,
    year_fate_age: Optional[int] = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: Optional[List[str]] = None,
    is_diurnal: Optional[bool] = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> Dict[str, Any]:
    natal = confirmed_natal_branch(birth_year_ganzhi, natal_branch, year_fate_age)
    seed = _build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    local_liureng = build_liureng_board(
        seed,
        gender=gender,
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    local_liureng["engine"] = "fatebridge-offline"
    liureng = local_liureng
    jinkou = build_jinkou_board(
        seed,
        local_liureng,
        gender=gender,
        di_fen=di_fen,
        natal_branch=natal,
        natal_branch_source=(
            "explicit_natal_branch"
            if natal_branch is not None
            else "explicit_birth_year_ganzhi" if birth_year_ganzhi is not None else None
        ),
        is_diurnal_override=is_diurnal,
    )
    jinkou["natal_course"] = build_natal_course(
        seed,
        local_liureng,
        birth_year_ganzhi=birth_year_ganzhi,
        natal_branch=natal_branch,
        gender=gender,
        is_diurnal=is_diurnal,
    )
    jinkou["year_fate"] = build_jinkou_year_fate(
        seed,
        local_liureng,
        birth_year_ganzhi=birth_year_ganzhi,
        age=year_fate_age,
        gender=gender,
        natal_branch=natal_branch,
        is_diurnal=is_diurnal,
    )
    jinkou["rule_trace"].append(
        {
            "rule_id": "jinkou.birth_xun_year_fate",
            "source_url": jinkou["year_fate"]["source_url"],
            "source_section": jinkou["year_fate"]["source_section"],
            "result": {k: v for k, v in jinkou["year_fate"].items() if k != "course"},
        }
    )
    jinkou["rule_trace"].append(natal_course_trace(jinkou["natal_course"]))
    jinkou["engine"] = "fatebridge-offline"
    snapshot_text = _build_jinkou_snapshot_text(seed=seed, jinkou=jinkou)
    snapshot_export = _build_snapshot_export(
        technique="jinkou",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "金口诀",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "liureng": liureng,
        "jinkou": jinkou,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
