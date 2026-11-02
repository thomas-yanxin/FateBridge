"""Named source scopes; excerpt conformance never certifies efficacy."""

from typing import Any, Dict

from fatebridge.core.metaphysics.ren_sources import (
    JINKOU_SOURCE,
    LIUREN_SOURCE,
    TANYUAN_SCAN_SHA256,
    TANYUAN_SOURCE,
    ZHINAN_SOURCE,
)


def ruleset_metadata(
    technique: str, *, guiren_profile: str = "liuren_common_v1"
) -> Dict[str, Any]:
    jinkou = technique == "jinkou"
    result: Dict[str, Any] = {
        "id": "jinkou_guben_excerpt_v1" if jinkou else "liuren_jiuzong_v1",
        "version": "1.16.0",
        "source_title": (
            "六壬神课金口诀古本·卷之上" if jinkou else "六壬大全·卷一 / 六壬指南·卷一"
        ),
        "source_urls": [JINKOU_SOURCE] if jinkou else [LIUREN_SOURCE, ZHINAN_SOURCE],
        "source_kind": "online_transcription_not_collated_edition",
        "classical_conformance": "partial_excerpt",
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
        "conventions": {
            "month_general": "中气换将；用实际民用时刻判断交气，不用太阳钟偏移后的时刻",
            "diurnal": "默认卯至申为昼，酉至寅为夜；未按地点计算星出星没",
            "day_boundary": "日时柱采用所选时钟23时子初换日；standard 指JDN+49日序，不表示民用零点换日",
        },
        "unresolved": [
            "未完成指定刻本影印校勘和全书独立课例验收",
            "默认昼夜时支约定不等于原文星没为旦、星出为暮",
            "局部规则通过不证明自由文本解释或现实预测有效",
        ],
    }
    if jinkou:
        result["conventions"][
            "pattern_conditions"
        ] = "所选58条课钤以同课四位和已算日旬事实列逐项条件；每组条件须全部成立，任一组满足即成立，结论由该证据求值；未命中仍列全部前提，必要输入缺项另标未知，6条原文疑义不编表达式；不据此改判原书4项不符或认证全书"
        result["conventions"][
            "natal_course"
        ] = "次客法本命另课以已确认本命支为派生地分，保留本次日时月将及昼夜选择，与原地分和行年另课分列；未知不补造，不自动换将换日，不认证综合取用或现实应验"
        from fatebridge.core.metaphysics.jinkou_pattern_tables import JINKOU_SCAN_URL

        from .jinkou_relations import SOURCE_URL as JINKOU_RELATIONS_SOURCE

        result["conventions"][
            "month_building"
        ] = "京本神将建旺按贵神固有支、将神本支分别与月建同支核对；将神进退仍单列，贵神进退未外推，不等同四季或日下完整旺衰与综合取用"
        result["source_title"] += " / 校正京本六十四课钤、四绝、岁日关系及三合条件"
        result["source_title"] += "、四位生克与五比"
        result["source_title"] += "、神将遁干"
        result["source_title"] += "、京本所选七项历法神煞与六甲旬行年另课"
        result["conventions"][
            "branch_stars"
        ] = "按京本所选天赦、天喜、天马、驿马、丧门、吊客、丧车条文列历法目标；驿马用月建支，月序采用当前节月名义序，支类只比三位本支，不据名称断现实结果"
        result["conventions"][
            "dun_stem_relations"
        ] = "干元类只按占日日干所起神将遁干比较，不以贵神固有干或支位五行替代；天干合、地支合及遁干支自身同旬分列，合化与五种位置合未作完整裁定"
        result["conventions"][
            "position_interactions"
        ] = "按京本五比同类、四位相生、四位相克及四爻生克颂识别十四条结构；完整六对保留方向，连续相生或合局不取消隔位相克，不代替完整旺衰与综合取用"
        result["source_urls"].append(JINKOU_SCAN_URL)
        result["conventions"][
            "year_fate"
        ] = "京本按明确出生年干支所属六甲旬取男女起点，男顺女逆；只用指定一岁起算岁序，另课采用行年支作地分的所选释读，不表示已观测来人方位；不借用大六壬通用行年起点。"
        result["source_urls"].append(JINKOU_RELATIONS_SOURCE)
        result["source_urls"].append(
            "https://archive.wul.waseda.ac.jp/kosho/ro14/ro14_02466/ro14_02466_0006/ro14_02466_0006.html"
        )
        result["conventions"][
            "unresolved_definition_evidence"
        ] = "六条疑义增列CNTS与早稻田抄本所选书影异文；隔生配对、昼夜候选、地支环距离与起丁路径分列条件事实，均不据此裁定课式；未鉴定版本先后或独立传承"
        result["source_kind"] = "online_transcription_and_selected_scan_collation"
        result["conventions"][
            "natal_absolute"
        ] = "将命大绝取显式本命支，或明确birth_year_ganzhi的年支，与本次将神支核对京本四组配对；两者均缺仍未知，不以分析年日时、地分或行年替代本命"
        result["unresolved"].extend(
            [
                "转录本夜占贵神及辛酉课纯阳描述存在内部冲突，尚未校勘",
                "四季土旺采用辰戌丑未整月口径，未比较季末十八日口径",
                "位内旺神仅实现十二例共有的唯一不受克规则；已列日支生将和月建进退，日下完整五态及综合取用未定",
                "课内旺衰十二例采用网上转录；京本PDF130天乙例图式末位木与转录水不同，且书影仍判土旺，尚未裁定",
                "六十四课钤列全64条，58条结构已评估；6条疑义未判，4条书影四位与定义不符；天门入地户按将神天魁戌，不能认证64课全部符合",
                "四绝按京本书影配对；命支未输入不算大绝；四败仅列五行临地分，不能代替完整日下旺衰及综合断法",
                "三合支齐、虚一支及空破条件分别列事实；所忌支的适用条件、妒合、完整合化及实际应期未裁定",
                "神将遁干已列干元类生克及配对事实；分局合局、五种位置合与完整合化的统一判断仍未裁定",
            ]
        )
        result["unresolved"].append(
            "京本行年换岁边界及己亥行年见甲人元所指课干未裁定，未认证综合喜用"
        )
    else:
        result["version"] = "1.16.0"
        from .ren_gods import TANYUAN_TRANSCRIPTION

        result["conventions"][
            "selection_evidence"
        ] = "九宗门选课、细名及推导轨迹绑定同次返回的日干支和天地盘；涉害列正五行与十干寄宫的逐站计数，不用地支藏干；终本家寄干异法与原书统计矛盾保留，内部一致不等于原典或预测满分"
        result["conventions"]["guiren_profile"] = guiren_profile
        result["conventions"][
            "subtype_names"
        ] = "按探原九宗门总说，从实际四课贼克、比用、伏吟刑冲及返吟有无贼克推导；逐课表注另行核对"
        result["source_urls"].extend([TANYUAN_TRANSCRIPTION, TANYUAN_SOURCE])
        result["source_title"] = "六壬大全/指南九宗门 / 大六壬探原·细课名"
        result["conventions"][
            "life_stages"
        ] = "十二运单独采用探原十干阳顺阴逆及戊己随丙丁；与五行长生口径有别，不随贵人表切换"
        result["unresolved"].append(
            "个别探原表内细课名与正文定义或更细分类不一；原转录错误与书影订正分别保留，未作全名认证"
        )
        result["unresolved"].append(
            "探原影印本表前卯午子与表内卯子午存在内部冲突；贵人配置不等于采用全书所有取传异法"
        )
        if guiren_profile == "tanyuan_xieji_v1":
            result["source_title"] = (
                "六壬大全/指南九宗门 / 大六壬探原·细课名与日夜贵人歌"
            )
            result["conventions"][
                "guiren_scope"
            ] = "仅采用探原日贵人歌、夜贵人歌及贵人旋转；非整书配置"
        else:
            result["conventions"][
                "guiren_scope"
            ] = "既有甲戊庚牛羊等表；与探原遵协纪辨方的十干表分开"
        result["source_title"] += "与德禄马定位"
        result["source_title"] += "、三传神将生克与局体"
        result["source_title"] += "、空亡分层条件"
        result["source_title"] += "、支位合冲刑破害并存条件"
        result["source_title"] += "、三传连茹间断条件"
        result["source_title"] += "、季节五态与本空条件"
        result["source_title"] += "、类神阴神"
        result["source_title"] += "、三种传序课体"
        from fatebridge.core.metaphysics.liureng_course_conditions_convention import (
            CONVENTION,
        )
        from fatebridge.core.metaphysics.liureng_day_placements_convention import (
            CONVENTION as DAY_PLACEMENT_CONVENTION,
        )

        result["source_title"] += "、课体纲要条件"
        result["source_title"] += "、课体可实现条件校核"
        result["conventions"]["course_layout_compatibility"] = (
            "按声明的十干十二运及两贵人表穷举昼夜、顺逆的八种配将必要配置；"
            "区分本课字面命中与配将可实现，不保证九宗取传或现实结果，崇位原意未裁"
        )
        result["conventions"]["course_conditions"] = CONVENTION
        result["source_title"] += "、干支加临课体"
        result["conventions"]["day_placement_patterns"] = DAY_PLACEMENT_CONVENTION
        from fatebridge.core.metaphysics.liureng_cross_harmony_convention import (
            CONVENTION as CROSS_HARMONY_CONVENTION,
        )

        result["source_title"] += "、交车六合条件"
        result["conventions"]["cross_harmony"] = CROSS_HARMONY_CONVENTION
        result["conventions"]["ordered_transmission_patterns"] = (
            "按探原课体纲要原页只识别斫轮卯戌巳、铸印巳戌卯、轩盖午卯子三条有序传序；"
            "不把同支集合、倒序或其他课体混同，不改变九宗门取传或据名称断现实结果"
        )
        result["conventions"]["god_yin"] = (
            "探原论阴神：十一天将取所乘支的上神，天乙贵人按所选昼夜表互取；"
            "课传及已知年命上神定位，缺年命保留未知，五态本空条件不认证类神综合可用性"
        )
        result["conventions"][
            "seasonal_evidence"
        ] = "探原五季25项五态表；月建支按季月整月配置，支神、天将、地盘各取自身五行，另列支神本空真半条件；季末十八日异法、扶助冲剋后的真半及综合有效空亡未裁，不折算成功率"
        result["conventions"][
            "transmission_progression"
        ] = "探原集说篇PDF110–111的连茹与间断支序，另列支神本空假设下的初空、末空及见空条件释读；综合有效空亡与实际进退未裁，不改取传或混用坐空、天将天空"
        result["conventions"][
            "branch_relations"
        ] = "依探原印刷配对并列六合、六冲、六害、六破和双向刑，保留寅亥破合、巳申刑合；首课用寄宫支比较空间关系，不替代日干五行或九宗门，不以合独断成局"
        result["conventions"][
            "emptiness_evidence"
        ] = "探原论空亡的天盘本空、地盘落底空、日干寄宫地盘例外及太岁月建月将角色分别列条件；不取消原旬空两支或三传本空、坐空，不裁综合有效空亡，年命、真空半空与填实冲实仍未定"
        result["conventions"][
            "transmission_relations"
        ] = "探原论三传的内外战、初末生墓、递克、朝日朝枝与旬空结构单列；天将固有五行、支神本五行及三合名义局体分层，未作完整合化、救制或吉凶应期裁断"
        result["conventions"][
            "auxiliary_stars"
        ] = "所选天德、月德、日德、日支德、日禄、驿马、天马依探原明文定位；月序按节换月月建寅至丑，非农历月或月将；仅列入课入传等事实，不作完整神煞及整书认证"
    return result


