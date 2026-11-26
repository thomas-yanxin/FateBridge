"""Positioned pillar facts, separate from formation and force judgments."""

from itertools import combinations
from typing import Literal, Mapping, TypedDict

from fatebridge.utils.data import (
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_TRIPLE_COMBINATIONS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    STEM_FOUR_CLASHES,
    Element,
)

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")
BranchGroup = Literal["四生", "四正", "四库"]
ElementRelation = Literal[
    "same_element", "generates", "generated_by", "controls", "controlled_by"
]


class PatternSource(TypedDict):
    id: str
    author: str
    title: str
    edition: str
    locator: str


SOURCES: tuple[PatternSource, ...] = (
    {
        "id": "sanming_siku_branch_relations",
        "author": "万民英",
        "title": "三命通会·论支元六合、论支元三合",
        "edition": "四库全书本，维基文库固定转录 oldid=761691",
        "locator": "卷二；广录五组禄位藏干往来与三合缺字条文",
    },
    {
        "id": "sanming_siku_arch",
        "author": "万民英",
        "title": "三命通会·拱禄拱贵",
        "edition": "景印文渊阁四库全书第810册",
        "locator": "卷六；扫描304–305／影印299–300页",
    },
    {
        "id": "sanming_siku_special_days",
        "author": "万民英",
        "title": "三命通会·日贵、魁罡、四位纯全、一气生成",
        "edition": "景印文渊阁四库全书第810册及固定转录 oldid=657375",
        "locator": "卷六；扫描310–312、324–326；只取名单、分类，不采用人生断语",
    },
    {
        "id": "sanming_siku_noble_time_variants",
        "author": "万民英",
        "title": "三命通会·论天乙贵人",
        "edition": "四库全书本，维基文库固定转录 oldid=657369",
        "locator": "卷三；冬夏阴阳、寅申及日出入等读法并列，不据此认证6–18时",
    },
)

PILLAR_SOURCES: tuple[PatternSource, ...] = (
    {
        "id": "lunar_python_literal_pillar_tables",
        "author": "6tail",
        "title": "lunar-python LunarUtil 五行、藏干、地支冲与天干四冲表",
        "edition": "1.4.9",
        "locator": "WU_XING_GAN、WU_XING_ZHI、ZHI_HIDE_GAN、CHONG、CHONG_GAN_4；非其他冲表",
    },
    {
        "id": "ditian1947_column_relation_scope",
        "author": "任鐵樵增注，李雨田校訂",
        "title": "任注滴天髓闡微·干支總論、順局、歲運",
        "edition": "上海大東書局經售，1947年4月初版",
        "locator": "PDF101、391、503–504；盖头可涉及支中藏干，天覆地载不等于两类单柱生助",
    },
)


class HiddenElementRelation(TypedDict):
    stem: str
    hidden_rank: int
    element: str
    relation: ElementRelation


class PillarElementRelations(TypedDict):
    pillar: str
    stem: str
    branch: str
    stem_element: str
    principal_branch_element: str
    principal_relation: ElementRelation
    hidden_relations: list[HiddenElementRelation]


class PillarRelationships(TypedDict):
    method_id: Literal["bazi_column_element_facts_v1"]
    rulesets: list[PatternSource]
    pillars: list[PillarElementRelations]
    scope: str


class PillarPair(TypedDict):
    pillars: list[str]
    pillar_content: list[str]
    identical: bool
    branch_six_clash: bool
    stem_four_clash: bool
    stem_relation: ElementRelation


class PillarPairRelationships(TypedDict):
    method_id: Literal["bazi_pillar_pair_facts_v1"]
    rulesets: list[PatternSource]
    pairs: list[PillarPair]
    scope: str


def _element_relation(left: Element, right: Element) -> ElementRelation:
    if left == right:
        return "same_element"
    if GENERATION_CYCLE[left] == right:
        return "generates"
    if GENERATION_CYCLE[right] == left:
        return "generated_by"
    if DESTRUCTION_CYCLE[left] == right:
        return "controls"
    return "controlled_by"


