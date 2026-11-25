"""Jin Kou snapshot sections."""

from __future__ import annotations

from typing import Any

from fatebridge.core.local_techniques.snapshot import join_lines
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.services.ren_calendar_snapshot import ren_calendar_snapshot_lines
from fatebridge.services.snapshot_builders import render_snapshot_text


def build_jinkou_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    jinkou: dict[str, Any],
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    overview = jinkou["overview"]
    yuejiang = overview["yuejiang"]
    month_general = overview["month_general"]
    guishen = overview["guishen"]
    row_lines = []
    for row in jinkou.get("rows", []) or []:
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
    else:
        pass
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
    else:
        pass
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
    else:
        pass
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
        else:
            pass
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
            join_lines(
                [
                    f"农历：{lunar_calendar.get('display') or '无'}",
                    *ren_calendar_snapshot_lines(jinkou.get("calendar_policy") or {}),
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
            join_lines(
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
        ("金口诀四位", join_lines(row_lines) or "无"),
        *(([("京本本命另课", join_lines(natal_lines))]) if natal_lines else []),
        *(([("京本行年另课", join_lines(year_fate_lines))]) if year_fate_lines else []),
        (
            "六十四课钤结构",
            join_lines(
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
            join_lines(
                [
                    *(
                        combination_lines
                        or ["神、将、地分未见同组三合的两个不同成员。"]
                    ),
                    jinkou["combinations"]["scope"],
                ]
            ),
        ),
        ("四位神煞", join_lines(shensha_lines) or "无"),
    ]
    return render_snapshot_text(sections)
