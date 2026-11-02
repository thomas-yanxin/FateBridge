"""Career occurrence counts, modern role analogies and explicit rule indices.

Day-branch hidden stems are included. Scores and role labels are not source
formation judgments or measurements of job competence or entrepreneurship.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.rules import BaZiRules
from ..utils.data import (
    STEM_ELEMENTS,
    Element,
    TenGod,
    count_element_distribution,
    count_ten_gods,
    get_ten_god,
    iter_pillar_gods,
)

# 五行对应行业
ELEMENT_INDUSTRIES = {
    Element.WOOD: {
        "label": "木",
        "industries": [
            "教育培训",
            "文化出版",
            "园林绿化",
            "家具木材",
            "纺织服装",
            "医药健康",
            "农业种植",
            "环保生态",
            "设计创意",
            "宗教哲学",
        ],
        "direction": "东方",
        "season": "春季",
    },
    Element.FIRE: {
        "label": "火",
        "industries": [
            "互联网科技",
            "电子电器",
            "能源电力",
            "餐饮娱乐",
            "传媒广告",
            "美容化妆",
            "照明光学",
            "冶炼铸造",
            "心理咨询",
            "演艺娱乐",
        ],
        "direction": "南方",
        "season": "夏季",
    },
    Element.EARTH: {
        "label": "土",
        "industries": [
            "房地产建筑",
            "农业畜牧",
            "矿业资源",
            "仓储物流",
            "陶瓷建材",
            "殡葬服务",
            "宗教场所",
            "人力资源",
            "会计审计",
            "仓储管理",
        ],
        "direction": "中央",
        "season": "四季月（辰戌丑未月）",
    },
    Element.METAL: {
        "label": "金",
        "industries": [
            "金融银行",
            "法律司法",
            "机械制造",
            "汽车交通",
            "珠宝首饰",
            "医疗器械",
            "军事国防",
            "体育竞技",
            "IT硬件",
            "精密仪器",
        ],
        "direction": "西方",
        "season": "秋季",
    },
    Element.WATER: {
        "label": "水",
        "industries": [
            "贸易流通",
            "物流运输",
            "旅游酒店",
            "水产渔业",
            "饮料酒业",
            "水利水务",
            "航海航空",
            "媒体传播",
            "咨询顾问",
            "外交公关",
        ],
        "direction": "北方",
        "season": "冬季",
    },
}

# 十神对应事业特征
TEN_GOD_CAREER = {
    TenGod.COMPARE: {
        "label": "比肩",
        "career_type": "独立经营",
        "traits": "现代讨论主题：自主职责、同辈竞争与合作分工",
        "suitable": ["创业", "合伙经营", "自由职业", "体育竞技"],
    },
    TenGod.ROB_WEALTH: {
        "label": "劫财",
        "career_type": "竞争型",
        "traits": "现代讨论主题：竞争任务、行动节奏与风险约束",
        "suitable": ["销售", "市场营销", "投机行业", "体育"],
    },
    TenGod.FOOD_GOD: {
        "label": "食神",
        "career_type": "才华型",
        "traits": "现代讨论主题：产品输出、表达与持续创作",
        "suitable": ["艺术创作", "餐饮美食", "教育培训", "文化出版"],
    },
    TenGod.HURT_OFFICER: {
        "label": "伤官",
        "career_type": "创新型",
        "traits": "现代讨论主题：规则质疑、改进与表达方式",
        "suitable": ["技术研发", "设计创意", "自媒体", "律师"],
    },
    TenGod.POSITIVE_WEALTH: {
        "label": "正财",
        "career_type": "稳健型",
        "traits": "现代讨论主题：持续经营、预算与资源管理",
        "suitable": ["财务管理", "银行金融", "会计审计", "实业经营"],
    },
    TenGod.PARTIAL_WEALTH: {
        "label": "偏财",
        "career_type": "投资型",
        "traits": "现代讨论主题：项目交易与非固定资源，不判断投资能力",
        "suitable": ["投资理财", "股票期货", "贸易经商", "地产"],
    },
    TenGod.POSITIVE_OFFICER: {
        "label": "正官",
        "career_type": "管理型",
        "traits": "现代讨论主题：制度责任、流程与岗位授权",
        "suitable": ["公务员", "企业管理", "行政管理", "法律"],
    },
    TenGod.SEVEN_KILLER: {
        "label": "七杀",
        "career_type": "权威型",
        "traits": "现代讨论主题：约束、决策责任与任务压力",
        "suitable": ["军警", "外科医生", "高管", "创业"],
    },
    TenGod.POSITIVE_SEAL: {
        "label": "正印",
        "career_type": "学术型",
        "traits": "现代讨论主题：学习支持、知识传递与规范",
        "suitable": ["教师", "研究员", "公务员", "文化行业"],
    },
    TenGod.PARTIAL_SEAL: {
        "label": "偏印",
        "career_type": "技术型",
        "traits": "现代讨论主题：专业方法、非标准知识与独立研究",
        "suitable": ["技术研发", "医疗", "玄学", "IT"],
    },
}


class CareerAnalysis:
    """事业分析工具类"""

    @staticmethod
    def analyze_career(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合事业分析。

        Args:
            pillars: 四柱
            gender: 性别
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            事业分析结果字典
        """
        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0]

        # 1. 主导十神分析
        dominant_god_analysis = CareerAnalysis._analyze_dominant_ten_gods(
            pillars, day_stem
        )

        # 2. 适合行业分析
        industry_analysis = CareerAnalysis._analyze_industries(
            pillars, day_stem, day_element
        )

        # 3. 事业格局
        career_structure = CareerAnalysis._analyze_career_structure(pillars, day_stem)

        # 4. 创业 vs 打工倾向
        entrepreneurship = CareerAnalysis._analyze_entrepreneurship(pillars, day_stem)

        # 5. 事业时机
        career_timing = CareerAnalysis._analyze_career_timing(
            pillars, day_stem, dayun_pillar, liunian_pillar
        )

        # 6. 贵人方位
        noble_direction = CareerAnalysis._analyze_noble_direction(pillars, day_element)

        # 7. 综合建议
        suggestions = CareerAnalysis._generate_suggestions(
            dominant_god_analysis, industry_analysis, career_structure, entrepreneurship
        )

        return {
            "interpretation_scope": (
                "个人命盘的传统事业规则分析；不测量实际能力、收入或创业成功概率，"
                "不能据此决定辞职、投资或创业。"
            ),
            "dominant_ten_gods": dominant_god_analysis,
            "industry_analysis": industry_analysis,
            "career_structure": career_structure,
            "entrepreneurship": entrepreneurship,
            "career_timing": career_timing,
            "noble_direction": noble_direction,
            "suggestions": suggestions,
        }

    @staticmethod
    def _analyze_dominant_ten_gods(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """分析命局中主导的十神，确定事业类型。"""
        # 排除日干自身，保留日支全部藏干；与共享十神证据同口径。
        god_counts = count_ten_gods(pillars, day_stem, skip_day_pillar=False)

        # 排序取前三
        sorted_gods = sorted(god_counts.items(), key=lambda x: x[1], reverse=True)
        positive = [(god, count) for god, count in sorted_gods if count > 0]
        cutoff = positive[min(2, len(positive) - 1)][1] if positive else 0
        top_gods = [(god, count) for god, count in positive if count >= cutoff]
        tied = [god for god, count in positive if count == positive[0][1]]

        career_profiles = []
        for god, count in top_gods:
            profile = TEN_GOD_CAREER.get(god, {})
            career_profiles.append(
                {
                    "ten_god": god.value,
                    "weight": round(count, 1),
                    "career_type": profile.get("career_type", "综合型"),
                    "traits": profile.get("traits", ""),
                    "suitable_roles": profile.get("suitable", []),
                }
            )

        return {
            "top_gods": career_profiles,
            "mapping_scope": "职业标签、traits及suitable_roles均为本工具的现代类比；不是原典岗位判定或能力测量。",
            "weighted_counts": {
                god.value: weight for god, weight in god_counts.items()
            },
            "counting_basis": {
                "included_pillars": [
                    n for n in ("year", "month", "day", "hour") if n in pillars
                ],
                "excluded_pillars": [],
                "excluded_stem_positions": ["day"],
                "stem_weight": 1.0,
                "hidden_stem_weight": 0.5,
                "scope": "非日干每次1、四柱每个藏干每次0.5；排除日干自身，保留日支藏干。计数不等于旺衰或实际能力。",
            },
            "tied_primary_gods": [
                god.value
                for god, weight in sorted_gods
                if weight > 0 and weight == sorted_gods[0][1]
            ],
            "primary_selection": "最高项及第三位全部并列保留，不以枚举顺序确定唯一主导。",
            "primary_career_type": (
                (
                    "并列："
                    + "、".join(str(TEN_GOD_CAREER[g]["career_type"]) for g in tied)
                )
                if len(tied) > 1
                else (
                    career_profiles[0]["career_type"] if career_profiles else "未见计数"
                )
            ),
        }

    @staticmethod
    def _analyze_industries(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        day_element: Element,
    ) -> Dict[str, Any]:
        """分析适合的行业方向。"""
        # 统计命局五行分布
        element_counts = count_element_distribution(pillars)

        # 喜用神五行
        profile = BaZiRules.chart_useful_profile(pillars)
        favorable = [Element(value) for value in profile["useful_elements"]]

        # 推荐行业基于喜用神
        recommended_industries: List[Dict[str, Any]] = []
        for elem in favorable:
            info = ELEMENT_INDUSTRIES.get(elem)
            if info:
                recommended_industries.append(
                    {
                        "element": info["label"],
                        "industries": info["industries"],
                        "direction": info["direction"],
                        "reason": f"规则候选{info['label']}对应本工具的现代行业类比，需核实现实职责与经验",
                    }
                )

        # 忌神行业
        avoid_elements = [Element(value) for value in profile["avoid_elements"]]
        avoid_industries: List[Dict[str, Any]] = []
        for elem in avoid_elements:
            info = ELEMENT_INDUSTRIES.get(elem)
            if info:
                avoid_industries.append(
                    {
                        "element": info["label"],
                        "industries": info["industries"][:3],
                        "reason": f"反向规则涉及{info['label']}；行业为本工具类比，不能据此排除职业",
                    }
                )

        return {
            "favorable_elements": [e.value for e in favorable],
            "conditional_elements": profile["conditional_elements"],
            "reference_scope": profile["resolution_policy"],
            "mapping_status": "modern_analogy_not_classical_or_aptitude_validation",
            "recommended_industries": recommended_industries,
            "avoid_industries": avoid_industries,
            "element_distribution": {
                e.value: round(c, 1) for e, c in element_counts.items()
            },
        }

    @staticmethod
    def _analyze_career_structure(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """计算事业共现启发式评分及候选线索，不判定古典成格。"""
        score = 60  # 基准分
        notes: List[str] = []
        rule_signals: List[Dict[str, Any]] = []

        # 1. 官印相生 is one positive contribution, not the overall grade.
        has_officer = False
        has_seal = False
        for e in iter_pillar_gods(pillars, day_stem, skip_day_pillar=False):
            if e.ten_god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
                has_officer = True
            if e.ten_god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
                has_seal = True

        if has_officer and has_seal:
            score += 15
            notes.append(
                "官印相生候选：仅官杀与印星共现，按启发式规则加分；未验证古典成格条件"
            )
            rule_signals.append(
                {
                    "label": "官印相生",
                    "trigger": "官或杀与正印或偏印共现（非日干及四柱藏干）",
                    "score_delta": 15,
                }
            )

        # 2. 食伤生财 → 经商格局
        has_food_hurt = False
        has_wealth = False
        for entry in iter_pillar_gods(pillars, day_stem):
            if entry.ten_god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
                has_food_hurt = True
            if entry.ten_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                has_wealth = True

        if has_food_hurt and has_wealth:
            score += 10
            notes.append(
                "食伤生财候选：非日干及四柱藏干共现，未验证生化条件；不据此预测收入"
            )
            rule_signals.append(
                {
                    "label": "食伤生财",
                    "trigger": "食神或伤官与正财或偏财共现（非日干及四柱藏干）",
                    "score_delta": 10,
                }
            )

        # 3. 财官双美
        if has_officer and has_wealth:
            score += 8
            notes.append(
                "财官双美候选：仅官杀与财星共现，未验证古典成格条件；不代表现实名利结果"
            )
            rule_signals.append(
                {
                    "label": "财官双美",
                    "trigger": "官杀（非日干及四柱藏干）与财星（非日干及四柱藏干）共现",
                    "score_delta": 8,
                }
            )

        # 4. 日主强弱影响
        from ..core.elements import ElementAnalysis

        dm_analysis = ElementAnalysis.analyze_day_master_strength(pillars)
        strength = dm_analysis["strength_level"]
        if strength == "强":
            score += 5
            notes.append("日主强旺，按本规则提高事业格局评分，不等于实际承压能力")
        elif strength == "弱":
            score -= 5
            notes.append("日主偏弱，按本规则降低事业格局评分，不据此判断个人能力")

        score = max(30, min(95, score))

        if score >= 85:
            level = "上等格局"
        elif score >= 70:
            level = "中等格局"
        elif score >= 55:
            level = "普通格局"
        else:
            level = "需努力突破"

        return {
            "score": score,
            "score_kind": "uncalibrated_rule_index",
            "scope": "individual_natal_career_structure",
            "formation_status": "heuristic_candidate_only",
            "rule_signals": rule_signals,
            "unverified_conditions": [
                "月令取格",
                "透藏位置与根气",
                "生克制化力度及救应",
                "格局成败",
            ],
            "interpretation_scope": "共现标签与分数只描述本实现的启发式线索；level为规则索引；legacy_level只保留旧评分分档供迁移，不是古典成格或现实事业层级认证。",
            "score_basis": (
                "以60为基准，按官印、食伤与财、财官及日主强弱规则加减，"
                "限制在30–95；不是事业成就或收入概率。"
            ),
            "level": f"规则索引{score}（未裁定古典格局）",
            "legacy_level": level,
            "notes": notes,
        }

    @staticmethod
    def _analyze_entrepreneurship(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """分析创业 vs 打工倾向。"""
        entrepreneur_score = 50
        notes: List[str] = []
        rule_signals: List[Dict[str, Any]] = []

        # 统计十神
        god_counts: Dict[str, float] = {}
        for e in iter_pillar_gods(pillars, day_stem, skip_day_pillar=False):
            key = e.ten_god.value
            god_counts[key] = god_counts.get(key, 0) + e.weight

        # 偏星多 → 创业倾向
        partial_stars = sum(
            god_counts.get(g, 0)
            for g in [
                TenGod.ROB_WEALTH.value,
                TenGod.HURT_OFFICER.value,
                TenGod.PARTIAL_WEALTH.value,
                TenGod.SEVEN_KILLER.value,
                TenGod.PARTIAL_SEAL.value,
            ]
        )
        normal_stars = sum(
            god_counts.get(g, 0)
            for g in [
                TenGod.COMPARE.value,
                TenGod.FOOD_GOD.value,
                TenGod.POSITIVE_WEALTH.value,
                TenGod.POSITIVE_OFFICER.value,
                TenGod.POSITIVE_SEAL.value,
            ]
        )

        if partial_stars > normal_stars:
            entrepreneur_score += 15
            notes.append("偏星为主，传统规则提高自主经营倾向评分")
        elif normal_stars > partial_stars:
            entrepreneur_score -= 10
            notes.append("正星为主，传统规则偏向稳定工作倾向")

        # 七杀有制 → 领导型创业者
        if god_counts.get(TenGod.SEVEN_KILLER.value, 0) > 0:
            if god_counts.get(TenGod.FOOD_GOD.value, 0) > 0:
                entrepreneur_score += 10
                notes.append(
                    "食神制杀候选：仅食神与七杀共现，未验证制杀力度及成格条件；不代表创业成功概率"
                )
                rule_signals.append(
                    {
                        "label": "食神制杀",
                        "trigger": "食神与七杀共现（非日干及四柱藏干）",
                        "score_delta": 10,
                    }
                )
            elif god_counts.get(TenGod.POSITIVE_SEAL.value, 0) > 0:
                entrepreneur_score += 8
                notes.append("杀印相生候选：仅七杀与正印共现，未验证生化及成格条件")
                rule_signals.append(
                    {
                        "label": "杀印相生",
                        "trigger": "七杀与正印共现且无食神（非日干及四柱藏干）",
                        "score_delta": 8,
                    }
                )

        entrepreneur_score = max(20, min(90, entrepreneur_score))

        if entrepreneur_score >= 70:
            tendency = "强烈创业倾向"
        elif entrepreneur_score >= 55:
            tendency = "可创业可打工"
        else:
            tendency = "更适合稳定工作"

        return {
            "score": entrepreneur_score,
            "weighted_counts": god_counts,
            "partial_star_weight": partial_stars,
            "normal_star_weight": normal_stars,
            "score_kind": "uncalibrated_rule_index",
            "scope": "individual_natal_entrepreneurship_tendency",
            "formation_status": "heuristic_candidate_only",
            "rule_signals": rule_signals,
            "unverified_conditions": [
                "日主与食杀印的旺衰根气",
                "位置及制化力度",
                "古典成格条件",
            ],
            "score_basis": (
                "以50为基准，按正偏十神权重、食神制杀或杀印相生规则加减，"
                "偏星多加15、正星多减10；有七杀及食神加10，否则有七杀及正印加8；"
                "限制在20–90。计数包含日支藏干，指数未校准为创业适合度或成功率。"
            ),
            "tendency": f"未校准规则索引{entrepreneur_score}；不据此决定创业或就业",
            "legacy_tendency": tendency,
            "notes": notes,
        }

    @staticmethod
    def _analyze_career_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """分析事业时机。"""
        signals: List[str] = []

        if dayun_pillar:
            d_stem, d_branch = dayun_pillar
            d_god = get_ten_god(day_stem, d_stem)
            if d_god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
                signals.append(
                    f"大运{d_stem}{d_branch}见官杀，传统规则关联事业与管理责任议题"
                )
            elif d_god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
                signals.append(
                    f"大运{d_stem}{d_branch}见印星，传统规则关联学习与支持议题"
                )
            elif d_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                signals.append(
                    f"大运{d_stem}{d_branch}见财星，传统规则关联经营与资源议题，不预测投资收益"
                )
            elif d_god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
                signals.append(
                    f"大运{d_stem}{d_branch}见食伤，传统规则关联创意与表达议题"
                )

        if liunian_pillar:
            l_stem, l_branch = liunian_pillar
            l_god = get_ten_god(day_stem, l_stem)
            if l_god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
                signals.append(
                    f"流年{l_stem}{l_branch}见官杀，传统规则关联当年的事业与责任议题"
                )
            elif l_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                signals.append(
                    f"流年{l_stem}{l_branch}见财星，传统规则关联经营与收入议题，不预测收益"
                )

        return {
            "timing_signals": signals,
        }

    @staticmethod
    def _analyze_noble_direction(
        pillars: Dict[str, Tuple[str, str]],
        day_element: Element,
    ) -> Dict[str, Any]:
        """分析贵人方位。"""
        # 喜用神方位
        profile = BaZiRules.chart_useful_profile(pillars)
        favorable = [Element(value) for value in profile["useful_elements"]]

        directions: List[Dict[str, Any]] = []
        for elem in favorable:
            info = ELEMENT_INDUSTRIES.get(elem)
            if info:
                directions.append(
                    {
                        "element": info["label"],
                        "direction": info["direction"],
                        "reason": f"喜用神{info['label']}对应{info['direction']}方",
                    }
                )

        return {
            "favorable_directions": directions,
            "conditional_elements": profile["conditional_elements"],
            "reference_scope": profile["resolution_policy"],
            "mapping_status": "modern_analogy_not_classical_or_aptitude_validation",
        }

    @staticmethod
    def _generate_suggestions(
        dominant_god: Dict[str, Any],
        industry: Dict[str, Any],
        structure: Dict[str, Any],
        entrepreneurship: Dict[str, Any],
    ) -> List[str]:
        """生成事业建议。"""
        suggestions: List[str] = []

        # Preserve ties through this derived prose exit, not only raw fields.
        primary_type = dominant_god.get("primary_career_type", "综合型")
        tied = dominant_god.get("tied_primary_gods", [])
        if len(tied) > 1:
            types = {
                god.value: profile["career_type"]
                for god, profile in TEN_GOD_CAREER.items()
            }
            labels = "、".join(f"{god}（{types.get(god, '综合型')}）" for god in tied)
            suggestions.append(
                f"本规则最高计权并列为{labels}；这些是职业类比，需结合实际职责与经验核验，首项不表示更强"
            )
        else:
            suggestions.append(
                f"本规则计权首项映射为{primary_type}，仅作职业类比，需结合实际职责与经验核验"
            )

        # Historical score bands are not classical formation determinations.
        level = structure.get("level", "普通格局")
        if structure.get("formation_status") == "heuristic_candidate_only":
            suggestions.append(
                f"本启发式评分的历史分档为“{level}”；共现标签仍属候选，未验证古典成格条件，也不代表现实事业层级或机遇大小"
            )
        else:
            suggestions.append(
                f"历史规则评分分档为“{level}”；单凭分档不能确认古典成格或现实事业层级"
            )

        suggestions.append(
            f"创业模块规则索引为{entrepreneurship['score']}；现实选择须核对需求、资金、职责和执行记录"
        )

        # 基于行业
        rec = industry.get("recommended_industries", [])
        if rec:
            suggestions.append(
                "行业字段中的五行分类仅为传统类比，列表顺序不构成优先级；选择需核对兴趣、经验与岗位要求"
            )

        return suggestions
