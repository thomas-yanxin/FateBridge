"""Traditional five-element correspondence, without medical inference.

Numerical weights describe a chart, not organs, symptoms, TCM syndromes,
fertility or treatment needs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..utils.data import (
    BRANCH_ELEMENTS,
    DESTRUCTION_CYCLE,
    Element,
    check_branch_conflict,
    count_element_distribution,
    get_ten_god,
)

# Traditional names only: no symptom, disease or organ-function mapping.
ELEMENT_ORGANS = {
    Element.WOOD: {"organs": "肝、胆"},
    Element.FIRE: {"organs": "心、小肠"},
    Element.EARTH: {"organs": "脾、胃"},
    Element.METAL: {"organs": "肺、大肠"},
    Element.WATER: {"organs": "肾、膀胱"},
}
WARM_ELEMENTS = {Element.FIRE, Element.EARTH}
COLD_ELEMENTS = {Element.WATER, Element.METAL}
_SCOPE = "传统五行文化对应；不是中医体质辨识、辨证或医学评估"


class HealthAnalysis:
    """Read chart classifications without deriving health findings."""

    @staticmethod
    def analyze_health(
        pillars: Dict[str, Tuple[str, str]],
        gender: Optional[str] = None,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]
        return {
            "constitution": HealthAnalysis._analyze_constitution(pillars),
            "organ_analysis": HealthAnalysis._analyze_organs(pillars),
            "health_timing": HealthAnalysis._analyze_health_timing(
                pillars, day_stem, dayun_pillar, liunian_pillar
            ),
            "scope": _SCOPE,
            "is_medical_assessment": False,
            "disclaimer": "仅解释盘内分类与传统对应；不推断疾病、症状或器官功能，不提供治疗及医疗择时。实际不适请寻求现实医疗评估。",
        }

    @staticmethod
    def _element_counts(pillars: Dict[str, Tuple[str, str]]) -> Dict[Element, float]:
        return count_element_distribution(pillars)

    @staticmethod
    def _analyze_constitution(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, Any]:
        from ..core.elements import ElementAnalysis

        strength = ElementAnalysis.analyze_day_master_strength(pillars)[
            "strength_level"
        ]
        counts = HealthAnalysis._element_counts(pillars)
        warm = round(sum(counts[e] for e in WARM_ELEMENTS), 1)
        cold = round(sum(counts[e] for e in COLD_ELEMENTS), 1)
        climate = (
            "偏燥热"
            if warm - cold >= 3
            else "偏寒湿" if cold - warm >= 3 else "寒暖均衡"
        )
        return {
            "day_master_strength": strength,
            "climate": climate,
            "warm_strength": warm,
            "cold_strength": cold,
            "notes": [
                f"日主{strength}、{climate}均为盘内规则分类，不表示身体强弱或中医证候。"
            ],
            "reference_scope": _SCOPE,
        }

    @staticmethod
    def _analyze_organs(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        counts = HealthAnalysis._element_counts(pillars)
        avg = (sum(counts.values()) or 1.0) / 5.0
        findings = []
        for elem, weight in counts.items():
            status = (
                "盘内缺失"
                if weight == 0
                else (
                    "盘内偏多"
                    if weight >= avg * 1.8
                    else "盘内偏少" if weight <= avg * 0.4 else "盘内相对均衡"
                )
            )
            organs = ELEMENT_ORGANS[elem]["organs"]
            findings.append(
                {
                    "element": elem.value,
                    "organs": organs,
                    "status": status,
                    "concern": f"{elem.value}在传统五行对应中关联{organs}；{status}只描述命盘权重，不评价这些器官。",
                }
            )
        return {
            "element_distribution": {e.value: round(c, 1) for e, c in counts.items()},
            "findings": findings,
            "summary": "以下是五行权重与传统名称对照，不产生器官功能或健康风险结论。",
            "reference_scope": _SCOPE,
        }

    @staticmethod
    def _analyze_health_timing(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
        dayun_pillar: Optional[Tuple[str, str]] = None,
        liunian_pillar: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        signals = []
        for label, pillar in (("大运", dayun_pillar), ("流年", liunian_pillar)):
            if pillar is None:
                continue
            stem, branch = pillar
            if check_branch_conflict(branch, pillars["day"][1]):
                signals.append(
                    f"{label}{stem}{branch}与日支存在相冲关系，仅为盘内关系。"
                )
            if get_ten_god(day_stem, stem).value == "七杀":
                signals.append(f"{label}{stem}{branch}的天干对应七杀，仅为十神分类。")
            element = BRANCH_ELEMENTS[branch][0]
            signals.append(
                f"{label}{stem}{branch}的{element.value}与{DESTRUCTION_CYCLE[element].value}为五行相克关系，不推断当期身体状态。"
            )
        return {
            "timing_signals": signals,
            "reference_scope": "传统关系变化，不表示发病、事故、治疗窗口或生死边界。",
        }