def check_pillar_patterns(pillars: Pillars) -> PillarRelationships:
    """Compare each visible stem to the principal element and every hidden stem."""
    rows: list[PillarElementRelations] = []
    for position in ORDER:
        stem, branch = pillars[position]
        element = STEM_ELEMENTS[stem][0]
        principal = BRANCH_ELEMENTS[branch][0]
        rows.append(
            {
                "pillar": position,
                "stem": stem,
                "branch": branch,
                "stem_element": element.value,
                "principal_branch_element": principal.value,
                "principal_relation": _element_relation(element, principal),
                "hidden_relations": [
                    {
                        "stem": hidden,
                        "hidden_rank": rank,
                        "element": STEM_ELEMENTS[hidden][0].value,
                        "relation": _element_relation(
                            element, STEM_ELEMENTS[hidden][0]
                        ),
                    }
                    for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[branch])
                ],
            }
        )
    return {
        "method_id": "bazi_column_element_facts_v1",
        "rulesets": [source.copy() for source in PILLAR_SOURCES],
        "pillars": rows,
        "scope": (
            "relation均从本柱明干指向所列本气或藏干；藏干序号不表示力量。"
            "生克事实不直接判盖头截脚效力，天生地与地生天不冒称完整天覆地载。"
        ),
    }


def check_pillar_pair_patterns(pillars: Pillars) -> PillarPairRelationships:
    """Keep all six pairs; four-stem clash, six-branch clash and identity differ."""
    pairs: list[PillarPair] = []
    for left, right in combinations(ORDER, 2):
        s1, b1 = pillars[left]
        s2, b2 = pillars[right]
        pairs.append(
            {
                "pillars": [left, right],
                "pillar_content": [s1 + b1, s2 + b2],
                "identical": pillars[left] == pillars[right],
                "branch_six_clash": BRANCH_CONFLICTS[b1] == b2,
                "stem_four_clash": (s1, s2) in STEM_FOUR_CLASHES
                or (s2, s1) in STEM_FOUR_CLASHES,
                "stem_relation": _element_relation(
                    STEM_ELEMENTS[s1][0], STEM_ELEMENTS[s2][0]
                ),
            }
        )
    return {
        "method_id": "bazi_pillar_pair_facts_v1",
        "rulesets": [source.copy() for source in PILLAR_SOURCES[:1]],
        "pairs": pairs,
        "scope": (
            "本命四柱位置事实；同柱、所选干四冲与支六冲分别列出，"
            "不把干四冲兼支六冲当成跨版本通用反吟定义，不据此断吉凶或力量。"
        ),
    }


class HiddenStemPair(TypedDict):
    stems: list[str]
    hidden_ranks: list[int]
    candidate_element: str


class HiddenStemRelation(TypedDict):
    pillars: list[str]
    branches: list[str]
    stem_pairs: list[HiddenStemPair]


class LuStemPair(TypedDict):
    pillars: list[str]
    branches: list[str]
    stems: list[str]
    source_ref: Literal["sanming_siku_branch_relations"]


class VisibleElementStem(TypedDict):
    pillar: str
    stem: str


class ArchCombination(TypedDict):
    pillars: list[str]
    branches: list[str]
    arched: str
    group_kind: Literal["三合", "三会"]
    candidate_element: str
    visible_element_stems: list[VisibleElementStem]
    formation_status: Literal["not_adjudicated"]


class ArchLuGui(TypedDict):
    kind: Literal["拱禄", "拱贵"]
    day_pillar: str
    hour_pillar: str
    arched: str
    target_present_at: list[str]
    status: Literal["excluded_by_filled_target", "not_adjudicated"]
    source_ref: Literal["sanming_siku_arch"]


class HiddenPatterns(TypedDict):
    method_id: Literal["bazi_hidden_relation_facts_v1"]
    rulesets: list[PatternSource]
    hidden_stem_combinations: list[HiddenStemRelation]
    lu_stem_pair_references: list[LuStemPair]
    arch_combinations: list[ArchCombination]
    arch_lu_gui: list[ArchLuGui]
    effect_status: Literal["not_adjudicated"]
    scope: str


