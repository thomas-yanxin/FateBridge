"""Liu Ren snapshot sections."""

from __future__ import annotations

from typing import Any

from fatebridge.core.local_techniques.snapshot import join_lines
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.services.ren_calendar_snapshot import ren_calendar_snapshot_lines
from fatebridge.services.snapshot_builders import render_snapshot_text


def build_liureng_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    liureng: dict[str, Any],
    runyear: dict[str, Any] | None = None,
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    month_general = liureng["month_general"]
    transmissions = liureng["three_transmissions"]
    auxiliary = liureng["auxiliary_stars"]
    auxiliary_lines: dict[str, list[str]] = {
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
    ]
    board_lines = [
        (
            f"{item.get('earth_branch', '无')}位："
            f"天盘{item.get('sky_branch', '无')}；"
            f"贵神{item.get('god', '无')}"
        )
        for item in liureng.get("twelve_board", []) or []
    ]
    lesson_lines = []
    for lesson in liureng.get("four_lessons", []) or []:
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
            + ("，命中本支填实例外" if r["xunkong_exception_applies"] else "")
            for r in empty["role_conditions"]
        ),
    ]
    for label, position in (("初传", "initial"), ("中传", "middle"), ("末传", "final")):
        r = empty_by_sky[transmissions[position]["branch"]]
        empty_lines.append(
            f"{label}天盘{r['sky_branch']}本空{r['sky_xun_kong']}；地盘{r['earth_branch']}落底本空{r['earth_xun_kong']}；"
            f"日干寄宫地盘例外{r['earth_stem_house_exception']}；天盘角色{'、'.join(r['sky_authority_roles']) or '无所列角色'}；"
            f"天盘角色填实例外{'命中' if r['sky_authority_xunkong_exception'] else '未命中'}；综合有效空亡未裁定"
        )
    for role, branch in empty["year_fate_earth_branches"].items():
        if branch is None:
            continue
        else:
            pass
        row = next(r for r in empty["rows"] if r["earth_branch"] == branch)
        empty_lines.append(
            f"{'本命' if role == 'natal' else '行年'}书地盘{branch}；"
            + (
                "本空，依年命条不作空论"
                if row["earth_year_fate_xunkong_exception"]
                else "本支不空"
            )
        )
    empty_lines.append(empty["scope"])
    runyear_lines = ["无"]
    relation_evidence = liureng["transmission_relations"]
    course = relation_evidence["course_conditions"]
    transmission_lines.extend(
        [
            "三传关系依据：探原卷下论三传、论十二天将、论合（所选结构）",
            *(
                f"{ {'initial': '初传', 'middle': '中传', 'final': '末传'}[r['position']] }：支神{r['branch']}{r['element']}，天将{r['god']}{r['god_element']}；将对神{r['god_to_spirit']}，{r['war'] or '无内外战'}；六亲仍按支神为{r['day_relation']}"
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
        else:
            pass
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
            else:
                pass
        else:
            pass
        if age_calendar := runyear.get("age_calendar"):
            runyear_lines += [
                f"虚岁参考时区：{age_calendar['timezone']}；分析瞬间在该区：{age_calendar['analysis_civil_datetime']}。",
                f"虚岁农历年：出生{age_calendar['birth_lunar_year']}、分析{age_calendar['analysis_lunar_year']}；两端同区，正月初一00:00换岁。",
            ]
        else:
            pass
        if year_fate := runyear.get("year_fate"):
            for key, label in (("natal", "本命"), ("annual", "行年")):
                item = year_fate[key]
                if item["status"] == "not_calculated":
                    runyear_lines.append(f"{label}落盘：未计算；{item['reason']}")
                    continue
                else:
                    pass
                runyear_lines.append(
                    f"{label}干支{item['subject_ganzhi']}书地盘{item['earth_branch']}；"
                    f"上见{item['sky_branch']}乘{item['god']}，对占日为{item['upper_relation']}；"
                    f"上神旬遁：{item['upper_ganzhi'] or '旬空无遁干'}；"
                    f"上神旬空：{'是' if item['upper_xun_kong'] else '否'}；"
                    f"地盘旬空：{'是' if item['earth_xun_kong'] else '否'}。"
                )
            runyear_lines.append(f"年命口径：{year_fate['birth_year_basis']}。")
        else:
            pass
    else:
        pass
    sections = [
        (
            "起盘信息",
            join_lines(
                [
                    f"农历：{lunar_calendar.get('display') or '无'}",
                    *ren_calendar_snapshot_lines(liureng.get("calendar_policy") or {}),
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
            join_lines(
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
        ("十二地盘/十二天盘/十二贵神对应", join_lines(board_lines) or "无"),
        ("四课", join_lines(lesson_lines) or "无"),
        ("三传", join_lines(transmission_lines) or "无"),
        ("三传连茹与间断", join_lines(progression_lines)),
        ("季节五态与支神本空条件", join_lines(seasonal_lines)),
        ("类神阴神", join_lines(god_yin_lines)),
        ("空亡分层条件", join_lines(empty_lines)),
        ("支位合冲刑破害", join_lines(branch_lines)),
        ("行年", join_lines(runyear_lines) or "无"),
        (
            "旬日",
            join_lines(
                [
                    f"旬首：{liureng.get('xun_head', '无')}",
                    f"空亡：{liureng.get('kongwang', '无')}",
                ]
            ),
        ),
        (
            "旺衰",
            join_lines(
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
            join_lines(
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
            join_lines(
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
            join_lines(
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
            join_lines(
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
            join_lines(
                [
                    f"岁干：{seed.pillars['year'][0]}",
                    f"岁支：{seed.pillars['year'][1]}",
                    f"问占性别：{(liureng.get('meta') or {}).get('questioner_gender', '无')}",
                ]
            ),
        ),
        (
            "十二长生",
            join_lines(
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
        ("大格", join_lines(pattern_lines) or "无"),
        ("小局", join_lines(transmission_lines) or "无"),
        ("参考", join_lines(liureng.get("overview", [])) or "无"),
        (
            "概览",
            join_lines(
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
    return render_snapshot_text(sections)
