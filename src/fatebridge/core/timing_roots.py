"""Time-layer root categories reuse the natal source rule, without rescoring it."""

from copy import deepcopy
from typing import Literal, Mapping, Sequence, TypedDict

from fatebridge.core.classical_roots import (
    SOURCE,
    RootClassification,
    RootSource,
    classify_classical_root,
)

METHOD_ID = "natal_timing_root_support_v1"
SCOPE = "沿用原局根类规则，分别核对日主在时运支的根和运干在原局支的根。月令仍为原局月支；关系引用仅是同次结构触点，不裁定根已失效、获救、合化或力量增减。同一地支位置的根可被多干引用，但不能重复相加为预算。阴长生名不补造真实藏干；未见根不直接判弱。"
BRANCH_RELATION_KINDS = frozenset(
    {
        "branch_clash",
        "branch_combination",
        "branch_harm",
        "self_punishment",
        "branch_punishment",
        "partial_punishment",
        "half_combination",
        "triple_combination",
        "seasonal_meeting",
    }
)


class RootRelationReference(TypedDict):
    id: str
    participants: list[str]


class TimingRoot(TypedDict):
    stem_node_id: str
    branch_node_id: str
    classification: RootClassification
    branch_relation_ids: list[str]


class TimingRootContext(TypedDict):
    method_id: str
    month_command_node_id: str
    day_master_roots: list[TimingRoot]
    timing_stem_natal_roots: list[TimingRoot]
    effective_force_status: Literal["not_adjudicated"]
    source: RootSource
    scope: str


def build_timing_root_context(
    natal: Mapping[str, tuple[str, str]],
    timing: Mapping[str, Mapping[str, str]],
    relations: Sequence[RootRelationReference],
) -> TimingRootContext:
    """Consume validated pillars and same-run branch relation IDs, once.

    Retain absent roots too, so an unread observation cannot become a negative.
    References identify physical branch nodes, never extra copies of root mass.
    """
    day_roots: list[TimingRoot] = []
    external_roots: list[TimingRoot] = []
    for layer, pillar in timing.items():
        timing_id = f"timing.{layer}"
        day_roots.append(
            TimingRoot(
                stem_node_id="natal.day",
                branch_node_id=timing_id,
                classification=classify_classical_root(
                    natal["day"][0], pillar["branch"]
                ),
                branch_relation_ids=[
                    r["id"] for r in relations if timing_id in r["participants"]
                ],
            )
        )
        for position in ("year", "month", "day", "hour"):
            natal_id = f"natal.{position}"
            external_roots.append(
                TimingRoot(
                    stem_node_id=timing_id,
                    branch_node_id=natal_id,
                    classification=classify_classical_root(
                        pillar["stem"], natal[position][1]
                    ),
                    branch_relation_ids=[
                        r["id"] for r in relations if natal_id in r["participants"]
                    ],
                )
            )
    return TimingRootContext(
        method_id=METHOD_ID,
        month_command_node_id="natal.month",
        day_master_roots=day_roots,
        timing_stem_natal_roots=external_roots,
        effective_force_status="not_adjudicated",
        source=deepcopy(SOURCE),
        scope=SCOPE,
    )


def timing_root_snapshot_lines(context: TimingRootContext) -> list[str]:
    labels = {
        "dayun": "大运",
        "liunian": "流年",
        "liuyue": "流月",
        "liuri": "流日",
        "liushi": "流时",
    }
    lines = []
    for row in context["day_master_roots"]:
        root = row["classification"]
        hidden = "、".join(root["matching_hidden_stems"]) or "未见同气藏干"
        layer = row["branch_node_id"].split(".")[-1]
        lines.append(
            f"{labels.get(layer, layer)}支{root['branch']}与日主{root['stem']}："
            f"{root['label']}，{hidden}；该支有{len(row['branch_relation_ids'])}条结构触点。"
        )
    if lines:
        lines.append(
            "根类与冲合刑触点分列；未裁定行运后的有效旺衰，不能把阴长生名当真实藏根或把未见根直接判弱。"
        )
    return lines
