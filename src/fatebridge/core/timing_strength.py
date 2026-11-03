"""Bounded time-branch effects on the existing natal root budget.

This is a single-layer counterfactual, not another natal column or a complete
post-timing strength classifier. Unresolved combinations block the projection.
"""

from copy import deepcopy
from fractions import Fraction
from typing import Literal, Mapping, Sequence, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.root_budget import initial_hidden_budgets
from fatebridge.core.stem_effects import PAIRS as STEM_PAIRS
from fatebridge.core.storage_movement import storage_movement_effect
from fatebridge.core.strength_thresholds import exact_threshold_decision
from fatebridge.utils.data import (
    BRANCH_ELEMENTS,
    Element,
)

METHOD_ID = "single_layer_natal_budget_retention_projection_v2"
SCOPE = "逐时间层独立投影六冲、完整刑、自刑及唯一运干五合对原局既有预算的作用；复用原旺衰工程系数、原局月令及有理数账本，多事件取最小保留而不连乘。时间干支不加入原局能量，只在大运层对原局非日干的唯一五合采用既有合绊系数，其他时间层的干合保留未裁；日主之合、争合、原合冲突或支会合未解时不输出投影。新根、生克流通及层间救应未计，数值档仅属残存原局预算，不是行运后的全局旺衰或吉凶。"
STEM_SOURCE = {
    "id": "ziping_timing_stem_combination_budget_v1",
    "title": "秘本子平真詮·論十干配合性情、論十干合而不合、論行動",
    "author": "沈孝瞻",
    "edition": "国家图书馆藏本 NLC416-11jh010455-35296，上海世界图书馆发行",
    "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
    "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
    "locator": "PDF18–19、56–57；印页9–10、47–48；正文篇题作論行動，目录作論行運",
    "supported_layer": "dayun",
    "scope": "原页行运规则仅用于大运层，其他时间粒度有配对时保留未裁。唯一配对是有限工程准入，0.85仍为既有工程系数，非原典数值或完整成化、合去和格局裁定。",
}
POSITIONS = ("year", "month", "day", "hour")
COMBINATIONS = {
    "branch_combination",
    "half_combination",
    "triple_combination",
    "seasonal_meeting",
}


class NatalRootInteraction(TypedDict):
    kind: str
    positions: list[str]
    status: str
    target: NotRequired[str]
    root_multipliers: NotRequired[dict[str, float]]
    storage_effect: NotRequired[dict[str, object]]


class StrengthProjectionBaseline(TypedDict):
    method_id: str
    strength_level: str
    numerical_label: str
    support_share_exact: str
    energies_exact: dict[str, str]
    parameters: dict[str, float]
    seasonal_phases: dict[str, str]
    seasonal_factors: dict[str, float]
    relations: list[NatalRootInteraction]


class BudgetEffectRelation(TypedDict):
    id: str
    rule_id: str
    participants: list[str]
    complete: bool


class ProjectedHiddenRoot(TypedDict):
    pillar: str
    stem: str
    element: str
    remaining_mass_exact: str


class TimingRootEffectLayer(TypedDict):
    node_id: str
    status: Literal["projected", "blocked"]
    blocker_relation_ids: list[str]
    effect_relation_ids: list[str]
    quantity_kind: Literal["residual_natal_budget_only"]
    comparison_powers_exact: dict[str, str]
    retention_factors_exact: dict[str, dict[str, str]]
    stem_retention_factors_exact: dict[str, str]
    hidden_roots: list[ProjectedHiddenRoot]
    energies_exact: dict[str, str]
    support_share_exact: str | None
    residual_natal_numerical_label: str | None


class TimingStrengthProjection(TypedDict):
    method_id: str
    baseline_method_id: str
    baseline: StrengthProjectionBaseline
    month_command_node_id: Literal["natal.month"]
    combination_resolution: Literal["not_implemented"]
    full_timing_strength_status: Literal["not_adjudicated"]
    layers: list[TimingRootEffectLayer]
    scope: str
    stem_binding_source: dict[str, str]


