"""Source-scoped Taiyi cyclic arithmetic and annual calendar adapter.

Rules: Wang Ximing, Taiyi Jinjing Shijing, Siku text, volumes 1/2/3/6/9.
The cyclic arithmetic is implemented here; the independent volume-3 oracle
lives only in tests. Rule/table conflicts remain open; selected facsimile
pages confirm the disputed table readings rather than resolving the conflicts.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.core.almanac import (
    get_lunar_context,
    localize_datetime,
    lunar_supported_range_message,
)
from fatebridge.core.metaphysics.taiyi_geometry import (
    BRANCHES,
    PALACES,
    RING,
    SOURCES,
    count_to_taiyi,
    general_for_count,
)

from .common import MetaphysicsSeed, chinese_numeral
from .taiyi_civil_calendar import civil_lunar_evidence, civil_lunar_text
from .taiyi_conditions import conditions_text, five_general_conditions
from .taiyi_cycles import counter_cycles, counter_cycles_text

DISPLAY_ORDER = "巽巳午未坤申酉戌乾亥子丑艮寅卯辰"
RULESET_ID = "jinjing_year_core_v1"


def count_categories(count: int) -> List[str]:
    """Literal missing-count labels, named numeric inference and sourced 杜塞."""
    from .taiyi_counts import count_labels

    return count_labels(count)


def cyclic_core(accumulation: int, *, yin: bool = False) -> Dict[str, Any]:
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
    from .taiyi_shiji import rotate_shiji

    shiji = rotate_shiji(eyes, jishen)["derived_shiji"]
    home = count_to_taiyi(eyes, taiyi_number)
    guest = count_to_taiyi(shiji, taiyi_number)
    main_general = general_for_count(home["count"])
    guest_general = general_for_count(guest["count"])
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
        "main_count": home["count"],
        "guest_count": guest["count"],
        "main_count_des": count_categories(home["count"]),
        "guest_count_des": count_categories(guest["count"]),
        "main_general": main_general,
        "guest_general": guest_general,
        "main_vice_general": main_general * 3 % 10,
        "guest_vice_general": guest_general * 3 % 10,
        "count_trace": {"main": home, "guest": guest},
    }


def yearly_core(year: int) -> Dict[str, Any]:
    """Resolve a CE year using vol. 1's 724 CE = 1,937,281 anchor."""
    if type(year) is not int or year < 1:
        raise ValueError("年计需要正整数公元年份")
    accumulation = 1937281 + year - 724
    core = cyclic_core(accumulation)
    core.update(
        {
            "kook_year": ("理天", "理地", "理人")[(accumulation - 1) % 3],
            "suijun": BRANCHES[(year - 4) % 12],
            "heshen": BRANCHES[(1 - (year - 4)) % 12],
        }
    )
    return core


