"""Render the supplied Hinoo evidence without promoting it to a new edition."""

from __future__ import annotations

import html
import re
from typing import Any

from fatebridge.core.sukuyo_hinoo_catalog import catalogue_lines
from fatebridge.core.sukuyo_hinoo_context import context_lines
from fatebridge.core.sukuyo_hinoo_meanings import calendar_clause_meaning_lines
from fatebridge.core.sukuyo_hinoo_natal_scope import natal_scope_lines
from fatebridge.core.sukuyo_kyoto_layers import layered_reading_lines
from fatebridge.core.sukuyo_seibunkan import seibunkan_lines
from fatebridge.core.sukuyo_witness_research import (
    native_completion_lines,
    native_followup_lines,
    research_lines,
)
from fatebridge.core.sukuyo_zentsuji_later import later_reading_lines


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
    downloaded = source.get("downloaded_primary_edition")
    if downloaded and source["active_primary_evidence"] == "downloaded_primary_edition":
        lines.append(
            "本次活动证据为SAT完整HTML响应，指纹"
            f"{downloaded['publisher_html_response_sha256']}；"
            "历史缓存摘录分别保留，摘录哈希不代表完整响应或抄本。"
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
        if natal := critical.get("natal_half_application"):
            lines.extend(natal_scope_lines(natal))
        if later := critical.get("later_seibunkan_comparison"):
            lines.extend(seibunkan_lines(later))
        lines.extend(catalogue_lines(critical["witness_catalogue_candidates"]))
        if research := critical.get("image_witness_research"):
            lines.extend(research_lines(research))
        if native := critical.get("image_witness_native_followup"):
            lines.extend(native_followup_lines(native))
        if completed := critical.get("image_witness_native_completion"):
            lines.extend(native_completion_lines(completed))
        if context := critical.get("image_witness_context_followup"):
            lines.extend(context_lines(context))
        primary = critical["selected_primary"]
        for glyph in primary["unaccepted_glyphs"]:
            if not glyph["accepted_as_a_normalized_variant"]:
                lines.append(
                    f"京都所选末句候选{glyph['candidate_reading']}仍未接纳为规范异文；"
                    f"大正读法{glyph['taisho_reading']}分别保留，不补定墨点或疑字。"
                )
        if not primary["independent_human_transcription_accepted"]:
            lines.append("所选归一化工作录未获独立人工验收；红校层未据此合成完整版本。")
        if layered := primary.get("later_layered_reading"):
            lines.extend(layered_reading_lines(layered))
        for witness in critical.get("supplemental_witnesses", []):
            lines.append(
                f"补充直接见证：{witness['holding_institution']}"
                f"{witness['call_number']}《{witness['title']}》，"
                f"{witness['catalogue_url']}；所用第{witness['canvas_one_based']}帧，"
                f"原图指纹{witness['image_sha256']}，来源包指纹{witness['source_bundle_sha256']}。"
            )
            if witness.get("later_reading_followup"):
                lines.append(
                    "以下善通寺原文为既有首录；后续校读的未决分歧另列，"
                    "不得将旧片段当作已统一定字。"
                )
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
        boundary = critical["day_boundary_reference"]
        lines.append(
            f"T1299所选日界原段{boundary['locator']}明说{boundary['starting_boundary_literal']}"
            f"起曜、至{boundary['next_boundary_literal']}换曜，日夜各{boundary['day_parts']}时；"
            "未据此确定现代钟时、太阳高度或完整日内曜序，也未将桧尾半日等同昼夜分界。"
        )
    return lines
