"""Selected-text direction for the distinct 四墓土 movement mechanism.

The scanned 子平真诠 PDF44–45 calls this 冲动 rather than 冲克. It
does not give numeric weights, certify formation, or release stored elements.
"""

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, Sequence

from fatebridge.core.classical_roots import SOURCE as ROOT_SOURCE
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, get_shishen

SOURCE = {
    **ROOT_SOURCE,
    "id": "ziping_storage_movement_v1",
    "title": "秘本子平真诠·论墓库刑冲之说",
    "pdf_pages": [44, 45],
    "printed_pages": [35, 36],
}
_CLASHES = {frozenset("辰戌"), frozenset("丑未")}


def storage_movement_effect(
    branches: Mapping[str, str],
    positions: Sequence[str],
    kind: str,
    day_stem: str,
    water_retention: float,
) -> Optional[Dict[str, Any]]:
    """Separate a text-supported direction from an explicit numeric policy.

    Only actual participating positions qualify. A lone storage branch,
    incomplete earth punishment, or different clash cannot trigger this rule.
    """
    present = frozenset(branches[p] for p in positions)
    applicable = (kind == "六冲" and len(positions) == 2 and present in _CLASHES) or (
        kind == "刑" and present == frozenset("丑未戌")
    )
    if not applicable:
        return None
    retention = min(1.0, max(0.0, water_retention))
    return {
        "method_id": "ziping_storage_movement_v1",
        "movement_kind": "same_element_earth_movement",
        "root_effects": [
            {
                "pillar": name,
                "branch": branches[name],
                "stem": stem,
                "element": STEM_ELEMENTS[stem][0].value,
                "ten_god": get_shishen(day_stem, stem),
                "event_retention_multiplier": (
                    retention if STEM_ELEMENTS[stem][0].value == "水" else 1.0
                ),
                "basis": (
                    "earth_movement_water_control_engineering_retention"
                    if STEM_ELEMENTS[stem][0].value == "水"
                    else "no_automatic_root_damage_or_release_by_this_event"
                ),
            }
            for name in positions
            for stem in BRANCH_HIDDEN_STEMS[branches[name]]
        ],
        "earth_energy_bonus": 0.0,
        "water_retention_policy": retention,
        "numeric_magnitude_origin": "engineering_policy_not_classical_coefficient",
        "formation_status": "not_adjudicated",
        "source": deepcopy(SOURCE),
        "scope": "本事件按所选原典保留土根，不自动增土或释放金木水火；土动对参与支水根的减损幅度沿用工程参数。未裁定全局制化、透干财官是否有效或成格。其他合绊、刑冲仍分别作用。",
    }


def storage_movement_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    """Quote supplied event factors only; do not infer a chart from the text."""
    labels = {"year": "年支", "month": "月支", "day": "日支", "hour": "时支"}
    lines = []
    for event in assessment.get("relations", []):
        effect = event.get("storage_effect")
        if not effect:
            continue
        roots = effect["root_effects"]
        seats = list(
            dict.fromkeys(
                labels.get(r["pillar"], r["pillar"]) + r["branch"] for r in roots
            )
        )
        factors = list(
            dict.fromkeys(
                f"{r['element']}根本事件保留系数{r['event_retention_multiplier']:g}"
                for r in roots
                if r["element"] in {"土", "水"}
            )
        )
        lines.append(
            f"四墓土冲动（{event['kind']}）：{'、'.join(seats)}；{'，'.join(factors)}。"
        )
    if lines:
        lines.append(
            "保留系数为工程约定；其他合绊等作用及最终根量另见同次回执，不据本条判开库或成格。"
        )
    return lines
