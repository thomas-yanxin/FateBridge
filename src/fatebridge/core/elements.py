"""
Five Elements analysis for BaZi calculations.
"""

from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Tuple

from ..utils.data import (
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    Element,
    get_ten_god,
)
from .strength import assess_strength


class ElementAnalysis:
    """
    五行分析工具类，负责分析八字中五行的分布、关系和强弱

    该类提供了完整的五行分析功能，包括：
    - 五行统计：计算各五行在四柱中的出现次数和百分比
    - 日主强弱：分析日干的旺衰程度
    - 十神分析：根据日干与其他干支的关系确定十神
    - 喜用神：根据日主强弱确定有利的五行
    - 综合分析：整合所有五行相关的分析结果

    分析考虑因素：
    - 天干五行：直接对应的五行属性
    - 地支五行：地支本气和藏干的五行
    - 生克关系：五行相生相克的影响
    - 季节因素：月令对五行旺衰的影响
    """

    # element_distribution 的统计口径说明：它是结构计数，不是旺衰强弱。
    DISTRIBUTION_BASIS = (
        "结构计数（天干1 / 本气1 / 藏干0.5，四柱等权）；"
        "不含月令旺衰加权，亦不含刑冲合化。月令旺衰另见 element_seasonal_phase。"
    )

    @staticmethod
    def seasonal_phases(month_branch: str) -> Dict[str, str]:
        """各五行相对月令的旺衰相位（旺 / 相 / 休 / 囚 / 死）。

        经典确定映射，无主观加权：与月令同类为旺；月令所生为相；生月令者为休；
        月令所克者为囚；克月令者为死。补足 element_distribution 缺失的旺衰维度。
        """
        month_element = BRANCH_ELEMENTS[month_branch][0]
        phases: Dict[str, str] = {}
        for element in Element:
            if element == month_element:
                phase = "旺"
            elif GENERATION_CYCLE[month_element] == element:
                phase = "相"
            elif GENERATION_CYCLE[element] == month_element:
                phase = "休"
            elif DESTRUCTION_CYCLE[month_element] == element:
                phase = "囚"
            else:  # 克月令者
                phase = "死"
            phases[element.value] = phase
        return phases

    @staticmethod
    def count_elements(pillars: Dict[str, Tuple[str, str]]) -> Dict[Element, float]:
        """Count the occurrence of each element in the chart."""
        element_count: DefaultDict[Element, float] = defaultdict(float)

        # Count stem elements
        for stem, branch in pillars.values():
            stem_element, _ = STEM_ELEMENTS[stem]
            element_count[stem_element] += 1

            # Count main branch element
            branch_element, _ = BRANCH_ELEMENTS[branch]
            element_count[branch_element] += 1

            # Count hidden stems (with reduced weight)
            hidden_stems = BRANCH_HIDDEN_STEMS[branch]
            for hidden_stem in hidden_stems:
                hidden_element, _ = STEM_ELEMENTS[hidden_stem]
                element_count[hidden_element] += 0.5  # Hidden stems have less influence

        return dict(element_count)

    @staticmethod
    def convert_to_percentage(element_counts: Dict[Element, float]) -> Dict[str, float]:
        """Convert element counts to percentages."""
        total = sum(element_counts.values())
        if total == 0:
            return {elem.value: 0.0 for elem in Element}

        percentages = {}
        for element, count in element_counts.items():
            percentage = (count / total) * 100
            percentages[element.value] = round(percentage, 1)

        # 把各项凑齐到 100%（吸收四舍五入误差）。
        # 用「四舍五入后的残差」判断，而不是 abs(sum-100) > 0.1 的浮点刀刃：
        # CPython 3.12 起 sum() 改用 Neumaier 补偿求和，会让 99.9 这类 0.1 倍数
        # 的浮点和在 3.11/3.12 间落到刀刃两侧，导致补偿是否触发随版本翻转。
        # round(残差, 1) 把比较拉回 0.1 量化网格，跨版本确定。
        residual = round(100.0 - sum(percentages.values()), 1)
        if residual:
            # 把残差并到占比最大的元素上，使总和恰为 100%。
            max_key = max(percentages.keys(), key=lambda k: percentages[k])
            percentages[max_key] = round(percentages[max_key] + residual, 1)

        return percentages

    @staticmethod
    def validate_percentage_total(percentages: Dict[str, float]) -> bool:
        """Validate that percentages sum to 100% within tolerance."""
        total = sum(percentages.values())
        return abs(total - 100.0) <= 0.1

    @staticmethod
    def analyze_day_master_strength(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, Any]:
        """Analyze the strength of the day master (日主)."""
        day_master_stem = pillars["day"][0]
        day_master_element, day_master_polarity = STEM_ELEMENTS[day_master_stem]

        element_counts = ElementAnalysis.count_elements(pillars)
        element_percentages = ElementAnalysis.convert_to_percentage(element_counts)
        assessment = assess_strength(
            pillars, ElementAnalysis.seasonal_phases(pillars["month"][1])
        )
        return {
            "assessment": assessment,
            "day_master": day_master_stem,
            "day_element": day_master_element.value,
            "day_polarity": day_master_polarity.value,
            "support_strength": assessment["support_strength"],
            "weaken_strength": assessment["weaken_strength"],
            "strength_level": assessment["strength_level"],
            "element_distribution": element_percentages,
            "element_distribution_raw": {
                element_enum.value: count
                for element_enum, count in element_counts.items()
            },  # Keep raw scores for internal calculations
            "element_distribution_basis": ElementAnalysis.DISTRIBUTION_BASIS,
            "element_seasonal_phase": ElementAnalysis.seasonal_phases(
                pillars["month"][1]
            ),
        }

    @staticmethod
    def analyze_ten_gods(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Dict[str, str]]]:
        """Analyze the Ten Gods relationships in the chart."""
        day_master_stem = pillars["day"][0]
        ten_gods_analysis = {}

        for pillar_name, (pillar_stem, pillar_branch) in pillars.items():
            pillar_ten_gods = []

            # Analyze stem
            if (
                pillar_name != "day" or pillar_stem != day_master_stem
            ):  # Don't analyze day stem with itself
                ten_god_relationship = get_ten_god(day_master_stem, pillar_stem)
                pillar_ten_gods.append(
                    {
                        "position": f"{pillar_name}_stem",
                        "character": pillar_stem,
                        "ten_god": ten_god_relationship.value,
                    }
                )

            # Analyze hidden stems in branch
            hidden_stems_in_branch = BRANCH_HIDDEN_STEMS[pillar_branch]
            for hidden_stem_index, hidden_stem in enumerate(hidden_stems_in_branch):
                # Hidden stems that share the day-master stem still matter —
                # they represent the day master's 根 (root strength) and show
                # up as 比肩 in classical ten-god tables. Skipping them used to
                # hide a chart's roots (e.g. 庚日 at 巳月 藏 庚 should list
                # 比肩, not disappear).
                ten_god_relationship = get_ten_god(day_master_stem, hidden_stem)
                pillar_ten_gods.append(
                    {
                        "position": f"{pillar_name}_branch_hidden_{hidden_stem_index+1}",
                        "character": hidden_stem,
                        "ten_god": ten_god_relationship.value,
                    }
                )

            ten_gods_analysis[pillar_name] = pillar_ten_gods

        return ten_gods_analysis

    @staticmethod
    def get_favorable_elements(day_master_analysis: Dict[str, Any]) -> List[Element]:
        """Determine favorable elements based on day master strength."""
        day_master_element: Element | None = None
        for element_enum in Element:
            if element_enum.value == day_master_analysis["day_element"]:
                day_master_element = element_enum
                break
        if day_master_element is None:
            raise ValueError(
                f"Unknown day element: {day_master_analysis['day_element']!r}"
            )

        assessment = day_master_analysis.get("assessment", {})
        if (
            assessment.get("requires_special_structure_review")
            or assessment.get("status") == "boundary_sensitive"
        ):
            return []
        day_master_strength_level = day_master_analysis["strength_level"]

        if day_master_strength_level == "强":
            # Strong day master needs elements that drain or control it
            favorable_elements = []

            # Elements generated by day master (drain)
            if day_master_element in GENERATION_CYCLE:
                favorable_elements.append(GENERATION_CYCLE[day_master_element])

            # Elements that destroy day master (control)
            for element_enum, destroyed_element in DESTRUCTION_CYCLE.items():
                if destroyed_element == day_master_element:
                    favorable_elements.append(element_enum)
                    break

            # Wealth elements (destroyed by day master)
            if day_master_element in DESTRUCTION_CYCLE:
                favorable_elements.append(DESTRUCTION_CYCLE[day_master_element])

        elif day_master_strength_level == "弱":
            # Weak day master needs support
            favorable_elements = []

            # Same element (support)
            favorable_elements.append(day_master_element)

            # Elements that generate day master
            for element_enum, generated_element in GENERATION_CYCLE.items():
                if generated_element == day_master_element:
                    favorable_elements.append(element_enum)
                    break

        else:  # 中和
            # A middle score supplies no directional preference by itself.
            favorable_elements = []

        return favorable_elements

    @staticmethod
    def comprehensive_analysis(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        """Perform comprehensive element analysis."""
        day_master_analysis = ElementAnalysis.analyze_day_master_strength(pillars)
        ten_gods_analysis = ElementAnalysis.analyze_ten_gods(pillars)
        favorable_elements = ElementAnalysis.get_favorable_elements(day_master_analysis)

        # Validate percentage totals
        element_distribution = day_master_analysis["element_distribution"]
        is_valid = ElementAnalysis.validate_percentage_total(element_distribution)

        result = {
            "day_master": day_master_analysis,
            "ten_gods": ten_gods_analysis,
            "favorable_elements": [elem.value for elem in favorable_elements],
            "element_distribution": element_distribution,
            "percentage_validation": {
                "is_valid": is_valid,
                "total": round(sum(element_distribution.values()), 1),
            },
        }

        # Add warning if validation fails
        if not is_valid:
            result["warning"] = (
                f"百分比总和异常: {result['percentage_validation']['total']}%"
            )

        return result
