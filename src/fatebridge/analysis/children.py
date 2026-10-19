"""
子女分析模块

基于八字命理的子女分析功能，综合以下经典技法：
- 子女星：男命以官杀为子女，女命以食伤为子女（子平传统六亲法）
- 子女宫：时柱为子女宫，看命主的子女传统对应
- 时柱十神：解释命主视角的亲子传统象意
- 神煞辅助：时柱逢生扶/冲克影响子女缘

核心分析维度：
1. 子女星定位（按性别取官杀/食伤）与强弱
2. 子女宫（时柱）状态分析
3. 子女传统对应的规则分类
4. 命主视角的亲子传统象意
5. 大运流年引动子女星与子女宫的传统关系

说明：仅解释命主视角的传统对应，不推断生育能力、子女数量或孩子本人的能力。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..utils.data import (
    TenGod,
    check_branch_combination,
    check_branch_conflict,
    get_ten_god,
    iter_pillar_gods,
    normalize_gender,
)

# 命主时柱十神的传统象意，不是孩子本人的性格或能力画像
HOUR_TEN_GOD_CHILDREN = {
    TenGod.COMPARE: "命主子女宫比肩的传统象意涉及平等相处与自主边界。",
    TenGod.ROB_WEALTH: "命主子女宫劫财的传统象意涉及竞争与资源分配。",
    TenGod.FOOD_GOD: "命主子女宫食神的传统象意涉及表达、照料与日常互动。",
    TenGod.HURT_OFFICER: "命主子女宫伤官的传统象意涉及表达与规范之间的张力。",
    TenGod.POSITIVE_WEALTH: "命主子女宫正财的传统象意涉及资源安排与日常责任。",
    TenGod.PARTIAL_WEALTH: "命主子女宫偏财的传统象意涉及资源流动与对外交往。",
    TenGod.POSITIVE_OFFICER: "命主子女宫正官的传统象意涉及规范与责任。",
    TenGod.SEVEN_KILLER: "命主子女宫七杀的传统象意涉及约束与压力。",
    TenGod.POSITIVE_SEAL: "命主子女宫正印的传统象意涉及学习与支持。",
    TenGod.PARTIAL_SEAL: "命主子女宫偏印的传统象意涉及不同学习方式与个人空间。",
}


class ChildrenAnalysis:
    """子女分析工具类"""

    @staticmethod
    def analyze_children(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合子女分析。

        Args:
            pillars: 四柱
            gender: 性别（决定子女星：男命官杀、女命食伤）
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            子女分析结果字典
        """
        day_stem = pillars["day"][0]
        norm_gender = normalize_gender(gender)

        # 子女星：男命官杀，女命食伤；性别未知则两者并参
        if norm_gender == "male":
            child_gods: Tuple[TenGod, ...] = (
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
            )
            star_label = "官杀（男命子女星）"
        elif norm_gender == "female":
            child_gods = (TenGod.FOOD_GOD, TenGod.HURT_OFFICER)
            star_label = "食伤（女命子女星）"
        else:
            child_gods = (
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
                TenGod.FOOD_GOD,
                TenGod.HURT_OFFICER,
            )
            star_label = "官杀/食伤（性别未提供，兼看）"

        child_star = ChildrenAnalysis._locate_child_star(
            pillars, day_stem, child_gods, star_label
        )
        palace = ChildrenAnalysis._analyze_child_palace(pillars, day_stem)
        affinity = ChildrenAnalysis._analyze_affinity(child_star, palace)
        relationship = ChildrenAnalysis._analyze_relationship(pillars, day_stem)
        timing = ChildrenAnalysis._analyze_children_timing(
            pillars, day_stem, child_gods, dayun_pillar, liunian_pillar
        )

        return {
            "interpretation_scope": "命主视角的传统对应，不是孩子本人测算，不预测数量或生育结果，不推断孩子的性格、能力或成就。",
            "gender_basis": star_label,
            "child_star": child_star,
            "child_palace": palace,
            "affinity": affinity,
            "relationship": relationship,
            "children_timing": timing,
        }

    @staticmethod
    def _locate_child_star(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        child_gods: Tuple[TenGod, ...],
        star_label: str,
    ) -> Dict[str, Any]:
        """定位子女星及其力量。"""
        positions: List[Dict[str, Any]] = []
        weight = 0.0
        for e in iter_pillar_gods(pillars, day_stem):
            if e.ten_god not in child_gods:
                continue
            positions.append(
                {
                    "pillar": e.pillar,
                    "location": e.location,
                    "char": e.char,
                    "ten_god": e.ten_god.value,
                }
            )
            weight += e.weight

        weight = round(weight, 1)
        if weight == 0:
            status = (
                "命主盘内子女星不显，仅为十神分布分类，不推断现实亲子关系或生育结果"
            )
        elif weight >= 2.5:
            status = "命主盘内子女星权重较高，仅为十神分布分类"
        else:
            status = "命主盘内子女星权重适中，仅为十神分布分类"

        return {
            "star": star_label,
            "positions": positions,
            "weight": weight,
            "status": status,
        }

    @staticmethod
    def _analyze_child_palace(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """子女宫（时柱）状态。"""
        hour_stem, hour_branch = pillars["hour"]
        hour_god = get_ten_god(day_stem, hour_stem)

        # 时支与其他地支的冲合
        relations: List[str] = []
        for p_name, (_, branch) in pillars.items():
            if p_name == "hour":
                continue
            if check_branch_conflict(hour_branch, branch):
                relations.append(
                    f"时支{hour_branch}与{p_name}支{branch}相冲，仅记录命主盘内子女宫的相冲关系"
                )
            elif check_branch_combination(hour_branch, branch):
                relations.append(
                    f"时支{hour_branch}与{p_name}支{branch}相合，仅记录命主盘内子女宫的相合关系"
                )

        if not relations:
            relations.append("命主盘内子女宫（时柱）无明显冲合，不据此判断现实亲子关系")

        return {
            "hour_pillar": f"{hour_stem}{hour_branch}",
            "hour_ten_god": hour_god.value,
            "palace_relations": relations,
            "trait": HOUR_TEN_GOD_CHILDREN.get(hour_god, ""),
        }

    @staticmethod
    def _analyze_affinity(
        child_star: Dict[str, Any],
        palace: Dict[str, Any],
    ) -> Dict[str, Any]:
        """子女传统对应的规则分类（综合星与宫）。"""
        weight = child_star["weight"]
        palace_disturbed = any("相冲" in r for r in palace["palace_relations"])

        score = 60
        notes: List[str] = []
        if weight >= 2.5:
            score += 12
            notes.append("命主盘内子女星权重较高，计入传统规则分")
        elif weight == 0:
            score -= 12
            notes.append("子女星权重弱／不显，仅为命主盘内分类")
        if palace_disturbed:
            score -= 8
            notes.append("命主盘内子女宫存在相冲，计入传统规则分")
        else:
            score += 5
            notes.append("命主盘内子女宫未见相冲，计入传统规则分")

        score = max(30, min(92, score))
        if score >= 78:
            tendency = "子女传统对应规则分较高"
        elif score >= 60:
            tendency = "子女传统对应规则分居中"
        else:
            tendency = "子女传统对应规则分较低"

        return {
            "score": score,
            "tendency": tendency,
            "notes": notes,
        }

    @staticmethod
    def _analyze_relationship(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """命主时柱的传统象意；保留 achievement 字段供现有调用方读取。"""
        hour_stem = pillars["hour"][0]
        hour_god = get_ten_god(day_stem, hour_stem)
        trait = HOUR_TEN_GOD_CHILDREN.get(hour_god, "命主子女宫的传统象意本轮未覆盖。")

        achievement: List[str] = []
        if hour_god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
            achievement.append(
                "命主时柱官杀的传统象意涉及规范与责任，不推断孩子的社会成就"
            )
        elif hour_god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
            achievement.append(
                "命主时柱食伤的传统象意涉及表达与创造，不推断孩子的才能或适合的专业"
            )
        elif hour_god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
            achievement.append(
                "命主时柱印星的传统象意涉及学习与支持，不推断孩子的学业表现"
            )
        elif hour_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
            achievement.append(
                "命主时柱财星的传统象意涉及资源安排，不推断孩子的理财能力或未来赡养情况"
            )

        return {
            "hour_ten_god": hour_god.value,
            "trait": trait,
            "achievement": achievement,
        }

    @staticmethod
    def _analyze_children_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        child_gods: Tuple[TenGod, ...],
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """传统时间关系：引动子女星或子女宫，不生成生育建议。"""
        signals: List[str] = []
        hour_branch = pillars["hour"][1]

        def _assess(label: str, pillar: Tuple[str, str]) -> None:
            stem, branch = pillar
            god = get_ten_god(day_stem, stem)
            if god in child_gods:
                signals.append(f"{label}{stem}{branch}引动子女星，仅为传统对应关系变化")
            if check_branch_combination(branch, hour_branch):
                signals.append(
                    f"{label}支{branch}合子女宫{hour_branch}，子女宫得动，仅为传统对应关系变化"
                )
            elif check_branch_conflict(branch, hour_branch):
                signals.append(
                    f"{label}支{branch}冲子女宫{hour_branch}，仅记录相冲关系，不推断生育或孩子的现实状态"
                )

        if dayun_pillar:
            _assess("大运", dayun_pillar)
        if liunian_pillar:
            _assess("流年", liunian_pillar)

        if not signals:
            signals.append("本轮未取得子女星／宫的时间关系，不据此判断生育时机")

        return {"timing_signals": signals}
