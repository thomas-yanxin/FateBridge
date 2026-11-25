"""Replayable graph witnesses for Type and Authority, not decision efficacy."""

from collections import deque
from typing import Any

PRIORITY = ("solar_plexus", "sacral", "spleen", "ego", "g")
CENTER_NAMES = {
    "head": "头顶中心",
    "ajna": "逻辑中心",
    "throat": "喉中心",
    "g": "G中心",
    "ego": "意志中心",
    "spleen": "脾中心",
    "sacral": "骶骨中心",
    "solar_plexus": "情绪中心",
    "root": "根部中心",
}


def classification_evidence(
    defined: set[str], channels: list[dict[str, Any]], authority: str
) -> dict[str, Any]:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for channel in channels:
        a, b = channel["centers"]
        adjacency.setdefault(a, []).append((b, channel["id"]))
        adjacency.setdefault(b, []).append((a, channel["id"]))

    def path(start: str, end: str) -> dict[str, Any] | None:
        if start not in defined or end not in defined:
            return None
        pending: deque[tuple[list[str], list[str]]] = deque([([start], [])])
        seen = {start}
        while pending:
            centers, ids = pending.popleft()
            if centers[-1] == end:
                return {"centers": centers, "channel_ids": ids}
            for neighbor, channel_id in sorted(adjacency.get(centers[-1], [])):
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append((centers + [neighbor], ids + [channel_id]))
        return None

    motor_paths = [
        witness
        for motor in ("ego", "root", "sacral", "solar_plexus")
        if (witness := path(motor, "throat")) is not None
    ]
    priority_checks = []
    for center in PRIORITY:
        priority_checks.append({"center": center, "defined": center in defined})
        if center in defined:
            break
    endpoints = {
        "ego_manifested": ("ego", "throat"),
        "ego_projected": ("ego", "g"),
        "self_projected": ("g", "throat"),
    }
    authority_path = path(*endpoints[authority]) if authority in endpoints else None
    return {
        "defined_centers": sorted(defined),
        "motor_to_throat_paths": motor_paths,
        "authority_priority_checks": priority_checks,
        "selected_authority": authority,
        "authority_paths": [authority_path] if authority_path is not None else [],
        "no_inner_authority": authority
        in {"environment_no_inner_authority", "lunar_no_inner_authority"},
        "scope": "Completed natal channels only; one deterministic shortest witness per reachable motor and selected authority connection. No transit, hanging-gate, psychological or predictive inference.",
    }


def authority_structure_text(evidence: dict[str, Any]) -> str:
    """A fixed sentence whose inputs are retained in the same run's graph."""
    checks = evidence["authority_priority_checks"]
    absent = [CENTER_NAMES[row["center"]] for row in checks if not row["defined"]]
    defined = [CENTER_NAMES[row["center"]] for row in checks if row["defined"]]
    authority = evidence["selected_authority"]
    if authority == "lunar_no_inner_authority":
        return "结构依据：没有完整通道，九中心均未定义；月亮过程不属于内在权威。"
    if authority == "environment_no_inner_authority":
        names = "、".join(CENTER_NAMES[c] for c in evidence["defined_centers"])
        return (
            f"结构依据：仅{names}有定义，喉以下中心均未定义；讨论过程不属于内在权威。"
        )
    prefix = "、".join(absent) + "均未定义；" if absent else ""
    paths = evidence["authority_paths"]
    if paths:
        witness = paths[0]
        route = "→".join(CENTER_NAMES[c] for c in witness["centers"])
        return f"结构依据：{prefix}完整通道{'、'.join(witness['channel_ids'])}形成{route}连接。"
    return f"结构依据：{prefix}{'、'.join(defined)}已定义，按权威优先序选中。"
