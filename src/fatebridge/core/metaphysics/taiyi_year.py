"""Calculate the cyclic core and annual Taiyi calendar board."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import (
    get_lunar_context,
    localize_datetime,
    lunar_supported_range_message,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed, chinese_numeral
from fatebridge.core.metaphysics.taiyi_board import assemble_board, calendar_summary
from fatebridge.core.metaphysics.taiyi_civil_calendar import civil_lunar_evidence
from fatebridge.core.metaphysics.taiyi_counts import count_labels
from fatebridge.core.metaphysics.taiyi_gates import attach_gate_board
from fatebridge.core.metaphysics.taiyi_geometry import (
    BRANCHES,
    PALACES,
    RING,
    SOURCES,
    count_to_taiyi,
    general_for_count,
)
from fatebridge.core.metaphysics.taiyi_long_cycles import attach_long_cycles
from fatebridge.core.metaphysics.taiyi_shiji import resolve_shiji_variant
from fatebridge.core.metaphysics.taiyi_year_calendar import (
    HISTORICAL_YEAR_PROFILE,
    HISTORICAL_YEAR_PROFILES,
    YEAR_PROFILES,
    historical_year_context,
)

RULESET_ID = "jinjing_year_core_v1"


def cyclic_core(
    accumulation: int, *, yin: bool = False, shiji_profile: str | None = None
) -> dict[str, Any]:
    """The two 72-ju cores, independent of a civil/calendar accumulation rule.

    Vol. 1 gives Yang from 乾 and Yin from 巽, three units per palace;
    vol. 3 freezes both tables. Counts always follow the counting ring from
    vol. 2: Yin reverses Taiyi and reflects the eyes, not the arithmetic path.
    """
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("太乙积数必须是正整数")
    ju = (accumulation - 1) % 72 + 1
    taiyi_number = (1, 2, 3, 4, 6, 7, 8, 9)[((accumulation - 1) % 24) // 3]
    # Vol. 1: start at 武德申; repeat 阴德乾 and 大武坤.
    eyes_cycle = "申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤"
    eyes = eyes_cycle[(accumulation - 1) % 18]
    if yin:
        taiyi_number = 10 - taiyi_number
        eyes = RING[(RING.index(eyes) + 8) % 16]
    jishen = BRANCHES[((8 if yin else 2) - (accumulation - 1)) % 12]
    starting_spirit = resolve_shiji_variant(
        yin=yin,
        ju=ju,
        wenchang=eyes,
        jishen=jishen,
        shiji_profile=shiji_profile,
    )
    shiji = starting_spirit["shiji"]
    home = count_to_taiyi(eyes, taiyi_number)
    guest = count_to_taiyi(shiji, taiyi_number)
    printed_guest_count = starting_spirit["guest_count_override"]
    guest_count = guest["count"] if printed_guest_count is None else printed_guest_count
    guest_trace = dict(guest)
    if printed_guest_count is not None:
        guest_trace.update(
            selected_count=printed_guest_count,
            selected_count_basis="卷三原表字面；count与path保留卷二重算",
        )
    main_general = general_for_count(home["count"])
    guest_general = general_for_count(guest_count)
    return {
        "accumulation": accumulation,
        "yin_dun": yin,
        "kook_number": ju,
        "main_calculation": f"{'陰' if yin else '陽'}遁{chinese_numeral(ju)}局",
        "taiyi_number": taiyi_number,
        "taiyi_palace": PALACES[taiyi_number],
        "wenchang_palace": eyes,
        "jishen": jishen,
        "shiji": shiji,
        "shiji_profile": starting_spirit["profile"],
        **(
            {"requested_shiji_profile": starting_spirit["requested_profile"]}
            if starting_spirit["requested_profile"] != starting_spirit["profile"]
            else {}
        ),
        "main_count": home["count"],
        "guest_count": guest_count,
        "main_count_des": count_labels(home["count"]),
        "guest_count_des": count_labels(guest_count),
        "main_general": main_general,
        "guest_general": guest_general,
        "main_vice_general": main_general * 3 % 10,
        "guest_vice_general": guest_general * 3 % 10,
        "count_trace": {"main": home, "guest": guest_trace},
    }


def yearly_core(year: int, *, shiji_profile: str | None = None) -> dict[str, Any]:
    """Resolve a CE year using vol. 1's 724 CE = 1,937,281 anchor."""
    if type(year) is not int or year < 1:
        raise ValueError("年计需要正整数公元年份")
    accumulation = 1937281 + year - 724
    core = cyclic_core(accumulation, shiji_profile=shiji_profile)
    core.update(
        {
            "kook_year": ("理天", "理地", "理人")[(accumulation - 1) % 3],
            "suijun": BRANCHES[(year - 4) % 12],
            "heshen": BRANCHES[(1 - (year - 4)) % 12],
        }
    )
    return core


