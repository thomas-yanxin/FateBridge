"""Wealth-star positions, root prerequisites and actual storage/clash relations.

Fixed rule indices are uncalibrated descriptions, never
wealth levels, investment probabilities or forecasts of financial outcomes.
《秘本子平真诠》PDF44–45 rejects universal storage-opening rules; PDF76
requires examining wealth roots and relative body/food/wealth force.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.bazi_root_context import wealth_rule_context
from ..utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    Element,
    TenGod,
    check_branch_conflict,
    count_element_distribution,
    get_ten_god,
    iter_pillar_gods,
)

# 财库：辰戌丑未对应所藏之财（墓库）
# 每个土支为某一五行的墓库
STORAGE_BRANCHES = {
    "辰": Element.WATER,  # 水库
    "戌": Element.FIRE,  # 火库
    "丑": Element.METAL,  # 金库
    "未": Element.WOOD,  # 木库
}

# 正财/偏财求财方式说明
WEALTH_STAR_STYLE = {
    TenGod.POSITIVE_WEALTH: {
        "label": "正财",
        "source": "正业、固定收入、薪资、稳健经营",
        "traits": "持续性收入的现代类比，不测量实际收入或品行",
    },
    TenGod.PARTIAL_WEALTH: {
        "label": "偏财",
        "source": "投资、投机、副业、经商、意外之财",
        "traits": "项目与交易类收入的现代类比，不判断投资能力或收益",
    },
}

# 五行求财方位
ELEMENT_DIRECTION = {
    Element.WOOD: "东方",
    Element.FIRE: "南方",
    Element.EARTH: "中央/本地",
    Element.METAL: "西方",
    Element.WATER: "北方",
}


class WealthAnalysis:
    """财运分析工具类"""

    @staticmethod
    def analyze_wealth(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合财运分析。

        Args:
            pillars: 四柱 {"year"/"month"/"day"/"hour": (stem, branch)}
            gender: 性别（财运分析中影响较小，保留以统一接口）
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            财运分析结果字典
        """
        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0]
        wealth_element = DESTRUCTION_CYCLE[day_element]  # 日主所克即为财

        wealth_stars = WealthAnalysis._locate_wealth_stars(pillars, day_stem)
        structure = WealthAnalysis._analyze_wealth_structure(
            pillars, day_stem, wealth_element
        )
        storage = WealthAnalysis._analyze_wealth_storage(pillars, wealth_element)
        style = WealthAnalysis._analyze_wealth_style(wealth_stars)
        direction = WealthAnalysis._analyze_wealth_direction(wealth_element)
        risk = WealthAnalysis._analyze_wealth_risk(pillars, day_stem, wealth_element)
        timing = WealthAnalysis._analyze_wealth_timing(
            day_stem, wealth_element, dayun_pillar, liunian_pillar, pillars=pillars
        )
        suggestions = WealthAnalysis._generate_suggestions(structure, style, risk)

        return {
            "counting_basis": "非日干每次1、每个藏干每次0.5；计数不等于有效力量。wealth_strength另按元素计权，非财旺裁定。",
            "classical_context": wealth_rule_context(pillars),
            "wealth_element": wealth_element.value,
            "wealth_stars": wealth_stars,
            "wealth_structure": structure,
            "wealth_storage": storage,
            "wealth_style": style,
            "wealth_direction": direction,
            "wealth_risk": risk,
            "wealth_timing": timing,
            "suggestions": suggestions,
        }

    @staticmethod
    def _locate_wealth_stars(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """定位命局中的正财、偏财（含地支藏干）。"""
        positions: List[Dict[str, Any]] = []
        zheng_count = 0.0
        pian_count = 0.0

        for e in iter_pillar_gods(pillars, day_stem):
            if e.ten_god not in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
                continue
            positions.append(
                {
                    "pillar": e.pillar,
                    "location": e.location,
                    "char": e.char,
                    "ten_god": e.ten_god.value,
                }
            )
            if e.ten_god == TenGod.POSITIVE_WEALTH:
                zheng_count += e.weight
            else:
                pian_count += e.weight

        total = round(zheng_count + pian_count, 1)
        if total == 0:
            visibility = "本次天干和全部藏干均未见财星；不代表现实无收入"
        elif zheng_count >= pian_count:
            visibility = "正财加权计数不低于偏财；不判断实际财源稳定性或正当性"
        else:
            visibility = "偏财加权计数较高；不据此判断经商或投资结果"

        return {
            "positions": positions,
            "zheng_wealth_weight": round(zheng_count, 1),
            "pian_wealth_weight": round(pian_count, 1),
            "total_weight": total,
            "visibility": visibility,
        }

    @staticmethod
    def _analyze_wealth_structure(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        wealth_element: Element,
    ) -> Dict[str, Any]:
        """计算固定规则指数，显式区分模型分类、计数与原典成格。"""
        from ..core.elements import ElementAnalysis

        dm_analysis = ElementAnalysis.analyze_day_master_strength(pillars)
        strength = dm_analysis["strength_level"]

        element_counts = count_element_distribution(pillars)
        wealth_strength = round(element_counts[wealth_element], 1)

        score = 60
        notes: List[str] = []

        has_wealth = wealth_strength >= 1.5

        if strength == "强" and has_wealth:
            score += 18
            notes.append(
                "扶抑模型为强且财元素计权达到1.5；不能据计数认定财旺或财富层次"
            )
        elif strength == "中和" and has_wealth:
            score += 12
            notes.append("扶抑模型为中和且财元素计权达到1.5；不等于原典身财两停")
        elif strength == "弱" and wealth_strength >= 2.5:
            score -= 12
            notes.append("扶抑模型为弱且财元素计权至少2.5；不推断现实贫富或守财能力")
        elif strength == "强" and not has_wealth:
            score -= 5
            notes.append("扶抑模型为强且财元素计权低于1.5；不推断致富路径")
        else:
            notes.append("未命中上述模型和计数阈值分支；不能把规则未命中解释为财务平稳")

        # 食伤生财：财源活水
        has_food_hurt = False
        for p_name, (stem, branch) in pillars.items():
            if p_name == "day":
                continue
            if get_ten_god(day_stem, stem) in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
                has_food_hurt = True
        if has_food_hurt and has_wealth:
            score += 8
            notes.append(
                "非日干见食伤且财元素计权达到阈值；财根、相对力量与成格条件另查classical_context"
            )

        score = max(30, min(95, score))
        if score >= 82:
            level = "规则索引82–95"
        elif score >= 68:
            level = "规则索引68–81"
        elif score >= 55:
            level = "规则索引55–67"
        else:
            level = "规则索引30–54"

        return {
            "day_master_strength": strength,
            "wealth_strength": wealth_strength,
            "pattern": f"模型{strength}／财元素计权{wealth_strength:g}（未裁定格局）",
            "formation_status": "not_adjudicated",
            "score_kind": "uncalibrated_rule_index",
            "score_basis": "基础60；扶抑模型强且财计权达1.5加18，中和且达1.5加12，弱且达2.5减12，强且低于1.5减5；非日干见食伤且财达阈值加8；截断30–95。非概率。",
            "wealth_strength_kind": "element_occurrence_weight",
            "score": score,
            "level": level,
            "notes": notes,
        }

    @staticmethod
    def _analyze_wealth_storage(
        pillars: Dict[str, Tuple[str, str]],
        wealth_element: Element,
    ) -> Dict[str, Any]:
        """只记录墓库对应与实际冲；不套四墓喜冲的普遍规则。"""
        storage_hits: List[Dict[str, Any]] = []
        for name, (_, branch) in pillars.items():
            if STORAGE_BRANCHES.get(branch) != wealth_element:
                continue
            clashes = [
                {"other_pillar": other, "other_branch": value[1]}
                for other, value in pillars.items()
                if other != name and check_branch_conflict(branch, value[1])
            ]
            storage_hits.append(
                {
                    "pillar": name,
                    "branch": branch,
                    "stores": f"{wealth_element.value}（四墓类比）",
                    "opened": None,
                    "clash_present": bool(clashes),
                    "clashes": clashes,
                    "note": "仅记录四墓对应与实际六冲；刑冲不自动开库，也不自动进财。",
                }
            )
        return {
            "has_storage": bool(storage_hits),
            "storage_hits": storage_hits,
            "summary": (
                "按四墓对应查见财元素库支；未裁定开库、聚财或进财"
                if storage_hits
                else "本四墓映射未命中财元素库支；不能据此判断资产积聚能力"
            ),
            "effect_status": "storage_symbol_not_financial_prediction",
            "source_ref": "ziping_prerequisites_v1:storage_clash",
        }

    @staticmethod
    def _analyze_wealth_style(wealth_stars: Dict[str, Any]) -> Dict[str, Any]:
        """根据正偏财比重判断求财方式。"""
        zheng = wealth_stars["zheng_wealth_weight"]
        pian = wealth_stars["pian_wealth_weight"]

        recommendations: List[str] = []
        if zheng > 0:
            info = WEALTH_STAR_STYLE[TenGod.POSITIVE_WEALTH]
            recommendations.append(f"正财：{info['source']}（{info['traits']}）")
        if pian > 0:
            info = WEALTH_STAR_STYLE[TenGod.PARTIAL_WEALTH]
            recommendations.append(f"偏财：{info['source']}（{info['traits']}）")
        if not recommendations:
            recommendations.append("本次未见财星；不能据此指定实际收入来源")

        if pian > zheng:
            primary = "偏财计数较高；可讨论项目收入类比，需核实现实收入结构"
        elif zheng > pian:
            primary = "正财计数较高；可讨论持续收入类比，需核实现实收入结构"
        else:
            primary = "正偏财计数相同；不据此选择职业或投资方式"

        return {
            "primary_style": primary,
            "recommendations": recommendations,
        }

    @staticmethod
    def _analyze_wealth_direction(wealth_element: Element) -> Dict[str, Any]:
        """求财方位（以财星五行所主方位为参考）。"""
        return {
            "wealth_element": wealth_element.value,
            "direction": ELEMENT_DIRECTION.get(wealth_element, "本地"),
            "note": f"五行方位查表：{wealth_element.value}对应{ELEMENT_DIRECTION.get(wealth_element, '本地')}；不据此判断投资、置业或迁移结果",
        }

    @staticmethod
    def _analyze_wealth_risk(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        wealth_element: Element,
    ) -> Dict[str, Any]:
        """破财风险：比劫夺财、财星受冲。"""
        risks: List[str] = []

        bijie = sum(
            e.weight
            for e in iter_pillar_gods(pillars, day_stem)
            if e.ten_god in (TenGod.COMPARE, TenGod.ROB_WEALTH)
        )
        if bijie >= 1.5:
            risks.append(
                f"比劫加权计数{bijie:g}；未裁定夺财，不据此判断借贷、合伙或损失"
            )
        relations = []
        for name, (_, branch) in pillars.items():
            wealth_hidden = [
                stem
                for stem in BRANCH_HIDDEN_STEMS[branch]
                if STEM_ELEMENTS[stem][0] == wealth_element
            ]
            if not wealth_hidden:
                continue
            for other, (_, other_branch) in pillars.items():
                if other != name and check_branch_conflict(branch, other_branch):
                    relations.append(
                        {
                            "wealth_pillar": name,
                            "wealth_branch": branch,
                            "wealth_hidden_stems": wealth_hidden,
                            "other_pillar": other,
                            "other_branch": other_branch,
                        }
                    )
        if relations:
            risks.append("含财藏干的柱支有实际六冲；尚未裁定财根损益或现实收入变化")
        if not risks:
            risks.append("未命中本模块计数阈值及含财藏干支的六冲；不代表现实财务安稳")
        return {
            "bijie_weight": round(bijie, 1),
            "risks": risks,
            "relations": relations,
            "assessment_status": "structural_candidates_not_loss_prediction",
        }

    @staticmethod
    def _analyze_wealth_timing(
        day_stem: str,
        wealth_element: Element,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
        *,
        pillars: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """实际天干对应与本命库支的六冲触点，不预测收益。"""
        signals: List[str] = []
        storage_events: List[Dict[str, Any]] = []
        for label, pillar in (("大运", dayun_pillar), ("流年", liunian_pillar)):
            if pillar is None:
                continue
            stem, branch = pillar
            god = get_ten_god(day_stem, stem)
            if god in (
                TenGod.POSITIVE_WEALTH,
                TenGod.PARTIAL_WEALTH,
                TenGod.FOOD_GOD,
                TenGod.HURT_OFFICER,
                TenGod.COMPARE,
                TenGod.ROB_WEALTH,
            ):
                signals.append(
                    f"{label}{stem}{branch}天干对应{god.value}；仅为传统主题触点"
                )
            if STORAGE_BRANCHES.get(branch) == wealth_element:
                signals.append(
                    f"{label}支{branch}为本四墓表的{wealth_element.value}库；出现库支不等于开库或进财"
                )
            for name, (_, natal_branch) in (pillars or {}).items():
                if STORAGE_BRANCHES.get(
                    natal_branch
                ) == wealth_element and check_branch_conflict(natal_branch, branch):
                    storage_events.append(
                        {
                            "layer": label,
                            "timing_pillar": stem + branch,
                            "natal_pillar": name,
                            "storage_branch": natal_branch,
                            "relation": "六冲",
                            "effect_status": "not_adjudicated",
                        }
                    )
        provided = dayun_pillar is not None or liunian_pillar is not None
        return {
            "timing_signals": signals,
            "storage_events": storage_events,
            "assessment_status": (
                "matched"
                if signals or storage_events
                else "no_matching_rule" if provided else "missing_timing_input"
            ),
        }

    @staticmethod
    def _generate_suggestions(
        structure: Dict[str, Any],
        style: Dict[str, Any],
        risk: Dict[str, Any],
    ) -> List[str]:
        """生成财运建议。"""
        return [
            "传统解读：先核对财星透藏、财根、食伤路径及实际运年触点，不能只凭数量称财旺",
            "现实核实：依据真实收支、现金流、合同义务及可承受损失作财务安排",
            "现代类比：" + style["primary_style"],
        ]
