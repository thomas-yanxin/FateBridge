"""Pure structural Ziwei classical pattern (格局) detectors without None stubs."""

from __future__ import annotations

from typing import Any

from fatebridge.utils.data import EARTHLY_BRANCHES, ZIWEI_BRANCH_SEQUENCE

ZIWEI_MAJOR_STARS = frozenset(
    {
        "紫微",
        "天机",
        "太阳",
        "武曲",
        "天同",
        "廉贞",
        "天府",
        "太阴",
        "贪狼",
        "巨门",
        "天相",
        "天梁",
        "七杀",
        "破军",
    }
)
SHA_STARS = frozenset({"擎羊", "陀罗", "火星", "铃星", "地空", "地劫"})
JI_STARS = frozenset({"左辅", "右弼", "文昌", "文曲", "天魁", "天钺"})

PATTERN_CATALOGUE: tuple[dict[str, str], ...] = (
    {
        "id": "zi_fu_tong_gong",
        "name": "紫府同宫格",
        "category": "富贵格",
        "rule": "紫微天府同坐寅或申命宫",
    },
    {
        "id": "zi_fu_chao_yuan",
        "name": "紫府朝垣格",
        "category": "富贵格",
        "rule": "命宫三方四正会紫微天府（不同宫）",
    },
    {
        "id": "jun_chen_qing_hui",
        "name": "君臣庆会格",
        "category": "富贵格",
        "rule": "紫微守命，左辅右弼同宫或三方会吉",
    },
    {
        "id": "ji_yue_tong_liang",
        "name": "机月同梁格",
        "category": "富贵格",
        "rule": "命宫三方四正会齐天机太阴天同天梁",
    },
    {
        "id": "sha_po_lang",
        "name": "杀破狼格",
        "category": "特殊格",
        "rule": "命宫三方四正为七杀破军贪狼",
    },
    {
        "id": "ju_ri_tong_gong",
        "name": "巨日同宫格",
        "category": "富贵格",
        "rule": "太阳巨门同宫守命（寅或申）",
    },
    {
        "id": "ri_chu_fu_sang",
        "name": "日照雷门格",
        "category": "富贵格",
        "rule": "太阳居卯宫守命或官禄",
    },
    {
        "id": "ri_yue_zhao_bi",
        "name": "日月照壁格",
        "category": "富贵格",
        "rule": "太阳太阴同坐田宅宫",
    },
    {
        "id": "ri_yue_bing_ming",
        "name": "日月并明格",
        "category": "富贵格",
        "rule": "太阳居巳午、太阴居酉亥并照命宫三方四正",
    },
    {
        "id": "ming_zhu_chu_hai",
        "name": "明珠出海格",
        "category": "富贵格",
        "rule": "未宫无正曜守命，卯日亥月三方会照",
    },
    {
        "id": "yue_luo_hai_gong",
        "name": "月朗天门格",
        "category": "富贵格",
        "rule": "太阴在亥宫守命",
    },
    {
        "id": "yue_sheng_cang_hai",
        "name": "月生沧海格",
        "category": "富贵格",
        "rule": "天同太阴同坐子宫守命",
    },
    {
        "id": "yang_liang_chang_lu",
        "name": "阳梁昌禄格",
        "category": "富贵格",
        "rule": "命宫三方四正会齐太阳天梁文昌与禄存/化禄",
    },
    {
        "id": "tan_wu_tong_xing",
        "name": "贪武同行格",
        "category": "富贵格",
        "rule": "贪狼武曲同宫守命（丑或未）",
    },
    {
        "id": "lian_zhen_wen_wu",
        "name": "廉贞文武格",
        "category": "富贵格",
        "rule": "廉贞坐命，三方四正会武曲及昌曲",
    },
    {
        "id": "wu_qu_shou_yuan",
        "name": "武曲守垣格",
        "category": "富贵格",
        "rule": "武曲守命且非卯宫",
    },
    {
        "id": "fu_xiang_chao_yuan",
        "name": "府相朝垣格",
        "category": "富贵格",
        "rule": "命宫三方四正会见天府与天相",
    },
    {
        "id": "shuang_lu_jiao_liu",
        "name": "双禄交流格",
        "category": "富贵格",
        "rule": "禄存与化禄同入命宫三方四正",
    },
    {
        "id": "lu_ma_jiao_chi",
        "name": "禄马交驰格",
        "category": "富贵格",
        "rule": "禄存或化禄与天马在命宫三方四正会合",
    },
    {
        "id": "san_qi_jia_hui",
        "name": "三奇加会格",
        "category": "富贵格",
        "rule": "化禄化权化科会齐命宫三方四正",
    },
    {
        "id": "ke_quan_lu_jia",
        "name": "科权禄夹格",
        "category": "富贵格",
        "rule": "命宫左右邻宫分见化禄化权化科中两星",
    },
    {
        "id": "quan_lu_sheng_feng",
        "name": "权禄生逢格",
        "category": "富贵格",
        "rule": "化禄与化权同坐命宫（庙旺为全）",
    },
    {
        "id": "ri_yue_jia_ming",
        "name": "日月夹命格",
        "category": "富贵格",
        "rule": "太阳与太阴分居命宫左右邻宫",
    },
    {
        "id": "zuo_you_jia_ming",
        "name": "左右夹命格",
        "category": "富贵格",
        "rule": "左辅与右弼分居命宫左右邻宫",
    },
    {
        "id": "chang_qu_jia_ming",
        "name": "昌曲夹命格",
        "category": "富贵格",
        "rule": "文昌与文曲分居命宫左右邻宫",
    },
    {
        "id": "kui_yue_jia_ming",
        "name": "魁钺夹命格",
        "category": "富贵格",
        "rule": "天魁与天钺分居命宫左右邻宫",
    },
    {
        "id": "zuo_gui_xiang_gui",
        "name": "坐贵向贵格",
        "category": "富贵格",
        "rule": "天魁天钺分坐命宫与迁移宫对拱",
    },
    {
        "id": "huo_tan_ge",
        "name": "火贪格",
        "category": "特殊格",
        "rule": "火星与贪狼同坐命/身/财/官",
    },
    {
        "id": "ling_tan_ge",
        "name": "铃贪格",
        "category": "特殊格",
        "rule": "铃星与贪狼同坐命/身/财/官",
    },
    {
        "id": "ling_chang_tuo_wu",
        "name": "铃昌陀武格",
        "category": "凶忌格",
        "rule": "命宫三方四正会铃星文昌陀罗武曲",
    },
    {
        "id": "ming_wu_zheng_yao",
        "name": "命无正曜格",
        "category": "结构特征",
        "rule": "命宫无十四主星，须参迁移宫借星",
    },
    {
        "id": "ma_tou_dai_jian",
        "name": "马头带剑格",
        "category": "特殊格",
        "rule": "擎羊坐午宫守命",
    },
    {
        "id": "shi_zhong_yin_yu",
        "name": "石中隐玉格",
        "category": "富贵格",
        "rule": "巨门在子或午宫守命",
    },
    {
        "id": "shui_cheng_gui_e",
        "name": "水澄桂萼格",
        "category": "富贵格",
        "rule": "太阳居午且太阴居子（或太阴守子会禄科权）",
    },
    {
        "id": "xiong_su_chao_yuan",
        "name": "雄宿朝元格",
        "category": "富贵格",
        "rule": "廉贞在寅或申宫守命",
    },
    {
        "id": "qi_sha_chao_dou",
        "name": "七杀朝斗格",
        "category": "富贵格",
        "rule": "七杀在寅申子午宫守命",
    },
)


