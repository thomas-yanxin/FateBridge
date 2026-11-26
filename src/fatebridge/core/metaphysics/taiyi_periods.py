"""Build Taiyi month and hour boards from their selected calendar frames."""

from __future__ import annotations

from datetime import date
from typing import Any

from fatebridge.core.almanac import elapsed_seconds_between, localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.taiyi_board import assemble_board, calendar_summary
from fatebridge.core.metaphysics.taiyi_clock import SOLAR_ANCHOR_SCOPE
from fatebridge.core.metaphysics.taiyi_gates import attach_gate_board
from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES
from fatebridge.core.metaphysics.taiyi_historical import source_date_reference
from fatebridge.core.metaphysics.taiyi_hour import (
    DEFAULT_HOUR_PROFILE,
    KEY_HOUR_PROFILE,
    double_hour_slot,
)
from fatebridge.core.metaphysics.taiyi_month import (
    DEFAULT_MONTH_PROFILE,
    KEY_MONTH_PROFILE,
    month_calendar_reference,
)
from fatebridge.core.metaphysics.taiyi_origin_selection import winter_origin_selection
from fatebridge.core.metaphysics.taiyi_period_frame import period_frame as period_frame
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.utils.civil_time import gregorian_date_parts

MODE_LABELS = {"month": "月计", "hour": "时计"}


def build_period_board(
    seed: MetaphysicsSeed,
    gender: str,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
    *,
    shiji_profile: str | None = None,
) -> dict[str, Any]:

    instant = localize_datetime(seed.input_datetime, seed.timezone)
    frame = period_frame(seed, mode, hour_profile, month_profile)
    is_key_month = mode == "month" and month_profile == KEY_MONTH_PROFILE
    is_key_hour = mode == "hour" and hour_profile == KEY_HOUR_PROFILE
    hour_clock_basis = (
        "local_apparent_solar" if seed.applied_true_solar else "civil_wall_clock"
    )
    core = cyclic_core(
        frame["accumulation"], yin=frame["yin"], shiji_profile=shiji_profile
    )
    ruler = frame["ruler_branch"]
    # A month/hour branch is a time label, not the annual 太岁. Do not put it
    # in suijun or render the annual name on a monthly/hourly board.
    core["ruler_branch"] = ruler
    core["ruler_label"] = "月建" if mode == "month" else "时支"
    # Monthly 合神 is the month's branch partner (六纪月建). Hourly 合神
    # uses the day: vol. 1's 庚申日/戊寅时 worked example explicitly gives 巳.
    he_anchor = seed.pillars["day"][1] if mode == "hour" and not is_key_hour else ruler
    core["heshen"] = BRANCHES[(1 - BRANCHES.index(he_anchor)) % 12]
    board: dict[str, Any] = assemble_board(core, calculation_mode=mode)
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
        "anchor_utc": term.calendar.utc.isoformat(),
        "anchor_provider": term.resolution_provider,
        "counter": frame["accumulation"],
        "boundary_instant_basis": "civil_utc_instant",
        "ruler_branch_basis": (
            "solar_month_branch" if mode == "month" else "selected_clock_hour_branch"
        ),
        "heshen_branch_basis": (
            "solar_month_branch" if mode == "month" else "day_pillar_branch"
        ),
        "anchor_precision": "以保留民用主点选锚并计算距锚秒数；独立年历按分钟验收",
        "seconds_from_anchor": elapsed_seconds_between(term.point, instant),
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
                counter_formula="(10155478 + nominal_year - 1561 - 1) * 12 + 2 + nominal_month",
                modern_conventions="天地二正积月规则按现代节月月序适配；寅月换名义年，闰朔月不额外增数，不是原书古历月界复原。",
            )
        else:
            calendar.update(
                input_calendar="proleptic_gregorian",
                month_profile=DEFAULT_MONTH_PROFILE,
                month_origin=frame["month_origin"],
                modern_conventions=frame["month_origin"]["year_label_policy"]
                + frame["month_origin"]["scope"],
            )
    else:
        target_hour_slot = double_hour_slot(frame["target_clock"])
        calendar.update(
            {
                "hour_profile": hour_profile or DEFAULT_HOUR_PROFILE,
                "clock_basis": hour_clock_basis,
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
                "target_slot": target_hour_slot,
                "anchor_slot": double_hour_slot(frame["anchor_clock"]),
            }
        )
        if is_key_hour:

            calendar.update(
                input_calendar="proleptic_gregorian",
                hour_origin=frame["hour_origin"],
                heshen_branch_basis="selected_clock_hour_branch",
                counter_formula="(day_number_from_winter_previous_Jiazi - 1) * 12 + hour_number",
                initial_interval="积时从冬至前甲子日子初连续计算；二至仅换遁，夏至不把积时归一",
                modern_conventions="冬至前甲子日计数取所选现代钟面，23时子初换日；不等同原书古历夜半或完整唐历时实",
            )
            year, month, day = gregorian_date_parts(target_hour_slot // 12)
            historical_reference = (
                source_date_reference(
                    date(year, month, day),
                    "hour",
                    frame["accumulation"],
                    frame["hour_origin"]["target_day_ganzhi"],
                    ruler,
                )
                if 1 <= year <= 9999
                else None
            )
            if historical_reference:
                calendar["historical_date_reference"] = historical_reference
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
                "time_granularity": "solar_month" if mode == "month" else "double_hour",
                "classical_conformance": "partial_with_unresolved_table_and_calendar_adaptation_questions",
                "classical_acceptance_passed": False,
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
            hour_clock_basis,
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
