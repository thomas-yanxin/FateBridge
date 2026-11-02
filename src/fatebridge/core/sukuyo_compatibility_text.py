"""Explain already computed date branches and directed candidate relations."""

from __future__ import annotations

from typing import Any

from fatebridge.core.sukuyo_date_support import (
    input_timezone_reading,
    support_completeness_reading,
    support_interval_duration_reading,
)


def joint_reconstruction_contract(analysis: dict[str, Any]) -> str:
    """Describe the join actually returned, including states with no row filter."""
    shared = analysis.get("shared_reconstruction_analysis")
    if not shared:
        return ""
    status = shared.get("status")
    resolved = analysis.get("status") == "not_needed"
    if status == "applied":
        scope = (
            "共同重建状态applied：rows仅列双方共同采用同一套具名现代重建时有完整联合支持的条件组合；"
            "完整原无约束矩阵保留在unconstrained_rows。"
        )
    elif status == "not_shared":
        scope = "共同重建状态not_shared：档案、算法、来源或宿主历法身份未核成相同，未施加共同重建约束。" + (
            "宿名已定，rows为空，有向关系由person1_to_person2和person2_to_person1交付。"
            if resolved
            else "rows仍为原无约束外包络，不能视为通过共同模型筛选。"
        )
    elif status == "incomplete":
        scope = "共同重建状态incomplete：支持覆盖不完整，未筛掉任何原候选行，缺支持记录不能判成不成立。"
        if resolved:
            scope += (
                "宿名已定，rows为空，有向关系由person1_to_person2和person2_to_person1交付；"
                "已返回的具体模型条件另见resolved_support，不据此确定唯一模型。"
            )
        else:
            scope += "rows仍为原无约束外包络。"
            if "unconstrained_rows" in analysis:
                scope += "完整原矩阵也保留在unconstrained_rows。"
    elif status == "not_needed":
        scope = (
            "共同重建状态not_needed：双方宿名已定，rows为空；有向关系由person1_to_person2和person2_to_person1交付。"
            "resolved_support保留具体模型、日期与半日条件，不能由宿名一致确定唯一模型或半日。"
        )
    else:
        scope = "共同重建状态未识别，不能断言已筛选rows、支持覆盖完整或原矩阵另存。"
    return scope + (
        "未知日期、半日各自保留，不拆散完整联合支持记录再交叉；"
        "未获共同支持不等于历史绝对不可能，未裁定原典优先次序。"
    )


def ordinary_candidate_envelope_reading(
    contexts: list[dict[str, Any]], analysis: dict[str, Any]
) -> str:
    """Require positive ordinary-profile evidence; absence of a join is insufficient."""
    if (
        len(contexts) != 2
        or analysis.get("status") != "candidate_only"
        or not analysis.get("rows")
        or "shared_reconstruction_analysis" in analysis
    ):
        return ""
    for context in contexts:
        if not isinstance(context, dict):
            return ""
        candidates = context.get("calendar_candidates")
        if candidates is not None and not isinstance(candidates, list):
            return ""
        leaves = candidates or [context]
        for node in [context, *leaves]:
            if not isinstance(node, dict):
                return ""
            profile = node.get("profile_calculation")
            if not isinstance(profile, dict) or not (
                node.get("calendar_profile")
                == profile.get("calendar_profile")
                == "t1299_fullmoon27"
                and node.get("mansion_method_id")
                == profile.get("mansion_method_id")
                == "t1299_lower_fullmoon27_v1"
            ):
                return ""
            # Date aggregates omit leaf-only source/assignment fields. If an
            # aggregate does supply them, contradictory evidence still vetoes.
            if any(
                key in profile and profile[key] is not None
                for key in ("hinoo_source", "short_month_assignment")
            ):
                return ""
        if any(
            key not in leaf["profile_calculation"]
            or leaf["profile_calculation"][key] is not None
            for leaf in leaves
            for key in ("hinoo_source", "short_month_assignment")
        ):
            return ""
    completeness = (
        "仅在本次档案内完整，不认证全部历史规则。"
        if analysis.get("candidate_set_complete_within_profile") is True
        else "候选未穷尽，已列行不能当全部可能关系。"
    )
    return (
        "双方明确采用t1299_fullmoon27；下列日期和宿名组合是该档案的条件外包络，"
        "本次未施加Hinoo共同重建筛选。每行日期条件须分别满足，未选定出生时刻或确定相性。"
        + completeness
    )


