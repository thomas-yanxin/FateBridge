"""
健康分析模块

基于八字命理的健康分析功能，综合以下经典技法：
- 五行藏象：木肝胆、火心小肠、土脾胃、金肺大肠、水肾膀胱（黄帝内经五行配脏腑）
- 地支断健康：以地支冲克与旺衰断脏腑伤病（参《八字系列之地支断健康成败原理》）
- 十神断病：以十神受克受冲推疾病类型（参《十神断病五大直断法》）
- 调候寒暖：命局过寒过燥、过湿过亢皆主病

核心分析维度：
1. 五行平衡与体质（日主强弱、寒暖燥湿）
2. 脏腑强弱（过旺、过弱、缺失五行对应的脏腑隐患）
3. 易患疾病提示（受冲受克的五行/地支）
4. 健康风险时机（大运/流年冲克日主或忌神引动）
5. 养生调理方向（喜用神五行对应的调养建议）

说明：本模块仅作命理参考，不构成医学诊断，身体不适请就医。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.rules import BaZiRules
from ..utils.data import (
    BRANCH_ELEMENTS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    Element,
    check_branch_conflict,
    count_element_distribution,
    get_ten_god,
)

# 五行对应脏腑与身体系统
ELEMENT_ORGANS = {
    Element.WOOD: {
        "organs": "肝、胆",
        "systems": "神经、筋膜、眼睛、情绪",
        "excess": "肝火旺、易怒、头痛眩晕、筋骨酸痛",
        "deficient": "肝胆虚弱、视力差、易疲劳、抑郁",
    },
    Element.FIRE: {
        "organs": "心、小肠",
        "systems": "血液循环、血压、舌、精神",
        "excess": "心火亢、失眠、心悸、血压偏高、口舌生疮",
        "deficient": "心气不足、心慌、循环不良、精神不振",
    },
    Element.EARTH: {
        "organs": "脾、胃",
        "systems": "消化、肌肉、口唇",
        "excess": "脾湿、肠胃胀满、肥胖、湿气重",
        "deficient": "脾胃虚弱、消化不良、食欲差、易腹泻",
    },
    Element.METAL: {
        "organs": "肺、大肠",
        "systems": "呼吸、皮肤、鼻、免疫",
        "excess": "肺燥、咳喘、皮肤干燥、易上火",
        "deficient": "肺气虚、易感冒、呼吸道弱、皮肤过敏",
    },
    Element.WATER: {
        "organs": "肾、膀胱",
        "systems": "泌尿、生殖、骨、耳、内分泌",
        "excess": "水湿泛滥、水肿、肾水寒、泌尿频",
        "deficient": "肾气虚、腰膝酸软、生殖泌尿弱、耳鸣、骨弱",
    },
}

# 调候：火土暖燥 / 水金寒湿
WARM_ELEMENTS = {Element.FIRE, Element.EARTH}
COLD_ELEMENTS = {Element.WATER, Element.METAL}


class HealthAnalysis:
    """健康分析工具类"""

    @staticmethod
    def analyze_health(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        综合健康分析。

        Args:
            pillars: 四柱
            gender: 性别（保留以统一接口）
            dayun_pillar: 当前大运柱 (可选)
            liunian_pillar: 当前流年柱 (可选)

        Returns:
            健康分析结果字典
        """
        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0]

        constitution = HealthAnalysis._analyze_constitution(pillars, day_element)
        organs = HealthAnalysis._analyze_organs(pillars)
        risks = HealthAnalysis._analyze_disease_risks(pillars, day_stem)
        timing = HealthAnalysis._analyze_health_timing(
            pillars, day_stem, day_element, dayun_pillar, liunian_pillar
        )
        regimen = HealthAnalysis._analyze_regimen(pillars)

        return {
            "constitution": constitution,
            "organ_analysis": organs,
            "disease_risks": risks,
            "health_timing": timing,
            "regimen": regimen,
            "disclaimer": "本分析仅供命理参考，不构成医学诊断；身体不适请及时就医。",
        }

    @staticmethod
    def _element_counts(pillars: Dict[str, Tuple[str, str]]) -> Dict[Element, float]:
        return count_element_distribution(pillars)

    @staticmethod
    def _analyze_constitution(
        pillars: Dict[str, Tuple[str, str]],
        day_element: Element,
    ) -> Dict[str, Any]:
        """体质：日主强弱 + 寒暖燥湿调候。"""
        from ..core.elements import ElementAnalysis

        dm_analysis = ElementAnalysis.analyze_day_master_strength(pillars)
        strength = dm_analysis["strength_level"]

        counts = HealthAnalysis._element_counts(pillars)
        warm = round(sum(counts[e] for e in WARM_ELEMENTS), 1)
        cold = round(sum(counts[e] for e in COLD_ELEMENTS), 1)

        notes: List[str] = []
        if strength == "强":
            notes.append(
                "日主旺，体质底子较强，但忌过亢，宜疏泄（食伤、财官）以免郁结生热"
            )
        elif strength == "弱":
            notes.append("日主偏弱，元气根基较虚，宜固本培元、规律作息、避免过劳")
        else:
            notes.append("日主中和，体质较为均衡，重在保持平衡、防外感与情志失调")

        if warm - cold >= 3:
            climate = "偏燥热"
            notes.append("命局偏燥热，宜滋阴润燥、清心降火，少辛辣，多补水")
        elif cold - warm >= 3:
            climate = "偏寒湿"
            notes.append("命局偏寒湿，宜温阳祛湿、保暖健脾，忌生冷")
        else:
            climate = "寒暖均衡"
            notes.append("寒暖调候大致均衡")

        return {
            "day_master_strength": strength,
            "climate": climate,
            "warm_strength": warm,
            "cold_strength": cold,
            "notes": notes,
        }

    @staticmethod
    def _analyze_organs(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        """脏腑强弱：过旺、过弱、缺失五行对应脏腑隐患。"""
        counts = HealthAnalysis._element_counts(pillars)
        total = sum(counts.values()) or 1.0
        avg = total / 5.0

        findings: List[Dict[str, Any]] = []
        for elem, weight in counts.items():
            info = ELEMENT_ORGANS[elem]
            if weight == 0:
                findings.append(
                    {
                        "element": elem.value,
                        "organs": info["organs"],
                        "status": "缺失",
                        "concern": f"命局缺{elem.value}，{info['organs']}相关功能先天偏弱：{info['deficient']}",
                    }
                )
            elif weight >= avg * 1.8:
                findings.append(
                    {
                        "element": elem.value,
                        "organs": info["organs"],
                        "status": "过旺",
                        "concern": f"{elem.value}过旺，{info['organs']}易亢：{info['excess']}",
                    }
                )
            elif weight <= avg * 0.4:
                findings.append(
                    {
                        "element": elem.value,
                        "organs": info["organs"],
                        "status": "偏弱",
                        "concern": f"{elem.value}偏弱，{info['organs']}宜调养：{info['deficient']}",
                    }
                )

        if not findings:
            summary = "五行较为均衡，脏腑无明显偏颇，重在日常保养"
        else:
            summary = "存在五行偏颇，相关脏腑为健康关注重点"

        return {
            "element_distribution": {e.value: round(c, 1) for e, c in counts.items()},
            "findings": findings,
            "summary": summary,
        }

    @staticmethod
    def _analyze_disease_risks(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> Dict[str, Any]:
        """易患疾病：地支相冲、五行受克处易现伤病。"""
        risks: List[str] = []
        branch_items = [(name, branch) for name, (_, branch) in pillars.items()]

        # 地支相冲 → 冲处脏腑/部位易伤
        seen_pairs = set()
        for i, (n1, b1) in enumerate(branch_items):
            for n2, b2 in branch_items[i + 1 :]:
                if check_branch_conflict(b1, b2):
                    key = frozenset((b1, b2))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    e1 = BRANCH_ELEMENTS[b1][0]
                    e2 = BRANCH_ELEMENTS[b2][0]
                    o1 = ELEMENT_ORGANS[e1]["organs"]
                    o2 = ELEMENT_ORGANS[e2]["organs"]
                    risks.append(
                        f"{b1}{b2}相冲，{o1}与{o2}相关部位易受外伤、急症或慢性不适，"
                        f"逢冲之大运流年尤须留意"
                    )

        # 过旺五行被克 / 受克脏腑
        counts = HealthAnalysis._element_counts(pillars)
        for elem, weight in counts.items():
            controller = next(
                (e for e in Element if DESTRUCTION_CYCLE[e] == elem), None
            )
            if controller and counts.get(controller, 0) >= 2.5 and weight <= 1.0:
                info = ELEMENT_ORGANS[elem]
                risks.append(
                    f"{elem.value}受{controller.value}强克且自身偏弱，{info['organs']}为薄弱环节：{info['deficient']}"
                )

        if not risks:
            risks.append("命局无明显冲克病灶，整体健康风险较低，重在规律养护")

        return {"risks": risks}

    @staticmethod
    def _analyze_health_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        day_element: Element,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """健康风险时机：冲克日主、引动忌神。"""
        signals: List[str] = []
        day_branch = pillars["day"][1]

        def _assess(label: str, pillar: Tuple[str, str]) -> None:
            stem, branch = pillar
            # 冲日支（配偶宫/自身宫）
            if check_branch_conflict(branch, day_branch):
                signals.append(
                    f"{label}{stem}{branch}冲日支{day_branch}，身体易有波动，注意休息与体检"
                )
            # 七杀克身
            if get_ten_god(day_stem, stem).value == "七杀":
                signals.append(
                    f"{label}{stem}{branch}七杀攻身，压力大、易劳损或意外，宜减压防伤"
                )
            # 引动过旺/受克脏腑
            b_elem = BRANCH_ELEMENTS[branch][0]
            controlled = DESTRUCTION_CYCLE[b_elem]
            info = ELEMENT_ORGANS[controlled]
            signals.append(
                f"{label}{stem}{branch}（{b_elem.value}）克{controlled.value}，{info['organs']}相关为当期调养重点"
            )

        if dayun_pillar:
            _assess("大运", dayun_pillar)
        if liunian_pillar:
            _assess("流年", liunian_pillar)

        if not signals:
            signals.append("未提供大运/流年，无法判断阶段性健康风险")

        return {"timing_signals": signals}

    @staticmethod
    def _analyze_regimen(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        """养生调理方向：以喜用神五行所主调养为先。"""
        profile = BaZiRules.chart_useful_profile(pillars)
        favorable = [Element(value) for value in profile["useful_elements"]]

        advice: List[str] = []
        for elem in favorable:
            info = ELEMENT_ORGANS[elem]
            advice.append(
                f"喜{elem.value}：宜养护{info['organs']}（{info['systems']}），相关饮食起居为调养重点"
            )

        if not advice:
            advice.append("以五行平衡为养生总则，作息规律、情志平和")

        return {
            "favorable_elements": [e.value for e in favorable],
            "conditional_elements": profile["conditional_elements"],
            "reference_scope": profile["resolution_policy"],
            "advice": advice,
        }