def check_hidden_patterns(pillars: Pillars) -> HiddenPatterns:
    """Enumerate actual concealed stem pairs and explicitly scoped arch facts."""
    result: HiddenPatterns = {
        "method_id": "bazi_hidden_relation_facts_v1",
        "rulesets": [SOURCES[0].copy(), SOURCES[1].copy()],
        "hidden_stem_combinations": [],
        "lu_stem_pair_references": [],
        "arch_combinations": [],
        "arch_lu_gui": [],
        "effect_status": "not_adjudicated",
        "scope": (
            "四柱六个位置对的藏干五合配对是计算事实，不统一命名为已成立暗合；"
            "藏干序号从0开始，只表示所选表顺序，不表示力量或统一司令次序。"
            "禄位往来按所选藏干／五合表形式化广录五组；电子本首组作甲巳，"
            "此处所用甲己依据已核五合表，原异字保留而不作新书影校勘。"
            "缺中神的拱合／拱会是本项目结构候选，"
            "透出同五行干只列事实，不增加力量或裁定三会成局。"
            "拱禄拱贵按原文十组日時配对；填实可排除，月令、空亡、刑冲与全局资格仍待裁定。"
        ),
    }
    branches = [pillars[name][1] for name in ORDER]
    for left, right in combinations(ORDER, 2):
        a, b = pillars[left][1], pillars[right][1]
        stem_pairs: list[HiddenStemPair] = []
        for rank_a, stem_a in enumerate(BRANCH_HIDDEN_STEMS[a]):
            for rank_b, stem_b in enumerate(BRANCH_HIDDEN_STEMS[b]):
                for first, second, element in STEM_COMBINATIONS:
                    if (stem_a, stem_b) in ((first, second), (second, first)):
                        stem_pairs.append(
                            {
                                "stems": [stem_a, stem_b],
                                "hidden_ranks": [rank_a, rank_b],
                                "candidate_element": element,
                            }
                        )
        if stem_pairs:
            result["hidden_stem_combinations"].append(
                {"pillars": [left, right], "branches": [a, b], "stem_pairs": stem_pairs}
            )

        # The source's five lu-position pairs are narrower than all hidden pairs.
        for ba, bb, sa, sb in (
            ("寅", "午", "甲", "己"),
            ("子", "巳", "癸", "戊"),
            ("巳", "酉", "丙", "辛"),
            ("卯", "申", "乙", "庚"),
            ("午", "亥", "丁", "壬"),
        ):
            if (a, b) in ((ba, bb), (bb, ba)):
                result["lu_stem_pair_references"].append(
                    {
                        "pillars": [left, right],
                        "branches": [a, b],
                        "stems": [sa, sb] if a == ba else [sb, sa],
                        "source_ref": "sanming_siku_branch_relations",
                    }
                )

        group_tables: tuple[tuple[Literal["三合", "三会"], Mapping[str, str]], ...] = (
            ("三合", BRANCH_TRIPLE_COMBINATIONS),
            ("三会", BRANCH_SEASONAL_COMBINATIONS),
        )
        for group_kind, groups in group_tables:
            for group, label in groups.items():
                start, middle, end = group[0], group[1], group[2]
                if (a, b) in ((start, end), (end, start)) and middle not in branches:
                    result["arch_combinations"].append(
                        {
                            "pillars": [left, right],
                            "branches": [a, b],
                            "arched": middle,
                            "group_kind": group_kind,
                            "candidate_element": label[0],
                            "visible_element_stems": [
                                {"pillar": name, "stem": pillars[name][0]}
                                for name in ORDER
                                if STEM_ELEMENTS[pillars[name][0]][0].value == label[0]
                            ],
                            "formation_status": "not_adjudicated",
                        }
                    )

    day, hour = "".join(pillars["day"]), "".join(pillars["hour"])
    arch_rules: tuple[tuple[Literal["拱禄", "拱贵"], str, str, str], ...] = (
        ("拱禄", "癸亥", "癸丑", "子"),
        ("拱禄", "癸丑", "癸亥", "子"),
        ("拱禄", "丁巳", "丁未", "午"),
        ("拱禄", "己未", "己巳", "午"),
        ("拱禄", "戊辰", "戊午", "巳"),
        ("拱贵", "甲申", "甲戌", "酉"),
        ("拱贵", "乙未", "乙酉", "申"),
        ("拱贵", "甲寅", "甲子", "丑"),
        ("拱贵", "戊申", "戊午", "未"),
        ("拱贵", "辛丑", "辛卯", "寅"),
    )
    for arch_kind, day_ref, hour_ref, target in arch_rules:
        if (day, hour) == (day_ref, hour_ref):
            occupied = [name for name in ORDER if pillars[name][1] == target]
            result["arch_lu_gui"].append(
                {
                    "kind": arch_kind,
                    "day_pillar": day,
                    "hour_pillar": hour,
                    "arched": target,
                    "target_present_at": occupied,
                    "status": (
                        "excluded_by_filled_target" if occupied else "not_adjudicated"
                    ),
                    "source_ref": "sanming_siku_arch",
                }
            )
    return result


