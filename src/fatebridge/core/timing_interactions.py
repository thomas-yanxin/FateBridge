"""Match structural relations while preserving natal and timing node positions."""

from itertools import combinations
from typing import Literal, Mapping, TypedDict

from pydantic import JsonValue
from typing_extensions import NotRequired, Unpack

from fatebridge.core.hidden_carriers import (
    describe_temporal_hidden_carrier,
    hidden_target_reference,
)
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.timing_carriers import SCOPE as CARRIER_SCOPE
from fatebridge.core.timing_carriers import SOURCE as CARRIER_SOURCE
from fatebridge.core.timing_carriers import (
    CarrierNatalRoot,
    TimingCarrierReceipt,
    TimingCarrierSummary,
    describe_timing_carrier,
    summarize_timing_carriers,
)
from fatebridge.core.timing_roots import (
    BRANCH_RELATION_KINDS,
    RootRelationReference,
    TimingRootContext,
    build_timing_root_context,
)
from fatebridge.core.timing_strength import (
    BudgetEffectRelation,
    StrengthProjectionBaseline,
    TimingStrengthProjection,
    project_timing_root_effects,
)
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_HARMS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    TRIPLE_COMBINATION_PEAK,
    get_shishen,
)

METHOD_ID = "natal_timing_relations_v2"
STEM_COMBINATIONS = {
    frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")
}
SOURCE_URL = "https://zh.wikisource.org/zh-hant/三命通會/卷二"


class TimingInteractionNode(TypedDict):
    id: str
    scope: Literal["natal", "timing"]
    layer: str
    stem: str
    branch: str
    pillar: str


class InteractionFacts(TypedDict, total=False):
    source: str
    target: str
    definition: str
    group: str
    bureau: str
    transformation: Literal["not_assessed"]
    complete: bool
    traditional_label: str


class TimingInteraction(InteractionFacts):
    id: str
    rule_id: str
    participants: list[str]
    scope: Literal["natal_timing", "timing_timing"]
    status: Literal["structural_match"]


class HiddenStemTenGod(TypedDict):
    stem: str
    ten_god: str
    rank: int


class TimingTenGodContext(TypedDict):
    node_id: str
    stem_ten_god: str
    hidden_stems: list[HiddenStemTenGod]
    natal_same_element_roots: list[CarrierNatalRoot]


class TimingInteractionAnalysis(TypedDict):
    strength_projection: NotRequired[TimingStrengthProjection]
    method_id: str
    assessment_status: Literal["structural_evidence_only"]
    nodes: list[TimingInteractionNode]
    ten_god_context: list[TimingTenGodContext]
    pillar_carriers: list[TimingCarrierReceipt]
    pillar_carrier_summary: list[TimingCarrierSummary]
    pillar_carrier_scope: str
    pillar_carrier_source: dict[str, str]
    hidden_target_reference: dict[str, JsonValue]
    hidden_target_carriers: list[dict[str, JsonValue]]
    relations: list[TimingInteraction]
    root_context: TimingRootContext
    rulesets: list[dict[str, str]]
    rule_trace: list[str]
    coverage: dict[str, list[str]]
    interpretation_scope: str


