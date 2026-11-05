"""
学业分析模块

输出十神加权计数、文昌命中及时间柱对应关系。兼容分数是未校准的固定
规则索引，不测量智力、学历、学科能力或录取概率。结构成败另由证据链审查。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.bazi_star_tables import WEN_CHANG_TARGETS

from ..core.rules import BaZiRules
from ..utils.data import (
    Element,
    TenGod,
    count_ten_gods,
    get_ten_god,
)

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
            "counting_basis": "非日干每次1，全部柱支每个藏干每次0.5；日干不计，日支藏干计入；是出现量，不是旺衰。",
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
        """统计可见干与藏干的固定加权出现量，不计算力量。"""
        counts = count_ten_gods(pillars, day_stem)
        return {
            "seal_weight": (counts[TenGod.POSITIVE_SEAL] + counts[TenGod.PARTIAL_SEAL])
            or 0,
            "food_hurt_weight": (counts[TenGod.FOOD_GOD] + counts[TenGod.HURT_OFFICER])
            or 0,
            "officer_weight": (
                counts[TenGod.POSITIVE_OFFICER] + counts[TenGod.SEVEN_KILLER]
            )
            or 0,
            "wealth_weight": (
                counts[TenGod.POSITIVE_WEALTH] + counts[TenGod.PARTIAL_WEALTH]
            )
            or 0,
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
            notes.append("官杀与印的加权计数均至少1；仅为同现，尚未裁定官印相生或成格")
        # 食伤配印：才学兼备
        if food_hurt >= 1.0 and seal >= 1.0:
            score += 10
            notes.append("食伤与印的加权计数均至少1；尚未核定配印所需位置、旺衰及制化")
        # 印为用而有力
        if seal >= 2.0:
            score += 8
            notes.append("印星加权计数至少2；出现量不等于旺度或学习能力")
        elif seal == 0:
            score -= 8
            notes.append("本次四柱计数未见印星；不能据此判断学历或学习能力")

        # 破格：财破印
        if wealth >= 2.0 and 0 < seal <= 1.0:
            score -= 12
            notes.append("财计数至少2且印计数在0至1之间；不足以认定财破印或求学中断")

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
            notes.append("非日干同时见伤官、正官且印计数低于1；未裁定作用路径及救应")

        score = max(30, min(95, score))
        if score >= 82:
            tier = "规则索引82–95"
        elif score >= 68:
            tier = "规则索引68–81"
        elif score >= 55:
            tier = "规则索引55–67"
        else:
            tier = "规则索引30–54"

        return {
            "score": score,
            "score_kind": "uncalibrated_rule_index",
            "assessment_status": "counts_only_not_education_prediction",
            "score_basis": "基础58；官印同现+18、食伤印同现+10、印计数至少2加8、无印减8、财印计数条件减12、伤官正官同透且印低于1减8；截断至30–95。非概率。",
            "tier": tier,
            "notes": notes,
        }

    @staticmethod
    def _analyze_wenchang(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """文昌贵人。"""
        target = WEN_CHANG_TARGETS.get(day_stem)
        hits = [p_name for p_name, (_, branch) in pillars.items() if branch == target]
        if hits:
            note = f"按日干{day_stem}查文昌{target}，命中柱位：{'、'.join(hits)}；这是神煞查表结果"
        else:
            note = f"日干{day_stem}的文昌目标为{target}，本次四柱未命中；不代表学习或考试不利"
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

        weights = {"印": seal, "食伤": food_hurt, "官杀": officer}
        leading = [
            name for name, weight in weights.items() if weight == max(weights.values())
        ]
        analogies = {"印": "知识整理", "食伤": "表达与制作", "官杀": "组织与规则"}
        inclination = (
            "、".join(leading) + "计数并列最高"
            if len(leading) > 1
            else leading[0] + "计数最高"
        )
        inclination += (
            "；现代主题类比："
            + "、".join(analogies[name] for name in leading)
            + "，需用兴趣和实际成绩验证"
        )

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
            "assessment_status": "modern_analogy_not_aptitude_measurement",
        }

    @staticmethod
    def _analyze_exam_timing(
        day_stem: str,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """考试/升学时机：印星、官星、文昌引动。"""
        signals: List[str] = []
        wenchang = WEN_CHANG_TARGETS.get(day_stem)

        def _assess(label: str, pillar: Tuple[str, str]) -> None:
            stem, branch = pillar
            god = get_ten_god(day_stem, stem)
            if god in (TenGod.POSITIVE_SEAL, TenGod.PARTIAL_SEAL):
                signals.append(
                    f"{label}{stem}{branch}的天干对应{god.value}；传统主题为学习、文书"
                )
            elif god in (TenGod.POSITIVE_OFFICER, TenGod.SEVEN_KILLER):
                signals.append(
                    f"{label}{stem}{branch}的天干对应{god.value}；传统主题为规范、资格"
                )
            elif god in (TenGod.FOOD_GOD, TenGod.HURT_OFFICER):
                signals.append(
                    f"{label}{stem}{branch}的天干对应{god.value}；传统主题为表达、输出"
                )
            if branch == wenchang:
                signals.append(
                    f"{label}地支{branch}命中文昌目标{wenchang}；不据此推断考试结果"
                )

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

    @staticmethod
    def _generate_suggestions(
        level: Dict[str, Any],
        subjects: Dict[str, Any],
        gods: Dict[str, Any],
    ) -> List[str]:
        """生成学业建议。"""
        return [
            "现实规划：用实际成绩、兴趣、课程要求和可支配时间选择学习路径",
            "备考安排：记录练习正确率、错题类型及复习进度，再据此调整计划",
            f"可讨论的文化类比：{subjects['inclination']}",
        ]