def named_pattern_catalogue() -> dict[str, Any]:
    return {
        "id": "ziwei_classical_patterns_v2",
        "version": "2.0.0",
        "count": len(PATTERN_CATALOGUE),
        "rules": [dict(r) for r in PATTERN_CATALOGUE],
    }


def evaluate_named_patterns(
    palaces: list[dict[str, Any]],
    *,
    ming_branch: str,
    shen_branch: str,
) -> dict[str, Any]:
    """Evaluate 36 classical Ziwei patterns with pure boolean structural predicates."""
    by_branch = {p["ganzhi"][1]: p for p in palaces}
    by_name = {p["name"]: p for p in palaces}
    ming_idx = ZIWEI_BRANCH_SEQUENCE.index(ming_branch)
    sanfang_branches = [
        ZIWEI_BRANCH_SEQUENCE[(ming_idx + off) % 12] for off in (0, 4, 8, 6)
    ]
    opp_branch = ZIWEI_BRANCH_SEQUENCE[(ming_idx + 6) % 12]
    earth_idx = EARTHLY_BRANCHES.index(ming_branch)
    adj_branches = {
        EARTHLY_BRANCHES[(earth_idx - 1) % 12],
        EARTHLY_BRANCHES[(earth_idx + 1) % 12],
    }

    star_map: dict[str, dict[str, Any]] = {}
    palace_stars: dict[str, set[str]] = {}
    palace_mutagens: dict[str, set[str]] = {}
    for p in palaces:
        b = p["ganzhi"][1]
        names = set()
        muts = set()
        for s in p["stars_detail"]:
            names.add(s["name"])
            if s["mutagen"]:
                muts.add(s["mutagen"])
            star_map[s["name"]] = {
                "branch": b,
                "palace": p["name"],
                "brightness": s["brightness"],
                "mutagen": s["mutagen"],
            }
        palace_stars[b] = names
        palace_mutagens[b] = muts

    ming_stars = palace_stars[ming_branch]
    opp_stars = palace_stars[opp_branch]
    sanfang_stars = set().union(*(palace_stars[b] for b in sanfang_branches))
    sanfang_mutagens = set().union(*(palace_mutagens[b] for b in sanfang_branches))
    adj_stars_list = [palace_stars[b] for b in adj_branches]
    adj_mutagens_list = [palace_mutagens[b] for b in adj_branches]

    def _flanks(a: str, b: str) -> bool:
        return (a in adj_stars_list[0] and b in adj_stars_list[1]) or (
            b in adj_stars_list[0] and a in adj_stars_list[1]
        )

    def _in_branch(star: str, *branches: str) -> bool:
        return star in star_map and star_map[star]["branch"] in branches

    def _same_palace(*stars: str) -> set[str]:
        return {b for b, s in palace_stars.items() if all(name in s for name in stars)}

    ming_majors = sorted(ming_stars & ZIWEI_MAJOR_STARS)
    opp_majors = sorted(opp_stars & ZIWEI_MAJOR_STARS)
    key_branches = {
        ming_branch,
        shen_branch,
        by_name["财帛宫"]["ganzhi"][1],
        by_name["官禄宫"]["ganzhi"][1],
    }

    quan_lu_stars = [
        info for info in star_map.values() if info["mutagen"] in {"化禄", "化权"}
    ]
    quan_lu_in_ming = len(quan_lu_stars) == 2 and all(
        info["branch"] == ming_branch for info in quan_lu_stars
    )
    quan_lu_miao_wang = quan_lu_in_ming and all(
        info["brightness"] in {"庙", "旺"} for info in quan_lu_stars
    )

    ke_quan_lu_flanks = (
        sum(1 for muts in adj_mutagens_list if muts & {"化禄", "化权", "化科"}) == 2
        and len(set().union(*adj_mutagens_list) & {"化禄", "化权", "化科"}) >= 2
    )

    checks: dict[str, tuple[bool, dict[str, bool]]] = {
        "zi_fu_tong_gong": (
            ming_branch in {"寅", "申"} and {"紫微", "天府"} <= ming_stars,
            {
                "ming_in_yin_shen": ming_branch in {"寅", "申"},
                "zi_fu_in_ming": {"紫微", "天府"} <= ming_stars,
            },
        ),
        "zi_fu_chao_yuan": (
            {"紫微", "天府"} <= sanfang_stars and not ({"紫微", "天府"} <= ming_stars),
            {
                "zi_fu_in_sanfang": {"紫微", "天府"} <= sanfang_stars,
                "not_same_palace": not ({"紫微", "天府"} <= ming_stars),
            },
        ),
        "jun_chen_qing_hui": (
            "紫微" in ming_stars
            and ({"左辅", "右弼"} <= ming_stars or _flanks("左辅", "右弼")),
            {
                "ziwei_in_ming": "紫微" in ming_stars,
                "zuo_you_assist": {"左辅", "右弼"} <= ming_stars
                or _flanks("左辅", "右弼"),
                "no_sha_in_ming": not bool(ming_stars & SHA_STARS),
            },
        ),
        "ji_yue_tong_liang": (
            {"天机", "太阴", "天同", "天梁"} <= sanfang_stars,
            {"all_four_in_sanfang": {"天机", "太阴", "天同", "天梁"} <= sanfang_stars},
        ),
        "sha_po_lang": (
            {"七杀", "破军", "贪狼"} <= sanfang_stars,
            {"all_three_in_sanfang": {"七杀", "破军", "贪狼"} <= sanfang_stars},
        ),
        "ju_ri_tong_gong": (
            ming_branch in {"寅", "申"} and {"太阳", "巨门"} <= ming_stars,
            {
                "ming_in_yin_shen": ming_branch in {"寅", "申"},
                "ju_ri_in_ming": {"太阳", "巨门"} <= ming_stars,
            },
        ),
        "ri_chu_fu_sang": (
            _in_branch("太阳", "卯")
            and star_map["太阳"]["palace"] in {"命宫", "官禄宫"},
            {
                "sun_in_mao": _in_branch("太阳", "卯"),
                "in_ming_or_career": star_map["太阳"]["palace"] in {"命宫", "官禄宫"},
            },
        ),
        "ri_yue_zhao_bi": (
            star_map["太阳"]["palace"] == "田宅宫"
            and star_map["太阴"]["palace"] == "田宅宫",
            {
                "sun_moon_in_property": star_map["太阳"]["palace"]
                == star_map["太阴"]["palace"]
                == "田宅宫",
                "in_tomb_branch": star_map["太阳"]["branch"]
                in {"辰", "戌", "丑", "未"},
            },
        ),
        "ri_yue_bing_ming": (
            _in_branch("太阳", "巳", "午")
            and _in_branch("太阴", "酉", "亥")
            and {"太阳", "太阴"} <= sanfang_stars,
            {
                "sun_bright": _in_branch("太阳", "巳", "午"),
                "moon_bright": _in_branch("太阴", "酉", "亥"),
                "both_in_sanfang": {"太阳", "太阴"} <= sanfang_stars,
            },
        ),
        "ming_zhu_chu_hai": (
            ming_branch == "未"
            and not ming_majors
            and _in_branch("太阳", "卯")
            and _in_branch("太阴", "亥"),
            {
                "ming_in_wei": ming_branch == "未",
                "empty_ming": not ming_majors,
                "sun_mao": _in_branch("太阳", "卯"),
                "moon_hai": _in_branch("太阴", "亥"),
            },
        ),
        "yue_luo_hai_gong": (
            ming_branch == "亥" and "太阴" in ming_stars,
            {"moon_in_hai_ming": ming_branch == "亥" and "太阴" in ming_stars},
        ),
        "yue_sheng_cang_hai": (
            ming_branch == "子" and {"天同", "太阴"} <= ming_stars,
            {
                "ming_in_zi": ming_branch == "子",
                "tong_yin_in_ming": {"天同", "太阴"} <= ming_stars,
            },
        ),
        "yang_liang_chang_lu": (
            {"太阳", "天梁", "文昌"} <= sanfang_stars
            and ("禄存" in sanfang_stars or "化禄" in sanfang_mutagens),
            {
                "sun_liang_chang_in_sanfang": {"太阳", "天梁", "文昌"} <= sanfang_stars,
                "lu_in_sanfang": "禄存" in sanfang_stars or "化禄" in sanfang_mutagens,
            },
        ),
        "tan_wu_tong_xing": (
            ming_branch in {"丑", "未"} and {"贪狼", "武曲"} <= ming_stars,
            {
                "ming_in_chou_wei": ming_branch in {"丑", "未"},
                "tan_wu_in_ming": {"贪狼", "武曲"} <= ming_stars,
            },
        ),
        "lian_zhen_wen_wu": (
            "廉贞" in ming_stars
            and "武曲" in sanfang_stars
            and bool({"文昌", "文曲"} & sanfang_stars),
            {
                "lianzhen_in_ming": "廉贞" in ming_stars,
                "wuqu_in_sanfang": "武曲" in sanfang_stars,
                "chang_or_qu_in_sanfang": bool({"文昌", "文曲"} & sanfang_stars),
            },
        ),
        "wu_qu_shou_yuan": (
            "武曲" in ming_stars and ming_branch != "卯",
            {"wu_qu_in_ming": "武曲" in ming_stars, "not_in_mao": ming_branch != "卯"},
        ),
        "fu_xiang_chao_yuan": (
            {"天府", "天相"} <= sanfang_stars,
            {"fu_xiang_in_sanfang": {"天府", "天相"} <= sanfang_stars},
        ),
        "shuang_lu_jiao_liu": (
            "禄存" in sanfang_stars and "化禄" in sanfang_mutagens,
            {
                "lucun_in_sanfang": "禄存" in sanfang_stars,
                "hualu_in_sanfang": "化禄" in sanfang_mutagens,
            },
        ),
        "lu_ma_jiao_chi": (
            ("禄存" in sanfang_stars or "化禄" in sanfang_mutagens)
            and "天马" in sanfang_stars,
            {
                "lu_in_sanfang": "禄存" in sanfang_stars or "化禄" in sanfang_mutagens,
                "tianma_in_sanfang": "天马" in sanfang_stars,
            },
        ),
        "san_qi_jia_hui": (
            {"化禄", "化权", "化科"} <= sanfang_mutagens,
            {"lu_quan_ke_in_sanfang": {"化禄", "化权", "化科"} <= sanfang_mutagens},
        ),
        "ke_quan_lu_jia": (
            ke_quan_lu_flanks,
            {"two_sihua_flank_ming": ke_quan_lu_flanks},
        ),
        "quan_lu_sheng_feng": (
            quan_lu_miao_wang,
            {
                "quan_lu_in_ming": quan_lu_in_ming,
                "quan_lu_in_miao_wang": quan_lu_miao_wang,
            },
        ),
        "ri_yue_jia_ming": (
            _flanks("太阳", "太阴"),
            {"sun_moon_flank_ming": _flanks("太阳", "太阴")},
        ),
        "zuo_you_jia_ming": (
            _flanks("左辅", "右弼"),
            {"zuo_you_flank_ming": _flanks("左辅", "右弼")},
        ),
        "chang_qu_jia_ming": (
            _flanks("文昌", "文曲"),
            {"chang_qu_flank_ming": _flanks("文昌", "文曲")},
        ),
        "kui_yue_jia_ming": (
            _flanks("天魁", "天钺"),
            {"kui_yue_flank_ming": _flanks("天魁", "天钺")},
        ),
        "zuo_gui_xiang_gui": (
            ("天魁" in ming_stars and "天钺" in opp_stars)
            or ("天钺" in ming_stars and "天魁" in opp_stars),
            {
                "kui_yue_ming_opp": ("天魁" in ming_stars and "天钺" in opp_stars)
                or ("天钺" in ming_stars and "天魁" in opp_stars)
            },
        ),
        "huo_tan_ge": (
            bool(_same_palace("火星", "贪狼") & key_branches),
            {
                "same_palace_in_key_palaces": bool(
                    _same_palace("火星", "贪狼") & key_branches
                )
            },
        ),
        "ling_tan_ge": (
            bool(_same_palace("铃星", "贪狼") & key_branches),
            {
                "same_palace_in_key_palaces": bool(
                    _same_palace("铃星", "贪狼") & key_branches
                )
            },
        ),
        "ling_chang_tuo_wu": (
            {"铃星", "文昌", "陀罗", "武曲"} <= sanfang_stars,
            {"all_four_in_sanfang": {"铃星", "文昌", "陀罗", "武曲"} <= sanfang_stars},
        ),
        "ming_wu_zheng_yao": (
            not ming_majors,
            {"empty_ming_palace": not ming_majors},
        ),
        "ma_tou_dai_jian": (
            ming_branch == "午" and "擎羊" in ming_stars,
            {
                "ming_in_wu": ming_branch == "午",
                "qingyang_in_ming": "擎羊" in ming_stars,
            },
        ),
        "shi_zhong_yin_yu": (
            ming_branch in {"子", "午"} and "巨门" in ming_stars,
            {
                "ming_in_zi_wu": ming_branch in {"子", "午"},
                "jumen_in_ming": "巨门" in ming_stars,
            },
        ),
        "shui_cheng_gui_e": (
            (_in_branch("太阳", "午") and _in_branch("太阴", "子"))
            or (
                ming_branch == "子"
                and "太阴" in ming_stars
                and bool(sanfang_mutagens & {"化禄", "化权", "化科"})
            ),
            {"sun_wu_moon_zi": _in_branch("太阳", "午") and _in_branch("太阴", "子")},
        ),
        "xiong_su_chao_yuan": (
            ming_branch in {"寅", "申"} and "廉贞" in ming_stars,
            {
                "ming_in_yin_shen": ming_branch in {"寅", "申"},
                "lianzhen_in_ming": "廉贞" in ming_stars,
            },
        ),
        "qi_sha_chao_dou": (
            ming_branch in {"寅", "申", "子", "午"} and "七杀" in ming_stars,
            {
                "ming_in_yin_shen_zi_wu": ming_branch in {"寅", "申", "子", "午"},
                "qisha_in_ming": "七杀" in ming_stars,
            },
        ),
    }

    matched: list[dict[str, Any]] = []
    unmatched_ids: list[str] = []
    for meta in PATTERN_CATALOGUE:
        is_met, conds = checks[meta["id"]]
        if is_met:
            entry: dict[str, Any] = {
                "id": meta["id"],
                "name": meta["name"],
                "category": meta["category"],
                "matched": True,
                "conditions": conds,
            }
            if meta["id"] == "ming_wu_zheng_yao":
                entry["borrowed_opposite_palace"] = by_branch[opp_branch]["name"]
                entry["borrowed_opposite_branch"] = opp_branch
                entry["borrowed_opposite_major_stars"] = opp_majors
            matched.append(entry)
        else:
            unmatched_ids.append(meta["id"])

    return {
        "method_id": "ziwei_classical_patterns_v2",
        "total_checked": len(PATTERN_CATALOGUE),
        "matched_count": len(matched),
        "matched": matched,
    }
