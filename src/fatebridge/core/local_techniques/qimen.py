"""
Qi Men (奇门) snapshot rendering and options over a metaphysics seed.

Pure relocation from the package facade.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import (
    build_qimen_board,
)
from fatebridge.core.qimen_profiles import DEFAULT_GOD_PROFILE, DEFAULT_SEASON_PROFILE
from fatebridge.utils.solar_time_provenance import solar_time_evidence_lines

from .chart import (
    _build_qimen_palace_overview_lines,
    _join_lines,
    _render_qimen_palace_sections,
    _render_snapshot_text,
)

QIMEN_NINE_GRID_LAYOUT = (
    ("巽四宫", "离九宫", "坤二宫"),
    ("震三宫", "中五宫", "兑七宫"),
    ("艮八宫", "坎一宫", "乾六宫"),
)


def _build_qimen_nine_grid_lines(qimen: Dict[str, Any]) -> List[str]:
    palace_map = {
        palace.get("name"): palace
        for palace in qimen.get("palaces", []) or []
        if isinstance(palace, dict) and palace.get("name")
    }
    rows: List[str] = []
    for row in QIMEN_NINE_GRID_LAYOUT:
        cells: List[str] = []
        for palace_name in row:
            palace = palace_map.get(palace_name, {})
            cell = (
                f"{palace_name}："
                f"{palace.get('door') or '无'}/"
                f"{'/'.join([palace['star'], *palace.get('hosted_stars', [])]) if palace.get('star') else '无'}/"
                f"{palace.get('god') or '无'}"
            )
            if palace.get("content_palace") and (
                palace.get("content_palace") != palace.get("name")
                or palace.get("content_trigram") != palace.get("trigram")
            ):
                cell += (
                    f" <- {palace.get('content_palace', '无')}/"
                    f"{palace.get('content_trigram', '无')}"
                )
            cells.append(cell)
        rows.append(" | ".join(cells))
    return rows


def _render_qimen_pattern_line(pattern: Dict[str, Any]) -> str:
    line = f"{pattern['palace']}：{pattern['name']}；{pattern['facts']}；{pattern['traditional_meaning']}"
    qualification = pattern.get("qualification")
    if qualification:
        condition_state = (
            "已观察到" if qualification["condition_observed"] else "未满足"
        )
        line += f"；附加条件{condition_state}：{qualification['condition']}"
        if qualification["blocking_rule_names"]:
            line += "；本宫限制：" + "、".join(qualification["blocking_rule_names"])
        if qualification["same_palace_conflicts"]:
            line += "；同宫冲突：" + "、".join(qualification["same_palace_conflicts"])
        for disagreement in qualification["source_disagreements"]:
            line += f"；原典差异待核（{disagreement['field']}）：原文{disagreement['source_value']}，本盘{disagreement['computed_value']}"
        binding = qualification.get("identity_binding")
        if binding:
            native = binding["native_raw_trigram"]
            if native != binding["native_host_trigram"]:
                native += f"寄{binding['native_host_trigram']}"
            line += f"；时旬身份：{binding['xun_head']}遁{binding['hidden_stem']}，地盘原宫{native}，天盘值符在{binding['moving_trigram']}"
        stem = qualification.get("stem_identity")
        tomb = qualification.get("tomb_evidence")
        punishment = qualification.get("punishment_evidence")
        gate_relation = qualification.get("door_palace_evidence")
        if gate_relation:
            line += f"；门宫关系：{gate_relation['relation_text']}，正文名{gate_relation['prose_label']}；关系名不作现实吉凶结论"
        if punishment:
            instrument = qualification["punishment_instrument_identity"]
            line += f"；击刑身份：本格{instrument['xun_head']}遁{instrument['hidden_stem']}，所刑{instrument['punished_branch']}在{instrument['trigram']}；本时{punishment['xun_head']}遁{punishment['hidden_stem']}，窄读候选{'命中' if punishment['current_zhifu_matched'] else '未命中'}；广义暂定，原文范围未裁定"
        if tomb:
            line += (
                "；入墓取法：卷二王璋明确列举；段首字面候选未采纳，释读及优先关系待核"
            )
        if stem:
            role = {
                "hour_stem_block": "时干",
                "year_stem_block": "岁干",
                "lunar_month_start_block": "月朔干",
            }.get(pattern["rule_id"], "日干")
            line += f"；{role}取用：{stem['ganzhi']}，实际用干{stem['effective_stem']}"
            if stem.get("anchor_date"):
                line += f"，月初一为{stem['anchor_date']}"
            if qualification.get("source_aliases"):
                line += "；原文别称：" + "、".join(qualification["source_aliases"])
                line += "；" + qualification["alias_scope"]
        if qualification.get("partial_judgment"):
            line += "；" + qualification["partial_judgment"]
        if qualification.get("overlapping_evidence_group"):
            line += (
                "；同据重叠："
                + qualification["overlapping_evidence_group"]
                + "，不作独立印证"
            )
        if qualification.get("coexisting_rule_names"):
            line += (
                "；同宫另见："
                + "、".join(qualification["coexisting_rule_names"])
                + (
                    "；不由五假名称覆盖这些条件"
                    if qualification.get("five_jia_evidence")
                    else "；不由三诈名称覆盖这些条件"
                )
            )
        line += "；仍须合看全局，不作现实成败断言"
    return line


def _qimen_stem_context_lines(qimen: Dict[str, Any]) -> List[str]:
    context = qimen.get("stem_context")
    if not context:
        return []
    day = context["day"]
    if day["status"] == "literal_stem_resolved":
        day_line = f"日干取用：{day['ganzhi']}，直取{day['effective_stem']}"
    else:
        choices = "、".join(
            f"{'按日甲' if c['policy'] == 'day_jia_own_six_instrument' else '按时旬'}：{c['xun_head']}遁{c['effective_stem']}"
            for c in day["candidates"]
        )
        day_line = f"日干取用：{day['ganzhi']}日甲身份待核；候选{choices}，均未采纳，不据候选补判伏干、飞干"
    hour = context["hour"]
    lines = [
        *solar_time_evidence_lines(
            qimen.get("calendar_policy", {}).get("solar_time_adjustment", {})
        ),
        day_line,
        f"时干取用：{hour['ganzhi']}，实际用干{hour['effective_stem']}",
    ]
    resolution = qimen.get("calendar_policy", {}).get("civil_clock_resolution")
    if resolution:
        lines.append(
            f"民用时刻消歧：{resolution['timezone']}，UTC偏移{resolution['resolved_utc_offset']}，fold={resolution['fold']}，实际UTC时刻{resolution['instant_utc']}；保留命名时区的全年历法规则"
        )
    for role, label in [("year", "岁干"), ("lunar_month_start", "月朔干")]:
        anchor = context.get(role)
        if not anchor:
            continue
        if anchor["status"] == "literal_stem_resolved":
            detail = f"{anchor['ganzhi']}，实际用干{anchor['effective_stem']}"
            if role == "year":
                detail += "，立春与农历年候选一致"
            else:
                detail += f"，本{'闰' if anchor['is_leap_month'] else ''}{anchor['lunar_month']}月初一{anchor['anchor_date']}，不取八字月干"
        elif anchor["status"] == "unresolved_year_boundary":
            detail = "年界待核；" + "、".join(
                f"{'立春' if c['policy']=='lichun' else '农历年'}候选{c['ganzhi']}"
                for c in anchor["boundary_candidates"]
            )
            detail += "，均未选定，不据未输出岁格判定不存在"
        elif anchor["status"] == "unresolved_jia_identity":
            detail = f"{anchor['ganzhi']}的甲身份待核；藏仪候选均未采纳，不据未输出格局判定不存在"
            if role == "lunar_month_start":
                detail += f"，本月初一{anchor['anchor_date']}"
        else:
            detail = "历法锚点不可用，不猜取用干"
        lines.append(f"{label}取用：{detail}")
    temporal = context.get("hour_branch_tomb")
    tomb_profile = qimen.get("rule_profiles", {}).get("wonder_tomb")
    punishment_profile = qimen.get("rule_profiles", {}).get("six_instrument_punishment")
    gate_profile = qimen.get("rule_profiles", {}).get("door_palace_relation")
    triple_profile = qimen.get("rule_profiles", {}).get("three_deceptions")
    if qimen.get("rule_profiles", {}).get("five_jia"):
        lines.append(
            "五假口径：天假为景门乙丙丁临九天；地假／神假／鬼假分别为杜／伤／死门合丁己癸临九地，天盘主寄干均核；丁己癸不是三奇。人假六合身份与层次未决，己候选未采纳，不把未命名当不存在"
        )
        for palace in qimen["palaces"]:
            context = palace.get("evidence", {}).get("five_jia", {})
            if context.get("human_jia", {}).get("unadopted_ji_stem_candidate_observed"):
                lines.append(
                    f"{palace['name']}人假候选：惊门、天盘己、九天同宫；跨段己为六合的候选未采纳，不命名人假或判断吉凶"
                )
            if context.get("unnamed_du_door_clause"):
                lines.append(
                    f"{palace['name']}五假旁例：杜门合丁己癸临{palace['god']}；原句未另命名地假，不移植九地下地假之名或现实效果"
                )
    if triple_profile:
        lines.append(
            "三诈口径：天盘奇、开休生门、太阴／九地／六合完整同宫命名真诈／重诈／休诈；得二缺项判断优先未决，十分七分不作概率；与人遁重叠不作独立印证"
        )
        for palace in qimen["palaces"]:
            partial = palace.get("evidence", {}).get("three_deceptions")
            if (
                partial
                and not partial["matched"]
                and partial["verse_exactly_two_components_present"]
            ):
                lines.append(
                    f"{palace['name']}三诈缺项：天盘三奇{'、'.join(partial['heaven_wonder_stems']) or '无'}，{partial['observed_door']}，{partial['observed_god']}；歌诀太阴三要素恰得二，完整三诈未命名，缺项吉凶优先未决"
                )
    if gate_profile:
        lines.append(
            "门宫关系口径：歌诀门克宫为门迫；正文另称吉迫、凶迫、和、义，关系名不作现实吉凶结论"
        )
    if punishment_profile:
        lines.append(
            "六仪击刑口径："
            + punishment_profile["title"]
            + "；广义暂定保留，另列本时直符候选；正文未明写仅本旬，原文范围未裁定"
        )
    if tomb_profile:
        lines.append(
            "三奇入墓口径："
            + tomb_profile["title"]
            + "；段首字面候选仅对照、未采纳，优先关系待核"
        )
    if temporal:
        state = "命中" if temporal["matched"] else "未命中"
        lines.append(
            f"时干支入墓：{temporal['hour_ganzhi']}，{state}卷二正文六时表；不以甲藏仪替代，不等同天盘时干落墓宫"
        )
        if temporal["matched"] and not temporal["matched_definition"]["verse_listed"]:
            lines.append("己丑为正文补列；歌诀五组未列它，不据此删去正文第六组")
    return lines


def _render_qimen_source_disagreements(qimen: Dict[str, Any]) -> List[str]:
    return [
        f"原典差异待核：{d['source_section']}，影印第{d['source_scan_page']}页，{d['field']}原文{d['source_value']}，本盘{d['computed_value']}；保留计算，不判已符合原典"
        for d in qimen.get("source_disagreements", [])
    ]


def build_qimen_snapshot_text(*, seed: MetaphysicsSeed, qimen: Dict[str, Any]) -> str:
    zhifu = qimen.get("zhifu") or {}
    zhishi = qimen.get("zhishi") or {}
    palace_map = {
        palace.get("name"): palace
        for palace in qimen.get("palaces", []) or []
        if isinstance(palace, dict) and palace.get("name")
    }
    zhifu_palace = palace_map.get(zhifu.get("palace"), {})
    zhishi_palace = palace_map.get(zhishi.get("palace"), {})

    def _content_note(item: Dict[str, Any]) -> str:
        if not item.get("content_palace"):
            return ""
        if item.get("content_palace") == item.get("palace") and item.get(
            "content_trigram"
        ) == item.get("trigram"):
            return ""
        return (
            f"；内容来源：{item.get('content_palace', '无')} / "
            f"{item.get('content_trigram', '无')}"
        )

    sections = [
        (
            "起盘信息",
            _join_lines(
                [
                    f"农历：{(seed.calendar_context.get('lunar_calendar') or {}).get('display') or '无'}",
                    f"起局时间：{seed.corrected_datetime:%Y-%m-%d %H:%M:%S}（{'真太阳时' if seed.applied_true_solar else '钟表时间'}）",
                    f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时",
                    f"定局法：{qimen.get('ju_method')}；天文节气按民用时刻判断",
                    "换日：子初换日",
                ]
            ),
        ),
        (
            "盘型",
            _join_lines(
                [
                    f"当前节气：{(seed.calendar_context.get('current_solar_term') or {}).get('name', '无')}",
                    f"下个节气：{(seed.calendar_context.get('next_solar_term') or {}).get('name', '无')}",
                    f"盘型：{qimen.get('ju_text', '无')}",
                    f"遁型：{qimen.get('dun_type', '无')}",
                    f"三元：{qimen.get('yuan', '无')}",
                    f"定局所用节气：{qimen.get('ju_term', '无')}",
                    f"符头：{qimen.get('fu_tou', '无')}",
                    f"旬首：{qimen.get('xun_head', '无')}",
                    f"空亡：{qimen.get('kongwang', '无')}",
                ]
            ),
        ),
        (
            "盘面要素",
            _join_lines(
                [
                    (
                        f"值符：{zhifu.get('star', '无')}在{zhifu.get('palace', '无')}"
                        + _content_note(zhifu)
                    ),
                    (
                        f"值使：{zhishi.get('door', '无')}在{zhishi.get('palace', '无')}"
                        + _content_note(zhishi)
                    ),
                    f"布局：{qimen.get('layout', 'direct')}",
                    f"规则版本：{(qimen.get('rulesets') or [{}])[0].get('id', '无')}",
                    f"八神口径：{qimen['rule_profiles']['god']['title']}（{qimen['god_profile']}）",
                    f"九星旺衰口径：{qimen['rule_profiles']['season']['title']}（{qimen['season_profile']}）",
                    *_qimen_stem_context_lines(qimen),
                ]
            ),
        ),
        (
            "奇门演卦",
            _join_lines(
                [
                    "来源范围：软件派生层，未作原典认证",
                    f"伏使卦：{(qimen.get('fushi_hexagram') or {}).get('name', '无')} / {(qimen.get('fushi_hexagram') or {}).get('binary_code', '无')}",
                    f"值符宫门卦：{(zhifu_palace.get('door_hexagram') or {}).get('name', '无')}",
                    f"值使宫门卦：{(zhishi_palace.get('door_hexagram') or {}).get('name', '无')}",
                ]
            ),
        ),
        (
            "规则依据",
            _join_lines(
                [
                    "来源：明·程道生《遁甲演义》，四库全书本在线转录及所列影印选页；卷四十八局值符值使宫数含2项分歧，全书未校勘。",
                    f"固定版本：{(qimen.get('rulesets') or [{}])[0].get('source', '无')}",
                    qimen["rule_profiles"]["god"]["variant_note"],
                    qimen["rule_profiles"]["season"]["variant_note"],
                    "对应规则只在其覆盖范围内成立；传统规则匹配不等于现实事件预测。",
                    *_render_qimen_source_disagreements(qimen),
                    *[_render_qimen_pattern_line(p) for p in qimen.get("patterns", [])],
                ]
            ),
        ),
        ("八宫详解", _join_lines(_build_qimen_palace_overview_lines(qimen)) or "无"),
        ("九宫方盘", _join_lines(_build_qimen_nine_grid_lines(qimen)) or "无"),
        *_render_qimen_palace_sections(qimen),
    ]
    return _render_snapshot_text(sections)


def build_qimen_with_options(
    seed: MetaphysicsSeed, options: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    normalized = dict(options or {})
    unknown = set(normalized) - {
        "layout",
        "palaceShift",
        "palace_shift",
        "ju_method",
        "god_profile",
        "season_profile",
    }
    if unknown:
        raise ValueError(f"不支持的奇门选项：{sorted(unknown)}")
    layout = normalized.get("layout", "direct")
    if layout not in ("direct", "rotating"):
        raise ValueError(
            "仅支持有明确规则的转盘 layout=direct；fly/fei、镜像或反转不是已实现的奇门流派"
        )
    for key in ("palaceShift", "palace_shift"):
        shift = normalized.get(key, 0)
        if type(shift) is not int or shift != 0:
            raise ValueError("palaceShift仅允许0；移动九宫内容不能冒充飞盘排法")
    method = normalized.get("ju_method", "zhirun")
    if method not in ("zhirun", "chaibu"):
        raise ValueError("ju_method仅支持zhirun（置闰）或chaibu（拆补）")
    return build_qimen_board(
        seed,
        ju_method=method,
        god_profile=normalized.get("god_profile", DEFAULT_GOD_PROFILE),
        season_profile=normalized.get("season_profile", DEFAULT_SEASON_PROFILE),
    )
