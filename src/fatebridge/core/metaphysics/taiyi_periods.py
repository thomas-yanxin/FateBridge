"""Jinjing monthly and hourly frames, with explicit modern clock conventions.

The classical rules and the calendar adapter are separate: resolved Jie/solstice
instants are astronomical, while civil-clock vs apparent-solar double hours are
named conventions. Neither is relabelled as a reconstructed Tang calendar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fatebridge.core.almanac import (
    SolarTerm,
    _solar_terms_for_context_year,
    get_solar_terms_for_year,
    is_calculated_solar_term,
    localize_datetime,
)
from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES, SOURCES
from fatebridge.core.solar_model_policy import solar_context_input_years
from fatebridge.utils.solar_time import calculate_equation_of_time_minutes

from .common import MetaphysicsSeed
from .taiyi_hour import (
    DEFAULT_HOUR_PROFILE,
    HOUR_PROFILES,
    KEY_HOUR_PROFILE,
    KEY_SOURCE,
)
from .taiyi_hour import double_hour_slot as _slot
from .taiyi_hour import key_hour_origin
from .taiyi_month import (
    DEFAULT_MONTH_PROFILE,
    KEY_MONTH_PROFILE,
    MONTH_PROFILES,
    jinjing_month_origin,
    key_month_origin,
    month_calendar_reference,
)
from .taiyi_origin_selection import winter_origin_selection
from .taiyi_year import assemble_board, calendar_summary, cyclic_core

JIE_ORDER = (
    "大雪",
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
)
MODE_LABELS = {"month": "月计", "hour": "时计"}
SOLAR_ANCHOR_SCOPE = (
    "记录本次实际采用的节气对象；resolution_provider是接口来源，ephemeris_model才是实际轨道模型。"
    "对象日名按其所标时区，不代替本盘所选钟面日名。"
    "钟时沿用声明的现代时标政策，1960年前为所选UT1/ΔT模型标签，1960—1971按已声明的漂移UTC适配；微秒输出不认证实测精度或原书古历。"
)


def _previous_term(instant: datetime, names: tuple[str, ...]) -> SolarTerm:
    """Compare UTC instants, including year and timezone/DST transitions."""
    utc = instant.astimezone(timezone.utc)
    # Source coverage belongs to the resolved civil input year, before UTC
    # or apparent-solar clock conversion. An endpoint input still needs the
    # previous year's winter/Jie; reuse the almanac's private guard without
    # authorizing a standalone request for that outside year.
    context_year = instant.year
    low, high = solar_context_input_years(context_year)
    candidates: List[SolarTerm] = []
    for year in range(max(1, context_year - 1), min(9999, context_year + 1) + 1):
        terms = (
            _solar_terms_for_context_year(year, "UTC", context_year)
            if low <= context_year <= high and not low <= year <= high
            else get_solar_terms_for_year(year, "UTC")
        )
        candidates.extend(t for t in terms if t.name in names and t.moment <= utc)
    if not candidates:
        raise ValueError("无法取得起盘之前的太乙节气锚点")
    term = max(candidates, key=lambda t: t.moment)
    if not is_calculated_solar_term(term):
        raise ValueError("太乙月/日/时计要求天文节气实刻，不能使用线性近似回退")
    return term


def _clock(moment: datetime, seed: MetaphysicsSeed) -> datetime:
    if seed.applied_true_solar:
        if seed.longitude is None:
            raise ValueError("太乙真太阳时计需要明确经度")
        utc = moment.astimezone(timezone.utc)
        # A local apparent clock is independent of the timezone representation
        # and of summer-time folds/gaps: UTC + longitude + equation of time.
        return utc.replace(tzinfo=None) + timedelta(
            minutes=4 * seed.longitude + calculate_equation_of_time_minutes(utc)
        )
    return moment.astimezone(
        localize_datetime(seed.input_datetime, seed.timezone).tzinfo
    ).replace(tzinfo=None)


def period_frame(
    seed: MetaphysicsSeed,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
) -> Dict[str, Any]:
    if month_profile is not None and (
        mode != "month"
        or not isinstance(month_profile, str)
        or month_profile not in MONTH_PROFILES
    ):
        raise ValueError("month_profile仅用于month，须选择已发布月计配置")
    if hour_profile is not None and (
        mode != "hour"
        or not isinstance(hour_profile, str)
        or hour_profile not in HOUR_PROFILES
    ):
        raise ValueError("hour_profile仅用于hour计法，须明确选择已发布时计配置")
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    from .taiyi_clock import validate_seed_civil_clock

    validate_seed_civil_clock(seed)
    if mode == "month":
        term = _previous_term(instant, JIE_ORDER)
        month_offset = JIE_ORDER.index(term.name)
        # Adapt vol.1's six year classes to the Gregorian year of 大雪.
        # This existing year-label choice is explicit in month_origin;
        # it does not adjudicate the source's 前十一月 wording.
        # January 小寒 belongs to the preceding 大雪-to-大雪 counting year.
        cycle_year = (
            term.moment.year
            if term.name == "大雪"
            else term.moment.year - int(term.name == "小寒")
        )
        if term.name not in ("大雪", "小寒"):
            cycle_year -= 1
        origin = jinjing_month_origin(cycle_year, month_offset)
        accumulation = origin["accumulation"]
        if month_profile == KEY_MONTH_PROFILE:
            origin = key_month_origin(cycle_year, month_offset)
            accumulation = origin["accumulation"]
        return {
            "accumulation": accumulation,
            "yin": False,
            "ruler_branch": BRANCHES[month_offset],
            "anchor": term,
            "cycle_year": cycle_year,
            "month_offset": month_offset,
            "month_origin": origin,
        }
    if mode != "hour":
        raise ValueError(
            "本节月/时计入口仅支持month/hour；其他计法请调用build_taiyi_board"
        )
    term = _previous_term(instant, ("冬至", "夏至"))
    anchor_clock = _clock(term.moment, seed)
    target_clock = _clock(instant, seed)
    if hour_profile == KEY_HOUR_PROFILE:
        winter = _previous_term(instant, ("冬至",))
        origin = key_hour_origin(_clock(winter.moment, seed), target_clock)
        origin.update(
            winter_anchor_utc=winter.moment.astimezone(timezone.utc).isoformat(),
            winter_anchor_provider=winter.resolution_provider,
        )
        return {
            "accumulation": origin["accumulation"],
            "yin": term.name == "夏至",
            "ruler_branch": BRANCHES[_slot(target_clock) % 12],
            "anchor": term,
            "anchor_clock": anchor_clock,
            "target_clock": target_clock,
            "hour_origin": origin,
            "winter_anchor": winter,
        }
    accumulation = _slot(target_clock) - _slot(anchor_clock) + 1
    if accumulation < 1:
        raise ValueError("太乙时计的时钟序列早于所选至点，不能静默倒推")
    return {
        "accumulation": accumulation,
        "yin": term.name == "夏至",
        "ruler_branch": BRANCHES[_slot(target_clock) % 12],
        "anchor": term,
        "anchor_clock": anchor_clock,
        "target_clock": target_clock,
    }


def build_period_board(
    seed: MetaphysicsSeed,
    gender: str,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
) -> Dict[str, Any]:
    from .taiyi_gates import attach_gate_board

    instant = localize_datetime(seed.input_datetime, seed.timezone)
    frame = period_frame(seed, mode, hour_profile, month_profile)
    is_key_month = mode == "month" and month_profile == KEY_MONTH_PROFILE
    is_key_hour = mode == "hour" and hour_profile == KEY_HOUR_PROFILE
    core = cyclic_core(frame["accumulation"], yin=frame["yin"])
    ruler = frame["ruler_branch"]
    # A month/hour branch is a time label, not the annual 太岁. Do not put it
    # in suijun or render the annual name on a monthly/hourly board.
    core["ruler_branch"] = ruler
    core["ruler_label"] = "月建" if mode == "month" else "时支"
    # Monthly 合神 is the month's branch partner (六纪月建). Hourly 合神
    # uses the day: vol. 1's 庚申日/戊寅时 worked example explicitly gives 巳.
    he_anchor = seed.pillars["day"][1] if mode == "hour" and not is_key_hour else ruler
    core["heshen"] = BRANCHES[(1 - BRANCHES.index(he_anchor)) % 12]
    board: Dict[str, Any] = assemble_board(core, calculation_mode=mode)
    term = frame["anchor"]
    label = MODE_LABELS[mode]
    profile = DEFAULT_MONTH_PROFILE if mode == "month" else "jinjing_hour_solstice_v1"
    if is_key_hour:
        profile = KEY_HOUR_PROFILE
    if is_key_month:
        profile = KEY_MONTH_PROFILE
    board["solar_anchors"] = {
        "boundary": term.as_dict(),
        **(
            {"winter_origin": frame["winter_anchor"].as_dict()}
            if "winter_anchor" in frame
            else {}
        ),
    }
    board["solar_anchor_scope"] = SOLAR_ANCHOR_SCOPE
    calendar = {
        "calculation_mode": mode,
        "civil_datetime": localize_datetime(
            seed.input_datetime, seed.timezone
        ).isoformat(),
        "timezone": seed.timezone,
        "anchor_name": term.name,
        "anchor_utc": term.moment.astimezone(timezone.utc).isoformat(),
        "anchor_provider": term.resolution_provider,
        "counter": frame["accumulation"],
        "boundary_instant_basis": "civil_utc_instant",
        "ruler_branch_basis": (
            "solar_month_branch" if mode == "month" else "selected_clock_hour_branch"
        ),
        "heshen_branch_basis": (
            "solar_month_branch" if mode == "month" else "day_pillar_branch"
        ),
        "counter_rule_source": SOURCES["1"]
        + ("#推六紀月建法" if mode == "month" else "#推冬夏二至以後太乙所在法"),
        "anchor_precision": "按秒返回的天文求解；独立年历按分钟验收，不认证亚秒实测精度",
        "seconds_from_anchor": (
            instant.astimezone(timezone.utc) - term.moment
        ).total_seconds(),
    }
    if mode == "month":
        calendar.update(
            {
                "cycle_year": frame["cycle_year"],
                "month_offset": frame["month_offset"],
                "leap_month_policy": "十二节月，每逢节换月；闰农历月不另增计数",
                "clock_basis": "astronomical_jie_instant",
                "counter_formula": "(1937281 + counted_year - 724 - 1) * 12 + month_offset + 1",
            }
        )
        if is_key_month:
            origin = frame["month_origin"]
            reference = month_calendar_reference(instant.date(), origin)
            if reference:
                origin["calendar_reference"] = reference
            calendar.update(
                input_calendar="proleptic_gregorian",
                month_profile=KEY_MONTH_PROFILE,
                month_origin=origin,
                counter_rule_source=KEY_SOURCE,
                counter_formula="(10155478 + nominal_year - 1561 - 1) * 12 + 2 + nominal_month",
                modern_conventions="天地二正积月规则按现代节月月序适配；寅月换名义年，闰朔月不额外增数，不是原书古历月界复原。",
            )
        else:
            calendar.update(
                input_calendar="proleptic_gregorian",
                month_profile=DEFAULT_MONTH_PROFILE,
                month_origin=frame["month_origin"],
                counter_rule_source=SOURCES["1"],
                modern_conventions=frame["month_origin"]["year_label_policy"]
                + frame["month_origin"]["scope"],
            )
    else:
        calendar.update(
            {
                "hour_profile": hour_profile or DEFAULT_HOUR_PROFILE,
                "clock_basis": (
                    "local_apparent_solar"
                    if seed.applied_true_solar
                    else "civil_wall_clock"
                ),
                "anchor_clock": frame["anchor_clock"].isoformat(),
                "target_clock": frame["target_clock"].isoformat(),
                "double_hour_start": "23:00_Zi",
                "initial_interval": "至点实刻立即换遁并从1计起，至点所在时辰只计一次，下一时辰边界加一",
                "modern_conventions": "至点实刻置一及23时子初边界的现代适配；并非完整古历时实复原",
                "dst_policy": (
                    "真太阳钟由UTC瞬间与经度计算，不随夏令时跳变"
                    if seed.applied_true_solar
                    else "钟表标签按IANA时区重复或跳过；不是恒定UTC历时计数"
                ),
                "counter_formula": "target_slot - anchor_slot + 1",
                "target_slot": _slot(frame["target_clock"]),
                "anchor_slot": _slot(frame["anchor_clock"]),
            }
        )
        if is_key_hour:
            from .taiyi_historical import source_date_reference

            calendar.update(
                input_calendar="proleptic_gregorian",
                hour_origin=frame["hour_origin"],
                heshen_branch_basis="selected_clock_hour_branch",
                counter_rule_source=KEY_SOURCE,
                counter_formula="(day_number_from_winter_previous_Jiazi - 1) * 12 + hour_number",
                initial_interval="积时从冬至前甲子日子初连续计算；二至仅换遁，夏至不把积时归一",
                modern_conventions="冬至前甲子日计数取所选现代钟面，23时子初换日；不等同原书古历夜半或完整唐历时实",
            )
            reference = source_date_reference(
                datetime.fromisoformat(
                    frame["hour_origin"]["target_effective_date"]
                ).date(),
                "hour",
                frame["accumulation"],
                frame["hour_origin"]["target_day_ganzhi"],
                ruler,
            )
            if reference:
                calendar["historical_date_reference"] = reference
    board.update(
        {
            "style_label": f"太乙金镜式经·{label}",
            "accumulation_label": f"{label}{'节月积数' if mode == 'month' else '至点后时实序数'}：{frame['accumulation']}",
            "rotation": "逆布" if frame["yin"] else "顺布",
            "life_method": f"{label}（性别不参与定局）",
            "calendar_rules": calendar,
            "ruleset": {
                "id": profile,
                "version": (
                    "1.2.0" if mode == "month" and not is_key_month else "1.0.0"
                ),
                "author": "FateBridge contributors",
                "classical_author": "唐·王希明",
                "source_title": "太乙金镜式经（四库全书本）",
                "source_kind": "classical_transcription_and_selected_facsimile_with_explicit_modern_calendar_adapter",
                "sources": (
                    {
                        **SOURCES,
                        "month_nominal_year_wujing": "https://zh.wikisource.org/wiki/武經總要_(四庫全書本)/後集卷18",
                        "month_nominal_year_key_appendix": "https://upload.wikimedia.org/wikipedia/commons/1/19/NLC892-411999021066-66022_%E5%A4%AA%E4%B9%99%E9%87%91%E9%91%B0%E5%8C%99.pdf#page=47",
                    }
                    if mode == "month" and not is_key_month
                    else SOURCES
                ),
                "time_granularity": "solar_month" if mode == "month" else "double_hour",
                "classical_conformance": "partial_with_unresolved_table_and_calendar_adaptation_questions",
                "classical_acceptance_passed": False,
                "real_world_efficacy": "not_tested",
                "unresolved": [
                    "阳局39/50及阴局多处表文与通则不一致，未据程序修改原典读数。",
                    "以现代天文节气实刻适配原典规则，尚未复原书中缺讹的历法常数。",
                    (
                        "时计至点置一、时辰边界及合神取日支的范围需继续独立课例裁定。"
                        if mode == "hour"
                        else "采用卷一六纪节月法；未混用章岁章月求积月的另一套常数法。"
                    ),
                    "完整命法、日计、三基五福及全格局断法仍需独立验收。",
                ],
            },
            "interpretation_scope": {
                "calculation": f"{label}阴阳局、二目、计神、主客算及四将",
                "traditional_interpretation": "只解读实际命中的来源规则，不以未返回格局推断吉凶",
                "gender_used": False,
                "real_world_prediction": "不返回事件概率或权威认证",
            },
        }
    )
    board["calendar_summary"] = calendar_summary(board)
    if is_key_month:
        board["style_label"] = "太乙金钥匙续集·月计现代节月适配"
        board["accumulation_label"] = f"月计天地二正完整积月：{frame['accumulation']}"
        board["ruleset"].update(
            classical_author="《太乙金钥匙续集》底本题署，续集作者未独立考定",
            source_title="太乙金钥匙续集·月计（NLC892-411999021066-66022）",
            sources={
                "key": KEY_SOURCE,
                "shared_count_rules": SOURCES["2"],
                "shared_relation_rules": SOURCES["3"],
            },
            unresolved=[
                "天地二正积月起元与金镜六纪节月起元分开；边界仍用现代节月，不能认作完整古历或原例朔月范围全符。",
                "原例前段截数695，门段684、余184、死门第4月互不相合，双方保留，不按有利门值选择。",
                "所直门加定计目；太乙主客三门核对主体尚未独立裁定，不借王法三门判断补齐。",
                "课式壬子元第四缺完整局数；全盘断语及年度十神不因数值重放而认证。",
            ],
        )
    if is_key_hour:
        board["accumulation_label"] = f"时计冬至前甲子积时：{frame['accumulation']}"
        board["style_label"] = "太乙金钥匙续集·时计现代日期适配"
        board["ruleset"].update(
            classical_author="《太乙金钥匙续集》底本题署，作者未独立考定",
            source_title="太乙金钥匙续集（NLC892-411999021066-66022）",
            sources={
                "key": KEY_SOURCE,
                "shared_count_rules": SOURCES["2"],
                "shared_relation_rules": SOURCES["3"],
                "shared_five_general_clauses": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷04",
            },
            unresolved=[
                "现代冬至、时钟和23时子初为明示适配；本书古历年月日、子正夜半及岁差常数未完整复原。",
                "本例47为只求行宫的捷数；文昌沿用完整积时所得23局，不拿47冒充完整积时。",
                "本书庚戌例定计写33算、大将3、参将9；按逐项算路得到32/2/6；同相位在定计结果保留双方，未裁定底本。",
                "夏至阴遁用本书阴局与四门序，连续积时不重置；独立夏至全盘古例验收尚缺。",
                "本书太乙主客三门主体与门具将发课语未裁定；不把已布八门当三门已评估。",
                "主客算原表未决异文及完整断法仍需独立验收。",
                "空间七类与卷四三项五将层分别援用已注明的金镜来源，不当作金钥匙全套断语。",
            ],
        )
    if is_key_hour:
        board["winter_origin_selection"] = winter_origin_selection(
            frame["hour_origin"],
            board["solar_anchors"]["winter_origin"],
            calendar["clock_basis"],
        )
    board["long_cycles"] = {
        "status": "not_computed_for_selected_mode",
        "selected_mode": mode,
        "time_granularity": "year",
        "interpretation_scope": "本盘不混入年度十神；需要年度背景时另选year并区分时间层。",
    }
    board["extra_palace_marks"] = []
    board["long_cycle_summary"] = {
        "status": "not_computed_for_selected_mode",
        "time_granularity": "year",
        "scope": "本盘未附年度十神，不从月/时积数外推。",
    }
    attach_gate_board(board, mode)
    return board
