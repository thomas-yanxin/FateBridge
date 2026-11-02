"""Same-column timing support, separated from roots supplied by the natal chart.

The selected 任注 describes 盖头/截脚 in relation to which component is
desired. The same 丙申 may obstruct desired 申金 with 丙火 or leave desired
丙火 without principal-branch support. Neither observation adjudicates fortune.
"""

from typing import Any, Mapping, Sequence, Tuple

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
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
    "source_url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "source_pdf_pages": "502–510，盖头截脚举例503，乙酉及丁酉反例506",
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
}

RELATION_LABELS = {
    "same_element": "干支本气同五行",
    "branch_generates_stem": "支本气生干",
    "stem_generates_branch": "干生支本气",
    "branch_overcomes_stem": "支本气克干",
    "stem_overcomes_branch": "干克支本气",
}

SCOPE = "本柱主气生克、本柱真实藏根与原局外援分别计算。盖头按支为所喜、截脚压力按干为所喜给条件，未裁定真正喜忌与救应。长生名不是实际藏根；既有根不自动消除主气相克或泄耗。任注运年上下同看，其他时间层仅给同柱事实，不套十年运法。"


def describe_timing_carrier(
    node_id: str, stem: str, branch: str, natal: Mapping[str, Tuple[str, str]]
) -> dict[str, Any]:
    """Calculate literal principal relation and actual root presence, once.

    External natal roots are a different receipt from this pillar's roots.
    Hidden-root presence does not erase a contrary principal relation. Pressure
    is a formal conditional observation; original-chart and annual rescue,
    month command, effective force and actual desired gods remain unadjudicated.
    """
    if stem + branch not in SEXAGENARY_INDEX:
        raise ValueError("时运本柱承载需要六十甲子中的完整干支")
    element = STEM_ELEMENTS[stem][0]
    principal = BRANCH_ELEMENTS[branch][0]
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
    own = [
        {"stem": hidden, "rank": index + 1, "exact_stem": hidden == stem}
        for index, hidden in enumerate(BRANCH_HIDDEN_STEMS[branch])
        if STEM_ELEMENTS[hidden][0] == element
    ]
    external = [
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
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project the same receipts; root count is positions, never force or scores."""
    keys = (
        "node_id",
        "pillar",
        "principal_relation",
        "own_hidden_root_present",
        "branch_covered_if_desired",
        "stem_pressure_if_desired",
        "effective_force_status",
    )
    return [
        {
            **{k: row[k] for k in keys},
            "external_natal_root_count": len(row["external_natal_roots"]),
        }
        for row in rows
    ]
