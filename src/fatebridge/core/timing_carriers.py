"""Describe principal relations, actual hidden roots and external natal support separately."""

from typing import Any, Literal, Mapping, Sequence, TypedDict

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.source_identity import DITIAN_SUI_CHANWEI_SCAN_URL
from fatebridge.utils.data import (
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
)

SOURCE = {
    "id": "ditian_ren_suiyun_carrier_v1",
    "source_title": "任注滴天髓闡微·歲運",
    "source_author": "任鐵樵增注，李雨田校訂兼發行",
    "source_edition": "上海大東書局經售，1947年4月初版",
    "source_url": DITIAN_SUI_CHANWEI_SCAN_URL,
    "source_pdf_pages": "502–510，盖头截脚举例503，乙酉及丁酉反例506",
}

RELATION_LABELS = {
    "same_element": "干支本气同五行",
    "branch_generates_stem": "支本气生干",
    "stem_generates_branch": "干生支本气",
    "branch_overcomes_stem": "支本气克干",
    "stem_overcomes_branch": "干克支本气",
}

SCOPE = "本柱主气生克、本柱真实藏根与原局外援分别计算。盖头按支为所喜、截脚压力按干为所喜给条件，未裁定真正喜忌与救应。长生名不是实际藏根；既有根不自动消除主气相克或泄耗。任注运年上下同看，其他时间层仅给同柱事实，不套十年运法。"


CarrierPrincipalRelation = Literal[
    "same_element",
    "branch_generates_stem",
    "stem_generates_branch",
    "branch_overcomes_stem",
    "stem_overcomes_branch",
]


class CarrierHiddenRoot(TypedDict):
    stem: str
    rank: int
    exact_stem: bool


class CarrierNatalRoot(TypedDict):
    position: str
    hidden_stem: str
    exact_stem: bool


class TimingCarrierReceipt(TypedDict):
    node_id: str
    pillar: str
    stem_element: str
    branch_principal_element: str
    principal_relation: CarrierPrincipalRelation
    own_hidden_roots: list[CarrierHiddenRoot]
    own_hidden_root_present: bool
    external_natal_roots: list[CarrierNatalRoot]
    branch_covered_if_desired: bool
    stem_pressure_if_desired: bool
    effective_force_status: Literal["not_adjudicated"]
    source_ref: str


class TimingCarrierSummary(TypedDict):
    node_id: str
    pillar: str
    principal_relation: CarrierPrincipalRelation
    own_hidden_root_present: bool
    branch_covered_if_desired: bool
    stem_pressure_if_desired: bool
    effective_force_status: Literal["not_adjudicated"]
    external_natal_root_count: int


def describe_timing_carrier(
    node_id: str, stem: str, branch: str, natal: Mapping[str, tuple[str, str]]
) -> TimingCarrierReceipt:
    """Calculate the principal branch relation and actual hidden-root presence."""
    if stem + branch not in SEXAGENARY_INDEX:
        raise ValueError("时运本柱承载需要六十甲子中的完整干支")
    element = STEM_ELEMENTS[stem][0]
    principal = BRANCH_ELEMENTS[branch][0]
    relation: CarrierPrincipalRelation
    if element == principal:
        relation = "same_element"
    elif GENERATION_CYCLE[principal] == element:
        relation = "branch_generates_stem"
    elif GENERATION_CYCLE[element] == principal:
        relation = "stem_generates_branch"
    elif DESTRUCTION_CYCLE[principal] == element:
        relation = "branch_overcomes_stem"
    else:
        relation = "stem_overcomes_branch"
    own: list[CarrierHiddenRoot] = [
        {"stem": hidden, "rank": index + 1, "exact_stem": hidden == stem}
        for index, hidden in enumerate(BRANCH_HIDDEN_STEMS[branch])
        if STEM_ELEMENTS[hidden][0] == element
    ]
    external: list[CarrierNatalRoot] = [
        {"position": name, "hidden_stem": hidden, "exact_stem": hidden == stem}
        for name in ("year", "month", "day", "hour")
        for hidden in BRANCH_HIDDEN_STEMS[natal[name][1]]
        if STEM_ELEMENTS[hidden][0] == element
    ]
    return {
        "node_id": node_id,
        "pillar": stem + branch,
        "stem_element": element.value,
        "branch_principal_element": principal.value,
        "principal_relation": relation,
        "own_hidden_roots": own,
        "own_hidden_root_present": bool(own),
        "external_natal_roots": external,
        "branch_covered_if_desired": relation == "stem_overcomes_branch",
        "stem_pressure_if_desired": relation
        not in {"same_element", "branch_generates_stem"},
        "effective_force_status": "not_adjudicated",
        "source_ref": SOURCE["id"],
    }


def timing_carrier_snapshot_lines(interactions: Mapping[str, Any]) -> list[str]:
    """Format the supplied receipt without recalculating roots or suitability."""
    rows = interactions.get("pillar_carriers") or []
    if not rows:
        return []
    layers = {
        "dayun": "大运",
        "liunian": "流年",
        "liuyue": "流月",
        "liuri": "流日",
        "liushi": "流时",
    }
    lines = []
    hidden_rows = interactions.get("hidden_target_carriers") or []
    for row in rows:
        own = "、".join(r["stem"] for r in row["own_hidden_roots"]) or "未见"
        lines.append(
            f"{layers.get(row['node_id'].split('.')[-1], row['node_id'])}{row['pillar']}："
            f"{RELATION_LABELS[row['principal_relation']]}；本柱同五行藏根{own}；"
            f"原局外援根{len(row['external_natal_roots'])}处，分别列示。"
        )
        hidden: Mapping[str, Any] = next(
            (r for r in hidden_rows if r["node_id"] == row["node_id"]),
            {},
        )
        covered = [
            t["hidden_stem"]
            for t in hidden.get("targets", [])
            if t["covering_candidate_if_target_desired"]
        ]
        if covered:
            lines.append(
                f"{row['pillar']}另见干克真实藏干{'、'.join(covered)}；仅在这些藏干为所喜时列盖头候选，不改述为全支受克。"
            )
    lines.append(
        "盖头须以支为所喜、截脚压力须以干为所喜分别核对；本柱关系、藏根与长生名不裁定实际喜忌、救应或吉凶。"
    )
    return lines


def summarize_timing_carriers(
    carriers: Sequence[TimingCarrierReceipt],
) -> list[TimingCarrierSummary]:
    """Count natal root positions in each supplied carrier receipt."""
    return [
        {
            "node_id": carrier["node_id"],
            "pillar": carrier["pillar"],
            "principal_relation": carrier["principal_relation"],
            "own_hidden_root_present": carrier["own_hidden_root_present"],
            "branch_covered_if_desired": carrier["branch_covered_if_desired"],
            "stem_pressure_if_desired": carrier["stem_pressure_if_desired"],
            "effective_force_status": carrier["effective_force_status"],
            "external_natal_root_count": len(carrier["external_natal_roots"]),
        }
        for carrier in carriers
    ]
