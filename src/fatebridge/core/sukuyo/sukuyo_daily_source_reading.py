"""Render traditional daily sources, clock witnesses and documented limits."""

from __future__ import annotations

from typing import Any

from fatebridge.core.sukuyo.sukuyo_commentarial_clock import commentarial_boundary_lines
from fatebridge.core.sukuyo.sukuyo_futen_clock import futen_clock_lines
from fatebridge.core.sukuyo.sukuyo_kenyu import printed_clock_reading_lines
from fatebridge.core.sukuyo.sukuyo_phase_clock import phase_clock_lines
from fatebridge.core.sukuyo.sukuyo_senmyo_phase import phase_annotation_lines
from fatebridge.core.sukuyo.sukuyo_waterclock import source_specific_time_lines


def daily_source_reading_lines(
    day: dict[str, Any],
    calendar: dict[str, Any],
    name: str | None,
    reference_zone: str,
) -> list[str]:
    lines: list[str] = []
    position = day["calendar_day"]["clock_doctrine"].get("textual_position_reference")
    if position:
        lines.append(
            "下卷段落位置校记：0398页注15与0399页注16两端互指，"
            "明本将248字特殊日段（太陽至禍）与93字分时段（一切至一，含平明及昼八夜八）互换位置；"
            "这是同底本所载的一组位置异文，不是两个独立见证。邻注另记删去前文的一字‘一’。"
            "∞表示位置转换，此组校记没有记八改六或删除分时段；不据此改写本曜宿字、事项或运行钟时。"
            "仅示意这组位置关系，电子校记自身没有提供具名明本原页，未由校记重建全部字句，也未解决古代日界、桧尾半日或补配次序。"
        )
        direct = position.get("direct_japanese_print_reference")
        if direct:
            lines.append(
                "京都大学附属图书馆藏《修註宿曜經》RB00017017、题录延宝九年刊另作直接印本对照："
                "帧71末至72右先见平明、每日八时、夜亦八时及明日晓时次后曜当直，随后为七曜占，"
                "特殊日表则在帧76至78。这个次序与上述位置交换方向相合，但前文諸國后的‘一’仍见于该印本，"
                "不能据位置相合就认定为大正【明】见证或混合重建全文。"
                "乃至□戌的字形保留酉／西未定，前文典籍后的具／且及并字异体也未作全段逐字验收；"
                "当直的直字可读。未由这些读字选择现代平明、昼夜时长、桧尾半日或闰小月优先。"
            )
        chinese = position.get("direct_chinese_print_reference")
        if chinese:
            lines.append(
                "台大馆藏《永樂北藏》第一三〇册影印所选上下卷的56页正文图像，"
                "与网络分卷逐页解码图像哈希一致，两处下载只计同一影像来源。"
                "印页592（整册PDF第596页）先见‘平明’、昼八夜八和‘明日曉時’，"
                "随后为七曜占，特殊日三表在印页596至597；段序与大正明本位置校记方向相合。"
                "这不能认证它就是该校记所指的明本，也未核定确切印次年代。"
                "正文译者署名有宋字，整册前置目录作唐，字面差异保留；"
                "尚未由所选五句及段序建立现代钟时、逐时七曜顺序、桧尾半日或闰小月优先。"
                "‘萬不失一’是原典效力宣称，未作为现实预测证据。"
            )
    if day["weekday"]["luminary"] == "月":
        lines.append(
            "上卷月曜主文私精与下卷私情字面不同；未改字补定上卷旅行规则，因私出行条件仅按下卷匹配。"
        )
    comparative_clock = day["calendar_day"]["clock_doctrine"].get(
        "comparative_time_systems"
    )
    if comparative_clock:
        lines.append(
            "分时原典对照：《大智度论》所选段记从旦至旦、一日夜三十时，春秋分昼十五夜十五，"
            "五月至昼十八夜十二，十一月至昼十二夜十八；"
            "《大唐西域记》正文每时五牟呼栗多、六时成一日夜，行内注为昼三夜三；"
            "居俗八时的行内注为昼四夜四，每时各四分。"
            "三十时不是现代三十小时，居俗八时也不是T1299昼八夜八；"
            "这些对照未证明旦等于平明、现代固定钟时、太阳高度或桧尾前后半，未代入本次计算。"
        )
    source_specific_clock = day["calendar_day"]["clock_doctrine"].get(
        "source_specific_time_calibration"
    )
    if source_specific_clock:
        lines.extend(source_specific_time_lines(source_specific_clock))
    commentarial_clock = day["calendar_day"]["clock_doctrine"].get(
        "commentarial_boundary_reference"
    )
    if commentarial_clock:
        lines.extend(commentarial_boundary_lines(commentarial_clock))
    phase_clock = day["calendar_day"]["clock_doctrine"].get("phase_and_time_reference")
    if phase_clock:

        lines.extend(phase_clock_lines(phase_clock))
    senmyo = day["calendar_day"]["clock_doctrine"].get(
        "senmyo_phase_annotation_reference"
    )
    if senmyo:
        lines.extend(phase_annotation_lines(senmyo))
    historical_clock = day["calendar_day"]["clock_doctrine"].get(
        "historical_clock_arithmetic"
    )
    futen_clock = day["calendar_day"]["clock_doctrine"].get(
        "futen_research_clock_arithmetic"
    )
    if futen_clock:
        lines.extend(futen_clock_lines(futen_clock))
    if historical_clock:
        lines.append(
            "具注历时刻研究对照：相马充、渡边瑞穗子、谷川清隆2019年研究所选998至1020年记录，"
            "时点按一日50刻、一刻6分、一辰刻25分；初为零刻，时正为12.5分，四刻一分到下一辰刻边界。"
            "同页昼夜长度的100刻尺度、宣明历一刻84分的100刻制、延喜式48刻制分别保留，不能混算。"
            "延喜式从第1刻编号，其分制及解码尚未接纳；不能套用具注历从零起计的时点读法。"
            "半分与半刻按名义24小时日分别相当于144秒和864秒；只是单位比值，不是本次实际钟时。"
            "英文摘要称half koku，日文摘要的‘半’未明单位，正文及表3的分半按半分增量，差别保留，未推定作者意图。"
            "表3共40组、42对读数，芒种13日与大雪13日的带半分和不带半分均保留；"
            "和数相对25分的六组非零残差未调平：大寒8日、立夏13日、大暑8日、立冬13日为多一分，"
            "另两组的两读分别少半分或一分。"
            "通日是省没日的360日平气名义轴，不直接对应公历日；末段18只闭合这个360单位循环。"
            "实际年份的没日位置和平气瞬时尚未提供，不能将通日减一加到公历冬至，也不能改用现代定气。"
            "滅日另属朔望月名义三十分段，不能据此决定桧尾补配。"
            "论文把所选日出入解释为无大气差的太阳中心过几何地平，这只是作者对该记录的推断；"
            "未重做其天文比较，也未给T1299平明设零度、转换本次日界或桧尾半日，未改变事项。"
        )
    printed_clock = day["calendar_day"]["clock_doctrine"].get("kenyu_printed_reference")
    if printed_clock:

        lines.extend(printed_clock_reading_lines(printed_clock))
    taibai = day["taibai_direction_reference"]
    lines.append(
        f"下卷太白月日方位主表在入月第{taibai['lunar_day']}日列为{taibai['location']}；这是日序查表，不是实测金星方位或天文顺逆行。顺逆行路判据尚未核定，未据此改变事项宜忌。"
    )
    if not taibai["witnesses_agree_for_selected_day"]:
        lines.append(
            "明本校记删去初十、二十、三十的天上行；本日该见证未列，不补为天上，也不解释成没有太白或行动已获允许。"
        )
    clothing = day.get("clothing_reference")
    if clothing:
        labels_clothing = {"favorable": "列可用", "caution": "按余并失列慎用"}
        membership = clothing["primary_assessment"]
        lines.append(
            "衣事专章按大正主文十四宿正表及未列宿补集核对；"
            + (
                f"本次{'已核定日宿' if clothing['mansion'] else '完整候选共同结论'}{labels_clothing[membership]}。"
                if membership
                else "本次尚无可采用的唯一或完整候选共同表项。"
            )
            + "裁缝、制作、修理、穿着及王者身份的条文另依明确动作核对。"
        )
        lines.append(
            "明本校记将井改作并，并将余并失改为并大吉；并字未补作井宿，未列宿也未补成同样慎用。专章口诀及上卷裁衣原句另作为文献见证保留，未转作现实病灾断言或事项评分。"
        )
        for candidate in clothing["candidate_references"]:
            verse = candidate.get("verse") or {}
            cutting = candidate.get("upper_literal_cutting_statement") or {}
            excerpts = [verse.get("taisho_text"), cutting.get("source_excerpt")]
            if any(excerpts):
                lines.append(
                    f"衣事候选{candidate['mansion']}宿的独立原文见证："
                    + "／".join(text for text in excerpts if text)
                    + "；口诀与上卷裁衣断语分别保留，未纳入事项汇总，不保证现实应验。"
                )
        predicate_limits = {
            "教女人裁衣服": "此条含教学与身份条件，不能泛化为任何人裁衣",
            "初王者嚴服觀兵": "此条同时要求王者严服与观兵，王者身份不能代替观兵条件，也未泛化为普通穿衣",
            "取衣取財": "取衣未自动解释为买衣，取财也未补作购买或付款事实",
        }
        for predicate in clothing["unmapped_clothing_predicates"]:
            lines.append(
                f"衣事未映射谓词：{predicate['literal']}（{predicate['locator']}）；"
                + predicate_limits.get(predicate["literal"], predicate["reason"])
                + "；未代入本次行为规则。"
            )
    six = day.get("six_palace_reference")
    if six and six["status"] == "natal_reference":
        members = "、".join(f"{r['name']}宿{r['mansion']}" for r in six["members"])
        lines.append(
            f"以已给定本命{six['natal_mansion']}宿本身计一，六宫宿为{members}（{six['locator']}）。"
            "这是本命相对位置参考；七曜运行犯宿及原文要求的三九参断均未计算，不据此生成当日吉凶。"
        )
    elif six and six["status"] == "natal_mansion_required":
        lines.append(
            "本次未提供本命宿，个人三九日关系未计算，六宫位置未计算；"
            "七曜运行犯宿未计算，原文要求的三九参断亦未完成，未以历日宿或星期代替。"
        )
    methods = day.get("lower_methods") or {}
    group = (methods.get("nature") or {}).get("selected_group")
    if group:
        lines.append(
            f"下卷按明列成员归为{group['name']}宿（{group['locator']}），与上卷分别保留；牛宿只在参考表中，不进入历日27宿。"
        )
        for variant in group["textual_variants"]:
            lines.append(
                f"下卷校勘：{variant['meaning']}（校记{variant['apparatus_id']}）。"
            )
    if methods:
        lines.append(
            f"下卷七曜证言为{methods['weekday']['literal_title']}（{methods['weekday']['locator']}）；继续按声明的{reference_zone}民用日索引，未核定平明钟时边界。"
        )
    special = day.get("special_day_evidence")
    if special:
        primary_labels = "、".join(special["primary"]["matched_labels"])
        lines.append(
            "特殊日主表采用上卷大正："
            + (
                (primary_labels or "未匹配标签")
                if name
                else "历日宿未定，候选不代入标签"
            )
            + "；下卷合宿文仅作历日宿名查表，未判定实际月亮合宿。"
        )
        for candidate in special.get("candidate_primary", []):
            candidate_labels = "、".join(candidate["matched_labels"])
            lines.append(
                f"候选{candidate['mansion']}的上卷主表"
                + (f"标签为{candidate_labels}" if candidate_labels else "未匹配标签")
                + "；未作为确定本日标签或事项结论，不以该支匹配或未匹配情况排除其他见证的未定字。"
            )
        relevant_labels = {
            label
            for witness in [
                special["primary"],
                *special["comparisons"],
                *special.get("direct_printed_comparisons", []),
                *special.get("candidate_primary", []),
            ]
            for label in witness["matched_labels"]
        }
        meanings = [
            (
                "甘露",
                "T21n1299_p0398b25-26",
                "宜冊立、受灌頂法、造作寺宇及受戒、習學經法、出家修道，一切並吉",
            ),
            (
                "金刚峰",
                "T21n1299_p0398c01-02",
                "宜作一切降伏法，誦日天子呪及作護摩，并諸猛利等事",
            ),
        ]
        lower_body = day["calendar_day"]["clock_doctrine"][
            "textual_position_reference"
        ]["blocks"][0]["normalized_base_text"]
        for label, locator, clause in meanings:
            if label in relevant_labels:
                if clause not in lower_body:
                    raise ValueError("特殊日词义参考原段已变，须重新校勘")
                lines.append(
                    f"{label}标签的传统词义另参考下卷大正{locator}：“{clause}”。"
                    "这是该卷的专门事项范围，不表示所有学习、交易或旅行均宜；"
                    "未声称其他印本说明全文相同，也不由此选择候选主宿、改变本次事项或认证现实效果。"
                )
        witness_names = {
            "upper_taisho": "上卷大正",
            "lower_taisho": "下卷大正",
            "upper_ming_apparatus": "上卷明本校记重建",
            "lower_ming_apparatus": "下卷明本校记重建",
        }
        for witness in [special["primary"], *special["comparisons"]]:
            witness_items = []
            for row in witness["rows_for_weekday"]:
                item = f"{row['label']}位{row['literal_mansion']}"
                main_literal = row.get("source_main_literal")
                if main_literal and main_literal != row["literal_mansion"]:
                    item += f"（正文{main_literal}，校记重建{row['literal_mansion']}）"
                main_weekday = row.get("source_main_weekday_index")
                if main_weekday is not None and main_weekday != row["weekday_index"]:
                    item += (
                        f"（正文{'日月火水木金土'[main_weekday]}曜，"
                        f"校记重建{row['luminary']}曜）"
                    )
                witness_items.append(item)
            matched_text = "、".join(witness["matched_labels"]) or "未匹配标签"
            if not name:
                matched_text = "日宿未定，候选不代入确定标签"
            completeness = (
                "本次标签集合完整"
                if witness["labels_complete_for_selected_day"]
                else "标签集合未定，未匹配不等于确定没有特殊日"
            )
            lines.append(
                f"{witness_names[witness['witness']]}本曜表项："
                + "、".join(witness_items)
                + f"；本次{matched_text}；{completeness}。"
            )
        for comparison in special["comparisons"]:
            witness_name = witness_names[comparison["witness"]]
            if comparison["unresolved_rows"]:
                words = "、".join(
                    r["literal_mansion"] for r in comparison["unresolved_rows"]
                )
                lines.append(
                    f"{witness_name}本曜宿字{words}未识别，不默改为胃或氐；该卷标签集合未定，不把未匹配当作无此特殊日。"
                )
            if comparison["disagrees_with_primary"]:
                witness_labels = "、".join(comparison["matched_labels"]) or "未匹配标签"
                lines.append(
                    f"{witness_name}本次为{witness_labels}，与主表不同；明本对照不代入主表或确定事项。"
                )
        if not day.get("activity_assessment"):
            lower_special = next(
                (
                    row
                    for row in special["comparisons"]
                    if row["witness"] == "lower_taisho"
                ),
                None,
            )
            lower_candidate_rasetsu = (
                [
                    row["mansion"]
                    for row in lower_special["rows_for_weekday"]
                    if row["label"] == "罗刹"
                    and row.get("mansion") in (calendar.get("candidate_su27s") or [])
                ]
                if lower_special and not name
                else []
            )
            if lower_special and (
                "罗刹" in lower_special["matched_labels"]
                or lower_special["unresolved_rows"]
                or lower_candidate_rasetsu
            ):
                lines.append(
                    "下卷罗刹条文为“不宜舉百事”，属传统事项慎用证言"
                    "（T21n1299_p0398c06）；"
                    + (
                        "本次该卷已识别宿字与组合命中，但仅为所选日宿查表，未判物理合宿。"
                        if "罗刹" in lower_special["matched_labels"]
                        else (
                            f"若主宿候选取{'、'.join(lower_candidate_rasetsu)}，该卷已识别宿字对应罗刹；"
                            "这是该候选的条件慎文，主宿仍未定，未反填确定本日标签。"
                            if lower_candidate_rasetsu
                            else "本曜宿字未识别，不能将该慎文确定应用于本日；未定字不代替条文本身的含义。"
                        )
                    )
                    + "本次没有事项输入，未形成事项汇总；不是现实失败或灾祸预告。"
                )
    return lines
