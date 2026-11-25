"""Render the supplied Hinoo evidence without promoting it to a new edition."""

from __future__ import annotations

import html
import re
from typing import Any

from fatebridge.core.sukuyo.sukuyo_hinoo_catalog import catalogue_lines
from fatebridge.core.sukuyo.sukuyo_hinoo_context import context_lines
from fatebridge.core.sukuyo.sukuyo_hinoo_meanings import calendar_clause_meaning_lines
from fatebridge.core.sukuyo.sukuyo_hinoo_natal_scope import natal_scope_lines
from fatebridge.core.sukuyo.sukuyo_kyoto_layers import layered_reading_lines
from fatebridge.core.sukuyo.sukuyo_printed_pages import hinoo_printed_page_lines
from fatebridge.core.sukuyo.sukuyo_seibunkan import seibunkan_lines
from fatebridge.core.sukuyo.sukuyo_witness_research import (
    native_completion_lines,
    native_followup_lines,
    research_lines,
)
from fatebridge.core.sukuyo.sukuyo_zentsuji_later import later_reading_lines


def _plain(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def hinoo_source_lines(source: dict[str, Any]) -> list[str]:
    lines = [
        f"所据{source['author']}：闰月段{source['leap_locator']}，小月段{source['short_month_locator']}。",
        source["scope"],
        source["half_interpretation"],
        source["provenance_scope"],
    ]
    cached = source.get("cached_primary_excerpt")
    if cached:
        lines.extend(cached["reading_notes"])
    else:
        pass
    downloaded = source.get("downloaded_primary_edition")
    if downloaded and source["active_primary_evidence"] == "downloaded_primary_edition":
        lines.append(
            "本次活动证据为SAT完整HTML响应；历史缓存摘录分别保留，"
            "摘录不代表完整响应或抄本。"
        )
        lines.append(
            "SAT见证注：" + _plain(downloaded["edition_witness_note_html"]) + "。"
        )
        for window in downloaded["downloaded_calendar_windows"]:
            lines.append(
                f"SAT所选原段{window['locator']}（底本文字）：{window['text']}"
            )
        for note in downloaded["calendar_apparatus"]:
            lines.append(
                f"SAT校记{note['line']}："
                + "；".join(_plain(n) for n in note["notes_html"])
                + "；保留底本、甲本与イ读法的区别，不合成唯一正文。"
            )
        for difference in downloaded["cached_quotation_discrepancies"]:
            lines.append(
                f"缓存引文差异{difference['locator']}：历史缓存末文"
                f"{difference['cached_terminal_text']}，下载末文"
                f"{difference['downloaded_terminal_text']}；"
                + (
                    "本项记录为意义未变，原缓存未改写。"
                    if not difference["meaning_changed"]
                    else "本项记录有意义差别，不能静默归一。"
                )
            )
        lines.append(
            "完整HTML响应不等于原抄本、全部嵌入字图或影印校勘，未由此取得独立学术验收。"
        )
    else:
        lines.append(
            f"当前活动取证标识为{source.get('active_primary_evidence')}；未将历史缓存冒称新取得的完整原典。"
        )
    critical = source.get("critical_calendar_reference")
    if critical:
        if meanings := critical.get("calendar_clause_meanings"):
            lines.extend(calendar_clause_meaning_lines(meanings))
        else:
            pass
        if natal := critical.get("natal_half_application"):
            lines.extend(natal_scope_lines(natal))
        else:
            pass
        if later := critical.get("later_seibunkan_comparison"):
            lines.extend(seibunkan_lines(later))
        else:
            pass
        lines.extend(catalogue_lines(critical["witness_catalogue_candidates"]))
        if research := critical.get("image_witness_research"):
            lines.extend(research_lines(research))
        else:
            pass
        if native := critical.get("image_witness_native_followup"):
            lines.extend(native_followup_lines(native))
        else:
            pass
        if completed := critical.get("image_witness_native_completion"):
            lines.extend(native_completion_lines(completed))
        else:
            pass
        if context := critical.get("image_witness_context_followup"):
            lines.extend(context_lines(context))
        else:
            pass
        primary = critical["selected_primary"]
        for glyph in primary["unaccepted_glyphs"]:
            if not glyph["accepted_as_a_normalized_variant"]:
                lines.append(
                    f"京都所选末句候选{glyph['candidate_reading']}仍未接纳为规范异文；"
                    f"大正读法{glyph['taisho_reading']}分别保留，不补定墨点或疑字。"
                )
            else:
                pass
        if not primary["independent_human_transcription_accepted"]:
            lines.append("所选归一化工作录未获独立人工验收；红校层未据此合成完整版本。")
        else:
            pass
        if layered := primary.get("later_layered_reading"):
            lines.extend(layered_reading_lines(layered))
        else:
            pass
        for witness in critical.get("supplemental_witnesses", []):
            lines.append(
                f"补充直接见证：{witness['holding_institution']}"
                f"{witness['call_number']}《{witness['title']}》，"
                f"{witness['catalogue_url']}；所用第{witness['canvas_one_based']}帧。"
            )
            if witness.get("later_reading_followup"):
                lines.append(
                    "以下善通寺原文为既有首录；后续校读的未决分歧另列，"
                    "不得将旧片段当作已统一定字。"
                )
            else:
                pass
            for row in witness["observations"]:
                lines.append(f"善通寺所选原文：{row['normalized_transcription']}。")
            for row in witness["selected_example_comparisons"]:
                lines.append(
                    f"十二月{row['lunar_day']}日比较：善通寺"
                    f"{row['witness_literal_mansion']}、大正{row['taisho_literal_mansion']}、"
                    f"宿主算法{row['host_calculated_mansion']}；文字对照不覆盖运行配宿。"
                )
            lines.append(
                "善通寺首日直与京都所选重分别保留，善通寺三十日室与大正星分别保留；"
                "善通寺末句直宿無改代也不用于补定京都未决末句。"
            )
            lines.append(
                "善通寺半与上者之间、半与下者之间的字形未定，所列片段没有补字；"
                "依口説不据此认作甲本。末页只选读明和七年十月题记，"
                "未独立确定现存实物年代、传承关系或底本／甲本身份。"
            )
            lines.append(
                "摄影卡所列平成16年7月是摄影记录，不能当作抄写日期；"
                "本轮读录沿用了已知算法的历史上下文，并非对预期宿名设盲。"
            )
            lines.append(
                "本件不是善通寺109-5《护摩法略抄》；所选见证未获独立人工读录验收或全本校勘，"
                "不由多数、与算法相合或单宿结果裁定闰小月优先，也未确定古代平明或半日钟时。"
            )
            if followup := witness.get("later_reading_followup"):
                lines.extend(later_reading_lines(followup))
            else:
                pass
        collation = primary.get("supplemental_model_collation")
        if collation:
            for row in collation["conflicts"]:
                selected = row["selected_root_reading"] or "未定"
                lines.append(
                    f"所绑定历史补充模型首读在{row['location_zh']}有分歧："
                    f"生成角色读{row['generator']}、复核角色读{row['reviewer']}；"
                    f"该历史记录中根任务当时选读为{selected}，不是本次请求重读。"
                )
            lines.append(
                "首日重是既有根任务按同一原图选取的工作读，后续直／重分歧仍存；"
                "未改配宿数值，三十日婁／室异读及末句分歧照留，"
                "未以多数或与算法相合裁定，没有据此接纳完整校勘本或改变补配优先。"
            )
        else:
            pass
        boundary = critical["day_boundary_reference"]
        lines.append(
            f"T1299所选日界原段{boundary['locator']}明说{boundary['starting_boundary_literal']}"
            f"起曜、至{boundary['next_boundary_literal']}换曜，日夜各{boundary['day_parts']}时；"
            "未据此确定现代钟时、太阳高度或完整日内曜序，也未将桧尾半日等同昼夜分界。"
        )
    else:
        pass
    return lines


def hinoo_unassigned_month_start_lines(
    calendar: dict[str, Any], profile: dict[str, Any]
) -> list[str]:
    """Explain an unneeded split using the predecessor already in the trace."""
    if (
        not profile.get("hinoo_source")
        or calendar.get("lunar_day") != 1
        or profile.get("short_month_assignment") is not None
    ):
        return []
    else:
        pass
    trace = next(
        (
            row
            for row in calendar.get("rule_trace", [])
            if row.get("rule_id") == "t2465_repeat_and_short_month_assignment"
        ),
        None,
    )
    previous = trace["inputs"].get("previous_lunar") if trace else None
    if previous is None:
        return []
    else:
        pass
    month_label = "大" if previous["lunar_day"] == 30 else "小"
    month_label += "闰月" if previous["is_leap_month"] else "月"
    return [
        f"本次初一所用前一参考日为{previous['calendar_date']}，"
        f"农历{previous['lunar_year']}年"
        f"{'闰' if previous['is_leap_month'] else ''}"
        f"{previous['lunar_month']}月{previous['lunar_day']}日；"
        f"相邻前月为{previous['lunar_day']}日{month_label}。"
        + (
            "前月没有缺失第三十日，本次未生成小月分宿，仍按实际档案结果交付；"
            if previous["lunar_day"] == 30
            else "本次未生成小月分宿，所列相邻前月事实与档案分配状态分别保留；"
        )
        + "这不确定原典半日钟时或闰小月优先次序。"
    ]


def _hinoo_critical_lines(reference: dict[str, Any]) -> list[str]:
    primary = reference["selected_primary"]
    comparisons = reference["selected_example_comparisons"]

    def examples(field: str) -> str:
        return "、".join(
            f"{r['lunar_month']}月{r['lunar_day']}日{r[field]}" for r in comparisons
        )

    lines = [
        f"京都大学藏《{primary['title']}》第{primary['canvas_index_one_based']}幅所选黑字："
        + examples("kyoto_manuscript_mansion")
        + "；大正选文："
        + examples("taisho_literal_mansion")
        + "；本档案宿主望宿算法："
        + examples("host_calculated_mansion")
        + "。各项分别保留，写本例题未替换计算结果。"
        "这三项为既有归一化工作选录的字符串对照，"
        "后段叠改数字另属不同字位，不将相合称为独立校勘验收。"
    ]
    limits = [f"目录记作{primary['catalogue_copy_description']}"]
    if not primary["copy_date_established"]:
        limits.append("写成日期未定")
    else:
        pass
    if not primary["identified_as_taisho_base_or_ko_witness"]:
        limits.append("未识别为大正底本或甲本")
    else:
        pass
    if not reference["complete_critical_edition_accepted"]:
        limits.append("尚未完成全本校勘")
    else:
        pass
    lines.append("；".join(limits) + "，不据所选例题裁定补配次序或半日钟时。")
    span = reference["apparatus_span_reference"]
    lines.append(
        f"十六字校记按字数限定的候选范围为{span['normalized_candidate_span']}"
        f"（{span['character_count']}字）；保留イ标记，未独立取得甲本，不将其认定为无条件删文。"
    )
    if "current_scope_qualification" in span:
        lines.append(span["scope"])
    else:
        pass

    lines.extend(hinoo_printed_page_lines())
    return lines


def profile_calculation_lines(selection: dict[str, Any] | None) -> list[str]:
    """Render only the supplied profile calculations and their source conditions."""
    lines: list[str] = []
    if selection:
        host = selection["host_calculation"]
        lines.append(
            f"历法档案{selection['calendar_profile']}：本月表定十五日望宿为{host['fullmoon_mansion']}，逆顺法与生日加十三含首计数均得{host['direct_mansion']}；表定望日不等于实际满月瞬间。"
        )
        assignment = selection.get("short_month_assignment")
        if assignment:
            first, second = assignment["slots"]
            first_text = "、".join(first["candidate_mansions"])
            lines.append(
                f"相邻前月有{assignment['previous_lunar']['lunar_day']}日；T2465分宿重建前半候选{first_text}、后半{second['mansion']}（{assignment['locator']}）。"
            )
            previous = assignment["previous_lunar"]
            lines.append(
                f"相邻前月末为农历{previous['lunar_year']}年"
                f"{'闰' if previous['is_leap_month'] else ''}{previous['lunar_month']}月{previous['lunar_day']}日。"
            )
            omitted = assignment.get("omitted_day_calculation")
            if omitted:
                host = selection["host_calculation"]
                lines.append(
                    f"相邻月补配路径的前半使用该月缺失三十日，按{omitted['lunar_month']}月{omitted['lunar_day']}日查得{omitted['direct_mansion']}；"
                    f"本月常规初一另按{host['lunar_month']}月{host['lunar_day']}日查得{host['direct_mansion']}，也是后半的来源。"
                    "宿名相同仍分别保留来源；闰月初一若有另一重建路径，继续按下列分支交付。"
                )
            else:
                pass
            if assignment["selected_day_part"]:
                part = (
                    "前半"
                    if assignment["selected_day_part"] == "first_half"
                    else "后半"
                )
                lines.append(
                    f"已明确提供原典日序{part}；"
                    + (
                        "按此取宿，没有按民用钟时自动判半。"
                        if selection["resolved"]
                        else "规则次序仍有歧义，未取唯一宿；没有按民用钟时自动判半。"
                    )
                )
            elif first["candidate_mansions"] == second["candidate_mansions"]:
                lines.append("两个半日候选同宿，故宿名已定；未推断半日钟时。")
            else:
                lines.append(
                    "前/后半未定，候选宿全部保留；已知民用钟时不自动解决原典半日界。"
                )
            precedence = assignment.get("leap_short_month_precedence")
            if precedence:
                for branch in precedence["reconstruction_calculations"]:
                    label = {
                        "adjacent_month_short_day_assignment": "相邻月补配重建",
                        "repeat_regular_month_first_day_assignment": "重用普通月初一重建",
                    }[branch["id"]]
                    previous = branch["previous_lunar"]
                    first_calc = branch["first_half_calculation"]
                    second_calc = branch["second_half_calculation"]
                    lines.append(
                        f"{label}：所用前月末为农历{previous['lunar_month']}月{previous['lunar_day']}日；"
                        f"前半按{first_calc['lunar_month']}月{first_calc['lunar_day']}日查得{first_calc['direct_mansion']}，"
                        f"后半按{second_calc['lunar_month']}月{second_calc['lunar_day']}日查得{second_calc['direct_mansion']}。"
                    )
            else:
                pass
            if (
                precedence
                and precedence["adjacent_month_first_half"]
                != precedence["repeat_true_month_first_half"]
            ):
                lines.append(
                    "闰月复用与缺日分宿的先后未由原典明确，两个现代重建次序在前半不同；未将重建分支说成原典两条明定算法。"
                )
            else:
                pass
        else:
            pass
        if selection.get("hinoo_source"):

            lines.append(
                "Hinoo研究档案使用T1299望宿主表，保留T2465十二月三十日星/室字面差异；未复原历史日本旧历。"
            )
            critical = selection["hinoo_source"].get("critical_calendar_reference")
            if critical:
                lines.extend(_hinoo_critical_lines(critical))
            else:
                pass
            lines.extend(hinoo_source_lines(selection["hinoo_source"]))
        else:
            pass
    else:
        pass
    return lines
