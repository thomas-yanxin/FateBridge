"""
学业分析模块

基于八字命理的学业分析功能，综合以下经典技法：
- 十神看学历：印星主学习力与文凭，官印相生主高学历（参《如何从八字十神看学历高低》）
- 食伤看才华：食伤主聪明才艺、表达创造，与印配合定学术/技艺方向
- 文昌贵人：日干引文昌，主聪慧、利读书考试
- 破格提示：财破印、伤官见官（无制）主学业波折

核心分析维度：
1. 印星与食伤（学习力与才华）评估
2. 学历层次倾向（官印相生 / 食伤配印 / 破印等）
3. 文昌等利学神煞
4. 适合学科方向（文理倾向）
5. 考试/升学时机（大运流年引动印星、官星、文昌）

说明：学历高低受现实条件影响，命理仅供潜质与时机参考。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.rules import BaZiRules
from ..utils.data import (
    Element,
    TenGod,
    get_ten_god,
    sum_ten_god_weight,
)

# 文昌贵人：以日干（或年干）查地支
WENCHANG_TABLE = {
    "甲": "巳",
    "乙": "午",
    "丙": "申",
    "丁": "酉",
    "戊": "申",
    "己": "酉",
    "庚": "亥",
    "辛": "子",
    "壬": "寅",
    "癸": "卯",
}

# 五行/十神 → 学科方向
SEAL_SUBJECT = {
    Element.WOOD: "文科、教育、文学、中医、林业生物",
    Element.FIRE: "理工、电子信息、能源、传媒、艺术",
    Element.EARTH: "管理、土木建筑、地理、农业、哲学宗教",
    Element.METAL: "金融、法律、机械、军警、精密工科",
    Element.WATER: "贸易、外语、传播、水利、流通服务",
}


class EducationAnalysis:
    """学业分析工具类"""

    @staticmethod
    def analyze_education(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合学业分析。

        Args:
            pillars: 四柱
            gender: 性别（保留以统一接口）
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            学业分析结果字典
        """
        day_stem = pillars["day"][0]

        gods = EducationAnalysis._count_study_gods(pillars, day_stem)
        level = EducationAnalysis._analyze_education_level(pillars, day_stem, gods)
        wenchang = EducationAnalysis._analyze_wenchang(pillars, day_stem)
        subjects = EducationAnalysis._analyze_subjects(pillars, day_stem, gods)
        timing = EducationAnalysis._analyze_exam_timing(
            day_stem, dayun_pillar, liunian_pillar
        )
        suggestions = EducationAnalysis._generate_suggestions(level, subjects, gods)

        return {
            "study_stars": gods,
            "education_level": level,
            "wenchang": wenchang,
            "subject_orientation": subjects,
            "exam_timing": timing,
            "suggestions": suggestions,
        }

    @staticmethod
    def _count_study_gods(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """统计印星、食伤、官星、财星力量（学业关键十神）。"""
        # 四组十神互不相交，逐组求和与原 elif 单遍累加结果一致。
        return {
            "seal_weight": sum_ten_god_weight(
                pillars, day_stem, (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL)
            ),
            "food_hurt_weight": sum_ten_god_weight(
                pillars, day_stem, (TenGod.FOOD_GOD, TenGod.HURT_OFFICER)
            ),
            "officer_weight": sum_ten_god_weight(
                pillars, day_stem, (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER)
            ),
            "wealth_weight": sum_ten_god_weight(
                pillars, day_stem, (TenGod.POSITIVE_WEALTH, TenGod.PARTIAL_WEALTH)
            ),
        }

    @staticmethod
    def _analyze_education_level(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        gods: Dict[str, Any],
    ) -> Dict[str, Any]:
        """学历层次倾向。"""
        seal = gods["seal_weight"]
        food_hurt = gods["food_hurt_weight"]
        officer = gods["officer_weight"]
        wealth = gods["wealth_weight"]

        score = 58
        notes: List[str] = []

        # 官印相生：高学历经典格
        if officer >= 1.0 and seal >= 1.0:
            score += 18
            notes.append("官印相生，学历层次高，利于体制内、学术与功名")
        # 食伤配印：才学兼备
        if food_hurt >= 1.0 and seal >= 1.0:
            score += 10
            notes.append("食伤配印，聪明又有定力，才学兼备，宜深造")
        # 印为用而有力
        if seal >= 2.0:
            score += 8
            notes.append("印星有力，学习能力强、记忆专注佳，读书运好")
        elif seal == 0:
            score -= 8
            notes.append("命局无印，学历靠后天努力，或以技艺、实务见长")

        # 破格：财破印
        if wealth >= 2.0 and 0 < seal <= 1.0:
            score -= 12
            notes.append("财旺破印，求学易受外务/经济牵扯而中断，宜专心、忌过早逐利")

        # 破格：伤官见官无制
        has_hurt = False
        has_officer_zheng = False
        for p_name, (stem, branch) in pillars.items():
            if p_name == "day":
                continue
            if get_ten_god(day_stem, stem) == TenGod.HURT_OFFICER:
                has_hurt = True
            if get_ten_god(day_stem, stem) == TenGod.POSITIVE_OFFICER:
                has_officer_zheng = True
        if has_hurt and has_officer_zheng and seal < 1.0:
            score -= 8
            notes.append("伤官见官而印不制，学途易有波折、与师长制度生摩擦")

        score = max(30, min(95, score))
        if score >= 82:
            tier = "高学历潜质（本科以上/研究型）"
        elif score >= 68:
            tier = "学历良好（本科可期）"
        elif score >= 55:
            tier = "学历中等（务实进取可提升）"
        else:
            tier = "应试学历偏弱，宜走技能/实务路线"

        return {
            "score": score,
            "tier": tier,
            "notes": notes,
        }

    @staticmethod
    def _analyze_wenchang(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """文昌贵人。"""
        target = WENCHANG_TABLE.get(day_stem)
        hits = [p_name for p_name, (_, branch) in pillars.items() if branch == target]
        if hits:
            note = f"命带文昌贵人（{target}），聪慧好学、利读书考试与文书"
        else:
            note = f"命无文昌（日干{day_stem}文昌在{target}），逢{target}之大运流年学运增强"
        return {
            "wenchang_branch": target,
            "hit_pillars": hits,
            "has_wenchang": bool(hits),
            "note": note,
        }

    @staticmethod
    def _analyze_subjects(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        gods: Dict[str, Any],
    ) -> Dict[str, Any]:
        """适合学科方向（文理倾向）。"""
        # 文理倾向：印旺偏文/学术，食伤偏才艺/技术，官杀偏管理/法政
        seal = gods["seal_weight"]
        food_hurt = gods["food_hurt_weight"]
        officer = gods["officer_weight"]

        if seal > food_hurt and seal >= officer:
            inclination = "偏文科/学术理论型（印主），擅长记忆、研究、系统知识"
        elif food_hurt > seal:
            inclination = "偏才艺/技术应用型（食伤主），擅长创造、动手、表达"
        elif officer >= seal:
            inclination = "偏管理/法政规则型（官杀主），擅长纪律、组织、规范"
        else:
            inclination = "文理较均衡，可依兴趣选择"

        # 以喜用神五行给学科方向
        profile = BaZiRules.chart_useful_profile(pillars)
        favorable = [Element(value) for value in profile["useful_elements"]]
        fields: List[str] = []
        for elem in favorable:
            subject = SEAL_SUBJECT.get(elem)
            if subject:
                fields.append(f"{elem.value}：{subject}")

        return {
            "inclination": inclination,
            "favorable_fields": fields,
            "conditional_elements": profile["conditional_elements"],
            "reference_scope": profile["resolution_policy"],
        }

    @staticmethod
    def _analyze_exam_timing(
        day_stem: str,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """考试/升学时机：印星、官星、文昌引动。"""
        signals: List[str] = []
        wenchang = WENCHANG_TABLE.get(day_stem)

        def _assess(label: str, pillar: Tuple[str, str]) -> None:
            stem, branch = pillar
            god = get_ten_god(day_stem, stem)
            if god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
                signals.append(
                    f"{label}{stem}{branch}见印星，学习运、文书运佳，利考试升学"
                )
            elif god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
                signals.append(
                    f"{label}{stem}{branch}见官星，功名考运动，利考公、考编、竞争性考试"
                )
            elif god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
                signals.append(
                    f"{label}{stem}{branch}见食伤，思维活跃、表达灵感佳，利创作型考核"
                )
            if branch == wenchang:
                signals.append(f"{label}逢文昌{wenchang}，读书考试如有神助")

        if dayun_pillar:
            _assess("大运", dayun_pillar)
        if liunian_pillar:
            _assess("流年", liunian_pillar)

        if not signals:
            signals.append("未提供大运/流年，无法判断考试升学时机")

        return {"timing_signals": signals}

    @staticmethod
    def _generate_suggestions(
        level: Dict[str, Any],
        subjects: Dict[str, Any],
        gods: Dict[str, Any],
    ) -> List[str]:
        """生成学业建议。"""
        suggestions: List[str] = []
        suggestions.append(f"学历倾向：{level['tier']}")
        suggestions.append(f"学科方向：{subjects['inclination']}")
        if gods["seal_weight"] == 0:
            suggestions.append(
                "命局缺印，宜培养专注与持续学习习惯，或走技能证照路线扬长避短"
            )
        if gods["wealth_weight"] >= 2.0 and gods["seal_weight"] <= 1.0:
            suggestions.append(
                "求学阶段宜专注学业、节制逐利与外务，以免财旺破印影响学运"
            )
        return suggestions
