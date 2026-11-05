"""Evidence for the implemented Heluo / Jin Suo Yin Chi rules.

Edition agreement, port parity, quotation fidelity and predictive performance
are independent claims. In particular, a corpus hash is not a collation.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.canping_texts import collation_summary as canping_collation_summary
from fatebridge.core.heluo_najia import collation_summary as najia_collation_summary
from fatebridge.core.heluo_poems import collation_summary as poem_collation_summary
from fatebridge.core.heluo_texts import collation_summary, commentary_collation_summary
from fatebridge.core.zhouyi import classical_hexagram

VOLUME_ONE = "https://www.shidianguji.com/book/NA09030/chapter/1m8od60nhc1me"
VOLUME_SIX = "https://www.shidianguji.com/zh/book/NA09030/chapter/1m8od6rwizt4b"


@lru_cache(maxsize=2)
def _corpus_sha(technique: str) -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / technique
        / f"{technique}Tiaowen.json"
    )
    return sha256(path.read_bytes()).hexdigest()


def _base(technique: str, method_id: str) -> dict[str, Any]:
    return {
        "rulesets": [
            {
                "ruleset_id": method_id,
                "version": "1.0.0",
                "source_title": "河洛理數（史應選校訂本）",
                "source_url": VOLUME_ONE if technique == "heluo" else VOLUME_SIX,
                "source_status": "digital_transcription_with_ocr_errors; full_scan_collation_pending",
                "authorship_status": "traditional_attribution_not_independently_established",
            }
        ],
        "corpus_sha256": _corpus_sha(technique),
        "corpus_status": "inherited_transcription_not_fully_collated",
        "validation_status": {
            "calendar": "instant_based_shared_calendar; external_reference_tests_have_limited_coverage",
            "classical": "partial_rule_audit",
            "interpretation": "structured_selection_and_trace; free_text_interpretations_not_certified",
            "prediction": "not_validated",
        },
        "interpretation_constraints": [
            "传统条文是历史材料；不得当作现实事实、临床结论或寿命灾祸断言。",
            "算例通过不证明现实预测有效；不得把规则命中或测试通过率换成成功概率。",
            "缺条、空条、缺字仅表示本地语料不可用或待校勘，不据此推断现实吉凶。",
        ],
        "rule_trace": [],
    }


def heluo_evidence(chart: dict, judge: dict, solar: dict, pillars: dict) -> dict:
    from fatebridge.core.heluo import GAN_NUM, ZHI_PAIR, yao_text
    from fatebridge.core.heluo_timing import RULESET_ID, SOURCE_SHA256, SOURCE_URL

    result = _base("heluo", "heluo_shi_yingxuan_partial_v1")
    result["najia_collation"] = najia_collation_summary()
    result["yaoci_collation"] = collation_summary()
    result["commentary_collation"] = commentary_collation_summary()
    result["poem_collation"] = poem_collation_summary()
    line_evidence = judge["line_conditions"]
    result["rulesets"].append(
        {
            "ruleset_id": line_evidence["ruleset_id"],
            "version": line_evidence["version"],
            "source_title": "河洛理數卷一·论六爻位序、二五位、众宗与主本有援原句",
            "source_url": line_evidence["source_url"] + "#page=45",
            "source_pdf_sha256": line_evidence["source_pdf_sha256"],
            "source_status": line_evidence["review_status"],
        }
    )
    yuantang = chart["yuantang_derivation"]
    result["rulesets"].append(
        {
            "ruleset_id": yuantang["ruleset_id"],
            "version": yuantang["version"],
            "source_title": "河洛理數（上海文明書局印行本）卷一·元堂爻位图式与换后天",
            "source_url": yuantang["source_url"] + "#page=26",
            "source_pdf_sha256": yuantang["source_pdf_sha256"],
            "source_status": yuantang["review_status"],
        }
    )
    commentary = result["commentary_collation"]
    result["rulesets"].append(
        {
            "ruleset_id": commentary["corpus_id"],
            "version": commentary["version"],
            "source_title": f"河洛理數（上海文明書局印行本）卷二上·已核逐爻注文（{commentary['collated_line_commentaries']}条）",
            "source_url": commentary["source_url"] + "#page=119",
            "source_pdf_sha256": commentary["source_pdf_sha256"],
            "source_status": commentary["review_status"],
            "source_content_sha256": commentary["content_sha256"],
        }
    )
    poems = result["poem_collation"]
    result["rulesets"].append(
        {
            "ruleset_id": poems["corpus_id"],
            "version": poems["version"],
            "source_title": poems["source_title"],
            "source_url": poems["source_url"] + "#page=2",
            "source_pdf_sha256": poems["source_pdf_sha256"],
            "source_status": poems["review_status"],
            "source_content_sha256": poems["content_sha256"],
        }
    )
    result["interpretation_constraints"].append(
        "觀四外買／外賈、師二堪与拯的土旁异体家族、師五突咎／灾咎／災咎／突咨仍有未决读法；按逐条reading_notes保留暂录与候选，不据暂读选义、生成个人事件或证明全书已定。觀五不叶者亦中正君子的原文不能改成否定；叶否、岁运及病者／妇人子句均未自动选用。"
    )
    qi = judge["qi_phases"]
    opposition = qi["yuanqi_opposition"]
    result["rulesets"].append(
        {
            "ruleset_id": opposition["ruleset_id"],
            "version": opposition["version"],
            "source_title": opposition["source_title"],
            "source_url": opposition["source_url"] + "#page=33",
            "source_pdf_sha256": opposition["source_pdf_sha256"],
            "source_content_sha256": opposition["content_sha256"],
            "source_status": opposition["review_status"],
        }
    )
    result["rulesets"].append(
        {
            "ruleset_id": qi["ruleset_id"],
            "version": qi["version"],
            "source_title": "河洛理數卷一·元气化工、反化工重叠及先后天得失",
            "source_url": qi["source_url"],
            "source_pdf_sha256": qi["source_pdf_sha256"],
            "source_status": "selected_sections_PDF_32_33_34_35_50_51_63_visually_read; two_printings; independent_second_review_pending",
        }
    )
    bodies = judge["deTi"]
    result["rulesets"].append(
        {
            "ruleset_id": bodies["ruleset_id"],
            "version": bodies["version"],
            "source_title": "河洛理數卷一·得体、合理、纳音相生及互体",
            "source_url": bodies["source_url"],
            "source_pdf_sha256": bodies["source_pdf_sha256"],
            "source_status": "PDF_32_46_51_87_visually_read; year_nayin_and_directed_relations_named; full_deti_pending",
        }
    )
    month_evidence = judge["month_affinity"]
    result["rulesets"].append(
        {
            "ruleset_id": month_evidence["ruleset_id"],
            "version": month_evidence["version"],
            "source_title": "河洛理數（上海文明書局印行本）卦属月与另述得时窗口",
            "source_url": month_evidence["source_url"],
            "source_pdf_sha256": month_evidence["source_pdf_sha256"],
            "source_status": "64_introductions_and_volume_one_table_reviewed; 63_intro_and_64_table_months; five_source_conflicts_retained; thirteen_month_najia_connectors_and_boundary_convention_pending; independent_second_review_pending",
        }
    )
    seasonal = judge["seasonal_numbers"]
    result["rulesets"].append(
        {
            "ruleset_id": seasonal["ruleset_id"],
            "version": seasonal["version"],
            "source_title": "河洛理數（上海文明書局印行本）卷一天地数与时损益",
            "source_url": seasonal["source_url"],
            "source_pdf_sha256": seasonal["source_pdf_sha256"],
            "source_status": "PDF_pages_64_to_74_visually_collated; literal_conditions_and_overlaps_retained",
        }
    )
    result["rulesets"].append(
        {
            "ruleset_id": RULESET_ID,
            "version": "1.0.0",
            "source_title": "河洛理數（上海文明書局印行本）卷一小象年月日定式",
            "source_url": SOURCE_URL + "#page=37",
            "source_pdf_sha256": SOURCE_SHA256,
            "source_status": "PDF_pages_37_to_40_visually_collated; full_book_collation_pending",
            "authorship_status": "traditional_attribution_not_independently_established",
        }
    )
    result["rulesets"].append(
        {
            "ruleset_id": "heluo_hexagram_najia_qiankun_borrowed_v2",
            "version": "2.2.0",
            "source_title": "河洛理數（上海文明書局印行本）纳甲及借用",
            "source_url": SOURCE_URL + "#page=119",
            "source_pdf_sha256": SOURCE_SHA256,
            "source_status": f"{result['najia_collation']['directly_collated_hexagrams']}_hexagram_entries; {result['najia_collation']['pure_trigram_tables']}_pure_tables; {result['najia_collation']['direct_assignment_observations']}_direct_and_{result['najia_collation']['borrowed_assignment_observations']}_borrowed_observations; {result['najia_collation']['other_hexagrams_not_individually_collated']}_other_entries_not_individually_collated; independent_second_review_pending",
            "authorship_status": "traditional_attribution_not_independently_established",
        }
    )
    trace = result["rule_trace"]
    trace.append(
        {
            "rule_id": line_evidence["ruleset_id"],
            "source_section": "卷一三三至三五·论六爻与十体小注；主本阴元堂阳应爻有援式，位序阴阳不代原典当位",
            "facts": deepcopy(line_evidence),
        }
    )
    trace.append(
        {
            "rule_id": yuantang["ruleset_id"],
            "source_section": "卷一一四至二〇·元堂图式、纯爻男女与至点方向、换后天及三至尊",
            "facts": deepcopy(yuantang),
        }
    )
    trace.append(
        {
            "rule_id": qi["ruleset_id"],
            "source_section": "卷一·论元气、论化工及反例、先后天得失、正逢与互德",
            "facts": deepcopy(qi),
        }
    )
    trace.append(
        {
            "rule_id": opposition["ruleset_id"],
            "source_section": "卷一·元气相反无正而有反原句及反中有救说；逐阶段具名卦体范围",
            "facts": deepcopy(opposition),
        }
    )
    trace.append(
        {
            "rule_id": bodies["ruleset_id"],
            "source_section": "卷一·论元气、贵命十吉体、重论先后天纳音相生之气、互体",
            "facts": deepcopy(bodies),
        }
    )
    trace.append(
        {
            "rule_id": month_evidence["ruleset_id"],
            "source_section": "卷二上、下卦解；卷一贵命十吉、得体及应其时合其用相关段落",
            "facts": deepcopy(month_evidence),
        }
    )
    trace.append(
        {
            "rule_id": seasonal["ruleset_id"],
            "source_section": "卷一五二至六二·至弱、太过、三等数与时损益及诸数式",
            "facts": deepcopy(seasonal),
        }
    )
    trace.append(
        {
            "rule_id": "stem_luoshu_branch_hetu",
            "source_section": "卷一·八字內天數地數例",
            "facts": {
                "pillars": [
                    {
                        "pillar": key,
                        "ganzhi": value,
                        "stem_number": GAN_NUM[value[0]],
                        "branch_numbers": ZHI_PAIR[value[1]][:],
                    }
                    for key, value in pillars.items()
                ],
                "tian": chart["tian"],
                "di": chart["di"],
                "tian_num": chart["tianNum"],
                "di_num": chart["diNum"],
                "reduction_policy": "subtract_base_once_then_discard_tens_v1",
            },
        }
    )
    trace.append(
        {
            "rule_id": "five_palace_three_yuan",
            "source_section": "卷一·五數寄宮例",
            "facts": {
                "cycle_year": chart["cycleYear"],
                "yuan_cycle": chart["yuanCycle"],
                "tian_gua": chart["tianGua"],
                "di_gua": chart["diGua"],
                "tian_top": chart["tianTop"],
            },
        }
    )
    trace.append(
        {
            "rule_id": "yuantang_and_houtian",
            "source_section": "卷一·元堂爻位式、換後天卦例",
            "facts": {
                "yang_ling": chart["yangLing"],
                "yang_ling_basis": chart["yangLingBasis"],
                "birth_instant_utc": solar["anchor_utc"],
                "xian": deepcopy(chart["xian"]),
                "hou": deepcopy(chart["hou"]),
            },
        }
    )
    trace.append(
        {
            "rule_id": "huagong",
            "source_section": "卷一·論化工",
            "facts": {
                "term": solar["term"],
                "quarter": solar["quarter"],
                "tuyong": solar["tuyong"],
                "tuyong_policy": solar["tuyong_policy"],
                "candidates": solar["hg"],
                "present": judge["huagong"]["present"],
            },
        }
    )
    trace.append(
        {
            "rule_id": "year_najia_at_actual_line_positions",
            "source_section": "八纯卦及屯、比、小畜、井、渙十三条卦解；正纳、借用与逐位源据分列，其他五十一卦未逐卦核",
            "facts": {
                "policy": judge["deSheng_policy"],
                "phases": deepcopy(judge["najia"]),
                "present": judge["deSheng"],
                "scope": "year_ganzhi_membership_only; not_complete_xie_buxie_assessment",
            },
        }
    )
    result["selected_texts"] = [
        {
            "phase": phase,
            "hexagram": chart[phase]["name"],
            "line": chart[phase]["yuan"],
            "corpus_key": f"{chart[phase]['name']}.yao.{chart[phase]['yuan']}",
            "text": deepcopy(
                yao_text(chart[phase]["name"], chart[phase]["yuan"]) or {}
            ),
        }
        for phase in ("xian", "hou")
    ]
    trace.append(
        {
            "rule_id": "heluo_selected_line_collation_v1",
            "source_section": "本次实际先后天元堂；卷二标题注文与另件卷三诗诀分别记录",
            "facts": {
                "commentary_corpus_id": commentary["corpus_id"],
                "commentary_sha256": commentary["sha256"],
                "commentary_content_sha256": commentary["content_sha256"],
                "header_content_sha256": result["yaoci_collation"]["content_sha256"],
                "poem_corpus_id": poems["corpus_id"],
                "poem_sha256": poems["sha256"],
                "poem_content_sha256": poems["content_sha256"],
                "automatic_branch_selection": False,
                "selections": [
                    {
                        "phase": s["phase"],
                        "corpus_key": s["corpus_key"],
                        "commentary_status": s["text"]["text_provenance"][
                            "commentary_status"
                        ],
                        "commentary_pdf_pages": s["text"]["text_provenance"].get(
                            "commentary_pdf_pages"
                        ),
                        "poem_status": s["text"]["text_provenance"]["poem_status"],
                        "poem_pdf_pages": s["text"]["text_provenance"].get(
                            "poem_pdf_pages"
                        ),
                        "poem_count": len(s["text"].get("poem_sections", [])),
                    }
                    for s in result["selected_texts"]
                ],
            },
        }
    )
    # 周易经文与河洛注文各自保留来源，不用另一部书静默覆盖本地条文。
    for selected in result["selected_texts"]:
        gua = chart[selected["phase"]]
        reference = classical_hexagram("".join(str(bit) for bit in gua["lines"]))
        verse = next(v for v in reference["yaoci"] if v["position"] == gua["yuan"])
        selected["zhouyi_reference"] = {
            "corpus_id": reference["corpus_id"],
            "edition_status": reference["edition_status"],
            "source_url": reference["source_url"],
            "source_revision": reference["source_revision"],
            "source_wikitext_sha256": reference["source_wikitext_sha256"],
            "verse": deepcopy(verse),
            "scope": "周易经文参照；不替代河洛注文版本校勘。",
        }
    result["unresolved_rules"] = [
        "减一次正数后去十取零已核读影印正文；更广的四柱组合仍须独立算例覆盖。",
        "土用采用四立前十八连续日；季月十八日的版本、起算和交界约定仍待影印校勘。",
        "年命纳甲已按实际六爻及乾坤借用计算，八个纯卦基础48项正纳及12项借用、另五个复卦30项正纳及6项借用经影印核对；13条卦解与其余51卦的纯卦推演分开。解卦两印本列举末两支顺序均不同于计算爻序，尚未核定列举按爻位含义。不等于完整得势或综合葉否。",
        "deTime仅为卦属月匹配，63项有底本明文；month_affinity区分月份条件及冲突；十三条月份及纳甲句分别列月号与同阶段年命纳甲事实，及字范围和解卦例外未决，单项true或false不决定整条match。默认优先卦条，缺号取卷首；可显式选卷首表，晋节睽震井五处异号及双方本月匹配均保留，跨来源共识另列，不能把所选方法称为统一原文。月界、边界月仍待核；無妄八月现有卷首明文，卦条本月及五世疑点保留。deTi现列年纳音与实际卦体五行关系，完整present为null；不以日干查卦代替纳音与卦体关系。第51页无元气前提和相生方向不得略去，也不能用第87页反向关系覆盖。",
        "二数正数比较与原典至弱太过、十一数式、六个时令窗口已分列；得中未量化，重叠不裁优先，未完成爻位势援辞理的综合强弱判断。",
        "judge.xie 仅为元气或化工命中布尔量，不能据此选定条文的葉者或不葉者分支。",
        "judge.qi_phases按先后天分列正反元气、化工的实际上下与互体位置；合并字段只表示两阶段并集。反化工春分至夏至同时保留离、巽，未据气虚制化等完成综合裁定；第83页乾化工命例与第34页定义冲突仍待核。",
        "heluo_timing已实现所核影印页的流年月卦和三十日定式；年界、寄刻、节月长度及闰日未桥接现代日期。",
        "三至尊段原文陽月／陰令，现按邻近纯卦段的至点半年解释；此为具名实现取法，完整术语校定及独立复核仍待完成。",
    ]
    result["interpretation_constraints"].append(
        "元堂条文同时含葉者、不葉者及歲運分支；目前保留全文，不自动选吉凶分支。"
    )
    result["interpretation_constraints"].append(
        "fanYuan和qi_phases.matches中的反元气仅为反候选卦体命中；yuanqi_opposition按同阶段上下体／两互体计算无正而有反前提。正反并存不能省略无正条件，只取上下体的结果仅作比较；节气浅深、气虚、尅制及反中有救未定，不据condition_match自动选择条文或裁断吉凶。"
    )
    result["interpretation_constraints"].append(
        "judge.line_conditions按先后天实际元堂计算二五位、五同一异众宗及主本阴元堂阳应爻有援式；source_youyuan保留同阶段实际应位、阴阳和原句匹配，反向相应不冒称该式命中，未中不推出无援或反面。yuanTang.youYing仅为先天通用阴阳相应。位序偏好不是综合评分。position_polarity_match仅为位序阴阳比较，不是原典阴月当位；source_dangwei.match=null，不能以至点半年补定义。"
    )
    result["interpretation_constraints"].append(
        "yuanTang.heLi只比较用爻阴阳与所用阴阳令是否同类，不表示完整合理或综合顺逆时。"
    )
    result["interpretation_constraints"].append(
        "corpus_sha256仅标识继承语料；yaoci_collation.sha256标识实际载入字节，content_sha256锁定该版标题正文、标签与来源元数据的规范JSON身份，不受排版空白影响。每条text_provenance分别说明爻辞、注文与诗歌状态；内容身份不证明原典读法或预测有效，局部目校不能当作全书完成。"
    )
    result["interpretation_constraints"].append(
        f"commentary_collation单独标识本版{commentary['collated_line_commentaries']}条注文单次目校层；sha256为载入字节，content_sha256锁定正文、条件标签和元数据，不能交换正文后沿用已目校身份。commentary_sections只按原文分段，applicability=null不表示不匹配。阳月、阴命、字兆等嵌套条件仍须保留。隨、蠱、臨三卦保留原印叶字，不机械改作葉；字典异体说明不选定命局叶否。诗歌未见于这些已核爻解段落，另件卷三取文查poem_collation；旧verdict标签不是底本对当前输入的条件分支裁定。"
    )
    result["interpretation_constraints"].append(
        f"poem_collation为另件154页卷三文件的单次目校层：{'、'.join(poems['covered_hexagrams'])}共{poems['collated_line_poem_groups']}个普通爻组、{poems['collated_individual_poems']}首，未核爻组{poems['pending_line_poem_groups']}个。组数分母384不能用首数作分子；全书首数未定。poem_sections按原印次保留全部诗，序号不决定适用或吉凶，不择有利诗；屯四原题无首数且仅一首，不补其二。shige仅含本爻已核诗；inherited_shige保留旧合并文，inherited_xiang_reference的象曰具体来源未由诗诀底本核定。屯初不當進步且盤桓的否定不可省，含此章、繇來、無處而即鹿等保留所选诗诀读法，不按熟语或别部经文改写。逐首reading_notes保留原字与所指未定；訟三原题一首而实列其二、其三，原题与三首并留，计数矛盾未决；訟初嘹喨、二王事、四名懼、五末稍却及六不須懽／困來按原PDF嵌入像素作同一读者复核，前次选字及修订理由留存；懽同歡，不須懽不能释为无需畏惧；该复核没有完成独立校勘，也不自动选定个人适用或现实结果；需五亨／享仍为暂读，白羊成一楚不指定星座或月日；诗中数字不自行生成具体年龄或日期。其他爻诗仍待核；卷二与卷三PDF身份不同，版片关系、独立复核未定。"
    )
    result["interpretation_constraints"].append(
        "commentary_cross_references保留师六三如與命相合者的引升三原句及单爻翻转核对；不交换上下体，目标地風升三不等于正式后天變換的風地觀上爻。applicability=null，不能改盘、代选葉否或以引文证明升卦全文已校。大有九三在岁运段在庶俗凶则语境只引睽卦名，目标爻与目标原文未印，不能由单爻变的三位反推原注引睽三或替代正式后天革上。蠱六四歲運段一變為鼎九四只作未定条件引卦，明印九四而未引鼎爻原文，不替代正式后天盘；蠱四叶者含不利措辞，蠱二女命句及蠱初數凶、蠱上數吉仍保留岁运父段。臨四歲運段但變歸妹的愆期引辞与臨五不叶者段變節的引卦名各留原条件父段；原文均未印目标爻位，单爻结构核对不补原印爻位、不自动裁定适用或替代正式后天盘；臨三女命句留不叶者段，臨五中字／行字只是原句字兆，不推定个人官职或日期。比六二不再混入比卦总论纳甲句；该全卦条件仍查month_affinity与najia。"
    )
    result["interpretation_constraints"].append(
        "谦初歲運逢之段的凶者引明夷、谦四同段引小過及往厲必戒勿用，均未印目标爻号；单爻翻转核对只确认卦形关联，不反推原文已指定目标爻，也不替代正式后天卦。谦的不葉者段仍有正面叙述，标签不等于负面结论；暂录字形与候选依各条读稿说明保留，不能把单次目读说成逐字已定或独立专家认证。"
    )
    result["interpretation_constraints"].append(
        "小畜九三未另印不葉者，condition_labels_not_separately_printed只说明标签未单列，不表示该条件false；葉者段有不利叙述，不可按标签自动分类吉凶。小畜初九數凶者引巽初仅为未定条件引用，正式后天虽同为巽卦但元堂在四爻，不能只比卦名或挪用爻辞。履上九變為引兌之小人未被当成已选变卦。"
    )
    result["interpretation_constraints"].append(
        "泰九二如不入局不得位引明夷二、否九四葉者段引觀四、否九五歲運段引晉五均保留source_section_id与source_condition_label；这些单爻变引用不交换上下体，适用仍为null，不替代正式后天卦，也不认证目标卦全文。否四原句觀光上國不改成周易另一读法。泰六四葉者亦含不利叙述；泰六五女命句仍在葉者段内；隨五不叶者亦有正面描述，隨二、三的女命句仍保留各自父段。否初纵爻辞美不足羡、否上未明写目标卦等限制不可略去。疑读见各条commentary_reading_notes，不补字求通顺。"
    )
    result["interpretation_constraints"].append(
        "chart.yuantang_derivation保留实际逐时爻位及至点半年来源；counterfactuals仅比较两种半年设置，实际选择以half_year.value为准。固定四柱子午月未给半年时，只允许两个半年结果相同的计算继续；heLi为null时不解释成异类，三至尊陽月／陰令沿用明确的至点半年取法。"
    )
    structure = judge["body_structure"]
    result["rulesets"].append(
        {
            "ruleset_id": structure["ruleset_id"],
            "version": structure["version"],
            "source_title": "河洛理數卷一·论互体四体八体渐卦例",
            "source_url": structure["source_url"] + "#page=77",
            "source_pdf_sha256": structure["source_pdf_sha256"],
            "source_status": structure["review_status"],
        }
    )
    result["rule_trace"].append(
        {
            "rule_id": structure["ruleset_id"],
            "source_section": "PDF77–78渐卦结构段；五命干支字表另列于75–76页",
            "facts": deepcopy(structure),
        }
    )
    result["interpretation_constraints"].extend(structure["constraints"])
    return result


def canping_evidence(calculation: dict) -> dict:
    from fatebridge.core.canping_timing import SOURCE_SHA256, SOURCE_URL

    method = calculation["method"]
    result = _base(
        "canping",
        "jinsuo_day_branch_v1" if method == "gu" else "canping_month_variant_v1",
    )
    collation = canping_collation_summary()
    result["canping_text_collation"] = collation
    result["corpus_sha256"] = collation["inherited_corpus_sha256"]
    result["rulesets"].append(
        {
            "ruleset_id": collation["corpus_id"],
            "version": collation["version"],
            "source_title": collation["source_title"],
            "source_url": collation["source_url"],
            "source_pdf_sha256": collation["source_pdf_sha256"],
            "source_status": collation["review_status"],
        }
    )
    result["interpretation_constraints"].append(
        "参评上层男命、中层女命、下层男女共用岁运，不能串栏；selectionShun/Ni逐项标出所用栏、编号、局部校勘与本地缺行。○为原页圈空，□为编辑目读未定，疑读不计已确定校勘，也不按熟悉典故补字；局部圈空不等于整格无文。原书允许顺有逆无或逆有顺无，同号仅同一行；本地缺行、继承圈缺和原页已核圈空不等于同一事实，更不推现实吉凶。附列2869编号与所核公式不合、栏目未明，保留未决且不作通用补文。"
    )
    result["interpretation_constraints"].append(
        "witnesses仅为所选同一五行、编号、栏目的另一印本对读，不替换textShun/Ni，不按吉凶择本。不同字符串不自动等于版本异文或转录错误；继承读法与某对读格相同，不证明整份继承语料出自该版。主本圈空或疑读不可用另一版补齐，两版皆疑读仍属未决；同一审阅者对读两本不算独立二次复核。"
    )
    result["interpretation_constraints"].append(
        "金部末十一行按所选底本原页的编号与正文归属取条，继承同号旧文另行保留；这是特定底本的号文对应差异，计算编号不重映射，不撤销仍有效的编号键。差异原因及继承语料来源未定，不能泛称所有版本错排。"
    )
    result["interpretation_constraints"].append(
        "number_attribution_status=provisional_inherited_key表示原页编号遮损、暂沿继承键定位，号文归属未核定；正文或圈空可辨不代表编号归属已核。该行所有已录栏均保留source_reading_uncertain，不计已确定数；number_reading_uncertainties与正文疑读分别读取，未出现□不代表该格已确定。"
    )
    result["interpretation_constraints"].append(
        "numbered_table_visual_review_complete只表示五部编号表全部经过一次目读；numbered_table_clear_readings_complete另指所有格读法及号文归属均已确认。目读覆盖完成不等于疑读消除、独立复核完成、原典全书符合或现实预测有效。"
    )
    result["interpretation_constraints"].append(
        "reading_revision保留同馆藏原图复读前的疑读与原因，rereading_witness及additional_rereading_witnesses分别记录水部与后续各批馆方原图区域及身份，不能覆盖先前见证或把重复区域算成独立复核。复读清楚的字采用本次textShun/Ni；仍有□的格继续未定，不用另一印本或典故补字。更清晰图像和同一审阅者复读均不增加独立复核数、编号格数、原典命例或历法参考时刻。"
    )
    result["interpretation_constraints"].append(
        "number_reading_evidence记录原图编号残字和遮损原因；body_reading_status只描述暂定继承键行的正文可读、全圈空、局部圈空或正文疑读，不确认其编号归属。整格cell_status仍为source_reading_uncertain，三栏均不计已确定数；不得凭正文或圈空清楚、邻行顺序、公式或另一印本补定号码。"
    )
    result["rule_trace"] = [
        {
            "rule_id": "jinsuo_benming",
            "source_section": "卷六·逐句釋明金鎖銀匙歌訣",
            "facts": {
                "method": method,
                "day_palace_branch": calculation["dayPalaceBranch"],
                "birth_day_branch": calculation["fourPillars"]["dayBranch"],
                "hour_branch": calculation["fourPillars"]["hourBranch"],
                "nayin_element": calculation["element"],
                "kind": calculation["kindMain"],
                "numbers": {
                    k: v for k, v in calculation["benming"].items() if k != "verses"
                },
            },
        }
    ]
    result["selected_texts"] = [
        {
            "phase": "benming",
            "element": calculation["element"],
            "kind": calculation["kindMain"],
            "verses": deepcopy(calculation["benming"]["verses"]),
        }
    ]
    result["rule_trace"].append(
        {
            "rule_id": "canping_text_selection_v1",
            "source_section": "卷六·三层栏目例、顺冲有无说明及所用编号",
            "facts": {
                "collation_id": collation["corpus_id"],
                "collation_sha256": collation["sha256"],
                "comparison_witness_id": collation["comparison_witness"]["corpus_id"],
                "comparison_witness_sha256": collation["comparison_witness"]["sha256"],
                "inherited_corpus_sha256": collation["inherited_corpus_sha256"],
                "kind": calculation["kindMain"],
                "selectionShun": deepcopy(
                    calculation["benming"]["verses"]["selectionShun"]
                ),
                "selectionNi": deepcopy(
                    calculation["benming"]["verses"]["selectionNi"]
                ),
                "pair_resolution": deepcopy(
                    calculation["benming"]["verses"]["pair_resolution"]
                ),
            },
        }
    )
    timing = calculation.get("timing")
    selected = timing.get("selected") if timing else None
    query_pair = (
        {
            "at": selected["at"],
            "annual_taisui_branch": selected["ganzhi"][1],
            "active_dayun_branch": selected["dayunBranch"],
        }
        if selected and selected.get("status") == "active"
        else None
    )
    result["rulesets"].append(
        {
            "ruleset_id": "canping_luck_substitution_v1",
            "version": "1.0.0",
            "source_title": "河洛理數 史應選校訂 卷六逐句釋明起大運／推流年",
            "source_url": SOURCE_URL,
            "source_pdf_sha256": SOURCE_SHA256,
            "source_status": "two_bounded_excerpts_single_visual_reading; independent_second_review_pending",
        }
    )
    result["rule_trace"].append(
        {
            "rule_id": "canping_luck_substitution_v1",
            "source_section": "所选NAJDA本PDF64；诗诀另见PDF50",
            "facts": {
                "source_pdf_page": 64,
                "source_pdf_sha256": SOURCE_SHA256,
                "bounded_excerpts": {
                    "dayun": "只將人八字時支棄去不用以大運地支逐運對日地支算",
                    "liunian": "不用日時地支打算只將流年太歲地支與大運地支",
                },
                "implemented_annual_arguments": [
                    "annual_taisui_branch",
                    "active_dayun_branch",
                ],
                "selected_dayun_day_argument": calculation["dayPalaceBranch"],
                "dayun_day_argument_policy": (
                    "birth_day_branch" if method == "gu" else "explicit_month_variant"
                ),
                "nayin_basis": "birth_year_nayin_unchanged",
                "query_pair": query_pair,
                "whole_book_alignment_established": False,
                "independent_second_review_completed": False,
                "schedule_or_utc_mapping_certified_by_excerpts": False,
            },
        }
    )
    if timing and timing["profile_id"] != "legacy_minggong_v1":
        result["rulesets"].append(
            {
                "ruleset_id": timing["solar_year_context"]["policy_id"],
                "version": "1.0.0",
                "source_title": "Modern bounded Canping Lichun projection context",
                "source_url": None,
                "source_status": "actual_selected_solar_model_and_clock; not_classical_authorship_or_prediction_certification",
            }
        )
        result["rule_trace"].append(
            {
                "rule_id": "canping_actual_lichun_dependencies",
                "source_section": "Modern calendar bridge; complete original horizon",
                "facts": deepcopy(timing["solar_year_context"]),
            }
        )
        result["rulesets"].append(
            {
                "ruleset_id": timing["ruleset_id"],
                "version": timing["ruleset_version"],
                "source_title": timing["source_title"],
                "source_url": timing["source_url"],
                "source_pdf_sha256": timing["source_pdf_sha256"],
                "source_status": timing["source_status"],
                "authorship_status": "volume_seven_is_explicitly_an_appendix; not_attributed_to_Chen_Tuan",
            }
        )
        result["rule_trace"].append(
            {
                "rule_id": "canping_named_luck_schedule",
                "source_section": "卷六起大运例、起流年例；卷七附起大运诀",
                "facts": {
                    "profile": timing["profile_id"],
                    "start_at": timing["start_at"],
                    "calendar_policy": timing["calendar_policy"],
                    "calendar_offset": timing["calendar_offset"],
                    "start_details": timing["start_details"],
                    "periods": deepcopy(calculation["dayun"]),
                    "selected": deepcopy(timing["selected"]),
                },
            }
        )
        if timing["selected"] and timing["selected"]["status"] == "active":
            selected = timing["selected"]
            result["selected_texts"].append(
                {
                    "phase": "liunian_segment",
                    "at": selected["at"],
                    "ganzhi": selected["ganzhi"],
                    "dayun_pillar": selected["dayun_pillar"],
                    "kind": "luck",
                    "verses": deepcopy(selected["verses"]),
                }
            )
    result["unresolved_rules"] = [
        "卷六未唯一指定配运系统；默认明确选用卷七附子平月柱法，不与河洛阳九阴六大限混同。",
        "卷七三日折岁借除规则未细定日内分数；默认民用日期差整日借除、连续折算另具规则名，现代日期相加及DST是工程约定。",
        "条文表含缺字且尚未全量影印校勘，不能将空缺解释为现实灾祸。",
        "附列2869按当前目读编号不能由所核五行起数公式生成，栏目与适用范围未明；保留原文疑点，停用跨栏通用补文，待原页独立复核。",
        "文明书局本仅对读36格，其中两格仍有疑读；其余栏目、字形差异归因及继承语料版本来源尚未全量校定，不据此增加主本已确定格数或称独立复核完成。",
    ]
    if not timing or timing["profile_id"] == "legacy_minggong_v1":
        result["unresolved_rules"][:2] = [
            "legacy命宫顺行、固定一岁起运仅为继承实现，未获本次原典证明。",
            "legacy流年仅为与出生年柱对应的立春年标签，无已核定日期区间；不支持时刻查询。",
        ]
    if method == "ming":
        result["unresolved_rules"].append(
            "ming 以月支反向替日支，与卷六不用月令的起数段落不符；仅保留显式变法。"
        )
    return result