def structural_patterns(core: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate vol. 3's spatial conditions without inventing event outcomes.

    The individual reading of 囚 is independently supported by vol. 3 ju 1's
    主参一乾(囚); requiring all four generals to be with Taiyi would make the
    rule impossible away from center five. 上目无迫 is explicitly respected.
    """
    taiyi = core["taiyi_palace"]
    center = RING.index(taiyi)
    opposite = RING[(center + 8) % 16]
    positions = {"wenchang_palace": core["wenchang_palace"], "shiji": core["shiji"]}
    labels = {
        "wenchang_palace": "文昌",
        "shiji": "始击",
        "main_general": "主大将",
        "main_vice_general": "主参将",
        "guest_general": "客大将",
        "guest_vice_general": "客参将",
    }
    for field in (
        "main_general",
        "main_vice_general",
        "guest_general",
        "guest_vice_general",
    ):
        positions[field] = PALACES[core[field]]
    result: List[Dict[str, Any]] = []

    def fact(field: str) -> Dict[str, Any]:
        return {
            "field": (
                field
                if field in {"wenchang_palace", "taiyi_palace"}
                else "core_board." + field
            ),
            "value": core[field],
        }

    def add(
        name: str,
        subject: str,
        meaning: str,
        section: str,
        *,
        other: str = "taiyi_palace",
        variant: str | None = None,
    ) -> None:
        result.append(
            {
                "name": name,
                "subject": labels[subject],
                "variant": variant or name,
                "basis": [fact(subject), fact(other)],
                "traditional_meaning": meaning,
                "source": SOURCES["3"] + "#" + section,
                "scope": "原典空间条件；尚需全盘条件，不能单条推出事件成败",
            }
        )

    for field, palace in positions.items():
        if palace == taiyi:
            if field == "shiji":
                add("掩", field, "始击与太乙同宫", "推掩法")
            else:
                add("囚", field, f"{labels[field]}与太乙同宫", "推囚法")
        if palace == opposite:
            if field == "wenchang_palace":
                add("对", field, "文昌与太乙对宫", "推對法")
            elif field in {"shiji", "guest_general", "guest_vice_general"}:
                add("格", field, f"{labels[field]}与太乙对宫", "推格法")
        if palace not in RING:
            continue  # Center has no ring bearing; do not manufacture one.
        distance = (RING.index(palace) - center) % 16
        if distance not in (1, 2, 14, 15):
            continue
        forward = distance in (1, 2)
        adjacent_spirit = distance in (1, 15)
        if field == "shiji":
            variant = (
                ("前击" if forward else "后击")
                if adjacent_spirit
                else ("外宫击" if forward else "内宫击")
            )
            add(
                "击",
                field,
                f"始击在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                "推撃法",
                variant=variant,
            )
        else:
            variant = ("外" if forward else "内") + (
                "辰迫" if adjacent_spirit else "宫迫"
            )
            add(
                "迫",
                field,
                f"{labels[field]}在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                "推迫法",
                variant=variant,
            )
    for main in ("main_general", "main_vice_general"):
        for guest in ("guest_general", "guest_vice_general"):
            if positions[main] == positions[guest]:
                add(
                    "关",
                    main,
                    f"{labels[main]}与{labels[guest]}同宫",
                    "推闗法",
                    other=guest,
                )
    from .taiyi_enclosures import principal_enclosures
    from .taiyi_eye_relations import eye_general_relations

    result.extend(principal_enclosures(core))
    # Append so all previously emitted relation indices remain stable.
    result.extend(eye_general_relations(core))
    return result


def assemble_board(
    core: Dict[str, Any], *, calculation_mode: str | None = None
) -> Dict[str, Any]:
    """Place every supported marker and attach same-core explanations."""
    from .taiyi_counts import count_assessment
    from .taiyi_elemental_relations import elemental_guan_assessment
    from .taiyi_enclosures import enclosure_assessment
    from .taiyi_oppositions import opposition_assessment, opposition_summary
    from .taiyi_shiji import shiji_derivation
    from .taiyi_source_alignment import count_source_assessment
    from .taiyi_victory_matrix import victory_matrix_assessment

    marks: Dict[str, List[str]] = {palace: [] for palace in DISPLAY_ORDER + "中"}
    placements = {
        "太乙": core["taiyi_palace"],
        "文昌": core["wenchang_palace"],
        "始击": core["shiji"],
        core.get("ruler_label", "太歲"): (
            core["ruler_branch"] if "ruler_branch" in core else core["suijun"]
        ),
        "合神": core["heshen"],
        "計神": core["jishen"],
    }
    for label, field in (
        ("主大", "main_general"),
        ("主參", "main_vice_general"),
        ("客大", "guest_general"),
        ("客參", "guest_vice_general"),
    ):
        placements[label] = PALACES[core[field]]
    for label, palace in placements.items():
        marks[palace].append(label)
    patterns = structural_patterns(core)
    oppositions = opposition_assessment(core)
    opposition_digest = opposition_summary(oppositions)
    enclosures = enclosure_assessment(patterns, core=core)
    source_alignment = count_source_assessment(core)
    source_warning = (
        {"source_table_warning": source_alignment["summary"]}
        if source_alignment["status"] != "not_assessed"
        and source_alignment["summary"]["status"] == "differences_unadjudicated"
        else {}
    )
    return {
        "engine": "fatebridge-offline",
        "counter_cycles": counter_cycles(core, calculation_mode=calculation_mode),
        "taiyi_palace": core["taiyi_palace"],
        "wenchang_palace": core["wenchang_palace"],
        "core_board": {
            **{
                key: value
                for key, value in core.items()
                if key not in {"taiyi_palace", "wenchang_palace", "count_trace"}
            },
            "taiyi_position": f"太乙在{core['taiyi_palace']}宫（{core['taiyi_number']}）",
            "wenchang_position": f"文昌在{core['wenchang_palace']}宫",
        },
        "palace_marks": [
            {"palace": palace, "markers": sorted(marks[palace])}
            for palace in DISPLAY_ORDER
        ],
        "center_marks": {"palace": "中", "markers": sorted(marks["中"])},
        "rule_trace": core["count_trace"],
        "patterns": patterns,
        "enclosure_assessment": enclosures,
        "opposition_assessment": oppositions,
        "condition_assessment": five_general_conditions(patterns, core=core),
        "count_assessment": count_assessment(core),
        "count_source_assessment": source_alignment,
        "shiji_derivation": shiji_derivation(core),
        "victory_matrix_assessment": victory_matrix_assessment(
            core, calculation_mode=calculation_mode
        ),
        "elemental_guan_assessment": elemental_guan_assessment(
            core, patterns, calculation_mode=calculation_mode
        ),
        "pattern_summary": {
            **source_warning,
            "pair_enclosures": len(enclosures["two_general_enclosure"]["patterns"]),
            "main_oppositions": opposition_digest["main_oppositions"],
            "opposition_source_disagreements": opposition_digest[
                "source_disagreements"
            ],
            "conditions": [
                {key: p[key] for key in ("name", "subject", "variant")}
                for p in patterns
            ],
            "source": SOURCES["3"],
            "scope": "仅所核空间条件，含将目关掩；主方对宫几何及格/对异称另见opposition_assessment。逐项事实与版本范围保留，不单条断成败。",
        },
    }


def calendar_summary(board: Dict[str, Any]) -> Dict[str, Any]:
    """A compact first-read view; full adapter evidence stays in calendar_rules."""
    calendar = board["calendar_rules"]
    mode = calendar.get("calculation_mode", "year")
    common = {
        "calculation_mode": mode,
        "civil_datetime": calendar["civil_datetime"],
        "timezone": calendar["timezone"],
    }
    if mode == "year":
        used_lunar = calendar.get("historical_calendar") or calendar.get(
            "civil_lunar_calendar"
        )
        return {
            **common,
            "year": calendar["year"],
            "year_boundary": calendar["year_boundary"],
            "year_boundary_status": calendar["year_boundary_status"],
            **({"used_lunar_date": used_lunar["display"]} if used_lunar else {}),
            **(
                {"year_profile": calendar["year_profile"]}
                if "year_profile" in calendar
                else {}
            ),
        }
    return {
        **common,
        **(
            {
                "anchor_ephemeris_model": board["solar_anchors"]["boundary"][
                    "ephemeris_model"
                ],
                **(
                    {
                        "winter_anchor_ephemeris_model": board["solar_anchors"][
                            "winter_origin"
                        ]["ephemeris_model"]
                    }
                    if "winter_origin" in board["solar_anchors"]
                    else {}
                ),
            }
            if board.get("solar_anchors")
            else {}
        ),
        **{
            key: calendar[key]
            for key in (
                "anchor_name",
                "anchor_utc",
                "counter",
                "clock_basis",
                "hour_profile",
                "month_profile",
                "day_profile",
                "input_calendar",
            )
            if key in calendar
        },
        "convention": (
            calendar["modern_conventions"]
            if mode in {"hour", "day"} or calendar.get("month_origin")
            else calendar["leap_month_policy"]
        ),
    }


def build_year_board(
    seed: MetaphysicsSeed, gender: str, year_profile: str | None = None
) -> Dict[str, Any]:
    from .taiyi_gates import attach_gate_board
    from .taiyi_long_cycles import attach_long_cycles
    from .taiyi_year_calendar import (
        HISTORICAL_YEAR_PROFILE,
        HISTORICAL_YEAR_PROFILES,
        YEAR_PROFILES,
        historical_year_context,
    )

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
    core = yearly_core(year)
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


def evidence_text(board: Dict[str, Any]) -> str:
    """Deterministic interpretation copied from the same board, never recast."""
    from .taiyi_counts import counts_text
    from .taiyi_enclosures import enclosures_text
    from .taiyi_gates import gates_text
    from .taiyi_oppositions import oppositions_text

    core = board["core_board"]
    calendar = board["calendar_rules"]
    mode = calendar.get("calculation_mode", "year")
    lines = [
        f"规则：{board['ruleset']['source_title']} / {board['ruleset']['id']}；{board['life_method']}。"
    ]
    if board.get("counter_cycles"):
        lines.append(counter_cycles_text(board["counter_cycles"]))
    if board.get("winter_origin_selection"):
        from .taiyi_origin_selection import winter_origin_selection_text

        lines.append(winter_origin_selection_text(board["winter_origin_selection"]))
    resolution = calendar.get("civil_clock_resolution")
    if resolution:
        lines.append(
            f"民用时刻消歧：{resolution['wall_datetime']}，时区{resolution['timezone']}，"
            f"明确偏移{resolution['input_utc_offset']}，核对偏移{resolution['resolved_utc_offset']}，"
            f"fold={resolution['fold']}；实际UTC：{resolution['instant_utc']}。"
            + resolution["scope"]
        )
    if mode == "year":
        historical = calendar.get("historical_calendar")
        if historical:
            from .taiyi_year_calendar import historical_year_text

            lines.append(historical_year_text(historical))
            lines.append(calendar["pillars_role"])
        else:
            lines.extend(
                [
                    f"年计岁首：农历正月初一（工程约定）；年干支：{calendar['year_ganzhi']}。",
                    f"年计采用钟表日期：{calendar['civil_datetime']}；农历年：{calendar['year']}，不随真太阳时跨日改变。",
                    civil_lunar_text(calendar["civil_lunar_calendar"]),
                ]
            )
    else:
        anchors = board.get("solar_anchors", {})
        if anchors:
            labels = {"boundary": "换节/换遁", "winter_origin": "冬至起元"}
            lines.append(
                "节气实际模型："
                + "；".join(
                    f"{labels.get(key, key)} {value['name']} "
                    f"{value['datetime_with_offset']} "
                    f"{value['resolution_provider']}/{value['ephemeris_model']}"
                    for key, value in anchors.items()
                )
                + "。"
                + board["solar_anchor_scope"]
            )
        lines.extend(
            [
                f"起点：{calendar['anchor_name']} / {calendar['anchor_utc']}；天文来源：{calendar['anchor_provider']}。",
                f"计数时钟：{calendar['clock_basis']}；所选计数：{calendar['counter']}。",
            ]
        )
        if mode == "hour":
            lines.append(
                f"时钟读数：{calendar['target_clock']}；至点时钟：{calendar['anchor_clock']}；{calendar['initial_interval']}。"
            )
            origin = calendar.get("hour_origin")
            if origin:
                lines.append(
                    f"时计配置：{calendar['hour_profile']}；冬至前甲子锚{origin['origin_effective_date']}，本次所属日{origin['target_effective_date']}（{origin['target_day_ganzhi']}）。"
                )
                lines.append(
                    f"完整积时：({origin['day_number']} - 1) × 12 + {origin['hour_number']} = {origin['accumulation']}；23时子初为现代约定；来源：{origin['source']}。"
                )
        elif mode == "day":
            origin = calendar["day_origin"]
            lines.append(
                f"日计配置：{calendar['day_profile']}；冬至前甲子锚{origin['origin_effective_date']}，本次所属日{origin['target_effective_date']}（{origin['target_day_ganzhi']}），积{origin['accumulation']}日，不乘十二。"
            )
            lines.append(calendar["modern_conventions"])
            lines.append(calendar["pillars_role"])
        else:
            lines.append(f"月界：{calendar['leap_month_policy']}。")
            origin = calendar.get("month_origin")
            if origin and origin.get("profile") == "jinjing_month_jie_360_v1":
                from .taiyi_month import jinjing_month_origin_text

                lines.append(jinjing_month_origin_text(origin))
            elif origin:
                lines.append(
                    f"月计配置：{calendar['month_profile']}；完整积月({origin['annual_accumulation']} - 1) × 12 + 2 + {origin['nominal_month']} = {origin['accumulation']}；弘治17年截数为{origin['shortcut_count']}，相差{origin['full_minus_shortcut']}，按720月公周期同相位。"
                )
                lines.append(origin["year_label_policy"] + origin["scope"])
                reference = origin.get("calendar_reference")
                if reference:
                    lines.append(
                        f"朔月假设对照：{reference['source_label']}，独立历表月首儒略历{reference['lunar_month_start_julian']} → 推算公历{reference['lunar_month_start_gregorian']}，下月首{reference['next_lunar_month_start_gregorian']}；本盘节月名义序{reference['actual_nominal_month']}，所比历表农历月序{reference['source_month']}，一致标志{reference['month_label_matches']}。"
                    )
                    lines.append(
                        f"历表：{reference['calendar_authors']}《{reference['calendar_title']}》{reference['calendar_edition']}第{reference['calendar_printed_page']}页；{reference['calendar_source']}。{reference['scope']}"
                    )
    reference = calendar.get("historical_date_reference")
    if reference:
        lines.append(
            f"历史日期对照：{reference['source_date']}；儒略历{reference['western_source_date']} → 推算公历{reference['normalized_gregorian_date']}。"
            f"{reference['calendar_table_authors']}《{reference['calendar_table_title']}》{reference['calendar_table_edition']}第{reference['calendar_table_printed_page']}页；来源：{reference['calendar_table_source']}。"
        )
        lines.append(
            f"日期干支：原例{reference['source_day_ganzhi']}，本盘{reference['actual_day_ganzhi']}；积数：原例{reference['source_accumulation']}，本盘{reference['actual_accumulation']}。"
            + reference["scope"]
        )
    if board.get("shiji_derivation"):
        from .taiyi_shiji import shiji_derivation_text

        lines.append(shiji_derivation_text(board["shiji_derivation"]))
    for label, field in (("主算", "main"), ("客算", "guest")):
        trace = board["rule_trace"][field]
        path = " + ".join(f"{p['palace']}{p['value']}" for p in trace["path"])
        ending = (
            f"同宫取本宫数{trace['count']}"
            if not trace["terminal_excluded"]
            else f"止于{trace['terminal_palace']}宫前"
        )
        lines.append(f"{label}：{path} = {trace['count']}；{ending}。")
    lines.append(
        f"主大/主参：{core['main_general']}/{core['main_vice_general']}；客大/客参：{core['guest_general']}/{core['guest_vice_general']}。"
    )
    lines.extend(
        f"{p.get('variant', p['name'])}：{p['traditional_meaning']}；{p['scope']}。"
        for p in board["patterns"]
    )
    if board.get("count_assessment"):
        lines.append(counts_text(board["count_assessment"]))
    if board.get("victory_matrix_assessment"):
        from .taiyi_victory_matrix import victory_matrix_text

        lines.append(victory_matrix_text(board["victory_matrix_assessment"]))
    if board.get("elemental_guan_assessment"):
        from .taiyi_elemental_relations import elemental_relations_text

        lines.append(elemental_relations_text(board["elemental_guan_assessment"]))
    alignment = board.get("count_source_assessment")
    if alignment and (
        alignment["status"] == "not_assessed"
        or alignment["summary"]["status"] == "differences_unadjudicated"
        or alignment["facsimile_readings"]
    ):
        from .taiyi_source_alignment import source_alignment_text

        lines.append(source_alignment_text(alignment))
    lines.append(conditions_text(board["condition_assessment"]))
    if board.get("enclosure_assessment"):
        lines.append(enclosures_text(board["enclosure_assessment"]))
    if board.get("opposition_assessment"):
        lines.append(oppositions_text(board["opposition_assessment"]))
    lines.append(gates_text(board))
    if board.get("ten_jing"):
        from .taiyi_ten_jing import ten_jing_text

        lines.append(ten_jing_text(board["ten_jing"]))
    for comparison in board.get("day_source_comparisons", []):
        lines.append(
            f"{comparison['scope']} {comparison['field']}原文{comparison['source_value']}，本盘规则推算{comparison['rule_derived_value']}；来源：{comparison['source']}。"
        )
    lines.append("原典符合范围：部分，底本表文与通则分歧待裁定；现实预测效力：未检验。")
    return "\n".join(lines)
