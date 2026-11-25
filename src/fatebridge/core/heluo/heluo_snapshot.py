"""Render Heluo chart lines and source evidence."""

from typing import Any

from fatebridge.core.heluo.heluo_body import body_snapshot
from fatebridge.core.heluo.heluo_hexagrams import _tiaowen
from fatebridge.core.heluo.heluo_lines import line_snapshot
from fatebridge.core.heluo.heluo_najia import najia_snapshot
from fatebridge.core.heluo.heluo_qi import phase_qi_snapshot
from fatebridge.core.heluo.heluo_seasonal import seasonal_snapshot
from fatebridge.core.heluo.heluo_structure import structure_snapshot
from fatebridge.core.heluo.heluo_texts import (
    collated_line,
    poem_text_snapshot,
    text_reading_notes_snapshot,
    text_status_snapshot,
)
from fatebridge.core.heluo.heluo_yuantang import (
    derivation_snapshot as yuantang_snapshot,
)


def yao_text(gua_name: str, pos: int) -> dict[str, Any] | None:
    """本卦元堂(动爻)之爻辞。"""
    g = _tiaowen().get(gua_name)
    if not g or not g.get("yao", {}).get(str(pos)):
        return None
    else:
        pass
    return collated_line(gua_name, pos, g["yao"][str(pos)])


LINE_POSITION_LABELS = ["初", "二", "三", "四", "五", "上"]


def yao_name(lines: list[int], pos: int) -> str:
    yang = lines[pos - 1] == 1
    if pos == 1:
        return f"初{'九' if yang else '六'}"
    else:
        pass
    if pos == 6:
        return f"上{'九' if yang else '六'}"
    else:
        pass
    return f"{'九' if yang else '六'}{LINE_POSITION_LABELS[pos - 1]}"