def xun_dun_stems(day_ganzhi: str) -> Dict[str, str]:
    """The ten actual xun stems; the two empty branches have no stem."""
    from .common import SEXAGENARY_CYCLE, SEXAGENARY_INDEX

    head = SEXAGENARY_INDEX[day_ganzhi] // 10 * 10
    return {pair[1]: pair[0] for pair in SEXAGENARY_CYCLE[head : head + 10]}


def liuren_annotation_note(day_ganzhi: str, gan_upper: str) -> Dict[str, Any] | None:
    """Critical apparatus only; never an input to selection or label derivation.

    Locators refer to the identified scan file, PDF pages counted from 1.
    These notes expose remaining mismatches instead of hard-coding answers
    to make the calculator match the reference table.
    """
    notes = {
        ("丁卯", "申"): (
            "涉害",
            48,
            "broader_tabular_annotation",
            "总说有涉害细分察微；表内只注较宽的涉害，保留两层，不称逐字相同。",
        ),
        ("戊辰", "未"): (
            "重审",
            49,
            "broader_or_variant_tabular_annotation",
            "总说明细分为始入；贼克正文也用重审泛称下贼上，表注可能采用较宽名称，仍不称逐字相同。",
        ),
        ("戊申", "卯"): (
            "元首",
            59,
            "definition_annotation_disagreement",
            "本课有下贼上，总说要求贼先于克；表注元首与该定义不一，尚待校勘裁定。",
        ),
    }
    record = notes.get((day_ganzhi, gan_upper))
    if record is None:
        return None
    annotation, page, kind, explanation = record
    return {
        "annotation": annotation,
        "original_pdf_page": page,
        "source_url": TANYUAN_SOURCE,
        "source_sha256": TANYUAN_SCAN_SHA256,
        "kind": kind,
        "explanation": explanation,
        "scope": "只限制细课名的原典注释认证；不据此改写已算出的四课或三传",
    }