class BranchAttribute(TypedDict):
    branch: str
    type: BranchGroup


class BranchGroupFacts(TypedDict):
    branches: list[str]
    pillars: list[str]
    count: int
    complete: bool
    many: bool
    all_pillars: bool


class NobleDayReference(TypedDict):
    day_pillar: str
    required_lighting: Literal["day", "night"] | None
    clock_hour: int | None
    clock_convention: Literal["6<=hour<18"]
    clock_classification: Literal["day", "night"] | None
    clock_matches_required: bool | None
    actual_lighting_status: Literal["not_adjudicated"]
    formation_status: Literal["not_adjudicated", "not_applicable"]


class SpecialPatterns(TypedDict):
    method_id: Literal["bazi_special_pattern_facts_v1"]
    rulesets: list[PatternSource]
    noble_day: bool
    noble_day_reference: NobleDayReference
    kui_gang: bool
    uniform_stem: str | None
    uniform_branch: str | None
    branch_attributes: dict[str, BranchAttribute]
    branch_groups: dict[BranchGroup, BranchGroupFacts]
    formation_status: Literal["not_adjudicated"]
    scope: str


def analyze_special_patterns(
    pillars: Pillars, birth_hour: int | None = None
) -> SpecialPatterns:
    """Return literal day lists, branch categories and a labeled clock reference."""
    day = "".join(pillars["day"])
    required: Literal["day", "night"] | None = None
    if day in ("癸卯", "丁亥"):
        required = "day"
    elif day in ("癸巳", "丁酉"):
        required = "night"
    clock: Literal["day", "night"] | None = None
    if birth_hour is not None:
        clock = "day" if 6 <= birth_hour < 18 else "night"
    stems = [pillars[name][0] for name in ORDER]
    branches = [pillars[name][1] for name in ORDER]
    result: SpecialPatterns = {
        "method_id": "bazi_special_pattern_facts_v1",
        "rulesets": [SOURCES[2].copy(), SOURCES[3].copy()],
        "noble_day": required is not None,
        "noble_day_reference": {
            "day_pillar": day,
            "required_lighting": required,
            "clock_hour": birth_hour,
            "clock_convention": "6<=hour<18",
            "clock_classification": clock,
            "clock_matches_required": clock == required if clock and required else None,
            "actual_lighting_status": "not_adjudicated",
            "formation_status": "not_adjudicated" if required else "not_applicable",
        },
        "kui_gang": day in ("庚戌", "庚辰", "戊戌", "壬辰"),
        "uniform_stem": stems[0] if len(set(stems)) == 1 else None,
        "uniform_branch": branches[0] if len(set(branches)) == 1 else None,
        "branch_attributes": {},
        "branch_groups": {},
        "formation_status": "not_adjudicated",
        "scope": (
            "日贵、魁罡仅核所列日柱，不等于成格。6–18时沿用既有钟时计算，"
            "不是已经确认的日出入或唯一古法；未知昼夜不据钟时裁为不合时。"
            "四生、四正、四库按地支类别计数，三见称多为本项目统计约定，"
            "四字齐备与四柱全属一类分列；四生不是按年支或日支定位的实际驿马。"
        ),
    }
    branch_groups: tuple[tuple[BranchGroup, str], ...] = (
        ("四生", "寅申巳亥"),
        ("四正", "子午卯酉"),
        ("四库", "辰戌丑未"),
    )
    for label, members in branch_groups:
        positions = [name for name in ORDER if pillars[name][1] in members]
        complete = set(members).issubset(branches)
        result["branch_groups"][label] = {
            "branches": list(members),
            "pillars": positions,
            "count": len(positions),
            "complete": complete,
            "many": len(positions) >= 3 and not complete,
            "all_pillars": len(positions) == 4,
        }
        for name in positions:
            result["branch_attributes"][name] = {
                "branch": pillars[name][1],
                "type": label,
            }
    return result
