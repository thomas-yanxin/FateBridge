"""
性格心性分析模块

基于八字命理的性格分析，综合以下经典技法：
- 日主五行定基本心性（木仁、火礼、土信、金义、水智）
- 十神定性格倾向（主导十神决定行为风格）
- 日主强弱与阴阳定刚柔、内外向
- 格局清浊定心性层次

核心分析维度：
1. 日主五行基本心性
2. 主导十神性格特征
3. 强弱阴阳（刚柔/内外向）
4. 性格优势与短板
5. 调适建议
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..utils.data import (
    STEM_ELEMENTS,
    Element,
    Polarity,
    TenGod,
    count_ten_gods,
)

ELEMENT_NATURE = {
    Element.WOOD: {
        "virtue": "仁",
        "traits": "仁慈、有恻隐之心、积极进取、有规划力",
        "short": "过则优柔、固执、好面子",
    },
    Element.FIRE: {
        "virtue": "礼",
        "traits": "热情、礼貌、有表现力、直爽光明",
        "short": "过则急躁、虚荣、缺乏耐性",
    },
    Element.EARTH: {
        "virtue": "信",
        "traits": "诚信、稳重、包容、务实可靠",
        "short": "过则固执、保守、行动迟缓",
    },
    Element.METAL: {
        "virtue": "义",
        "traits": "重义气、果断、有原则、执行力强",
        "short": "过则刚硬、肃杀、不近人情",
    },
    Element.WATER: {
        "virtue": "智",
        "traits": "聪明、灵活、应变力强、有谋略",
        "short": "过则多虑、善变、城府深",
    },
}

TEN_GOD_PERSONALITY = {
    TenGod.COMPARE: "自主独立、重朋友、竞争心强、不喜依赖",
    TenGod.ROB_WEALTH: "行动力强、敢闯敢拼、好胜、理财较冲动",
    TenGod.FOOD_GOD: "温和乐天、有口福才艺、随和包容、享受生活",
    TenGod.HURT_OFFICER: "聪明才高、表现欲强、不拘常规、易恃才傲物",
    TenGod.POSITIVE_WEALTH: "务实节俭、重责任、踏实顾家、计划性强",
    TenGod.PARTIAL_WEALTH: "慷慨豪爽、善交际、机会主义、风流多情",
    TenGod.POSITIVE_OFFICER: "正派守规、有责任感、自律、重名誉",
    TenGod.SEVEN_KILLER: "果敢有魄力、抗压、霸气、易冲动偏激",
    TenGod.POSITIVE_SEAL: "仁厚好学、重感情、有依赖性、慈悲",
    TenGod.PARTIAL_SEAL: "思维独特、敏感内省、有专才、孤僻多疑",
}


class PersonalityAnalysis:
    """性格心性分析工具类"""

    @staticmethod
    def analyze_personality(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0]
        day_polarity = STEM_ELEMENTS[day_stem][1]

        core_nature = PersonalityAnalysis._core_nature(day_element)
        dominant = PersonalityAnalysis._dominant_traits(pillars, day_stem)
        disposition = PersonalityAnalysis._disposition(pillars, day_polarity)
        strengths, weaknesses = PersonalityAnalysis._strengths_weaknesses(
            core_nature, dominant, disposition
        )
        advice = PersonalityAnalysis._advice(dominant, disposition)

        return {
            "interpretation_scope": "五行、十神的传统象义与现代自省类比，不是人格测量；日主旺衰不测量内外向、决断力或心理健康。",
            "counting_basis": "非日干每次1，每个藏干每次0.5；同分并列，计数不测量性格。",
            "day_master": f"{day_stem}（{day_element.value}）",
            "core_nature": core_nature,
            "dominant_traits": dominant,
            "disposition": disposition,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "advice": advice,
        }

    @staticmethod
    def _core_nature(day_element: Element) -> Dict[str, Any]:
        info = ELEMENT_NATURE[day_element]
        return {
            "element": day_element.value,
            "virtue": info["virtue"],
            "traits": "传统五行象义：" + info["traits"],
            "shortcoming": "传统过度之象的自省类比：" + info["short"],
            "reference_scope": "本项目文化类比词典，未逐条认证某部原典或现实人格特质。",
        }

    @staticmethod
    def _dominant_traits(
        pillars: Dict[str, Tuple[str, str]], day_stem: str
    ) -> Dict[str, Any]:
        counts = count_ten_gods(pillars, day_stem)
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        present = [(g, c) for g, c in ranked if c > 0]
        cutoff = present[min(2, len(present) - 1)][1] if present else 0
        top = [(g, c) for g, c in present if c >= cutoff]
        tied = [g.value for g, c in present if c == present[0][1]] if present else []
        return {
            "top_gods": [
                {
                    "ten_god": g.value,
                    "weight": round(c, 1),
                    "traits": "传统十神象义：" + TEN_GOD_PERSONALITY.get(g, ""),
                }
                for g, c in top
            ],
            "primary": (
                tied[0]
                if len(tied) == 1
                else "并列：" + "、".join(tied) if tied else ""
            ),
            "tied_primary_gods": tied,
            "primary_selection": "按出现量排序，第三名同分全部保留；同分不按枚举先后认定性格主导。",
        }

    @staticmethod
    def _disposition(
        pillars: Dict[str, Tuple[str, str]], day_polarity: Polarity
    ) -> Dict[str, Any]:
        from ..core.elements import ElementAnalysis

        dm = ElementAnalysis.analyze_day_master_strength(pillars)
        strength = dm["strength_level"]
        notes: List[str] = []
        notes.append(
            f"日主在本工程扶抑模型中归为{strength}；这不是内外向、自信或依赖性的测量"
        )
        yin_yang = "阳" if day_polarity == Polarity.YANG else "阴"
        notes.append(f"日干阴阳查表为{yin_yang}；不据此判刚柔、行为或性别特质")
        return {
            "strength": strength,
            "polarity": "阳" if day_polarity == Polarity.YANG else "阴",
            "notes": notes,
        }

    @staticmethod
    def _strengths_weaknesses(
        core: Dict[str, Any], dominant: Dict[str, Any], disposition: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        strengths = [core["traits"]]
        weaknesses = [core["shortcoming"]]
        if dominant["top_gods"]:
            strengths.append(dominant["top_gods"][0]["traits"])
        return strengths, weaknesses

    @staticmethod
    def _advice(dominant: Dict[str, Any], disposition: Dict[str, Any]) -> List[str]:
        return [
            "将象义作为自省话题，用具体经历与他人反馈核实哪些描述适用",
            "需要人格评估时使用经过验证的测量方法，不以十神计数或旺衰代替",
        ]