def joint_reconstruction_reading(names: list[str], analysis: dict[str, Any]) -> str:
    shared = analysis.get("shared_reconstruction_analysis")
    if not shared:
        return ""
    if shared["status"] == "not_shared":
        return "双方档案、算法、来源或宿主历法身份未能核成相同，未施加共同重建约束，保留原无约束候选。"
    lines = [
        "以下仅在双方共同采用同一套已声明现代重建的条件下分析；不证明古代各时期规则统一，"
        "也未裁定原典优先次序。两人的日期和半日条件各自保留，未知半日不绑定为相同；支持记录不能拆开后再任意交叉。"
    ]
    if shared["status"] == "incomplete":
        lines.append(
            "共同模型支持覆盖不完整，未筛掉任何原无约束组合；缺支持记录不能判成组合不成立。"
        )
    elif shared["status"] == "not_needed":
        lines.append(
            "双方宿名虽已定，仍不能确定采用哪种重建；所列两套模型均支持既定宿，未选择模型。"
        )
    if "unconstrained_rows" in analysis:
        lines.append(
            f"原无约束矩阵{len(analysis['unconstrained_rows'])}行完整保留，另列共同模型支持。"
        )
    supports = [
        support for row in analysis["rows"] for support in row.get("joint_support", [])
    ] + shared.get("resolved_support", [])
    for support in supports:
        conditions = []
        for label, name in zip(("person1", "person2"), names):
            state = support[label]
            half = {
                "first_half": "前半",
                "second_half": "后半",
                None: "未以半日区分",
            }.get(
                state["calendar_day_part"],
                f"未识别的半日条件{state['calendar_day_part']}",
            )
            conditions.append(
                f"{name}{state['calendar_date']}、{half}、宿{state['natal_su27']}"
            )
        lines.append(
            f"共同重建{support['reconstruction_id']}支持：{'；'.join(conditions)}。"
        )
    if shared["status"] == "applied":
        for row in analysis["unconstrained_rows"]:
            if (
                row["joint_support_status"]
                != "unsupported_within_enumerated_shared_models"
            ):
                continue
            forward, reverse = row["person1_to_person2"], row["person2_to_person1"]
            lines.append(
                f"无共同重建支持的原矩阵对照：{row['person1_su27']}→{row['person2_su27']}为{forward['relation']}，"
                f"反向为{reverse['relation']}，配对{row['pair']}。纯宿名查表前向含义：{forward['meaning']}反向含义：{reverse['meaning']}"
                "此行在上述共享假设及已完整列举的模型内没有共同支持，不作为该条件下的相性候选；"
                "不表示原典禁止或其他未考证历史规则绝对不可能。"
            )
    return "".join(lines)


