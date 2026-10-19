"""
子女分析模块

基于八字命理的子女分析功能，综合以下经典技法：
- 子女星：男命以官杀为子女，女命以食伤为子女（子平传统六亲法）
- 子女宫：时柱为子女宫，看命主的子女传统对应
- 盲派六亲法：时柱十神与吉凶定子女关系与成就
- 神煞辅助：时柱逢生扶/冲克影响子女缘

核心分析维度：
1. 子女星定位（按性别取官杀/食伤）与强弱
2. 子女宫（时柱）状态分析
3. 子女传统对应的规则分类
4. 与子女关系及子女成就倾向
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

# 时柱十神对应子女特征与关系
HOUR_TEN_GOD_CHILDREN = {
    TenGod.COMPARE: "子女独立自主、个性强，与己如友",
    TenGod.ROB_WEALTH: "子女好动竞争、花费较大，关系需多沟通",
    TenGod.FOOD_GOD: "子女聪慧有才华、温和孝顺，晚年得享天伦",
    TenGod.HURT_OFFICER: "子女聪明叛逆、才气外露，宜因势利导",
    TenGod.POSITIVE_WEALTH: "子女务实顾家、能理财，关系稳定",
    TenGod.PARTIAL_WEALTH: "子女活络善交际、闯荡能力强",
    TenGod.POSITIVE_OFFICER: "子女端正有出息、守规矩，易有官贵之子",
    TenGod.SEVEN_KILLER: "子女刚强有魄力、能成大事，幼时管教较费心",
    TenGod.POSITIVE_SEAL: "子女好学有文化、孝顺顾家，重感情",
    TenGod.PARTIAL_SEAL: "子女思维独特、有专才，性格偏内向",
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
            "interpretation_scope": "命主视角的传统对应，不是孩子本人测算，不预测数量或生育结果。",
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
            status = "子女星不显，子女缘分宜待大运流年引动，或缘分较淡需顺其自然"
        elif weight >= 2.5:
            status = "子女星旺，子女缘分较厚，但星过旺亦主操心多、关系密"
        else:
            status = "子女星适中，子女缘分平稳"

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
                    f"时支{hour_branch}与{p_name}支{branch}相冲，子女宫受动，主子女缘聚少离多或操心"
                )
            elif check_branch_combination(hour_branch, branch):
                relations.append(
                    f"时支{hour_branch}与{p_name}支{branch}相合，子女宫得助，亲子关系融洽"
                )

        if not relations:
            relations.append("子女宫（时柱）无明显冲合，状态平稳")

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
            notes.append("子女星旺，得子女缘较厚")
        elif weight == 0:
            score -= 12
            notes.append("子女星权重弱／不显，仅为命主盘内分类")
        if palace_disturbed:
            score -= 8
            notes.append("子女宫受冲，与子女或聚少离多")
        else:
            score += 5
            notes.append("子女宫安稳，亲子关系较顺")

        score = max(30, min(92, score))
        if score >= 78:
            tendency = "子女传统对应规则分较高"
        elif score >= 60:
            tendency = "子女缘平稳"
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
        """与子女关系及子女成就倾向（以时柱十神为主）。"""
        hour_stem = pillars["hour"][0]
        hour_god = get_ten_god(day_stem, hour_stem)
        trait = HOUR_TEN_GOD_CHILDREN.get(hour_god, "子女特征需综合全局判断")

        achievement: List[str] = []
        if hour_god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
            achievement.append("时柱官杀，子女多有上进心、社会成就可期")
        elif hour_god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
            achievement.append("时柱食伤，子女才华出众，宜文艺、技术、表达类发展")
        elif hour_god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
            achievement.append("时柱印星，子女好学顾家，学业文化有成")
        elif hour_god in (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH):
            achievement.append("时柱财星，子女务实善理财，晚年得子女财力之助")

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