def analyze_timing_interactions(
    natal: Mapping[str, tuple[str, str]],
    timing: Mapping[str, Mapping[str, str]],
    *,
    strength_baseline: StrengthProjectionBaseline | None = None,
) -> TimingInteractionAnalysis:
    """Match pair and triple relations involving at least one timing node."""
    nodes: list[TimingInteractionNode] = []
    for name in ("year", "month", "day", "hour"):
        stem, branch = natal[name]
        nodes.append(
            {
                "id": f"natal.{name}",
                "scope": "natal",
                "layer": name,
                "stem": stem,
                "branch": branch,
                "pillar": stem + branch,
            }
        )
    for layer, pillar in timing.items():
        stem, branch = pillar["stem"], pillar["branch"]
        nodes.append(
            {
                "id": f"timing.{layer}",
                "scope": "timing",
                "layer": layer,
                "stem": stem,
                "branch": branch,
                "pillar": stem + branch,
            }
        )
    if any(node["pillar"] not in SEXAGENARY_INDEX for node in nodes):
        raise ValueError("时运关系需要六十甲子中的完整干支柱")

    events: list[TimingInteraction] = []

    def emit(
        kind: str,
        members: tuple[TimingInteractionNode, ...],
        **facts: Unpack[InteractionFacts],
    ) -> None:
        if not any(node["scope"] == "timing" for node in members):
            return
        participants = [node["id"] for node in members]
        events.append(
            {
                "id": kind + ":" + "+".join(participants),
                "rule_id": kind,
                "participants": participants,
                "scope": (
                    "natal_timing"
                    if any(n["scope"] == "natal" for n in members)
                    else "timing_timing"
                ),
                "status": "structural_match",
                **facts,
            }
        )

    for left, right in combinations(nodes, 2):
        pair = (left, right)
        stems = frozenset((left["stem"], right["stem"]))
        branches = frozenset((left["branch"], right["branch"]))
        if stems in STEM_COMBINATIONS:
            emit("stem_combination", pair, transformation="not_assessed")
        for source, target in (pair, pair[::-1]):
            if (
                DESTRUCTION_CYCLE[STEM_ELEMENTS[source["stem"]][0]]
                == STEM_ELEMENTS[target["stem"]][0]
            ):
                emit("stem_overcoming", pair, source=source["id"], target=target["id"])
                if (
                    BRANCH_CONFLICTS[left["branch"]] == right["branch"]
                    and STEM_ELEMENTS[source["stem"]][1]
                    == STEM_ELEMENTS[target["stem"]][1]
                ):
                    emit(
                        "heaven_overcoming_earth_clash",
                        pair,
                        source=source["id"],
                        target=target["id"],
                        definition="六冲加同阴阳天干相克；不等于已判断吉凶",
                    )
        if BRANCH_CONFLICTS[left["branch"]] == right["branch"]:
            emit("branch_clash", pair)
        if BRANCH_COMBINATIONS[left["branch"]] == right["branch"]:
            emit("branch_combination", pair, transformation="not_assessed")
        if BRANCH_HARMS[left["branch"]] == right["branch"]:
            emit("branch_harm", pair)
        if (
            left["branch"] == right["branch"]
            and left["branch"] in BRANCH_SELF_PUNISHMENTS
        ):
            emit("self_punishment", pair)
        for punishment_group in BRANCH_THREE_PUNISHMENTS:
            if len(branches) == 2 and branches <= set(punishment_group):
                emit(
                    (
                        "branch_punishment"
                        if len(punishment_group) == 2
                        else "partial_punishment"
                    ),
                    pair,
                    group="".join(punishment_group),
                    complete=len(punishment_group) == 2,
                )
        for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
            if (
                len(branches) == 2
                and branches <= set(group)
                and TRIPLE_COMBINATION_PEAK[group] in branches
            ):
                emit(
                    "half_combination",
                    pair,
                    group=group,
                    bureau=bureau,
                    transformation="not_assessed",
                )
        if left["pillar"] == right["pillar"]:
            emit("pillar_repeat", pair, traditional_label="同柱重见（伏吟结构）")
            if {left["id"], right["id"]} == {"timing.dayun", "timing.liunian"}:
                emit("suiyun_binglin", pair, traditional_label="岁运并临")

    for group_nodes in combinations(nodes, 3):
        group_branches = {node["branch"] for node in group_nodes}
        for kind, groups in (
            ("triple_combination", BRANCH_TRIPLE_COMBINATIONS),
            ("seasonal_meeting", BRANCH_SEASONAL_COMBINATIONS),
        ):
            for group, bureau in groups.items():
                if group_branches == set(group):
                    emit(
                        kind,
                        group_nodes,
                        group=group,
                        bureau=bureau,
                        transformation="not_assessed",
                    )
        for punishment_group in BRANCH_THREE_PUNISHMENTS:
            if len(punishment_group) == 3 and group_branches == set(punishment_group):
                emit(
                    "branch_punishment",
                    group_nodes,
                    group="".join(punishment_group),
                    complete=True,
                )

    day_stem = natal["day"][0]
    ten_gods: list[TimingTenGodContext] = []
    for node in nodes:
        if node["scope"] != "timing":
            continue
        ten_gods.append(
            {
                "node_id": node["id"],
                "stem_ten_god": get_shishen(day_stem, node["stem"]),
                "hidden_stems": [
                    {
                        "stem": stem,
                        "ten_god": get_shishen(day_stem, stem),
                        "rank": index + 1,
                    }
                    for index, stem in enumerate(BRANCH_HIDDEN_STEMS[node["branch"]])
                ],
                "natal_same_element_roots": [
                    {
                        "position": position,
                        "hidden_stem": stem,
                        "exact_stem": stem == node["stem"],
                    }
                    for position, (_, branch) in natal.items()
                    for stem in BRANCH_HIDDEN_STEMS[branch]
                    if STEM_ELEMENTS[stem][0] == STEM_ELEMENTS[node["stem"]][0]
                ],
            }
        )
    carriers = [
        describe_timing_carrier(node["id"], node["stem"], node["branch"], natal)
        for node in nodes
        if node["scope"] == "timing"
    ]
    strength_projection = (
        project_timing_root_effects(
            natal,
            timing,
            [
                BudgetEffectRelation(
                    id=e["id"],
                    rule_id=e["rule_id"],
                    participants=e["participants"],
                    complete=e.get("complete", False),
                )
                for e in events
                if e["rule_id"] in BRANCH_RELATION_KINDS
                or e["rule_id"] == "stem_combination"
            ],
            strength_baseline,
        )
        if strength_baseline is not None
        else None
    )
    interactions: TimingInteractionAnalysis = {
        "method_id": METHOD_ID,
        "assessment_status": "structural_evidence_only",
        "nodes": nodes,
        "ten_god_context": ten_gods,
        "pillar_carriers": carriers,
        "pillar_carrier_summary": summarize_timing_carriers(carriers),
        "pillar_carrier_scope": CARRIER_SCOPE,
        "pillar_carrier_source": dict(CARRIER_SOURCE),
        "hidden_target_reference": hidden_target_reference(),
        "hidden_target_carriers": [
            describe_temporal_hidden_carrier(node["id"], node["stem"], node["branch"])
            for node in nodes
            if node["scope"] == "timing"
        ],
        "relations": events,
        "root_context": build_timing_root_context(
            natal,
            timing,
            [
                RootRelationReference(id=e["id"], participants=e["participants"])
                for e in events
                if e["rule_id"] in BRANCH_RELATION_KINDS
            ],
        ),
        "rulesets": [
            {
                "id": METHOD_ID,
                "source_title": "三命通会·卷二·论十干合、支元六合、支元三合、六害、三刑、冲击、太岁、总论岁运",
                "source_url": SOURCE_URL,
            },
            dict(CARRIER_SOURCE),
        ],
        "rule_trace": sorted({event["rule_id"] for event in events}),
        "coverage": {
            "covered": [
                "原局与时运及时间层之间的关系",
                "位置保留",
                "透干十神与支中藏干",
                "原局同五行根的存在",
                "时运本柱主气生克与真实藏根，区别原局外援",
                "日主在时运支及运干在原局的原典根类与同次支关系触点",
            ],
            "not_assessed": [
                "行运后有效旺衰",
                "合化成立与争合解冲",
                "用神相神及成格破格救应",
                "人元分日司令",
                "空亡填实",
                "小运",
                "事件应期与吉凶",
            ],
        },
        "interpretation_scope": "关系可同时命中，不能相加计分或重复消耗根气；同柱、刑冲会合及根的存在不证明吉凶、合化或事件必然发生。",
    }
    if strength_projection is not None:
        return {"strength_projection": strength_projection, **interactions}
    else:
        return interactions
