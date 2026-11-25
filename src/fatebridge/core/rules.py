"""
BaZi rules and pattern analysis.
"""

from typing import Any, Iterable, Literal, Mapping, TypedDict

from fatebridge.core.bazi.bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.classical_candidate_selection import build_candidate_selection
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.useful_elements import resolve_useful_elements
from fatebridge.utils.data import (
    BRANCH_COMBINATION_ELEMENT,
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
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


class StemRelation(TypedDict):
    stems: list[str]
    pillars: list[str]
    name: str


class StemCombination(StemRelation):
    candidate_element: str


class StemPatterns(TypedDict):
    pair_scope: Literal["adjacent_visible_stems"]
    transformation_status: Literal["not_adjudicated"]
    combinations: list[StemCombination]
    clashes: list[StemRelation]
    controls: list[StemRelation]


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
        pillars: dict[str, tuple[str, str]],
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
                else:
                    pass

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
                else:
                    pass

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
                else:
                    pass
            else:
                pass

        return patterns

    @staticmethod
    def _ordered_unique(items: Iterable[str | None]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
            else:
                pass
        return result

    @staticmethod
    def _get_element_enum_by_value(element_value: str) -> Element | None:
        for element_enum in Element:
            if element_enum.value == element_value:
                return element_enum
            else:
                pass
        return None

    @staticmethod
    def _get_generating_element(target: Element) -> Element | None:
        for element_enum, generated in GENERATION_CYCLE.items():
            if generated == target:
                return element_enum
            else:
                pass
        return None

    @staticmethod
    def _get_destroying_element(target: Element) -> Element | None:
        for element_enum, destroyed in DESTRUCTION_CYCLE.items():
            if destroyed == target:
                return element_enum
            else:
                pass
        return None

    @staticmethod
    def _element_for_ten_god(day_stem: str, ten_god: str) -> str | None:
        day_element = STEM_ELEMENTS[day_stem][0]
        if ten_god in {TenGod.COMPARE.value, TenGod.ROB_WEALTH.value}:
            return day_element.value
        else:
            pass
        if ten_god in {TenGod.FOOD_GOD.value, TenGod.HURT_OFFICER.value}:
            return GENERATION_CYCLE[day_element].value
        else:
            pass
        if ten_god in {TenGod.POSITIVE_WEALTH.value, TenGod.PARTIAL_WEALTH.value}:
            return DESTRUCTION_CYCLE[day_element].value
        else:
            pass
        if ten_god in {TenGod.POSITIVE_OFFICER.value, TenGod.SEVEN_KILLER.value}:
            destroying = BaZiRules._get_destroying_element(day_element)
            return destroying.value if destroying else None
        else:
            pass
        if ten_god in {TenGod.POSITIVE_SEAL.value, TenGod.PARTIAL_SEAL.value}:
            generating = BaZiRules._get_generating_element(day_element)
            return generating.value if generating else None
        else:
            pass
        return None

    @staticmethod
    def _derive_ten_gods_from_elements(day_stem: str, elements: list[str]) -> list[str]:
        ten_gods: list[str] = []
        day_element = STEM_ELEMENTS[day_stem][0]
        for element_value in elements:
            element_enum = BaZiRules._get_element_enum_by_value(element_value)
            if element_enum is None:
                continue
            else:
                pass

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
            else:
                pass

        return BaZiRules._ordered_unique(ten_gods)

    @staticmethod
    def _get_significant_gods(
        pillars: dict[str, tuple[str, str]],
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
        else:
            pass

        return significant

    @staticmethod
    def _build_structure_candidates(
        pillars: dict[str, tuple[str, str]],
        day_stem: str,
    ) -> list[dict[str, Any]]:
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

        candidates: list[dict[str, Any]] = []

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
        else:
            pass

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
        else:
            pass

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
        else:
            pass

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
        else:
            pass

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
        else:
            pass

        for candidate in candidates:
            candidate["formation_status"] = "candidate_only"
        candidates.sort(key=lambda item: item["priority"], reverse=True)
        return candidates

    @staticmethod
    def _describe_day_master_impact(
        day_element_value: str,
        result_element_value: str | None,
    ) -> str:
        if not result_element_value:
            return "主要体现为气机扰动，需要结合被触动的五行再看。"
        else:
            pass

        day_element = BaZiRules._get_element_enum_by_value(day_element_value)
        result_element = BaZiRules._get_element_enum_by_value(result_element_value)
        if day_element is None or result_element is None:
            return "对日主影响需要结合五行关系进一步判断。"
        else:
            pass

        if day_element == result_element:
            return f"{result_element_value}与日主同气，助身增势。"
        else:
            pass
        if GENERATION_CYCLE[result_element] == day_element:
            return f"{result_element_value}生日主，对日主有补益作用。"
        else:
            pass
        if GENERATION_CYCLE[day_element] == result_element:
            return f"日主之气流向{result_element_value}，更偏向泄秀或输出。"
        else:
            pass
        if DESTRUCTION_CYCLE[result_element] == day_element:
            return f"{result_element_value}克日主，带来约束与压力。"
        else:
            pass
        if DESTRUCTION_CYCLE[day_element] == result_element:
            return f"日主可制{result_element_value}，更利于驾驭资源或对象。"
        else:
            pass
        return "与日主关系中性，需要结合全局判断。"

    @staticmethod
    def _describe_structure_impact(
        result_element_value: str | None,
        structure_profile: dict[str, Any],
        affected_elements: list[str] | None = None,
    ) -> str:
        dominant = structure_profile.get("dominant_structure", {}) or {}
        structure_label = dominant.get("label", "当前格局")
        useful_elements = set(structure_profile.get("useful_elements", []))
        avoid_elements = set(structure_profile.get("avoid_elements", []))

        if result_element_value:
            if result_element_value in useful_elements:
                return f"{result_element_value}属于{structure_label}可用之气，对格局流通有支持。"
            else:
                pass
            if result_element_value in avoid_elements:
                return f"{result_element_value}属于{structure_label}需回避之气，对格局流通有干扰。"
            else:
                pass
            return (
                f"{result_element_value}对{structure_label}影响中性，需结合全局衡量。"
            )
        else:
            pass

        affected = set(affected_elements or [])
        if useful_elements & affected:
            return f"事件触动了{structure_label}的可用五行，格局稳定性需要重点观察。"
        else:
            pass
        if avoid_elements & affected:
            return f"事件触动了{structure_label}的忌避五行，既可能化解也可能放大张力。"
        else:
            pass
        return f"事件对{structure_label}形成扰动，偏向张力型影响。"

    @staticmethod
    def build_structure_profile(
        pillars: dict[str, tuple[str, str]],
        element_analysis: dict[str, Any],
        harmony_patterns: Mapping[str, object] | None = None,
        clash_patterns: Mapping[str, object] | None = None,
        special_patterns: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
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
        month_uses = candidate_selection["month_use_resolution"]
        month_description = (
            "；".join(w["label"] for w in month_uses["witnesses"])
            or "暂无已建模取用见证"
        )
        month_reason = f"月令{selected_month['branch']}：{month_description}；见证并存不等于成格、喜忌或最终取用已定。"
        dominant_structure = {
            "key": "month_use_reference",
            "label": "月令取用见证参考",
            "formation_status": "not_adjudicated",
            "reason": month_reason,
            "useful_elements": [],
            "avoid_elements": [],
            "useful_ten_gods": [],
        }
        secondary_structures = recognized_structures
        decision_basis = [
            month_reason,
            f"工程扶抑模型判为{day_strength}；身、印及食财官杀的相对力量另列待判条件。",
            "原典取用路径按月令分列，未由十神共现或固定优先级选定；旧优先候选仅供追溯。",
        ]
        if (
            month_uses["policy_scope"] != "miscellaneous_qi_source"
            and selected_month["basis_status"] == "original_and_selected_differ"
        ):
            decision_basis.append(
                f"月令本气为{selected_month['original_main_qi']['ten_god']}，当前有限规则所选为{selected_month['ten_god']}；是否变格、兼格仍待裁定，不以透干即抹去本气。"
            )
        else:
            pass

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
        else:
            pass
        useful_elements = resolution["useful_elements"]
        avoid_elements = resolution["avoid_elements"]
        useful_ten_gods = BaZiRules._derive_ten_gods_from_elements(
            day_stem, useful_elements
        )
        decision_basis.append(
            "扶抑、原典待判路径、旧共现候选与调候分层保留；未裁定的旧候选不单独授予全局喜忌，未入喜不自动为忌。"
        )
        structure_profile: dict[str, Any] = {
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
            else:
                pass

        structure_profile["decision_basis"] = BaZiRules._ordered_unique(decision_basis)
        return structure_profile

    @staticmethod
    def chart_useful_profile(pillars: dict[str, tuple[str, str]]) -> dict[str, Any]:
        """Use the same layered resolver in birth and specialty analyses."""
        return BaZiRules.build_structure_profile(
            pillars, ElementAnalysis.comprehensive_analysis(pillars)
        )

    @staticmethod
    def analyze_harmony_effects(
        pillars: dict[str, tuple[str, str]],
        structure_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        harmony_patterns = check_harmony_patterns(pillars)
        clash_patterns = check_clash_patterns(pillars)

        day_stem = pillars["day"][0]
        day_element = STEM_ELEMENTS[day_stem][0].value
        useful_elements = set(structure_profile.get("useful_elements", []))
        avoid_elements = set(structure_profile.get("avoid_elements", []))
        events: list[dict[str, Any]] = []

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