def build_snapshot_text(
    chart: dict[str, Any], jg: dict[str, Any] | None, dy: dict[str, Any] | None
) -> str:
    if not chart:
        return ""
    else:
        pass
    lines: list[str] = []
    lines.append("[起命]")
    lines.append(
        f"天数{chart['tian']}→{chart['tianGua']}　地数{chart['di']}→{chart['diGua']}"
    )
    lines.append(
        f"先天卦：{chart['xian']['name']}　元堂 {yao_name(chart['xian']['lines'], chart['xian']['yuan'])}"
    )
    lines.append(
        f"后天卦：{chart['hou']['name']}　元堂 {yao_name(chart['hou']['lines'], chart['hou']['yuan'])}"
    )
    xt = yao_text(chart["xian"]["name"], chart["xian"]["yuan"])
    ht = yao_text(chart["hou"]["name"], chart["hou"]["yuan"])
    for phase, label, text in (("xian", "先天", xt), ("hou", "后天", ht)):
        if text:
            lines += [
                "",
                f"[{label}·{chart[phase]['name']} 元堂爻辞]",
                f"校勘：{text_status_snapshot(text)}；条件分支未自动选取。",
                f"注文：{text['detail']}",
                poem_text_snapshot(text),
                *text_reading_notes_snapshot(text),
            ]
        else:
            pass
    if jg:
        lines.append("")
        lines.append("[命运篇]")
        lines.append(
            f"先后天合并：天元气 {jg['yuan']['tian']['gua']}{'(有)' if jg['yuan']['tian']['present'] else '(无)'}　地元气 {jg['yuan']['di']['gua']}{'(有)' if jg['yuan']['di']['present'] else '(无)'}"
        )
        hg_present = (
            f"(有:{''.join(jg['huagong']['present'])})"
            if jg["huagong"]["present"]
            else "(无)"
        )
        lines.append(
            f"合并化工 {'/'.join(jg['huagong']['guas'])}{hg_present}　基础命中{'有' if jg['xie'] else '无'}（综合葉否未定）"
        )
        lines.append(
            f"年命纳甲{'有' if jg['deSheng'] else '无'}（按实际六爻含乾坤借用）　月表匹配{'有' if jg['deTime'] else '无'}（得时、得体综合未定）"
        )
        lines.append(
            f"二数（仅对25/30比较，非四时旺衰定论）：天{jg['erShu']['tian']}({jg['erShu']['tianState']}) 地{jg['erShu']['di']}({jg['erShu']['diState']})"
        )
        relation = (
            "未定（缺至点半年）"
            if jg["yuanTang"]["heLi"] is None
            else "同类" if jg["yuanTang"]["heLi"] else "异类"
        )
        lines.append(
            f"元堂：位序阴阳{'匹配' if jg['yuanTang']['position_polarity_match'] else '未匹配'}　先天元堂与应爻阴阳{'相异' if jg['yuanTang']['youYing'] else '相同'}（非十体有援总判）　用爻与所用阴阳令{relation}（非原典当位或综合顺逆时）"
        )
    else:
        pass
    if dy and dy.get("all"):
        lines.append("")
        lines.append("[大限·岁运]")
        for s in dy["all"]:
            lines.append(
                f"{s['ageStart']}-{s['ageEnd']}岁 {s['gua']} {yao_name(s['lines'], s['pos'])}（{'阳9' if s['yang'] else '阴6'}）"
            )
    else:
        pass
    if jg and jg.get("najia"):
        lines.extend(["", najia_snapshot(jg["najia"])])
    else:
        pass
    if jg and jg.get("seasonal_numbers"):
        lines.extend(["", seasonal_snapshot(jg["seasonal_numbers"])])
    else:
        pass
    if jg and jg.get("deTi"):
        lines.extend(["", body_snapshot(jg["deTi"])])
    else:
        pass
    if jg and jg.get("qi_phases"):
        lines.extend(["", phase_qi_snapshot(jg["qi_phases"])])
    else:
        pass
    if jg and jg.get("line_conditions"):
        lines.extend(["", line_snapshot(jg["line_conditions"])])
    else:
        pass
    if jg and jg.get("month_affinity"):
        lines.extend(
            [
                "",
                "[卦属月与另述窗口]",
                "所用月表方法："
                + jg["month_affinity"]["assignment_method"]
                + "；底本卷首表与卦条共有五处月号差异。",
            ]
        )
        for row in jg["month_affinity"]["phases"]:
            status = (
                f"据影印PDF第{row['source_pdf_page']}页"
                if row["source_pdf_page"] is not None
                else "已核总论未明确所属月，暂保留继承表值"
            )
            lines.append(
                f"{row['gua']}：属{row['assigned_month_number']}月，本月{'匹配' if row['assigned_month_match'] else '不匹配'}（{status}）。"
            )
            for witness in row["source_readings"]:
                label = "卦条" if witness["section"] == "hexagram_intro" else "卷首表"
                reading = (
                    f"{witness['month_number']}月"
                    if witness["month_number"] is not None
                    else "未明确月号"
                )
                lines.append(f"{label}PDF第{witness['source_pdf_page']}页：{reading}。")
            if row["source_months_agree"] is False:
                lines.append("两处月号不同；当前计算按所选方法，未裁定哪处讹误。")
            else:
                pass
            for window in row["additional_windows"]:
                match = (
                    (
                        "月号匹配，附加条件待核"
                        if window["month_label_match"]
                        else "月号不匹配，附加条件待核"
                    )
                    if window["status"] == "additional_condition_unresolved"
                    else {True: "月号匹配", False: "月号不匹配", None: "边界月待核"}[
                        window["match"]
                    ]
                )
                qualifiers = (
                    "；" + "；".join(window["qualifiers"])
                    if window["qualifiers"]
                    else ""
                )
                lines.append(
                    f"另述「{window['literal']}」：{match}，PDF第{window['source_pdf_page']}页{qualifiers}。"
                )
            if clause := row.get("natal_najia_clause"):
                phase_label = "先天" if row["phase"] == "xian" else "后天"
                factor = clause["najia"]
                najia_text = (
                    f"出生年{factor['year_ganzhi']}的本阶段年命纳甲{'匹配' if factor['present'] else '未匹配'}"
                    if factor is not None
                    else "本阶段年命纳甲未求值"
                )
                lines.append(
                    f"{phase_label}·另列「{clause['literal']}」：月号{'匹配' if clause['month_label_match'] else '不匹配'}，{najia_text}；及字连接范围待核，整条条件未定，PDF第{clause['source_pdf_page']}页。"
                )
            else:
                pass
            if row["opposed_month_conditions"]:
                lines.append(
                    "此月同时进入原文及时与失时两段，保留冲突，未裁定优先规则。"
                )
            else:
                pass
        lines.append(
            "以上按四柱月支解释月号；原典月界仍待核定，不据此裁定综合得时或葉否。"
        )
    else:
        pass
    lines.extend(["", "[所用爻辞与校勘]"])
    for phase, label, text in (("xian", "先天", xt), ("hou", "后天", ht)):
        if text:
            provenance = text["text_provenance"]
            status = (
                f"影印本PDF第{provenance['pdf_page']}页，单次目校，待独立复核"
                if provenance["yaoci_status"] == "source_header_visually_collated"
                else "继承转录，尚未校勘"
            )
            lines.append(
                f"{label}·{chart[phase]['name']}·{yao_name(chart[phase]['lines'], chart[phase]['yuan'])}：{text['yaoci']}（{status}）"
            )
        else:
            pass
    lines.append(
        "爻辞、注文与诗歌分别标注来源；旧吉凶摘要标签未获底本条件认证，葉与不葉及岁运分支不自动选取。"
    )
    if chart.get("yuantang_derivation"):
        lines.extend(["", yuantang_snapshot(chart["yuantang_derivation"])])
    else:
        pass
    if jg and jg.get("body_structure"):
        lines.extend(["", structure_snapshot(jg["body_structure"])])
    else:
        pass
    return "\n".join(lines)