def build_year_board(
    seed: MetaphysicsSeed,
    gender: str,
    year_profile: str | None = None,
    *,
    shiji_profile: str | None = None,
) -> dict[str, Any]:

    # Yearly counting uses the input civil date. Apparent-solar correction of
    # an hourly pillar must not move lunar new year across civil midnight.
    if year_profile is not None and (
        not isinstance(year_profile, str) or year_profile not in YEAR_PROFILES
    ):
        raise ValueError("year_profile须明确选择已发布年计配置")
    historical = (
        historical_year_context(
            localize_datetime(seed.input_datetime, seed.timezone).date(),
            profile=year_profile,
        )
        if year_profile is not None and year_profile in HISTORICAL_YEAR_PROFILES
        else None
    )
    lunar = (
        historical
        if historical
        else get_lunar_context(seed.input_datetime, timezone_name=seed.timezone)
    )
    if lunar is None:
        raise ValueError("太乙年计需要农历年，" + lunar_supported_range_message())
    year_value = lunar["year"]
    if not isinstance(year_value, int):
        raise ValueError("太乙年计农历年份必须是整数")
    year = year_value
    core = yearly_core(year, shiji_profile=shiji_profile)
    board = assemble_board(core, calculation_mode="year")
    board.update(
        {
            "engine": "fatebridge-offline",
            "style_label": "太乙金镜式经·年计核心",
            "accumulation_label": f"年计积年数：{core['accumulation']}",
            "rotation": "顺布",
            "life_method": "年计（性别不参与定局）",
            "calendar_rules": {
                "year": year,
                "year_boundary": "lunar_new_year_civil_date",
                "year_boundary_status": "modern_profile_convention_not_adjudicated_from_classic",
                "year_ganzhi": "甲乙丙丁戊己庚辛壬癸"[(year - 4) % 10] + core["suijun"],
                "civil_datetime": localize_datetime(
                    seed.input_datetime, seed.timezone
                ).isoformat(),
                "timezone": seed.timezone,
                "solar_correction_affects_year": False,
                "pillars_role": "四柱是时间上下文；太岁与合神按本年计农历年计算",
            },
            "ruleset": {
                "id": RULESET_ID,
                "version": "1.0.0",
                "author": "FateBridge contributors",
                "classical_author": "唐·王希明",
                "source_title": "太乙金镜式经（四库全书本）",
                "source_kind": "public_domain_transcription_with_selected_facsimile_checks",
                "sources": SOURCES,
                "time_granularity": "year",
                "classical_conformance": "partial_with_unresolved_rule_table_disagreements",
                "classical_acceptance_passed": False,
                "real_world_efficacy": "not_tested",
                "unresolved": [
                    "卷三阳局39主算25、局50主算6已核CADAL06056494影像111/112页，依卷二通则算得35/16；底本表文与通则冲突，待外部裁定。",
                    "岁首采用现代农历正月初一的工程约定，未完成古历岁首复原。",
                    "卷五年运十神已独立起元；直符中元表及额外三宫对应仍待校勘；地乙起九有明钞本补证，积年不混换版本，不能宣称全书通过。",
                    "月/日/时计另有配置；定目定算有金钥匙等后本独立补证，门盘有明确方法范围，各计完整古历、玄命与完整格局断验未完成。",
                ],
            },
            "interpretation_scope": {
                "calculation": "年计太乙、二目、计神、主客算及四将，含逐项计数路径",
                "traditional_interpretation": "解释实际命中的掩、击、迫、囚、关、格、对空间条件及三才数字分类",
                "real_world_prediction": "未做独立前瞻检验；不返回事件概率或权威认证",
                "gender_used": False,
            },
        }
    )
    if not historical:
        board["calendar_rules"]["civil_lunar_calendar"] = civil_lunar_evidence(
            lunar, localize_datetime(seed.input_datetime, seed.timezone).date()
        )
    if historical:
        board["calendar_rules"].update(
            year_profile=year_profile,
            input_calendar="proleptic_gregorian",
            historical_calendar=historical,
            year_boundary="historical_printed_lunar_new_year_civil_date",
            year_boundary_status="printed_calendar_boundary_used_classic_year_boundary_not_adjudicated",
            pillars_role=(
                "太乙岁首使用所选晋历主表；四柱仍是独立的现代节气/所选钟面上下文，不用四柱年替代历史年。"
                if year_profile == HISTORICAL_YEAR_PROFILE
                else "太乙岁首使用所选齐梁史历表；四柱仍是独立的现代节气/所选钟面上下文，不用四柱年替代历史年；502年闰标分歧随同次历表回执保留。"
            ),
        )
        board["ruleset"]["unresolved"] = [
            (
                "历史历表只覆盖381至385完整五年，晋历主表不代表并立王朝的统一历法；原典年计岁首语义、古代地点钟制与完整古历常数仍未裁定。"
                if year_profile == HISTORICAL_YEAR_PROFILE
                else "所选齐梁史历表只覆盖501至505完整五年，保留502年闰四月及未决算法候选；不代表北朝异历、王氏同元四分历或逐日改元裁定；原典年计岁首语义、古代地点钟制与完整古历仍未裁定。"
            ),
            *[
                s
                for s in board["ruleset"]["unresolved"]
                if not s.startswith("岁首采用现代")
            ],
        ]
    board["calendar_summary"] = calendar_summary(board)
    attach_long_cycles(board, year)
    attach_gate_board(board, "year", year)
    return board