def project_timing_root_effects(
    natal: Mapping[str, tuple[str, str]],
    timing: Mapping[str, Mapping[str, str]],
    relations: Sequence[BudgetEffectRelation],
    baseline: StrengthProjectionBaseline,
) -> TimingStrengthProjection:
    """Consume validated same-run natal parameters; never choose new weights."""
    parameters = baseline["parameters"]
    q = {key: Fraction(str(value)) for key, value in parameters.items()}
    # Initial physical budgets, before interactions: the adopted clash proxy.
    natal_powers = {e: Fraction(0) for e in Element}
    initial = initial_hidden_budgets(
        {p: natal[p][1] for p in POSITIONS},
        {
            p: q["branch_budget"] * (q["month_multiplier"] if p == "month" else 1)
            for p in POSITIONS
        },
    )
    for roots in initial.values():
        for _, element, mass in roots:
            natal_powers[element] += mass
    layers: list[TimingRootEffectLayer] = []
    for layer, pillar in timing.items():
        node_id = f"timing.{layer}"
        allowed = {f"natal.{position}" for position in POSITIONS} | {node_id}
        local = [r for r in relations if set(r["participants"]) <= allowed]
        effects = [
            r
            for r in local
            if r["rule_id"] in {"branch_clash", "self_punishment"}
            or (r["rule_id"] == "branch_punishment" and r["complete"])
        ]
        touched = {
            p.removeprefix("natal.")
            for r in effects
            for p in r["participants"]
            if p.startswith("natal.")
        }
        blockers = [r["id"] for r in local if r["rule_id"] in COMBINATIONS]
        # A new clash can also break an existing natal combination. Its old
        # transfer/binding cannot simply survive while applying another loss.
        blockers.extend(
            f"natal.relations:{i}"
            for i, event in enumerate(baseline["relations"])
            if event["kind"] in {"三会", "三合", "六合", "半合"}
            and touched.intersection(event["positions"])
        )
        stem_matches = [r for r in local if r["rule_id"] == "stem_combination"]
        stem_retention = {p: Fraction(1) for p in POSITIONS if p != "day"}
        if stem_matches:
            partners = [
                p
                for p in POSITIONS
                if frozenset((natal[p][0], pillar["stem"])) in STEM_PAIRS
            ]
            # A repeated partner, a day-master match or another original copy
            # of the timing stem leaves priority/competition unresolved.
            competing = any(natal[p][0] == pillar["stem"] for p in POSITIONS)
            original_links = [
                f"natal.relations:{i}"
                for i, event in enumerate(baseline["relations"])
                if event["kind"] == "天干合"
                and set(partners).intersection(event["positions"])
            ]
            if (
                layer != "dayun"
                or len(partners) != 1
                or partners[0] == "day"
                or competing
                or original_links
            ):
                blockers.extend(r["id"] for r in stem_matches)
                blockers.extend(original_links)
            else:
                stem_retention[partners[0]] = q["binding"]
        row: TimingRootEffectLayer = {
            "node_id": node_id,
            "status": "blocked" if blockers else "projected",
            "blocker_relation_ids": blockers,
            "effect_relation_ids": [r["id"] for r in effects + stem_matches],
            "quantity_kind": "residual_natal_budget_only",
            "comparison_powers_exact": {},
            "retention_factors_exact": {},
            "stem_retention_factors_exact": {},
            "hidden_roots": [],
            "energies_exact": {},
            "support_share_exact": None,
            "residual_natal_numerical_label": None,
        }
        layers.append(row)
        if blockers:
            continue
        powers = dict(natal_powers)
        forcing = initial_hidden_budgets(
            {node_id: pillar["branch"]}, {node_id: q["branch_budget"]}
        )
        for _, element, mass in forcing[node_id]:
            powers[element] += mass
        retention = {p: {e: Fraction(1) for e in Element} for p in POSITIONS}
        branches = {f"natal.{p}": natal[p][1] for p in POSITIONS}
        branches[node_id] = pillar["branch"]
        for event in effects:
            members = event["participants"]
            kind = "六冲" if event["rule_id"] == "branch_clash" else "刑"
            storage = storage_movement_effect(
                branches,
                members,
                kind,
                natal["day"][0],
                (
                    parameters["clash_equal"]
                    if kind == "六冲"
                    else parameters["punishment"]
                ),
            )
            if storage is not None:
                for root in storage["root_effects"]:
                    if root["pillar"].startswith("natal."):
                        p, e = root["pillar"].removeprefix("natal."), Element(
                            root["element"]
                        )
                        retention[p][e] = min(
                            retention[p][e],
                            Fraction(str(root["event_retention_multiplier"])),
                        )
                continue
            for member in members:
                if not member.startswith("natal."):
                    continue
                position = member.removeprefix("natal.")
                multiplier = q["punishment"]
                if kind == "六冲":
                    own = BRANCH_ELEMENTS[branches[member]][0]
                    other = BRANCH_ELEMENTS[pillar["branch"]][0]
                    multiplier = (
                        q["clash_equal"]
                        if own == other or powers[own] == powers[other]
                        else (
                            q["clash_winner"]
                            if powers[own] > powers[other]
                            else q["clash_loser"]
                        )
                    )
                for element in Element:
                    retention[position][element] = min(
                        retention[position][element], multiplier
                    )
        exact = exact_threshold_decision(
            natal,
            baseline["seasonal_phases"],
            baseline["seasonal_factors"],
            parameters,
            baseline["relations"],
            baseline["numerical_label"],
            external_root_retention=retention,
            external_stem_retention=stem_retention,
            include_hidden_ledger=True,
        )
        row.update(
            {
                "comparison_powers_exact": {
                    e.value: str(value) for e, value in powers.items()
                },
                "retention_factors_exact": {
                    p: {e.value: str(value) for e, value in factors.items()}
                    for p, factors in retention.items()
                },
                "stem_retention_factors_exact": {
                    p: str(value) for p, value in stem_retention.items()
                },
                "hidden_roots": exact["hidden_ledger_exact"],
                "energies_exact": exact["energies_exact"],
                "support_share_exact": exact["share_exact"],
                "residual_natal_numerical_label": exact["numerical_label"],
            }
        )
    return {
        "method_id": METHOD_ID,
        "baseline_method_id": baseline["method_id"],
        "baseline": deepcopy(baseline),
        "month_command_node_id": "natal.month",
        "combination_resolution": "not_implemented",
        "full_timing_strength_status": "not_adjudicated",
        "layers": layers,
        "scope": SCOPE,
        "stem_binding_source": dict(STEM_SOURCE),
    }


def timing_strength_snapshot_lines(projection: TimingStrengthProjection) -> list[str]:
    """Render only the supplied result; do not rerun force for the snapshot."""
    lines = []
    for row in projection["layers"]:
        if row["status"] == "blocked":
            lines.append(
                f"{row['node_id']}原局预算投影：存在未解会合、日主之合或争合关系，本层未输出预算或数值档。"
            )
        else:
            stem_count = sum(
                Fraction(value) < 1
                for value in row["stem_retention_factors_exact"].values()
            )
            lines.append(
                f"{row['node_id']}单层作用：已投影{len(row['hidden_roots'])}项原局藏干根预算，冲刑损耗取最小保留、不连乘；另有{stem_count}项原局非日干预算接受唯一大运干合绊。"
            )
    if lines:
        lines.append(
            "限定投影保留原局月令，不加入时间干支能量、新根或层间救应；运干五合只折减原局非日干既有预算，0.85为工程系数；残存原局数值档不是完整行运后旺衰。"
        )
    return lines
