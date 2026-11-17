"""
BaZi rules and pattern analysis.
"""

from collections import defaultdict
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    TypedDict,
)

from ..utils.data import (
    BRANCH_CLASH_PAIRS,
    BRANCH_COMBINATION_ELEMENT,
    BRANCH_ELEMENTS,
    BRANCH_HARM_PAIRS,
    BRANCH_HARMONY_PAIRS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_PUNISHMENT_GROUPS,
    BRANCH_TRIPLE_COMBINATIONS,
    BRANCH_TRIPLE_ELEMENTS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    STEM_FOUR_CLASHES,
    Element,
    TenGod,
    get_ten_god,
)
from .bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
    classify_triple_members,
)
from .classical_candidate_selection import build_candidate_selection
from .useful_elements import resolve_useful_elements


class StemRelation(TypedDict):
    stems: List[str]
    pillars: List[str]
    name: str


class StemCombination(StemRelation):
    candidate_element: str


class StemPatterns(TypedDict):
    pair_scope: Literal["adjacent_visible_stems"]
    transformation_status: Literal["not_adjudicated"]
    combinations: List[StemCombination]
    clashes: List[StemRelation]
    controls: List[StemRelation]


class BaZiRules:
    """Analyzes special patterns and rules in BaZi charts."""

    YANG_BLADE_BRANCHES = {
        "甲": "卯",
        "丙": "午",
        "戊": "午",
        "庚": "酉",
        "壬": "子",
    }

    STRUCTURE_PRIORITIES = {
        "yang_ren_jia_sha": 100,
        "shi_shen_zhi_sha": 92,
        "sha_yin_xiang_sheng": 86,
        "shang_guan_pei_yin": 78,
        "shang_guan_jian_guan": 68,
        "default_support": 10,
    }

    @staticmethod
    def check_stem_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> StemPatterns:
        """Match adjacent visible stems without adjudicating transformation.

        The five-combination table supplies a candidate element, not a change
        to either stem. Actual binding, competition and transformation require
        separate conditions; see 子平真诠·论十干合而不合 and bazi-assessment.md.
        """
        stems = {k: v[0] for k, v in pillars.items()}  # position -> stem
        patterns: StemPatterns = {
            "pair_scope": "adjacent_visible_stems",
            "transformation_status": "not_adjudicated",
            "combinations": [],
            "clashes": [],
            "controls": [],
        }

        pillar_names = ["year", "month", "day", "hour"]

        # This matcher covers Year-Month, Month-Day and Day-Hour only.
        # It does not adjudicate distant pairs or choose between competing pairs.
        for i in range(len(pillar_names) - 1):
            p1, p2 = pillar_names[i], pillar_names[i + 1]
            s1, s2 = stems[p1], stems[p2]

            # Combinations
            for c1, c2, candidate_element in STEM_COMBINATIONS:
                if (s1 == c1 and s2 == c2) or (s1 == c2 and s2 == c1):
                    patterns["combinations"].append(
                        {
                            "stems": [s1, s2],
                            "pillars": [p1, p2],
                            "candidate_element": candidate_element,
                            "name": f"{s1}{s2}相合",
                        }
                    )

            # Clashes (Chong)
            for c1, c2 in STEM_FOUR_CLASHES:
                if (s1 == c1 and s2 == c2) or (s1 == c2 and s2 == c1):
                    patterns["clashes"].append(
                        {
                            "stems": [s1, s2],
                            "pillars": [p1, p2],
                            "name": f"{s1}{s2}相冲",
                        }
                    )

            # Control (Ke) - General Elemental Control
            e1 = STEM_ELEMENTS[s1][0]
            e2 = STEM_ELEMENTS[s2][0]

            is_clash = any(
                (s1 == x and s2 == y) or (s1 == y and s2 == x)
                for x, y in STEM_FOUR_CLASHES
            )
            if not is_clash:
                if DESTRUCTION_CYCLE.get(e1) == e2:
                    patterns["controls"].append(
                        {"stems": [s1, s2], "pillars": [p1, p2], "name": f"{s1}克{s2}"}
                    )
                elif DESTRUCTION_CYCLE.get(e2) == e1:
                    patterns["controls"].append(
                        {"stems": [s2, s1], "pillars": [p2, p1], "name": f"{s2}克{s1}"}
                    )

        return patterns

    @staticmethod
    def _ordered_unique(items: Iterable[Optional[str]]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @staticmethod
    def _get_element_enum_by_value(element_value: str) -> Optional[Element]:
        for element_enum in Element:
            if element_enum.value == element_value:
                return element_enum
        return None

    @staticmethod
    def _get_generating_element(target: Element) -> Optional[Element]:
        for element_enum, generated in GENERATION_CYCLE.items():
            if generated == target:
                return element_enum
        return None

    @staticmethod
    def _get_destroying_element(target: Element) -> Optional[Element]:
        for element_enum, destroyed in DESTRUCTION_CYCLE.items():
            if destroyed == target:
                return element_enum
        return None

    @staticmethod
    def _element_for_ten_god(day_stem: str, ten_god: str) -> Optional[str]:
        day_element = STEM_ELEMENTS[day_stem][0]
        if ten_god in {TenGod.COMPARE.value, TenGod.ROB_WEALTH.value}:
            return day_element.value
        if ten_god in {TenGod.FOOD_GOD.value, TenGod.HURT_OFFICER.value}:
            return GENERATION_CYCLE[day_element].value
        if ten_god in {TenGod.POSITIVE_WEALTH.value, TenGod.PARTIAL_WEALTH.value}:
            return DESTRUCTION_CYCLE[day_element].value
        if ten_god in {TenGod.POSITIVE_OFFICER.value, TenGod.SEVEN_KILLER.value}:
            destroying = BaZiRules._get_destroying_element(day_element)
            return destroying.value if destroying else None
        if ten_god in {TenGod.POSITIVE_SEAL.value, TenGod.PARTIAL_SEAL.value}:
            generating = BaZiRules._get_generating_element(day_element)
            return generating.value if generating else None
        return None

    @staticmethod
    def _derive_ten_gods_from_elements(day_stem: str, elements: List[str]) -> List[str]:
        ten_gods: List[str] = []
        day_element = STEM_ELEMENTS[day_stem][0]
        for element_value in elements:
            element_enum = BaZiRules._get_element_enum_by_value(element_value)
            if element_enum is None:
                continue

            if element_enum == day_element:
                ten_gods.extend([TenGod.COMPARE.value, TenGod.ROB_WEALTH.value])
            elif GENERATION_CYCLE[day_element] == element_enum:
                ten_gods.extend([TenGod.FOOD_GOD.value, TenGod.HURT_OFFICER.value])
            elif DESTRUCTION_CYCLE[day_element] == element_enum:
                ten_gods.extend(
                    [TenGod.PARTIAL_WEALTH.value, TenGod.POSITIVE_WEALTH.value]
                )
            elif DESTRUCTION_CYCLE[element_enum] == day_element:
                ten_gods.extend(
                    [TenGod.SEVEN_KILLER.value, TenGod.POSITIVE_OFFICER.value]
                )
            elif GENERATION_CYCLE[element_enum] == day_element:
                ten_gods.extend([TenGod.PARTIAL_SEAL.value, TenGod.POSITIVE_SEAL.value])

        return BaZiRules._ordered_unique(ten_gods)

    @staticmethod
    def _get_significant_gods(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> set[str]:
        significant = set()
        # Stems (excluding day master)
        for p in ["year", "month", "hour"]:
            stem = pillars[p][0]
            god = get_ten_god(day_stem, stem).value
            significant.add(god)

        # Month Branch Main Qi
        month_branch = pillars["month"][1]
        hidden = BRANCH_HIDDEN_STEMS.get(month_branch, [])
        if hidden:
            main_hidden = hidden[0]
            main_god = get_ten_god(day_stem, main_hidden).value
            significant.add(main_god)

        return significant

    @staticmethod
    def _build_structure_candidates(
        pillars: Dict[str, Tuple[str, str]],
        day_stem: str,
    ) -> List[Dict[str, Any]]:
        branches = [branch for _, branch in pillars.values()]
        sig_gods = BaZiRules._get_significant_gods(pillars, day_stem)

        killer_element = BaZiRules._element_for_ten_god(
            day_stem, TenGod.SEVEN_KILLER.value
        )
        seal_element = BaZiRules._element_for_ten_god(
            day_stem, TenGod.POSITIVE_SEAL.value
        )
        food_element = BaZiRules._element_for_ten_god(day_stem, TenGod.FOOD_GOD.value)
        hurt_element = BaZiRules._element_for_ten_god(
            day_stem, TenGod.HURT_OFFICER.value
        )

        candidates: List[Dict[str, Any]] = []

        blade_branch = BaZiRules.YANG_BLADE_BRANCHES.get(day_stem)
        if (
            blade_branch
            and blade_branch in branches
            and TenGod.SEVEN_KILLER.value in sig_gods
        ):
            candidates.append(
                {
                    "key": "yang_ren_jia_sha",
                    "label": "羊刃驾杀",
                    "priority": BaZiRules.STRUCTURE_PRIORITIES["yang_ren_jia_sha"],
                    "reason": f"四柱见{day_stem}的阳刃位{blade_branch}并见七杀；这是旧共现候选，不认证月刃格或制杀效力。",
                    "useful_elements": BaZiRules._ordered_unique(
                        [killer_element, seal_element]
                    ),
                    "avoid_elements": BaZiRules._ordered_unique(
                        [food_element] if food_element else []
                    ),
                    "useful_ten_gods": [
                        TenGod.SEVEN_KILLER.value,
                        TenGod.POSITIVE_OFFICER.value,
                        TenGod.POSITIVE_SEAL.value,
                        TenGod.PARTIAL_SEAL.value,
                    ],
                }
            )

        if TenGod.SEVEN_KILLER.value in sig_gods and (
            TenGod.POSITIVE_SEAL.value in sig_gods
            or TenGod.PARTIAL_SEAL.value in sig_gods
        ):
            candidates.append(
                {
                    "key": "sha_yin_xiang_sheng",
                    "label": "杀印相生",
                    "priority": BaZiRules.STRUCTURE_PRIORITIES["sha_yin_xiang_sheng"],
                    "reason": "旧规则观察到杀星与印星并见；杀格用印、印格用杀及伤官用杀印另按月令和力量审查。",
                    "useful_elements": BaZiRules._ordered_unique(
                        [killer_element, seal_element]
                    ),
                    "avoid_elements": [],
                    "useful_ten_gods": [
                        TenGod.SEVEN_KILLER.value,
                        TenGod.POSITIVE_OFFICER.value,
                        TenGod.POSITIVE_SEAL.value,
                        TenGod.PARTIAL_SEAL.value,
                    ],
                }
            )

        if TenGod.SEVEN_KILLER.value in sig_gods and TenGod.FOOD_GOD.value in sig_gods:
            candidates.append(
                {
                    "key": "shi_shen_zhi_sha",
                    "label": "食神制杀",
                    "priority": BaZiRules.STRUCTURE_PRIORITIES["shi_shen_zhi_sha"],
                    "reason": "旧规则观察到食神与七杀同见；食神格制杀与杀格用食分列，尚未裁定制杀适当。",
                    "useful_elements": BaZiRules._ordered_unique(
                        [food_element, killer_element]
                    ),
                    "avoid_elements": [],
                    "useful_ten_gods": [
                        TenGod.FOOD_GOD.value,
                        TenGod.SEVEN_KILLER.value,
                    ],
                }
            )

        if TenGod.HURT_OFFICER.value in sig_gods and (
            TenGod.POSITIVE_SEAL.value in sig_gods
            or TenGod.PARTIAL_SEAL.value in sig_gods
        ):
            candidates.append(
                {
                    "key": "shang_guan_pei_yin",
                    "label": "伤官配印",
                    "priority": BaZiRules.STRUCTURE_PRIORITIES["shang_guan_pei_yin"],
                    "reason": "旧规则观察到伤官与印并见；伤官佩印与印格用食伤不能混为同一取用结论。",
                    "useful_elements": BaZiRules._ordered_unique(
                        [hurt_element, seal_element]
                    ),
                    "avoid_elements": [],
                    "useful_ten_gods": [
                        TenGod.HURT_OFFICER.value,
                        TenGod.POSITIVE_SEAL.value,
                        TenGod.PARTIAL_SEAL.value,
                    ],
                }
            )

        if (
            TenGod.HURT_OFFICER.value in sig_gods
            and TenGod.POSITIVE_OFFICER.value in sig_gods
        ):
            candidates.append(
                {
                    "key": "shang_guan_jian_guan",
                    "label": "伤官见官",
                    "priority": BaZiRules.STRUCTURE_PRIORITIES["shang_guan_jian_guan"],
                    "reason": "旧规则观察到伤官与正官并见；官格遇伤与金水伤官用官的条件分别审查，不由共现认定破格。",
                    "useful_elements": BaZiRules._ordered_unique(
                        [seal_element] if seal_element else []
                    ),
                    "avoid_elements": BaZiRules._ordered_unique(
                        [killer_element, hurt_element]
                    ),
                    "useful_ten_gods": [
                        TenGod.POSITIVE_SEAL.value,
                        TenGod.PARTIAL_SEAL.value,
                    ],
                }
            )

        for candidate in candidates:
            candidate["formation_status"] = "candidate_only"
        candidates.sort(key=lambda item: item["priority"], reverse=True)
        return candidates

    @staticmethod
    def _describe_day_master_impact(
        day_element_value: str,
        result_element_value: Optional[str],
    ) -> str:
        if not result_element_value:
            return "主要体现为气机扰动，需要结合被触动的五行再看。"

        day_element = BaZiRules._get_element_enum_by_value(day_element_value)
        result_element = BaZiRules._get_element_enum_by_value(result_element_value)
        if day_element is None or result_element is None:
            return "对日主影响需要结合五行关系进一步判断。"

        if day_element == result_element:
            return f"{result_element_value}与日主同气，助身增势。"
        if GENERATION_CYCLE[result_element] == day_element:
            return f"{result_element_value}生日主，对日主有补益作用。"
        if GENERATION_CYCLE[day_element] == result_element:
            return f"日主之气流向{result_element_value}，更偏向泄秀或输出。"
        if DESTRUCTION_CYCLE[result_element] == day_element:
            return f"{result_element_value}克日主，带来约束与压力。"
        if DESTRUCTION_CYCLE[day_element] == result_element:
            return f"日主可制{result_element_value}，更利于驾驭资源或对象。"
        return "与日主关系中性，需要结合全局判断。"

    @staticmethod
    def _describe_structure_impact(
        result_element_value: Optional[str],
        structure_profile: Dict[str, Any],
        affected_elements: Optional[List[str]] = None,
    ) -> str:
        dominant = structure_profile.get("dominant_structure", {}) or {}
        structure_label = dominant.get("label", "当前格局")
        useful_elements = set(structure_profile.get("useful_elements", []))
        avoid_elements = set(structure_profile.get("avoid_elements", []))

        if result_element_value:
            if result_element_value in useful_elements:
                return f"{result_element_value}属于{structure_label}可用之气，对格局流通有支持。"
            if result_element_value in avoid_elements:
                return f"{result_element_value}属于{structure_label}需回避之气，对格局流通有干扰。"
            return (
                f"{result_element_value}对{structure_label}影响中性，需结合全局衡量。"
            )

        affected = set(affected_elements or [])
        if useful_elements & affected:
            return f"事件触动了{structure_label}的可用五行，格局稳定性需要重点观察。"
        if avoid_elements & affected:
            return f"事件触动了{structure_label}的忌避五行，既可能化解也可能放大张力。"
        return f"事件对{structure_label}形成扰动，偏向张力型影响。"

    @staticmethod
    def build_structure_profile(
        pillars: Dict[str, Tuple[str, str]],
        element_analysis: Dict[str, Any],
        harmony_patterns: Optional[Mapping[str, object]] = None,
        clash_patterns: Optional[Mapping[str, object]] = None,
        special_patterns: Optional[Mapping[str, object]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]
        day_master = element_analysis["day_master"]
        day_strength = day_master["engineering_index"]["strength_level"]
        baseline_useful = list(element_analysis.get("favorable_elements", []))
        baseline_useful_ten_gods = BaZiRules._derive_ten_gods_from_elements(
            day_stem, baseline_useful
        )
        recognized_structures = BaZiRules._build_structure_candidates(pillars, day_stem)
        candidate_selection = build_candidate_selection(pillars)
        selected_month = candidate_selection["selected_month"]
        dominant_structure = {
            "key": "selected_month_reference",
            "label": selected_month["label"],
            "formation_status": "not_adjudicated",
            "reason": f"月令{selected_month['branch']}按同次{selected_month['selection_rule']}选{selected_month['ten_god']}；月令主类不等于完整成格或取用已定。",
            "useful_elements": [],
            "avoid_elements": [],
            "useful_ten_gods": [],
        }
        secondary_structures = recognized_structures
        decision_basis = [
            dominant_structure["reason"],
            f"工程扶抑模型判为{day_strength}；身、印及食财官杀的相对力量另列待判条件。",
            "原典取用路径按月令分列，未由十神共现或固定优先级选定；旧优先候选仅供追溯。",
        ]
        if selected_month["basis_status"] == "original_and_selected_differ":
            decision_basis.append(
                f"月令本气为{selected_month['original_main_qi']['ten_god']}，当前有限规则所选为{selected_month['ten_god']}；是否变格、兼格仍待裁定，不以透干即抹去本气。"
            )

        resolution = resolve_useful_elements(
            pillars, element_analysis, recognized_structures
        )
        engineering_reference = resolution["engineering_reference"]
        engineering_reference["useful_ten_gods"] = (
            BaZiRules._derive_ten_gods_from_elements(
                day_stem, engineering_reference["useful_elements"]
            )
        )
        if resolution["from_child_reference"]["ordinary_fuyi_requires_review"]:
            decision_basis.append(
                "任注顺局从儿的月柱食伤、分布与财星前提已见；从儿不以身弱为必要条件。成气、藏印官杀及承接救应未判，普通扶抑喜忌列为条件参考。"
            )
        useful_elements = resolution["useful_elements"]
        avoid_elements = resolution["avoid_elements"]
        useful_ten_gods = BaZiRules._derive_ten_gods_from_elements(
            day_stem, useful_elements
        )
        decision_basis.append(
            "扶抑、原典待判路径、旧共现候选与调候分层保留；未裁定的旧候选不单独授予全局喜忌，未入喜不自动为忌。"
        )
        structure_profile: Dict[str, Any] = {
            **resolution,
            "dominant_structure": dominant_structure,
            "candidate_selection": candidate_selection,
            "secondary_structures": secondary_structures,
            "secondary_structure_scope": "旧共现候选完整保留，不代表次格成立或已选定取用路径。",
            "recognized_structures": recognized_structures,
            "useful_elements": useful_elements,
            "avoid_elements": avoid_elements,
            "useful_ten_gods": useful_ten_gods,
            "decision_basis": decision_basis,
            "harmony_effects": [],
            "metadata": {
                "baseline_useful_elements": baseline_useful,
                "baseline_useful_ten_gods": baseline_useful_ten_gods,
                "day_master_strength": day_strength,
                "strength_basis": "uncalibrated_strength_policy_index",
                "harmony_patterns": harmony_patterns or {},
                "clash_patterns": clash_patterns or {},
                "special_patterns": special_patterns or {},
            },
        }

        structure_profile["engineering_harmony_effects"] = (
            BaZiRules.analyze_harmony_effects(
                pillars, {**structure_profile, **engineering_reference}
            )
        )
        structure_profile["harmony_effects"] = (
            BaZiRules.analyze_harmony_effects(pillars, structure_profile)
            if resolution["assessment_status"] != "not_adjudicated"
            else []
        )
        structure_profile["harmony_effects_status"] = resolution["assessment_status"]

        for event in structure_profile["harmony_effects"]:
            if event.get("classification") == "supportive":
                decision_basis.append(
                    f"{event['label']}：{event['impact_on_structure']}"
                )
            elif event.get("classification") == "risk":
                decision_basis.append(
                    f"{event['label']}：{event['impact_on_structure']}"
                )

        structure_profile["decision_basis"] = BaZiRules._ordered_unique(decision_basis)
        return structure_profile

    @staticmethod
    def chart_useful_profile(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
        """Use the same layered resolver in birth and specialty analyses."""
        from .elements import ElementAnalysis

        return BaZiRules.build_structure_profile(
            pillars, ElementAnalysis.comprehensive_analysis(pillars)
        )

    @staticmethod
    def analyze_harmony_effects(
        pillars: Dict[str, Tuple[str, str]],
        structure_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        harmony_patterns = check_harmony_patterns(pillars)
        clash_patterns = check_clash_patterns(pillars)

        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0].value
        useful_elements = set(structure_profile.get("useful_elements", []))
        avoid_elements = set(structure_profile.get("avoid_elements", []))
        events: List[Dict[str, Any]] = []

        for item in harmony_patterns.get("three_harmony", []):
            branches = item["branches"]
            result_element = next(
                (
                    element.value
                    for combo, element in BRANCH_TRIPLE_ELEMENTS.items()
                    if all(branch in combo for branch in branches)
                ),
                None,
            )
            source_elements = BaZiRules._ordered_unique(
                [BRANCH_ELEMENTS[branch][0].value for branch in branches]
            )
            classification = (
                "supportive"
                if result_element in useful_elements
                else "risk" if result_element in avoid_elements else "neutral"
            )
            events.append(
                {
                    "type": "three_harmony",
                    "label": f"{''.join(branches)}三合{result_element}局",
                    "branches": branches,
                    "result_element": result_element,
                    "strengthens": [result_element] if result_element else [],
                    "consumes": [
                        element
                        for element in source_elements
                        if element != result_element
                    ],
                    "impact_on_day_master": BaZiRules._describe_day_master_impact(
                        day_element, result_element
                    ),
                    "impact_on_structure": BaZiRules._describe_structure_impact(
                        result_element, structure_profile
                    ),
                    "classification": classification,
                }
            )

        for item in harmony_patterns.get("half_harmony", []):
            branches = item["branches"]
            result_element = next(
                (
                    element.value
                    for combo, element in BRANCH_TRIPLE_ELEMENTS.items()
                    if all(branch in combo for branch in branches)
                ),
                None,
            )
            source_elements = BaZiRules._ordered_unique(
                [BRANCH_ELEMENTS[branch][0].value for branch in branches]
            )
            classification = (
                "supportive"
                if result_element in useful_elements
                else "risk" if result_element in avoid_elements else "neutral"
            )
            events.append(
                {
                    "type": "half_harmony",
                    "label": f"{''.join(branches)}半合{result_element}局",
                    "branches": branches,
                    "result_element": result_element,
                    "strengthens": [result_element] if result_element else [],
                    "consumes": [
                        element
                        for element in source_elements
                        if element != result_element
                    ],
                    "impact_on_day_master": BaZiRules._describe_day_master_impact(
                        day_element, result_element
                    ),
                    "impact_on_structure": BaZiRules._describe_structure_impact(
                        result_element, structure_profile
                    ),
                    "classification": classification,
                }
            )

        for pair in harmony_patterns.get("six_harmony", []):
            result_element_enum = BRANCH_COMBINATION_ELEMENT.get(frozenset(pair))
            result_element = result_element_enum.value if result_element_enum else None
            source_elements = BaZiRules._ordered_unique(
                [BRANCH_ELEMENTS[branch][0].value for branch in pair]
            )
            classification = (
                "supportive"
                if result_element in useful_elements
                else "risk" if result_element in avoid_elements else "neutral"
            )
            events.append(
                {
                    "type": "six_harmony",
                    "label": f"{''.join(pair)}六合",
                    "branches": pair,
                    "result_element": result_element,
                    "strengthens": [result_element] if result_element else [],
                    "consumes": [
                        element
                        for element in source_elements
                        if element != result_element
                    ],
                    "impact_on_day_master": BaZiRules._describe_day_master_impact(
                        day_element, result_element
                    ),
                    "impact_on_structure": BaZiRules._describe_structure_impact(
                        result_element, structure_profile
                    ),
                    "classification": classification,
                }
            )

        conflict_groups = [
            ("six_clash", "六冲", clash_patterns["six_clash"]),
            ("six_harm", "六害", clash_patterns["six_harm"]),
        ]
        for group_key, group_label, pairs in conflict_groups:
            for pair in pairs:
                affected_elements = BaZiRules._ordered_unique(
                    [BRANCH_ELEMENTS[branch][0].value for branch in pair]
                )
                classification = (
                    "risk" if useful_elements & set(affected_elements) else "tension"
                )
                events.append(
                    {
                        "type": group_key,
                        "label": f"{''.join(pair)}{group_label}",
                        "branches": pair,
                        "result_element": None,
                        "strengthens": [],
                        "consumes": affected_elements,
                        "impact_on_day_master": BaZiRules._describe_day_master_impact(
                            day_element, None
                        ),
                        "impact_on_structure": BaZiRules._describe_structure_impact(
                            None, structure_profile, affected_elements
                        ),
                        "classification": classification,
                    }
                )

        for punishment in clash_patterns.get("punishments", []):
            affected_elements = BaZiRules._ordered_unique(
                [
                    BRANCH_ELEMENTS[branch][0].value
                    for branch in punishment.get("branches", [])
                ]
            )
            classification = (
                "risk" if useful_elements & set(affected_elements) else "tension"
            )
            events.append(
                {
                    "type": punishment["type"],
                    "label": punishment["name"],
                    "branches": punishment.get("branches", []),
                    "result_element": None,
                    "strengthens": [],
                    "consumes": affected_elements,
                    "impact_on_day_master": BaZiRules._describe_day_master_impact(
                        day_element, None
                    ),
                    "impact_on_structure": BaZiRules._describe_structure_impact(
                        None, structure_profile, affected_elements
                    ),
                    "classification": classification,
                }
            )

        return events

    @staticmethod
    def _classify_combined_event(
        *,
        event_type: str,
        result_element: Optional[str],
        affected_elements: List[str],
        structure_profile1: Optional[Dict[str, Any]],
        structure_profile2: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        profiles = [structure_profile1 or {}, structure_profile2 or {}]
        useful_hits = 0
        avoid_hits = 0

        for profile in profiles:
            useful_elements = set(profile.get("useful_elements", []))
            avoid_elements = set(profile.get("avoid_elements", []))

            if result_element:
                if result_element in useful_elements:
                    useful_hits += 1
                if result_element in avoid_elements:
                    avoid_hits += 1
            else:
                if useful_elements & set(affected_elements):
                    avoid_hits += 1
                elif avoid_elements & set(affected_elements):
                    useful_hits += 1

        if event_type in {"three_harmony", "half_harmony", "six_harmony"}:
            if avoid_hits >= 2:
                return "risk", "对双方格局都形成明显干扰。"
            if useful_hits >= 2:
                return "supportive", "对双方格局都形成支持。"
            if useful_hits and avoid_hits:
                return "tension", "一方受益而另一方承压，属于拉扯型事件。"
            if useful_hits or avoid_hits:
                return (
                    "unresolved",
                    "仅一方取用参考有命中；另一方效力未定，不据此认定双向受益或承压。",
                )
            return "unresolved", "已见名义合局，双方取用效力未定，不据此计为支持。"

        if avoid_hits >= 2:
            return "risk", "冲击双方可用之气，风险较高。"
        return "tension", "事件带来明显张力，需要结合格局取用判断。"

    @staticmethod
    def analyze_combined_chart_events(
        pillars1: Dict[str, Tuple[str, str]],
        pillars2: Dict[str, Tuple[str, str]],
        structure_profile1: Optional[Dict[str, Any]] = None,
        structure_profile2: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        combined_entries: List[Dict[str, Any]] = []
        for person_label, pillars in (("person1", pillars1), ("person2", pillars2)):
            for pillar_name, (stem, branch) in pillars.items():
                combined_entries.append(
                    {
                        "person": person_label,
                        "pillar": pillar_name,
                        "stem": stem,
                        "branch": branch,
                    }
                )

        branch_sources: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in combined_entries:
            branch_sources[entry["branch"]].append(
                {
                    "person": entry["person"],
                    "pillar": entry["pillar"],
                    "stem": entry["stem"],
                }
            )

        events: List[Dict[str, Any]] = []
        supportive_patterns: List[Dict[str, Any]] = []
        tension_patterns: List[Dict[str, Any]] = []
        risk_patterns: List[Dict[str, Any]] = []
        unresolved_patterns: List[Dict[str, Any]] = []

        def _append_event(event: Dict[str, Any]) -> None:
            events.append(event)
            summary = {
                "label": event["label"],
                "type": event["type"],
                "description": event["description"],
                "result_element": event.get("result_element"),
                "source_scope": event.get("source_scope"),
                "source_map": event.get("source_map", {}),
            }
            if event["classification"] == "supportive":
                supportive_patterns.append(summary)
            elif event["classification"] == "risk":
                risk_patterns.append(summary)
            elif event["classification"] == "unresolved":
                unresolved_patterns.append(summary)
            else:
                tension_patterns.append(summary)

        for combo, element in BRANCH_TRIPLE_ELEMENTS.items():
            present_branches = [
                branch for branch in combo if branch_sources.get(branch)
            ]
            membership = classify_triple_members("".join(combo), present_branches)
            if membership == "complete":
                source_scope = (
                    "cross_person"
                    if len(
                        {
                            source["person"]
                            for branch in combo
                            for source in branch_sources[branch]
                        }
                    )
                    > 1
                    else branch_sources[combo[0]][0]["person"]
                )
                classification, description = BaZiRules._classify_combined_event(
                    event_type="three_harmony",
                    result_element=element.value,
                    affected_elements=[
                        BRANCH_ELEMENTS[branch][0].value for branch in combo
                    ],
                    structure_profile1=structure_profile1,
                    structure_profile2=structure_profile2,
                )
                _append_event(
                    {
                        "type": "three_harmony",
                        "label": f"{''.join(combo)}三合{element.value}局",
                        "branches": list(combo),
                        "result_element": element.value,
                        "source_map": {
                            branch: branch_sources[branch] for branch in combo
                        },
                        "source_scope": source_scope,
                        "classification": classification,
                        "description": description,
                    }
                )
            elif membership == "peak_pair":
                classification, description = BaZiRules._classify_combined_event(
                    event_type="half_harmony",
                    result_element=element.value,
                    affected_elements=[
                        BRANCH_ELEMENTS[branch][0].value for branch in present_branches
                    ],
                    structure_profile1=structure_profile1,
                    structure_profile2=structure_profile2,
                )
                _append_event(
                    {
                        "type": "half_harmony",
                        "label": f"{''.join(present_branches)}半合{element.value}局",
                        "branches": present_branches,
                        "result_element": element.value,
                        "source_map": {
                            branch: branch_sources[branch]
                            for branch in present_branches
                        },
                        "source_scope": (
                            "cross_person"
                            if len(
                                {
                                    source["person"]
                                    for branch in present_branches
                                    for source in branch_sources[branch]
                                }
                            )
                            > 1
                            else branch_sources[present_branches[0]][0]["person"]
                        ),
                        "classification": classification,
                        "description": description,
                    }
                )

        for pair in BRANCH_HARMONY_PAIRS:
            if branch_sources.get(pair[0]) and branch_sources.get(pair[1]):
                result_element = BRANCH_COMBINATION_ELEMENT[frozenset(pair)].value
                classification, description = BaZiRules._classify_combined_event(
                    event_type="six_harmony",
                    result_element=result_element,
                    affected_elements=[
                        BRANCH_ELEMENTS[pair[0]][0].value,
                        BRANCH_ELEMENTS[pair[1]][0].value,
                    ],
                    structure_profile1=structure_profile1,
                    structure_profile2=structure_profile2,
                )
                _append_event(
                    {
                        "type": "six_harmony",
                        "label": f"{pair[0]}{pair[1]}六合",
                        "branches": list(pair),
                        "result_element": result_element,
                        "source_map": {
                            pair[0]: branch_sources[pair[0]],
                            pair[1]: branch_sources[pair[1]],
                        },
                        "source_scope": (
                            "cross_person"
                            if len(
                                {
                                    source["person"]
                                    for branch in pair
                                    for source in branch_sources[branch]
                                }
                            )
                            > 1
                            else branch_sources[pair[0]][0]["person"]
                        ),
                        "classification": classification,
                        "description": description,
                    }
                )

        conflict_pairs = [
            ("six_clash", BRANCH_CLASH_PAIRS, "六冲"),
            ("six_harm", BRANCH_HARM_PAIRS, "六害"),
        ]
        for event_type, pair_list, label_suffix in conflict_pairs:
            for pair in pair_list:
                if branch_sources.get(pair[0]) and branch_sources.get(pair[1]):
                    affected_elements = [
                        BRANCH_ELEMENTS[pair[0]][0].value,
                        BRANCH_ELEMENTS[pair[1]][0].value,
                    ]
                    classification, description = BaZiRules._classify_combined_event(
                        event_type=event_type,
                        result_element=None,
                        affected_elements=affected_elements,
                        structure_profile1=structure_profile1,
                        structure_profile2=structure_profile2,
                    )
                    _append_event(
                        {
                            "type": event_type,
                            "label": f"{pair[0]}{pair[1]}{label_suffix}",
                            "branches": list(pair),
                            "result_element": None,
                            "source_map": {
                                pair[0]: branch_sources[pair[0]],
                                pair[1]: branch_sources[pair[1]],
                            },
                            "source_scope": (
                                "cross_person"
                                if len(
                                    {
                                        source["person"]
                                        for branch in pair
                                        for source in branch_sources[branch]
                                    }
                                )
                                > 1
                                else branch_sources[pair[0]][0]["person"]
                            ),
                            "classification": classification,
                            "description": description,
                        }
                    )

        combined_branches = [entry["branch"] for entry in combined_entries]
        for punishment_set in BRANCH_PUNISHMENT_GROUPS:
            if len(punishment_set) == 3 and all(
                branch in combined_branches for branch in punishment_set
            ):
                affected_elements = [
                    BRANCH_ELEMENTS[branch][0].value for branch in punishment_set
                ]
                classification, description = BaZiRules._classify_combined_event(
                    event_type="three_punishment",
                    result_element=None,
                    affected_elements=affected_elements,
                    structure_profile1=structure_profile1,
                    structure_profile2=structure_profile2,
                )
                _append_event(
                    {
                        "type": "three_punishment",
                        "label": f"{''.join(punishment_set)}三刑",
                        "branches": list(punishment_set),
                        "result_element": None,
                        "source_map": {
                            branch: branch_sources[branch] for branch in punishment_set
                        },
                        "source_scope": (
                            "cross_person"
                            if len(
                                {
                                    source["person"]
                                    for branch in punishment_set
                                    for source in branch_sources[branch]
                                }
                            )
                            > 1
                            else branch_sources[punishment_set[0]][0]["person"]
                        ),
                        "classification": classification,
                        "description": description,
                    }
                )

        day_stem1, day_branch1 = pillars1["day"]
        day_stem2, day_branch2 = pillars2["day"]
        day_element1 = STEM_ELEMENTS[day_stem1][0].value
        day_element2 = STEM_ELEMENTS[day_stem2][0].value
        day_element_enum1 = STEM_ELEMENTS[day_stem1][0]
        day_element_enum2 = STEM_ELEMENTS[day_stem2][0]
        stem_control = (
            DESTRUCTION_CYCLE[day_element_enum1] == day_element_enum2
            or DESTRUCTION_CYCLE[day_element_enum2] == day_element_enum1
        )
        branch_clash = any(
            (day_branch1 == left and day_branch2 == right)
            or (day_branch1 == right and day_branch2 == left)
            for left, right in BRANCH_CLASH_PAIRS
        )
        if stem_control and branch_clash:
            avoid1 = set((structure_profile1 or {}).get("avoid_elements", []))
            avoid2 = set((structure_profile2 or {}).get("avoid_elements", []))
            classification = (
                "risk"
                if day_element2 in avoid1 and day_element1 in avoid2
                else "tension"
            )
            _append_event(
                {
                    "type": "tian_ke_di_chong",
                    "label": "天克地冲",
                    "branches": [day_branch1, day_branch2],
                    "result_element": None,
                    "source_map": {
                        day_branch1: [
                            {"person": "person1", "pillar": "day", "stem": day_stem1}
                        ],
                        day_branch2: [
                            {"person": "person2", "pillar": "day", "stem": day_stem2}
                        ],
                    },
                    "source_scope": "cross_person",
                    "classification": classification,
                    "description": "日干存在相克、日支同时六冲，属于高吸引与高摩擦并存的张力型关系。",
                }
            )

        return {
            "events": events,
            "supportive_patterns": supportive_patterns,
            "tension_patterns": tension_patterns,
            "risk_patterns": risk_patterns,
            "unresolved_patterns": unresolved_patterns,
        }

    @staticmethod
    def calculate_compatibility_score(
        pillars1: Dict[str, Tuple[str, str]], pillars2: Dict[str, Tuple[str, str]]
    ) -> Dict[str, Any]:
        """Calculate basic compatibility score between two BaZi charts."""
        compatibility: Dict[str, Any] = {
            "harmony_score": 0,
            "clash_score": 0,
            "overall_score": 0,
            "details": [],
        }

        # Extract branches by pillar position so details can name which
        # pillar of each person is being matched (avoids "巳与申六合 x4"
        # deduped output that hides whether each hit is a real new match
        # or just a display repeat).
        pillar_keys = ("year", "month", "day", "hour")
        pillar_labels = {"year": "年", "month": "月", "day": "日", "hour": "时"}
        branches1 = [(pk, pillars1[pk][1]) for pk in pillar_keys if pk in pillars1]
        branches2 = [(pk, pillars2[pk][1]) for pk in pillar_keys if pk in pillars2]

        for pk1, b1 in branches1:
            for pk2, b2 in branches2:
                for harmony_pair in BRANCH_HARMONY_PAIRS:
                    if (b1, b2) in [harmony_pair, harmony_pair[::-1]]:
                        compatibility["harmony_score"] += 2
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六合"
                        )

                for clash_pair in BRANCH_CLASH_PAIRS:
                    if (b1, b2) in [clash_pair, clash_pair[::-1]]:
                        compatibility["clash_score"] += 2
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六冲"
                        )

                # Check six harm (一方对二方某支相害；视为轻度减分)
                for harm_pair in BRANCH_HARM_PAIRS:
                    if (b1, b2) in [harm_pair, harm_pair[::-1]]:
                        compatibility["clash_score"] += 1
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六害"
                        )

                # Use the same peak-required pair convention as natal facts,
                # the force ledger and candidate inventory. End pairs are arches.
                for triple in BRANCH_TRIPLE_COMBINATIONS:
                    if classify_triple_members(triple, (b1, b2)) == "peak_pair":
                        pair = tuple(sorted((b1, b2)))
                        key = ("half_harmony", pk1, pk2, pair)
                        if key not in compatibility.setdefault("_half_seen", set()):
                            compatibility["_half_seen"].add(key)
                            compatibility["harmony_score"] += 3
                            compatibility["details"].append(
                                f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：半合{triple[0]}{triple[1]}{triple[2]}局"
                            )

        # Cross-chart triple harmony (三合): awarded once per distinct 三合 set
        # that has at least one branch from each person — matches the
        # "合盘构成三刑" convention used by the advanced analyzer.
        branches1_set = {b for _, b in branches1}
        branches2_set = {b for _, b in branches2}
        for triple in BRANCH_TRIPLE_COMBINATIONS:
            required = set(triple)
            covered_by_1 = required & branches1_set
            covered_by_2 = required & branches2_set
            if (
                covered_by_1
                and covered_by_2
                and required <= (covered_by_1 | covered_by_2)
            ):
                compatibility["harmony_score"] += 5
                compatibility["details"].append(f"合盘构成{''.join(triple)}三合")

        # Cross-chart triple punishment (三刑): symmetric reward with 三合.
        for punishment in BRANCH_PUNISHMENT_GROUPS:
            if len(punishment) != 3:
                continue
            required = set(punishment)
            covered_by_1 = required & branches1_set
            covered_by_2 = required & branches2_set
            if (
                covered_by_1
                and covered_by_2
                and required <= (covered_by_1 | covered_by_2)
            ):
                compatibility["clash_score"] += 5
                compatibility["details"].append(f"合盘构成{''.join(punishment)}三刑")

        compatibility.pop("_half_seen", None)

        # Check day pillar compatibility (most important)
        day_stem1, day_branch1 = pillars1["day"]
        day_stem2, day_branch2 = pillars2["day"]

        # Day branch harmony/clash has higher weight
        for harmony_pair in BRANCH_HARMONY_PAIRS:
            if (day_branch1, day_branch2) in [harmony_pair, harmony_pair[::-1]]:
                compatibility["harmony_score"] += 5
                compatibility["details"].append(
                    f"日支{day_branch1}与{day_branch2}六合(重要)"
                )

        for clash_pair in BRANCH_CLASH_PAIRS:
            if (day_branch1, day_branch2) in [clash_pair, clash_pair[::-1]]:
                compatibility["clash_score"] += 5
                compatibility["details"].append(
                    f"日支{day_branch1}与{day_branch2}六冲(重要)"
                )

        compatibility["overall_score"] = (
            compatibility["harmony_score"] - compatibility["clash_score"]
        )

        if compatibility["overall_score"] >= 8:
            compatibility["level"] = "非常匹配"
        elif compatibility["overall_score"] >= 4:
            compatibility["level"] = "比较匹配"
        elif compatibility["overall_score"] >= 0:
            compatibility["level"] = "一般匹配"
        elif compatibility["overall_score"] >= -4:
            compatibility["level"] = "需要磨合"
        else:
            compatibility["level"] = "不太匹配"

        return compatibility
