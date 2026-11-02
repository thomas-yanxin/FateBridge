"""Literal same-column hidden targets, including 丁丑 covering hidden 辛財.

The selected 順局 example names a subsidiary hidden target. A comparison with
branch principal qi alone does not describe it. These are conditional relations,
not a hidden-root loss policy, a complete 截腳 rule or an effective-force test.
"""

from copy import deepcopy
from typing import Any, Mapping, Tuple

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    get_ten_god,
)

SOURCE = {
    "id": "ditian_ren_hidden_cover_targets_v1",
    "title": "任注滴天髓闡微·順局（丑藏辛財與丁火蓋頭）",
    "author": "任鐵樵增注，李雨田校訂兼發行",
    "edition": "上海大東書局經售，1947年4月初版",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "pdf_pages": [391],
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
}
SCOPE = "逐个真实藏干列同柱生克；hidden_rank只表示当前藏干表序号，不是司令天数、气量轻重或各派统一中余气排序。干克某藏干只给该藏干为所喜时的盖头候选，不抹去其他藏干或全支。未裁定喜忌、干的实际力量、藏干显隐生发、跨柱救应、截脚或根损，不改写旺衰预算。原书单例支持藏干可为目标，不为全部关系提供效力常数。"
LABELS = {
    "same_element": "同五行",
    "hidden_generates_stem": "藏干生干",
    "stem_generates_hidden": "干生藏干",
    "hidden_overcomes_stem": "藏干克干",
    "stem_overcomes_hidden": "干克藏干",
}


def hidden_target_reference() -> dict[str, Any]:
    """Keep one shared source receipt for all temporal target rows."""
    return {
        "method_id": "literal_hidden_target_relations_v1",
        "effective_force_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": SCOPE,
    }


def describe_temporal_hidden_carrier(
    node_id: str, stem: str, branch: str
) -> dict[str, Any]:
    """Publish every target separately from the established principal table.

    The common reference and these pillar/target facts reconstruct the complete
    receipt exactly. The old pillar_carriers array stays byte-compatible.
    """
    full = describe_hidden_targets(stem, branch)
    return {"node_id": node_id, "pillar": full["pillar"], "targets": full["targets"]}


def describe_hidden_targets(stem: str, branch: str) -> dict[str, Any]:
    """Enumerate every literal hidden stem once, with no fitted force quantity."""
    if stem + branch not in SEXAGENARY_INDEX:
        raise ValueError("同柱藏干关系需要六十甲子中的完整干支")
    return _describe_literal_hidden_targets(stem, branch)


def _describe_literal_hidden_targets(stem: str, branch: str) -> dict[str, Any]:
    """Observe literal source characters without inventing a calendar origin."""
    if stem not in STEM_ELEMENTS or branch not in BRANCH_HIDDEN_STEMS:
        raise ValueError("字面藏干关系需要有效的单字天干和地支")
    element = STEM_ELEMENTS[stem][0]
    targets = []
    for index, hidden in enumerate(BRANCH_HIDDEN_STEMS[branch]):
        hidden_element = STEM_ELEMENTS[hidden][0]
        if element == hidden_element:
            relation = "same_element"
        elif GENERATION_CYCLE[hidden_element] == element:
            relation = "hidden_generates_stem"
        elif GENERATION_CYCLE[element] == hidden_element:
            relation = "stem_generates_hidden"
        elif DESTRUCTION_CYCLE[hidden_element] == element:
            relation = "hidden_overcomes_stem"
        else:
            relation = "stem_overcomes_hidden"
        targets.append(
            {
                "hidden_stem": hidden,
                "hidden_rank": index + 1,
                "element": hidden_element.value,
                "relation": relation,
                "covering_candidate_if_target_desired": relation
                == "stem_overcomes_hidden",
            }
        )
    return {
        "method_id": "literal_hidden_target_relations_v1",
        "pillar": stem + branch,
        "targets": targets,
        "effective_force_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": SCOPE,
    }


def build_natal_hidden_carriers(
    pillars: Mapping[str, Tuple[str, str]],
) -> dict[str, Any]:
    day_stem = pillars["day"][0]
    rows = []
    for position in ("year", "month", "day", "hour"):
        stem, branch = pillars[position]
        result = _describe_literal_hidden_targets(stem, branch)
        rows.append(
            {
                "position": position,
                "pillar": result["pillar"],
                **(
                    {"pair_consistency": "literal_nonsexagenary_pair"}
                    if stem + branch not in SEXAGENARY_INDEX
                    else {}
                ),
                "targets": [
                    {
                        **target,
                        "ten_god": get_ten_god(day_stem, target["hidden_stem"]).value,
                    }
                    for target in result["targets"]
                ],
            }
        )
    return {
        "method_id": "literal_hidden_target_relations_v1",
        "pillars": rows,
        "effective_force_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": SCOPE,
    }


def hidden_carrier_snapshot_lines(receipt: Mapping[str, Any]) -> list[str]:
    """Render the supplied natal table, without calculating another chart."""
    labels = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}
    lines = []
    for row in receipt.get("pillars") or []:
        covered = [
            t for t in row["targets"] if t["covering_candidate_if_target_desired"]
        ]
        if covered:
            names = "、".join(
                t["hidden_stem"] + "（" + t["ten_god"] + "）" for t in covered
            )
            lines.append(
                f"{labels[row['position']]}{row['pillar']}：干克本柱藏干{names}；仅在这些藏干为所喜时列盖头候选。"
            )
    if lines:
        lines.append(
            "藏干目标与支本气分别列示；生克关系未裁定真实喜忌、作用程度、救应或根损。"
        )
    return lines
