"""
BaZi rules and pattern analysis.
"""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..utils.data import (
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    EARTHLY_BRANCHES,
    GENERATION_CYCLE,
    HEAVENLY_STEMS,
    STEM_ELEMENTS,
    Element,
    TenGod,
    get_ten_god,
)
from .useful_elements import resolve_useful_elements


class BaZiRules:
    """Analyzes special patterns and rules in BaZi charts."""

    TRIPLE_HARMONY_ELEMENTS = {
        ("申", "子", "辰"): Element.WATER,
        ("亥", "卯", "未"): Element.WOOD,
        ("寅", "午", "戌"): Element.FIRE,
        ("巳", "酉", "丑"): Element.METAL,
    }

    SIX_HARMONY_ELEMENTS = {
        frozenset(("子", "丑")): Element.EARTH,
        frozenset(("寅", "亥")): Element.WOOD,
        frozenset(("卯", "戌")): Element.FIRE,
        frozenset(("辰", "酉")): Element.METAL,
        frozenset(("巳", "申")): Element.WATER,
        frozenset(("午", "未")): Element.EARTH,
    }

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

    # 地支三合 (Triple Harmony)
    TRIPLE_HARMONY = [
        ("申", "子", "辰"),  # 水局
        ("亥", "卯", "未"),  # 木局
        ("寅", "午", "戌"),  # 火局
        ("巳", "酉", "丑"),  # 金局
    ]

    # 地支六合 (Six Harmony)
    SIX_HARMONY = [
        ("子", "丑"),
        ("寅", "亥"),
        ("卯", "戌"),
        ("辰", "酉"),
        ("巳", "申"),
        ("午", "未"),
    ]

    # 地支六冲 (Six Clash)
    SIX_CLASH = [
        ("子", "午"),
        ("丑", "未"),
        ("寅", "申"),
        ("卯", "酉"),
        ("辰", "戌"),
        ("巳", "亥"),
    ]

    # 地支六害 (Six Harm)
    SIX_HARM = [
        ("子", "未"),
        ("丑", "午"),
        ("寅", "巳"),
        ("卯", "辰"),
        ("申", "亥"),
        ("酉", "戌"),
    ]

    # 地支三刑 (Triple Punishment)
    TRIPLE_PUNISHMENT = [
        ("寅", "巳", "申"),  # 无恩之刑
        ("丑", "戌", "未"),  # 恃势之刑
        ("子", "卯"),  # 无礼之刑
        ("辰",),
        ("午",),
        ("酉",),
        ("亥",),  # 自刑
    ]

    # 天干五合 (Heavenly Stems Combinations)
    STEM_COMBINATIONS = [
        ("甲", "己", "土"),  # 中正之合
        ("乙", "庚", "金"),  # 仁义之合
        ("丙", "辛", "水"),  # 威制之合
        ("丁", "壬", "木"),  # 淫匿之合
        ("戊", "癸", "火"),  # 无情之合
    ]

    # 天干四冲 (Heavenly Stems Clashes)
    STEM_CLASHES = [
        ("甲", "庚"),
        ("乙", "辛"),
        ("丙", "壬"),
        ("丁", "癸"),
    ]

    # 地支拱局 (Arch Combinations)
    # (Branch1, Branch2, Arched_Branch, Element, Related_Stem)
    ARCH_COMBINATIONS = [
        ("寅", "辰", "卯", "木", "乙"),  # 拱东方木
        ("巳", "未", "午", "火", "丁"),  # 拱南方火
        ("申", "戌", "酉", "金", "辛"),  # 拱西方金
        ("亥", "丑", "子", "水", "癸"),  # 拱北方水
    ]

    # 地支暗合 (Dark Combinations)
    # 一般指地支藏干相合
    DARK_COMBINATIONS = [
        ("子", "巳"),  # 癸-戊
        ("寅", "丑"),  # 甲-己, 丙-辛
        ("午", "亥"),  # 丁-壬, 己-甲
        ("卯", "申"),  # 乙-庚
        ("子", "辰"),  # 癸-戊 (Special case mentioned by user)
    ]

    # 四驿马 (Four Horses / Four Travels) - 生
    FOUR_HORSES = ["寅", "申", "巳", "亥"]

    # 四正 (Four Cardinals / Four Peaches) - 旺
    FOUR_CARDINALS = ["子", "午", "卯", "酉"]

    # 四库 (Four Treasuries / Four Graves) - 墓
    FOUR_TREASURIES = ["辰", "戌", "丑", "未"]

    @staticmethod
    def check_harmony_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Any]]:
        """Check for harmony patterns in the chart."""
        all_branches = [pillar_branch for _, pillar_branch in pillars.values()]
        harmony_patterns: Dict[str, List[Any]] = {
            "three_harmony": [],
            "half_harmony": [],
            "six_harmony": [],
        }

        # Check triple harmony and half harmony
        for triple_harmony_set in BaZiRules.TRIPLE_HARMONY:
            found_branches_in_set = [
                branch for branch in triple_harmony_set if branch in all_branches
            ]

            element_mapping = {
                ("申", "子", "辰"): "水局",
                ("亥", "卯", "未"): "木局",
                ("寅", "午", "戌"): "火局",
                ("巳", "酉", "丑"): "金局",
            }
            base_type = element_mapping[triple_harmony_set]

            if len(found_branches_in_set) == 3:
                harmony_patterns["three_harmony"].append(
                    {
                        "type": f"三合{base_type}",
                        "branches": found_branches_in_set,
                        "complete": True,
                    }
                )
            elif len(found_branches_in_set) == 2:
                # 半合 requires the 旺神 (中神 / cardinal of the set, e.g. 午 in
                # 寅午戌) to be present — a pair such as 寅戌 (no 午) does NOT
                # form a half-combination.
                cardinal = next(
                    branch
                    for branch in triple_harmony_set
                    if branch in BaZiRules.FOUR_CARDINALS
                )
                if cardinal in found_branches_in_set:
                    harmony_patterns["half_harmony"].append(
                        {
                            "type": f"半合{base_type}",
                            "branches": found_branches_in_set,
                            "complete": False,
                        }
                    )

        # Check six harmony
        for six_harmony_pair in BaZiRules.SIX_HARMONY:
            if all(branch in all_branches for branch in six_harmony_pair):
                harmony_patterns["six_harmony"].append(list(six_harmony_pair))

        return harmony_patterns

    @staticmethod
    def check_clash_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, Any]:
        """Check for clash patterns in the chart."""
        all_branches = [pillar_branch for _, pillar_branch in pillars.values()]
        clash_patterns: Dict[str, Any] = {
            "six_clash": [],
            "six_harm": [],
            "punishments": [],  # Unified list for all punishments
        }

        # Check six clash
        for six_clash_pair in BaZiRules.SIX_CLASH:
            if all(branch in all_branches for branch in six_clash_pair):
                clash_patterns["six_clash"].append(list(six_clash_pair))

        # Check six harm
        for six_harm_pair in BaZiRules.SIX_HARM:
            if all(branch in all_branches for branch in six_harm_pair):
                clash_patterns["six_harm"].append(list(six_harm_pair))

        # Check punishments
        # 1. Triple Punishments (寅巳申, 丑戌未)
        for punishment_set in BaZiRules.TRIPLE_PUNISHMENT:
            if len(punishment_set) == 3:
                found_branches = [b for b in punishment_set if b in all_branches]

                # Full Triple Punishment
                if len(found_branches) == 3:
                    name_map = {
                        ("寅", "巳", "申"): "无恩之刑",
                        ("丑", "戌", "未"): "恃势之刑",
                    }
                    name = name_map.get(punishment_set, "三刑")
                    clash_patterns["punishments"].append(
                        {
                            "name": name,
                            "type": "three_punishment",
                            "branches": found_branches,
                        }
                    )

                # Partial Punishment (Pairs within the set)
                elif len(found_branches) == 2:
                    # Specific pairs logic
                    # 寅巳: Harm + Punishment
                    # 巳申: Harmony + Punishment
                    # 寅申: Clash + Punishment
                    # 丑戌: Punishment
                    # 戌未: Punishment
                    # 丑未: Clash

                    b1, b2 = found_branches[0], found_branches[1]
                    pair_name = f"{b1}{b2}相刑"

                    # Filter out if it's purely a Clash (usually Clash overrides Punishment in nomenclature)
                    # But for completeness we can list it, or filter.
                    # Let's keep it but mark as 'pair_punishment'
                    clash_patterns["punishments"].append(
                        {
                            "name": pair_name,
                            "type": "pair_punishment",
                            "branches": found_branches,
                        }
                    )

            # 2. Rude Punishment (子卯)
            elif len(punishment_set) == 2:
                if all(branch in all_branches for branch in punishment_set):
                    clash_patterns["punishments"].append(
                        {
                            "name": "无礼之刑",
                            "type": "pair_punishment",
                            "branches": list(punishment_set),
                        }
                    )

            # 3. Self Punishment (辰, 午, 酉, 亥)
            elif len(punishment_set) == 1:
                punishment_branch = punishment_set[0]
                branch_count = all_branches.count(punishment_branch)
                if branch_count >= 2:
                    clash_patterns["punishments"].append(
                        {
                            "name": f"{punishment_branch}{punishment_branch}自刑",
                            "type": "self_punishment",
                            "branches": [punishment_branch] * branch_count,
                        }
                    )

        return clash_patterns

    @staticmethod
    def check_stem_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check for Heavenly Stem patterns (Combinations, Clashes, Control)."""
        stems = {k: v[0] for k, v in pillars.items()}  # position -> stem
        patterns: Dict[str, List[Dict[str, Any]]] = {
            "combinations": [],
            "clashes": [],
            "controls": [],
        }

        pillar_names = ["year", "month", "day", "hour"]

        # Check adjacent pairs only (Year-Month, Month-Day, Day-Hour)
        # This reflects the rule that stems must be adjacent to interact significantly.
        for i in range(len(pillar_names) - 1):
            p1, p2 = pillar_names[i], pillar_names[i + 1]
            s1, s2 = stems[p1], stems[p2]

            # Combinations
            for c1, c2, transform in BaZiRules.STEM_COMBINATIONS:
                if (s1 == c1 and s2 == c2) or (s1 == c2 and s2 == c1):
                    patterns["combinations"].append(
                        {
                            "stems": [s1, s2],
                            "pillars": [p1, p2],
                            "transform": transform,
                            "name": f"{s1}{s2}合化{transform}",
                        }
                    )

            # Clashes (Chong)
            for c1, c2 in BaZiRules.STEM_CLASHES:
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
                for x, y in BaZiRules.STEM_CLASHES
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
    def check_hidden_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check for Hidden/Dark/Arch patterns."""
        branches = {k: v[1] for k, v in pillars.items()}
        stems = [v[0] for v in pillars.values()]  # All stems for Arch check
        patterns: Dict[str, List[Dict[str, Any]]] = {
            "arch_combinations": [],  # 拱局
            "dark_combinations": [],  # 暗合
        }

        pillar_names = ["year", "month", "day", "hour"]

        # Arch Combinations (Gong)
        for i in range(len(pillar_names)):
            for j in range(i + 1, len(pillar_names)):
                p1, p2 = pillar_names[i], pillar_names[j]
                b1, b2 = branches[p1], branches[p2]

                for (
                    start,
                    end,
                    arched,
                    element,
                    related_stem,
                ) in BaZiRules.ARCH_COMBINATIONS:
                    if (b1 == start and b2 == end) or (b1 == end and b2 == start):
                        # Found an arch pair
                        entry = {
                            "branches": [b1, b2],
                            "pillars": [p1, p2],
                            "arched": arched,
                            "type": f"拱{element}",
                            "is_enhanced": False,
                        }
                        # Check if related stem is present (Dark Three Meeting)
                        if related_stem in stems:
                            entry["is_enhanced"] = True
                            entry["name"] = (
                                f"{b1}{b2}见{related_stem}暗拱三会{element}局"
                            )
                        else:
                            entry["name"] = f"{b1}{b2}拱{arched}"

                        patterns["arch_combinations"].append(entry)

        # Dark Combinations (An He)
        for i in range(len(pillar_names)):
            for j in range(i + 1, len(pillar_names)):
                p1, p2 = pillar_names[i], pillar_names[j]
                b1, b2 = branches[p1], branches[p2]

                for db1, db2 in BaZiRules.DARK_COMBINATIONS:
                    if (b1 == db1 and b2 == db2) or (b1 == db2 and b2 == db1):
                        patterns["dark_combinations"].append(
                            {
                                "branches": [b1, b2],
                                "pillars": [p1, p2],
                                "name": f"{b1}{b2}暗合",
                            }
                        )

        return patterns

    @staticmethod
    def check_pillar_patterns(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check for single pillar patterns (Gaito, Jiejiao, Fu, Zai)."""
        patterns: Dict[str, List[Dict[str, Any]]] = {
            "gai_tou": [],  # Stem controls Branch (盖头)
            "jie_jiao": [],  # Branch controls Stem (截脚)
            "fu": [],  # Stem generates Branch (覆 - 天生均)
            "zai": [],  # Branch generates Stem (载 - 地生天)
            "tong": [],  # Same Element (比和 - 天地同气)
        }

        for name, (stem, branch) in pillars.items():
            stem_elem = STEM_ELEMENTS[stem][0]
            branch_elem = BRANCH_ELEMENTS[branch][0]

            # Gaito: Stem controls Branch (盖头)
            if DESTRUCTION_CYCLE.get(stem_elem) == branch_elem:
                patterns["gai_tou"].append(
                    {
                        "pillar": name,
                        "stem": stem,
                        "branch": branch,
                        "name": f"{stem}{branch}盖头",
                    }
                )

            # Jie Jiao: Branch controls Stem (截脚)
            elif DESTRUCTION_CYCLE.get(branch_elem) == stem_elem:
                patterns["jie_jiao"].append(
                    {
                        "pillar": name,
                        "stem": stem,
                        "branch": branch,
                        "name": f"{stem}{branch}截脚",
                    }
                )

            # Fu: Stem generates Branch (覆 - 天覆地载之覆)
            elif GENERATION_CYCLE.get(stem_elem) == branch_elem:
                patterns["fu"].append(
                    {
                        "pillar": name,
                        "stem": stem,
                        "branch": branch,
                        "name": f"{stem}{branch}相生(覆)",
                    }
                )

            # Zai: Branch generates Stem (载 - 天覆地载之载)
            elif GENERATION_CYCLE.get(branch_elem) == stem_elem:
                patterns["zai"].append(
                    {
                        "pillar": name,
                        "stem": stem,
                        "branch": branch,
                        "name": f"{stem}{branch}相生(载)",
                    }
                )

            # Tong: Same Element (比和)
            elif stem_elem == branch_elem:
                patterns["tong"].append(
                    {
                        "pillar": name,
                        "stem": stem,
                        "branch": branch,
                        "name": f"{stem}{branch}比和",
                    }
                )

        return patterns

    @staticmethod
    def check_fu_yin_fan_yin(
        pillars: Dict[str, Tuple[str, str]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check for Fu Yin (Identical) and Fan Yin (Clashing) Pillars."""
        patterns: Dict[str, List[Dict[str, Any]]] = {
            "fu_yin": [],  # 伏吟 (Same Pillar)
            "fan_yin": [],  # 反吟 (Clashing Pillar: Stem Clash + Branch Clash)
        }

        pillar_names = ["year", "month", "day", "hour"]
        stems = {k: v[0] for k, v in pillars.items()}
        branches = {k: v[1] for k, v in pillars.items()}

        # Check all pairs
        for i in range(len(pillar_names)):
            for j in range(i + 1, len(pillar_names)):
                p1, p2 = pillar_names[i], pillar_names[j]

                # Fu Yin (伏吟): Both Stem and Branch are identical
                if stems[p1] == stems[p2] and branches[p1] == branches[p2]:
                    patterns["fu_yin"].append(
                        {
                            "pillars": [p1, p2],
                            "pillar_content": f"{stems[p1]}{branches[p1]}",
                            "name": f"{p1}{p2}伏吟",
                        }
                    )

                # Fan Yin (反吟): Stem Clashes AND Branch Clashes
                # Stem Clash check
                s1, s2 = stems[p1], stems[p2]
                is_stem_clash = any(
                    (s1 == x and s2 == y) or (s1 == y and s2 == x)
                    for x, y in BaZiRules.STEM_CLASHES
                )

                # Branch Clash check
                b1, b2 = branches[p1], branches[p2]
                is_branch_clash = any(
                    (b1 == x and b2 == y) or (b1 == y and b2 == x)
                    for x, y in BaZiRules.SIX_CLASH
                )

                if is_stem_clash and is_branch_clash:
                    patterns["fan_yin"].append(
                        {
                            "pillars": [p1, p2],
                            "pillar_content": [
                                f"{stems[p1]}{branches[p1]}",
                                f"{stems[p2]}{branches[p2]}",
                            ],
                            "name": f"{p1}{p2}反吟",
                        }
                    )

        return patterns

    @staticmethod
    def analyze_special_patterns(
        pillars: Dict[str, Tuple[str, str]], birth_hour: Optional[int] = None
    ) -> Dict[str, Any]:
        """Analyze special patterns in the BaZi chart."""
        stems = [stem for stem, _ in pillars.values()]
        branches = [branch for _, branch in pillars.values()]

        patterns: Dict[str, Any] = {}

        # Check for special day pillar patterns
        day_stem, day_branch = pillars["day"]

        # 日贵格 (Noble Day Pattern)
        # 正确的日贵格只有四日：丁酉、丁亥、癸巳、癸卯
        day_pillar = f"{day_stem}{day_branch}"
        noble_days = ["丁酉", "丁亥", "癸巳", "癸卯"]

        if day_pillar in noble_days:
            patterns["noble_day"] = True

            # 添加昼夜区分
            if birth_hour is not None:
                # 昼贵：癸卯、丁亥（白天6-18时）
                # 夜贵：癸巳、丁酉（夜晚18-6时）
                is_daytime = 6 <= birth_hour < 18

                if day_pillar in ["癸卯", "丁亥"] and is_daytime:
                    patterns["noble_day_type"] = "昼贵"
                elif day_pillar in ["癸巳", "丁酉"] and not is_daytime:
                    patterns["noble_day_type"] = "夜贵"
                else:
                    patterns["noble_day_type"] = "不合时"

        # 魁罡格 (Kui Gang Pattern)
        kui_gang_days = ["庚戌", "庚辰", "戊戌", "壬辰"]
        if f"{day_stem}{day_branch}" in kui_gang_days:
            patterns["kui_gang"] = True

        # Check stem patterns
        # 四同 (Four Same)
        for stem in HEAVENLY_STEMS:
            if stems.count(stem) == 4:
                patterns["four_same_stems"] = stem

        for branch in EARTHLY_BRANCHES:
            if branches.count(branch) == 4:
                patterns["four_same_branches"] = branch

        # 天干一气 (Heavenly Stems Unity)
        if len(set(stems)) == 1:
            patterns["stem_unity"] = stems[0]

        # 地支一气 (Earthly Branches Unity)
        if len(set(branches)) == 1:
            patterns["branch_unity"] = branches[0]

        # Check for Four Horses, Cardinals, Treasuries
        # 1. Analyze individual branch attributes (per pillar)
        branch_attributes = {}
        for pillar_name, (_, branch) in pillars.items():
            attr_data = {"branch": branch}

            if branch in BaZiRules.FOUR_HORSES:
                attr_data["type"] = "驿马"  # 生地
            elif branch in BaZiRules.FOUR_CARDINALS:
                attr_data["type"] = "四正"  # 旺地
            elif branch in BaZiRules.FOUR_TREASURIES:
                attr_data["type"] = "四库"  # 墓库
            else:
                attr_data["type"] = "未知"

            branch_attributes[pillar_name] = attr_data

        patterns["branch_attributes"] = branch_attributes

        # 2. Count occurrences and check for patterns
        horses_count = sum(1 for b in branches if b in BaZiRules.FOUR_HORSES)
        cardinals_count = sum(1 for b in branches if b in BaZiRules.FOUR_CARDINALS)
        treasuries_count = sum(1 for b in branches if b in BaZiRules.FOUR_TREASURIES)

        # Store counts
        patterns["counts"] = {
            "horses": horses_count,
            "cardinals": cardinals_count,
            "treasuries": treasuries_count,
        }

        # Initialize defaults
        patterns["four_horses_complete"] = False
        patterns["many_horses"] = False
        patterns["all_horses"] = False

        patterns["four_cardinals_complete"] = False
        patterns["many_cardinals"] = False
        patterns["all_cardinals"] = False

        patterns["four_treasuries_complete"] = False
        patterns["many_treasuries"] = False
        patterns["all_treasuries"] = False

        # Check for complete sets (all 4 unique branches present)
        unique_branches = set(branches)
        if all(b in unique_branches for b in BaZiRules.FOUR_HORSES):
            patterns["four_horses_complete"] = True  # 四位纯全 (四驿马)
        elif horses_count >= 3:
            patterns["many_horses"] = True

        if all(b in unique_branches for b in BaZiRules.FOUR_CARDINALS):
            patterns["four_cardinals_complete"] = True  # 四位纯全 (四正)
        elif cardinals_count >= 3:
            patterns["many_cardinals"] = True

        if all(b in unique_branches for b in BaZiRules.FOUR_TREASURIES):
            patterns["four_treasuries_complete"] = True  # 四位纯全 (四库)
        elif treasuries_count >= 3:
            patterns["many_treasuries"] = True

        # Check if all branches belong to one group (Pure)
        if horses_count == 4:
            patterns["all_horses"] = True  # 遍野桃花/四马之地
        if cardinals_count == 4:
            patterns["all_cardinals"] = True  # 四败/四正
        if treasuries_count == 4:
            patterns["all_treasuries"] = True  # 四库

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
                    "reason": f"{day_stem}日主临羊刃{blade_branch}，命局同时见七杀，格局判断优先看驭杀之力。",
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
                    "reason": "命局杀星与印星并见，格局更看杀印流通，而非单纯以官杀为压制。",
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
                    "reason": "命局食神与七杀同见，取食神制杀之路，比单纯官杀压制更关键。",
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
                    "reason": "命局伤官配印，宜看印星承接才气，而不宜只把伤官视为纯负项。",
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
                    "reason": "命局伤官与正官并见，先看张力与化解条件，不能只做简单吉凶判定。",
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
        harmony_patterns: Optional[Dict[str, Any]] = None,
        clash_patterns: Optional[Dict[str, Any]] = None,
        special_patterns: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        day_stem = pillars["day"][0]
        day_strength = element_analysis["day_master"]["strength_level"]
        baseline_useful = list(element_analysis.get("favorable_elements", []))
        baseline_useful_ten_gods = BaZiRules._derive_ten_gods_from_elements(
            day_stem, baseline_useful
        )
        recognized_structures = BaZiRules._build_structure_candidates(pillars, day_stem)

        if recognized_structures:
            dominant_structure = recognized_structures[0]
            secondary_structures = recognized_structures[1:]
            decision_basis = [
                f"识别到高影响格局：{dominant_structure['label']}。",
                dominant_structure["reason"],
                f"基础扶抑判断显示日主为{day_strength}，但本次以格局优先修正喜用。",
            ]
        else:
            dominant_structure = {
                "key": "default_support",
                "label": "扶抑参考",
                "priority": BaZiRules.STRUCTURE_PRIORITIES["default_support"],
                "reason": "未识别高影响白名单格局，按日主强弱与五行扶抑作为主判断。",
                "useful_elements": baseline_useful,
                "avoid_elements": [],
                "useful_ten_gods": baseline_useful_ten_gods,
            }
            secondary_structures = []
            decision_basis = [
                f"未识别高影响白名单格局，当前按日主{day_strength}做扶抑参考。",
            ]

        resolution = resolve_useful_elements(
            pillars, element_analysis, recognized_structures
        )
        useful_elements = resolution["useful_elements"]
        avoid_elements = resolution["avoid_elements"]
        useful_ten_gods = BaZiRules._derive_ten_gods_from_elements(
            day_stem, useful_elements
        )
        decision_basis.append(
            "扶抑、格局候选与调候分层保留；冲突及仅旁证支持的五行列为条件项，未入喜不自动为忌。"
        )
        structure_profile: Dict[str, Any] = {
            **resolution,
            "dominant_structure": dominant_structure,
            "secondary_structures": secondary_structures,
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
                "harmony_patterns": harmony_patterns or {},
                "clash_patterns": clash_patterns or {},
                "special_patterns": special_patterns or {},
            },
        }

        structure_profile["harmony_effects"] = BaZiRules.analyze_harmony_effects(
            pillars, structure_profile
        )

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
        harmony_patterns = BaZiRules.check_harmony_patterns(pillars)
        clash_patterns = BaZiRules.check_clash_patterns(pillars)

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
                    for combo, element in BaZiRules.TRIPLE_HARMONY_ELEMENTS.items()
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
                    for combo, element in BaZiRules.TRIPLE_HARMONY_ELEMENTS.items()
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
            result_element_enum = BaZiRules.SIX_HARMONY_ELEMENTS.get(frozenset(pair))
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
            ("six_clash", "六冲"),
            ("six_harm", "六害"),
        ]
        for group_key, group_label in conflict_groups:
            for pair in clash_patterns.get(group_key, []):
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
            if useful_hits or avoid_hits:
                return "tension", "一方受益而另一方承压，属于拉扯型事件。"
            return "supportive", "整体偏和合，可作为合盘支持因素。"

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
            else:
                tension_patterns.append(summary)

        for combo, element in BaZiRules.TRIPLE_HARMONY_ELEMENTS.items():
            present_branches = [
                branch for branch in combo if branch_sources.get(branch)
            ]
            if len(present_branches) == 3:
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
            elif len(present_branches) == 2:
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

        for pair in BaZiRules.SIX_HARMONY:
            if branch_sources.get(pair[0]) and branch_sources.get(pair[1]):
                result_element = BaZiRules.SIX_HARMONY_ELEMENTS[frozenset(pair)].value
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
            ("six_clash", BaZiRules.SIX_CLASH, "六冲"),
            ("six_harm", BaZiRules.SIX_HARM, "六害"),
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
        for punishment_set in BaZiRules.TRIPLE_PUNISHMENT:
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
            for left, right in BaZiRules.SIX_CLASH
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

        # Check harmony between charts
        for pk1, b1 in branches1:
            for pk2, b2 in branches2:
                # Check six harmony
                for harmony_pair in BaZiRules.SIX_HARMONY:
                    if (b1, b2) in [harmony_pair, harmony_pair[::-1]]:
                        compatibility["harmony_score"] += 2
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六合"
                        )

                # Check six clash
                for clash_pair in BaZiRules.SIX_CLASH:
                    if (b1, b2) in [clash_pair, clash_pair[::-1]]:
                        compatibility["clash_score"] += 2
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六冲"
                        )

                # Check six harm (一方对二方某支相害；视为轻度减分)
                for harm_pair in BaZiRules.SIX_HARM:
                    if (b1, b2) in [harm_pair, harm_pair[::-1]]:
                        compatibility["clash_score"] += 1
                        compatibility["details"].append(
                            f"一方{pillar_labels[pk1]}支{b1} × 二方{pillar_labels[pk2]}支{b2}：六害"
                        )

                # Check half-harmony (two branches of a triple-harmony set that
                # belong to the same group). A full 三合 built across both
                # charts is detected further below; here we reward any 2-branch
                # overlap that would otherwise be invisible.
                for triple in BaZiRules.TRIPLE_HARMONY:
                    if b1 in triple and b2 in triple and b1 != b2:
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
        for triple in BaZiRules.TRIPLE_HARMONY:
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
        for punishment in BaZiRules.TRIPLE_PUNISHMENT:
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
        for harmony_pair in BaZiRules.SIX_HARMONY:
            if (day_branch1, day_branch2) in [harmony_pair, harmony_pair[::-1]]:
                compatibility["harmony_score"] += 5
                compatibility["details"].append(
                    f"日支{day_branch1}与{day_branch2}六合(重要)"
                )

        for clash_pair in BaZiRules.SIX_CLASH:
            if (day_branch1, day_branch2) in [clash_pair, clash_pair[::-1]]:
                compatibility["clash_score"] += 5
                compatibility["details"].append(
                    f"日支{day_branch1}与{day_branch2}六冲(重要)"
                )

        # Calculate overall score
        compatibility["overall_score"] = (
            compatibility["harmony_score"] - compatibility["clash_score"]
        )

        # Determine compatibility level
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
