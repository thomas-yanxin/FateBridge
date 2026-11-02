"""
六亲关系分析模块

基于八字命理的六亲分析（聚焦父母与兄弟姐妹，配偶见婚姻模块、子女见子女模块），
综合以下经典技法：
- 子平六亲法：父为偏财、母为正印、兄弟姐妹为比劫
- 宫位法：年柱主祖上/父母，月柱主父母/兄弟
- 星宫同参：保留星的计数与宫位冲合，不从中断定亲疏、人数及现实助力

核心分析维度：
1. 父母星（偏财/正印）定位、强弱与缘分助力
2. 兄弟姐妹星（比劫）多寡与助益/竞争
3. 六亲宫位（年/月柱）状态
4. 与六亲关系（生克冲合）
5. 贵人助力提示
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..utils.data import (
    TenGod,
    check_branch_combination,
    check_branch_conflict,
    sum_ten_god_weight,
)


class RelativesAnalysis:
    """六亲关系分析工具类"""

    @staticmethod
    def analyze_relatives(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]

        parents = RelativesAnalysis._analyze_parents(pillars, day_stem)
        siblings = RelativesAnalysis._analyze_siblings(pillars, day_stem)
        palaces = RelativesAnalysis._analyze_palaces(pillars)
        nobles = RelativesAnalysis._analyze_support(pillars, day_stem)

        return {
            "counting_basis": "非日干每次1，全部柱支每个藏干每次0.5；日干不计，日支藏干计入；是出现量，不是旺衰。",
            "parents": parents,
            "siblings": siblings,
            "palaces": palaces,
            "support": nobles,
        }

    @staticmethod
    def _star_weight(
        pillars: Dict[str, Tuple[str, str]], day_stem: str, gods: Tuple[TenGod, ...]
    ) -> float:
        return sum_ten_god_weight(pillars, day_stem, gods)

    @staticmethod
    def _analyze_parents(
        pillars: Dict[str, Tuple[str, str]], day_stem: str
    ) -> Dict[str, Any]:
        father = RelativesAnalysis._star_weight(
            pillars, day_stem, (TenGod.PARTIAL_WEALTH,)
        )
        mother = RelativesAnalysis._star_weight(
            pillars, day_stem, (TenGod.POSITIVE_SEAL,)
        )

        notes: List[str] = []
        notes.append(f"按父星取偏财的传统对应，加权计数为{father:g}")
        notes.append(f"按母星取正印的传统对应，加权计数为{mother:g}")
        notes.append("计数不测量父母实际状况、亲疏或助力；未见对应星也不表示亲人缺席")
        return {
            "father_star_weight": father,
            "mother_star_weight": mother,
            "notes": notes,
        }

    @staticmethod
    def _analyze_siblings(
        pillars: Dict[str, Tuple[str, str]], day_stem: str
    ) -> Dict[str, Any]:
        weight = RelativesAnalysis._star_weight(
            pillars, day_stem, (TenGod.COMPARE, TenGod.ROB_WEALTH)
        )
        notes = [
            f"比肩、劫财加权计数为{weight:g}，传统类比为同辈；不能换算兄弟姐妹人数、关系或合作结果"
        ]
        return {"sibling_star_weight": weight, "notes": notes}

    @staticmethod
    def _analyze_palaces(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        year_branch = pillars["year"][1]
        month_branch = pillars["month"][1]
        relations: List[str] = []

        # 年柱（祖上/父母宫）、月柱（父母/兄弟宫）与日支冲合
        day_branch = pillars["day"][1]
        if check_branch_conflict(year_branch, day_branch):
            relations.append(
                f"年支{year_branch}与日支{day_branch}六冲；保留宫位关系，不据此断离乡或亲疏"
            )
        if check_branch_combination(year_branch, day_branch):
            relations.append(
                f"年支{year_branch}与日支{day_branch}六合；未裁定合化或现实关系"
            )
        if check_branch_conflict(month_branch, day_branch):
            relations.append(
                f"月支{month_branch}与日支{day_branch}六冲；保留宫位关系，不据此断摩擦或聚散"
            )
        if check_branch_combination(month_branch, day_branch):
            relations.append(
                f"月支{month_branch}与日支{day_branch}六合；未裁定合化或现实关系"
            )
        if not relations:
            relations.append(
                "年支、月支分别与日支未命中本模块六合、六冲规则；不代表现实关系平稳"
            )
        return {
            "year_pillar": "".join(pillars["year"]),
            "month_pillar": "".join(pillars["month"]),
            "relations": relations,
        }

    @staticmethod
    def _analyze_support(
        pillars: Dict[str, Tuple[str, str]], day_stem: str
    ) -> Dict[str, Any]:
        seal = RelativesAnalysis._star_weight(
            pillars, day_stem, (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL)
        )
        peer = RelativesAnalysis._star_weight(
            pillars, day_stem, (TenGod.COMPARE, TenGod.ROB_WEALTH)
        )
        notes = [
            f"印星加权计数{seal:g}、比劫加权计数{peer:g}；传统对应长辈支持与同辈互动",
            "是否获得现实支持，需要核实关系、资源与具体承诺；本计数不裁定喜忌和助力大小",
        ]
        return {"seal_weight": seal, "peer_weight": peer, "notes": notes}