def candidate_compatibility_reading(
    contexts: list[dict[str, Any]],
    names: list[str],
    analysis: dict[str, Any],
    palace_references: list[dict[str, Any]],
) -> str:
    lines = []
    has_daily_reference = any(
        b.get("calendar_reference", {}).get("manuscript_daily_annotations")
        for c in contexts
        for b in c.get("calendar_candidates") or [c]
    )
    for context, name in zip(contexts, names):
        clock = (
            f"已知时刻{context['input_datetime']}"
            if context.get("birth_time_known")
            else "时刻未知"
        )
        lines.append(
            f"{name}输入当地日期{context['input_date']}，时区{context['input_timezone']}，{clock}；"
            f"实际配宿档案{context['calendar_profile']}。"
        )
        if not context.get("calendar_candidates"):
            lines.append(input_timezone_reading(context))
        if context.get("calendar_candidates"):
            lines.append(
                "按输入当地整日映射到所选宿主参考日期，未猜出生钟时；区间长度不是出生概率。"
            )
            lines.append(support_completeness_reading(context))
            for interval in context.get("date_support", {}).get(
                "utc_support_intervals", []
            ):
                lines.append(
                    f"{name}参考日期{interval['calendar_date']}的UTC支持区间为"
                    f"[{interval['start_utc_inclusive']}, {interval['end_utc_exclusive']})，"
                    "左端含、右端不含；它是当地日期的计算支持范围，不是已知出生钟时。"
                )
                lines.append(support_interval_duration_reading(interval))
        if context.get("out_of_range_calendar_dates"):
            lines.append(
                f"另保留范围外参考日期{'、'.join(context['out_of_range_calendar_dates'])}，未为范围外分支补造农历或宿名。"
            )
        for branch in context.get("calendar_candidates") or [context]:
            reference_date = branch["calendar_date"]
            if all(
                branch.get(key)
                for key in (
                    "calendar_system",
                    "calendar_backend",
                    "calendar_timezone",
                    "calendar_source",
                )
            ):
                lines.append(
                    f"{name}此支实际宿主历法{branch['calendar_system']}，"
                    f"后端{branch['calendar_backend']}，参考日界{branch['calendar_timezone']}；"
                    f"历日来源{branch['calendar_source']}。这些身份属于本次计算条件，不由输入时区或档案名称替代。"
                )
            lunar = (
                f"{branch['lunar_year']}年{'闰' if branch['is_leap_month'] else ''}"
                f"{branch['lunar_month']}月{branch['lunar_day']}日"
                if all(
                    key in branch
                    for key in (
                        "lunar_year",
                        "lunar_month",
                        "lunar_day",
                        "is_leap_month",
                    )
                )
                else "该分支未返回完整农历月日"
            )
            mansion = branch["natal_su27"]
            choices = branch.get("candidate_su27s") or (
                [branch["candidate_su27"]] if branch.get("candidate_su27") else []
            )
            assignment = (
                f"宿{mansion}"
                if mansion
                else "主宿未定"
                + (f"，候选{'、'.join(choices)}" if choices else "，未列可用宿候选")
            )
            lines.append(f"{name}的参考日期{reference_date}：{lunar}，{assignment}。")
            host = branch.get("profile_calculation", {}).get("host_calculation")
            if host:
                agreement = "相合" if host["methods_agree"] else "不同"
                lines.append(
                    f"此支宿主同月日基准：表定十五日望宿{host['fullmoon_mansion']}，"
                    f"逆顺法得{host['direct_mansion']}、生日加十三含首法得{host['shortcut_mansion']}，两法{agreement}；"
                    "表定望日不等实际满月瞬间，基准结果不覆盖本次闰月／小月的实际宿或未定候选。"
                )
            variant = branch.get("source_table_variant")
            if variant:
                lines.append(
                    f"{name}此支上卷含牛字面28宿表为{variant['literal_mansion']}；"
                    f"同月日的基准27宿为{variant['reference_month_day_mansion_27']}，"
                    "与本次实际宿或全部候选分别保留，不覆盖本次27宿或三九结果。"
                )
            profile = branch.get("profile_calculation")
            printed = branch.get("printed_edition_reference")
            if printed:
                from fatebridge.core.sukuyo_koya import printed_reference_lines

                lines.extend(printed_reference_lines(printed))
            if profile and profile.get("hinoo_source"):
                from fatebridge.core.sukuyo_calendar_text import (
                    hinoo_unassigned_month_start_lines,
                    profile_calculation_lines,
                )

                lines.extend(hinoo_unassigned_month_start_lines(branch, profile))
                lines.extend(profile_calculation_lines(profile))
            if has_daily_reference and not branch.get("calendar_reference", {}).get(
                "manuscript_daily_annotations"
            ):
                lines.append(
                    f"参考日期{reference_date}未被本批逐日旁注选录覆盖；未返回不等于原卷无注，也未把月首注当本日直接实录。"
                )
            half = branch.get("calendar_day_part")
            if half in {"first_half", "second_half"}:
                label = "前半" if half == "first_half" else "后半"
                lines.append(
                    f"{name}原典{label}已声明；它不由民用钟时推定，也不能消除尚未确定的规则次序。"
                )
            elif profile and profile.get("hinoo_source"):
                lines.append(
                    f"{name}原典半日未声明；民用钟时和时区换日均未自动补出前半或后半，"
                    "本支实际宿和完整候选仍按已返回的分配条件交付。"
                )
    lines.append(joint_reconstruction_reading(names, analysis))
    lines.append(ordinary_candidate_envelope_reading(contexts, analysis))
    if analysis["candidate_set_complete_within_profile"]:
        lines.append("候选完整仅限本次声明档案与重建，不认证全部历史规则。")
    else:
        lines.append("候选集未穷尽；已列组合不能当全部可能关系，不能确定相性。")
    for row in analysis["rows"]:
        forward, reverse = row["person1_to_person2"], row["person2_to_person1"]
        dates = []
        for index, key in enumerate(
            ("person1_calendar_dates", "person2_calendar_dates")
        ):
            available = row.get(key)
            if available:
                dates.append(f"{names[index]}参考日期{'、'.join(available)}")
        condition = "；".join(dates)
        shared_status = analysis.get("shared_reconstruction_analysis", {}).get("status")
        if shared_status == "applied":
            prefix = "仅按上列不可拆分的完整联合支持条件，"
        elif shared_status in {"incomplete", "not_shared"}:
            prefix = "原无约束外包络的宿名对照中，"
        else:
            prefix = f"条件为{condition}时，" if condition else "已列宿候选组合中，"
        lines.append(
            prefix
            + f"{names[0]}对{names[1]}，{row['person1_su27']}→{row['person2_su27']}为{forward['relation']}，"
            f"反向为{reverse['relation']}；配对类别{row['pair']}。"
            f"前向含义：{forward['meaning']}反向含义：{reverse['meaning']}"
            "这行未作为确定相性应用。"
        )
    if analysis["rows"]:
        lines.append(
            "全部行按输入次序列出，不是优劣排名或概率；宿序组次不是近中远距离，不以重复标签投票确定关系。"
        )
    elif analysis["status"] != "not_needed":
        lines.append("当前没有可列的关系组合，未用缺失或范围外分支补造关系。")
    from fatebridge.core.sukuyo_padas import render_palace_reference

    for name, reference in zip(names, palace_references):
        lines.append(f"{name}：{render_palace_reference(reference)}")
        for palace in reference["candidate_palaces"]:
            lines.append(
                f"{name}所列{palace['name']}原文主曜{palace['ruler_literal']}、"
                f"表内分类{palace['division']}；不是现代出生足位或昼夜生盘。"
            )
            for variant in palace.get("textual_variants", []):
                lines.append(
                    f"{name}此宫主曜原文字面{variant['literal']}，校记异文{variant['variant']}"
                    f"（{variant['locator']}，{variant['witnesses']}）；分开保留，不静默改字。"
                )
        groups: dict[tuple[str, str], list[int]] = {}
        for row in reference["rows"]:
            groups.setdefault((row["mansion"], row["palace_name"]), []).append(
                row["pada"]
            )
        for (mansion, palace), padas in groups.items():
            lines.append(
                f"{name}所列查表格：{mansion}第{'、'.join(str(p) for p in padas)}足为{palace}；足序不表示已排得出生足位。"
            )
    return "".join(lines)
