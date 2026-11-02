"""
正缘桃花分析模块

区别于「婚姻」模块（侧重配偶宫/配偶星/婚姻质量），本模块侧重感情、异性缘与桃花，
综合以下经典技法：
- 桃花（咸池）神煞：申子辰见酉、寅午戌见卯、亥卯未见子、巳酉丑见午
- 红鸾、天喜：主婚恋喜庆
- 异性缘星：男命以财为异性缘，女命以官杀为异性缘
- 桃花关系：分别记录六合、六冲；不据此评价他人的品行或认定正缘身份

核心分析维度：
1. 桃花（咸池）定位与多寡
2. 红鸾天喜
3. 异性缘星（按性别）强弱
4. 桃花正邪（合/刑冲）
5. 正缘出现时机（大运流年引动桃花/异性缘星）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..utils.data import (
    TenGod,
    check_branch_combination,
    check_branch_conflict,
    get_ten_god,
    normalize_gender,
    sum_ten_god_weight,
)

# 桃花（咸池）：三合局 -> 桃花地支
_PEACH_TARGETS = (
    (("申", "子", "辰"), "酉"),
    (("寅", "午", "戌"), "卯"),
    (("亥", "卯", "未"), "子"),
    (("巳", "酉", "丑"), "午"),
)

# 红鸾（年支 -> 红鸾地支）
_HONGLUAN = {
    "子": "卯",
    "丑": "寅",
    "寅": "丑",
    "卯": "子",
    "辰": "亥",
    "巳": "戌",
    "午": "酉",
    "未": "申",
    "申": "未",
    "酉": "午",
    "戌": "巳",
    "亥": "辰",
}
# 天喜（年支 -> 天喜地支，红鸾对宫）
_TIANXI = {
    "子": "酉",
    "丑": "申",
    "寅": "未",
    "卯": "午",
    "辰": "巳",
    "巳": "辰",
    "午": "卯",
    "未": "寅",
    "申": "丑",
    "酉": "子",
    "戌": "亥",
    "亥": "戌",
}


class RomanceAnalysis:
    """正缘桃花分析工具类"""

    @staticmethod
    def analyze_romance(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]
        norm_gender = normalize_gender(gender)
        branches = {name: branch for name, (_, branch) in pillars.items()}

        peach = RomanceAnalysis._peach_blossom(pillars, branches)
        luan_xi = RomanceAnalysis._hongluan_tianxi(pillars, branches)
        opposite = RomanceAnalysis._opposite_sex_star(pillars, day_stem, norm_gender)
        quality = RomanceAnalysis._peach_quality(peach, pillars)
        timing = RomanceAnalysis._romance_timing(
            pillars, day_stem, norm_gender, peach, dayun_pillar, liunian_pillar
        )

        return {
            "counting_basis": "非日干每次1，全部柱支每个藏干每次0.5；日干不计，日支藏干计入；是出现量，不是旺衰。",
            "gender_basis": opposite["basis"],
            "peach_blossom": peach,
            "hongluan_tianxi": luan_xi,
            "opposite_sex_star": opposite,
            "peach_quality": quality,
            "romance_timing": timing,
        }

    @staticmethod
    def _peach_targets(branches: Dict[str, str]) -> set:
        triggers = {branches.get("year"), branches.get("day")}
        targets = set()
        for group, target in _PEACH_TARGETS:
            if triggers & set(group):
                targets.add(target)
        return targets

    @staticmethod
    def _peach_blossom(
        pillars: Dict[str, Tuple[str, str]], branches: Dict[str, str]
    ) -> Dict[str, Any]:
        targets = RomanceAnalysis._peach_targets(branches)
        hits = [name for name, b in branches.items() if b in targets]
        if hits:
            note = (
                "按年支、日支查咸池，命中柱位："
                + "、".join(hits)
                + "；命中数不等于追求者人数或魅力"
            )
        else:
            note = "按年支、日支查咸池，本次四柱未命中；不能推断现实感情状态"
        return {
            "peach_branches": sorted(targets),
            "hit_pillars": hits,
            "count": len(hits),
            "note": note,
        }

    @staticmethod
    def _hongluan_tianxi(
        pillars: Dict[str, Tuple[str, str]], branches: Dict[str, str]
    ) -> Dict[str, Any]:
        year_branch = branches.get("year", "")
        hongluan = _HONGLUAN.get(year_branch)
        tianxi = _TIANXI.get(year_branch)
        luan_hits = [n for n, b in branches.items() if b == hongluan]
        xi_hits = [n for n, b in branches.items() if b == tianxi]
        notes: List[str] = []
        if luan_hits:
            notes.append(
                f"以年支{year_branch}查红鸾{hongluan}，命中：{'、'.join(luan_hits)}"
            )
        if xi_hits:
            notes.append(
                f"以年支{year_branch}查天喜{tianxi}，命中：{'、'.join(xi_hits)}"
            )
        if not notes:
            notes.append(
                f"本次四柱未命中红鸾{hongluan}、天喜{tianxi}；目标支不等于实际命中"
            )
        return {
            "hongluan_branch": hongluan,
            "tianxi_branch": tianxi,
            "hongluan_hits": luan_hits,
            "tianxi_hits": xi_hits,
            "notes": notes,
        }

    @staticmethod
    def _opposite_sex_star(
        pillars: Dict[str, Tuple[str, str]], day_stem: str, norm_gender: Optional[str]
    ) -> Dict[str, Any]:
        if norm_gender == "male":
            gods: Tuple[TenGod, ...] = (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH)
            basis = "财星（男命异性缘）"
        elif norm_gender == "female":
            gods = (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER)
            basis = "官杀（女命异性缘）"
        else:
            gods = (
                TenGod.POSITIVE_WEALTH,
                TenGod.PARTIAL_WEALTH,
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
            )
            basis = "财/官杀（性别未提供，兼看）"

        weight = sum_ten_god_weight(pillars, day_stem, gods)
        if weight == 0:
            status = "所选传统对应星加权计数为0；不能据此判断关系早晚或主动性"
        elif weight >= 2.5:
            status = "所选传统对应星加权计数至少2.5；不代表旺度、追求者人数或关系质量"
        else:
            status = "所选传统对应星加权计数在0至2.5之间；不判断现实关系状态"
        return {"basis": basis, "weight": weight, "status": status}

    @staticmethod
    def _peach_quality(
        peach: Dict[str, Any], pillars: Dict[str, Tuple[str, str]]
    ) -> Dict[str, Any]:
        notes: List[str] = []
        relations: List[Dict[str, str]] = []
        for name in peach["hit_pillars"]:
            pb = dict(pillars)[name][1] if name in pillars else None
            if pb is None:
                continue
            for other_name, (_, other_branch) in pillars.items():
                if other_name == name:
                    continue
                for kind, check in (
                    ("六冲", check_branch_conflict),
                    ("六合", check_branch_combination),
                ):
                    if check(pb, other_branch):
                        relations.append(
                            {
                                "peach_pillar": name,
                                "peach_branch": pb,
                                "other_pillar": other_name,
                                "other_branch": other_branch,
                                "relation": kind,
                            }
                        )
                        notes.append(
                            f"{name}咸池{pb}与{other_name}支{other_branch}{kind}；不据此认定关系成败或他人品行"
                        )
        if not peach["hit_pillars"]:
            notes.append("本次四柱未命中咸池，未执行咸池合冲关系检查")
        elif not notes:
            notes.append(
                "已命中的咸池与其他柱支未见六合、六冲；本模块未检查刑害破，不判断现实感情"
            )
        return {
            "notes": notes,
            "relations": relations,
            "assessment_status": "structural_relations_only",
        }

    @staticmethod
    def _romance_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        norm_gender: Optional[str],
        peach: Dict[str, Any],
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        signals: List[str] = []
        year_branch = pillars["year"][1]
        peach_targets = set(peach["peach_branches"])
        hongluan = _HONGLUAN.get(year_branch)
        tianxi = _TIANXI.get(year_branch)

        if norm_gender == "male":
            star_gods: Tuple[TenGod, ...] = (
                TenGod.POSITIVE_WEALTH,
                TenGod.PARTIAL_WEALTH,
            )
        elif norm_gender == "female":
            star_gods = (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER)
        else:
            star_gods = (
                TenGod.POSITIVE_WEALTH,
                TenGod.PARTIAL_WEALTH,
                TenGod.POSITIVE_OFFICER,
                TenGod.SEVEN_KILLER,
            )

        def _assess(label: str, pillar: Tuple[str, str]) -> None:
            stem, branch = pillar
            if get_ten_god(day_stem, stem) in star_gods:
                signals.append(
                    f"{label}{stem}{branch}天干对应{get_ten_god(day_stem, stem).value}，命中所选传统关系星"
                )
            if branch in peach_targets:
                signals.append(f"{label}地支{branch}命中咸池目标；不推断恋爱事件")
            if branch == hongluan:
                signals.append(f"{label}地支{branch}命中红鸾目标")
            elif branch == tianxi:
                signals.append(f"{label}地支{branch}命中天喜目标")

        if dayun_pillar:
            _assess("大运", dayun_pillar)
        if liunian_pillar:
            _assess("流年", liunian_pillar)
        provided = bool(dayun_pillar or liunian_pillar)
        return {
            "timing_signals": signals,
            "assessment_status": (
                "matched"
                if signals
                else "no_matching_rule" if provided else "missing_timing_input"
            ),
        }
