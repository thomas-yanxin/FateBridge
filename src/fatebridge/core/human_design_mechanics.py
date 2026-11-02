"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from fatebridge.core.astro import runtime
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.human_design_apparent_positions import (
    observed_coordinates,
    record_position_batch,
)
from fatebridge.core.human_design_circuitry import circuitry_summary
from fatebridge.core.human_design_classification import classification_evidence
from fatebridge.core.human_design_natal_sources import observe_native_source
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

RULESET_ID = "human_design_public_mechanics_v1"


RULESET_VERSION = "1.39.0"


GATE_ORDER = (
    41,
    19,
    13,
    49,
    30,
    55,
    37,
    63,
    22,
    36,
    25,
    17,
    21,
    51,
    42,
    3,
    27,
    24,
    2,
    23,
    8,
    20,
    16,
    35,
    45,
    12,
    15,
    52,
    39,
    53,
    62,
    56,
    31,
    33,
    7,
    4,
    29,
    59,
    40,
    64,
    47,
    6,
    46,
    18,
    48,
    57,
    32,
    50,
    28,
    44,
    1,
    43,
    14,
    34,
    9,
    5,
    26,
    11,
    10,
    58,
    38,
    54,
    61,
    60,
)


CENTER_GATES = {
    "head": (64, 61, 63),
    "ajna": (47, 24, 4, 17, 43, 11),
    "throat": (62, 23, 56, 16, 20, 31, 8, 33, 45, 12, 35),
    "g": (1, 2, 7, 10, 13, 15, 25, 46),
    "ego": (21, 26, 40, 51),
    "spleen": (18, 28, 32, 44, 48, 50, 57),
    "sacral": (3, 5, 9, 14, 27, 29, 34, 42, 59),
    "solar_plexus": (6, 22, 30, 36, 37, 49, 55),
    "root": (19, 38, 39, 41, 52, 53, 54, 58, 60),
}


GATE_CENTER = {gate: center for center, gates in CENTER_GATES.items() for gate in gates}


CHANNELS = (
    (64, 47, "collective_sensing"),
    (61, 24, "individual_knowing"),
    (63, 4, "collective_understanding"),
    (17, 62, "collective_understanding"),
    (43, 23, "individual_knowing"),
    (11, 56, "collective_sensing"),
    (7, 31, "collective_understanding"),
    (1, 8, "individual_knowing"),
    (13, 33, "collective_sensing"),
    (10, 20, "integration"),
    (16, 48, "collective_understanding"),
    (20, 57, "individual_knowing"),
    (20, 34, "integration"),
    (12, 22, "individual_knowing"),
    (35, 36, "collective_sensing"),
    (21, 45, "tribal_ego"),
    (2, 14, "individual_knowing"),
    (5, 15, "collective_understanding"),
    (29, 46, "collective_sensing"),
    (10, 34, "individual_centering"),
    (10, 57, "integration"),
    (25, 51, "individual_centering"),
    (26, 44, "tribal_ego"),
    (37, 40, "tribal_ego"),
    (27, 50, "tribal_defense"),
    (6, 59, "tribal_defense"),
    (3, 60, "individual_knowing"),
    (9, 52, "collective_understanding"),
    (42, 53, "collective_sensing"),
    (34, 57, "integration"),
    (32, 54, "tribal_ego"),
    (28, 38, "individual_knowing"),
    (18, 58, "collective_understanding"),
    (19, 49, "tribal_ego"),
    (39, 55, "individual_knowing"),
    (30, 41, "collective_sensing"),
)


MOTORS = {"ego", "sacral", "solar_plexus", "root"}


BODY_IDS = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
    "Uranus": 7,
    "Neptune": 8,
    "Pluto": 9,
}


VALID_PROFILES = {
    "1/3",
    "1/4",
    "2/4",
    "2/5",
    "3/5",
    "3/6",
    "4/6",
    "4/1",
    "5/1",
    "5/2",
    "6/2",
    "6/3",
}


def longitude_activation(longitude: float) -> Dict[str, Any]:
    """Half-open sectors; never round a longitude before assigning a sector.

    Exact arithmetic on the supplied binary float avoids losing a neighboring
    float through subtraction/modulo rounding. No epsilon shifts a boundary.
    """
    if not math.isfinite(longitude):
        raise ValueError("人类图黄经必须为有限数值")
    return _rational_activation(Fraction(longitude) % 360)


def opposite_activation(source_longitude: float) -> Dict[str, Any]:
    """Classify exact 180-degree opposition before rounding its display float."""
    if not math.isfinite(source_longitude):
        raise ValueError("人类图对点来源黄经必须为有限数值")
    return {
        **_rational_activation((Fraction(source_longitude) + 180) % 360),
        "derivation_source_longitude": source_longitude,
    }


def _rational_activation(normalized: Fraction) -> Dict[str, Any]:
    units = ((normalized - 302) % 360) * 192  # base = 18.75 arcseconds
    index = int(units // 1080)
    within = units - index * 1080
    line_index = int(within // 180)
    color_index = int((within % 180) // 30)
    tone_index = int((within % 30) // 5)
    base_index = int(within % 5)
    gate = GATE_ORDER[index]
    return {
        "longitude": float(normalized) % 360.0,
        "gate": gate,
        "center": GATE_CENTER[gate],
        "line": line_index + 1,
        "color": color_index + 1,
        "tone": tone_index + 1,
        "base": base_index + 1,
        "tone_orientation": "left" if tone_index < 3 else "right",
        "gate_start_longitude": (302.0 + index * 5.625) % 360.0,
        "line_boundary_distance_degrees": float(
            min(within % 180, 180 - within % 180) / 192
        ),
        "base_boundary_distance_arcseconds": float(
            min(units % 1, 1 - units % 1) * Fraction(75, 4)
        ),
    }


def positions_at_tt(
    jd_tt: float,
    node_mode: str,
    *,
    require_swiss_files: bool = False,
    backend: str = "swieph",
    source_observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
    source_role: str = "activation",
) -> Dict[str, Any]:
    if runtime.swe is None:
        raise RuntimeError("人类图需要 Swiss Ephemeris")
    if node_mode not in {"true", "mean"}:
        raise ValueError("node_mode 必须为 true 或 mean")
    if backend not in {"swieph", "moshier"}:
        raise ValueError("人类图星历请求后端必须为 swieph 或 moshier")
    if backend == "moshier" and require_swiss_files:
        raise ValueError("强制 Moshier 与要求 Swiss 数据文件冲突")
    if require_swiss_files and configured_jpl_file() is not None:
        raise EphemerisSourceError("jpl_swiss_file_requirement_conflict")
    ids = {
        **BODY_IDS,
        "NorthNode": (
            runtime.swe.TRUE_NODE if node_mode == "true" else runtime.swe.MEAN_NODE
        ),
    }
    positions: Dict[str, Any] = {}
    physical_coordinates = []
    try:
        for body, body_id in ids.items():
            coords, flags = runtime.ephemeris_call(
                "calc",
                jd_tt,
                body_id,
                (
                    runtime.swe.FLG_MOSEPH
                    if backend == "moshier"
                    else runtime.swe.FLG_SWIEPH
                )
                | runtime.swe.FLG_SPEED,
            )
            try:
                model = position_flag_model(flags)
            except ValueError as exc:
                raise RuntimeError(
                    "Swiss Ephemeris 返回旗标与人类图坐标／速度口径不一致"
                ) from exc
            if not all(math.isfinite(float(coords[i])) for i in (0, 3)):
                raise RuntimeError(f"Swiss Ephemeris 未返回有效的 {body} 位置")
            if model not in {"swieph", "moshier", "jpl"}:
                raise RuntimeError("Swiss Ephemeris 返回未识别的星历后端标记")
            if require_swiss_files and model != "swieph":
                raise RuntimeError("要求 Swiss Ephemeris 数据文件，但实际后端发生降级")
            if backend == "moshier" and model != "moshier":
                raise RuntimeError("整盘参考后端未实际采用 Moshier")
            observe_native_source(
                body,
                jd_tt,
                flags,
                role=source_role,
                analytical=body == "NorthNode" and node_mode == "mean",
            )
            positions[body] = {
                "longitude": float(coords[0]) % 360.0,
                "longitude_speed": float(coords[3]),
                "ephemeris_model": native_factor_model(body_id, flags),
                "return_flags": int(flags),
                **({"native_return_flag_model": model} if body == "NorthNode" else {}),
            }
            if body in BODY_IDS:
                physical_coordinates.append(
                    {
                        "body": body,
                        "native_coordinates": observed_coordinates(coords),
                        "return_flags": int(flags),
                        "ephemeris_model": model,
                    }
                )
            if source_observer is not None:
                source_observer(body, jd_tt, dict(positions[body]))
    finally:
        if physical_coordinates:
            record_position_batch(
                positions, jd_tt, node_mode, backend, source_role, physical_coordinates
            )
    for body, opposite in (("Earth", "Sun"), ("SouthNode", "NorthNode")):
        source_longitude = positions[opposite]["longitude"]
        positions[body] = {
            **positions[opposite],
            "longitude": float((Fraction(source_longitude) + 180) % 360) % 360.0,
            "derived_from": opposite,
            "derivation_source_longitude": source_longitude,
        }
    return positions


def _components(active: Set[int]) -> List[List[str]]:
    graph: Dict[str, Set[str]] = {}
    for a, b, _ in CHANNELS:
        if {a, b} <= active:
            x, y = GATE_CENTER[a], GATE_CENTER[b]
            graph.setdefault(x, set()).add(y)
            graph.setdefault(y, set()).add(x)
    remaining = set(graph)
    groups = []
    while remaining:
        queue, found = [min(remaining)], set()
        while queue:
            center = queue.pop()
            if center in found:
                continue
            found.add(center)
            queue.extend(graph[center] - found)
        groups.append(sorted(found))
        remaining -= found
    return sorted(groups)


def bodygraph(personality: Iterable[int], design: Iterable[int]) -> Dict[str, Any]:
    """Definition requires two channel ends, across either calculation side."""
    p, d = set(personality), set(design)
    active = p | d
    if not active <= set(GATE_CENTER):
        raise ValueError("人类图门号必须在 1 至 64 之间")
    groups = _components(active)
    defined = set().union(*(set(group) for group in groups)) if groups else set()
    throat_group = next((set(g) for g in groups if "throat" in g), set())
    motor_path = bool(throat_group & MOTORS)
    if not defined:
        type_id, subtype = "reflector", None
    elif "sacral" in defined:
        type_id, subtype = (
            "generator",
            ("manifesting_generator" if motor_path else "pure_generator"),
        )
    elif motor_path:
        type_id, subtype = "manifestor", None
    else:
        type_id, subtype = "projector", None
    if "solar_plexus" in defined:
        authority = "emotional"
    elif "sacral" in defined:
        authority = "sacral"
    elif "spleen" in defined:
        authority = "splenic"
    elif "ego" in defined:
        authority = "ego_manifested" if type_id == "manifestor" else "ego_projected"
    elif "g" in defined:
        authority = "self_projected"
    elif type_id == "reflector":
        authority = "lunar_no_inner_authority"
    else:
        authority = "environment_no_inner_authority"
    channels: List[Dict[str, Any]] = []
    for a, b, circuit in CHANNELS:
        if {a, b} <= active:
            channels.append(
                {
                    "id": f"{a}-{b}",
                    "gates": [a, b],
                    "centers": [GATE_CENTER[a], GATE_CENTER[b]],
                    "circuit": circuit,
                    "personality_complete": {a, b} <= p,
                    "design_complete": {a, b} <= d,
                    "mixed_only": not ({a, b} <= p or {a, b} <= d),
                }
            )
    centers = {
        center: {
            "status": (
                "defined"
                if center in defined
                else "undefined" if set(gates) & active else "completely_open"
            ),
            "activated_gates": sorted(set(gates) & active),
        }
        for center, gates in CENTER_GATES.items()
    }
    bridges = []
    if len(groups) > 1:
        for gate in sorted(set(GATE_CENTER) - active):
            new_groups = _components(active | {gate})
            if any(
                sum(bool(set(group) & set(original)) for original in groups) > 1
                for group in new_groups
            ):
                bridges.append(gate)
    return {
        "type": type_id,
        "subtype": subtype,
        "authority": authority,
        "strategy": {
            "generator": "respond",
            "manifestor": "inform",
            "projector": "recognition_and_invitation",
            "reflector": "wait_a_lunar_cycle",
        }[type_id],
        "motor_to_throat": motor_path,
        "classification_evidence": classification_evidence(
            defined, channels, authority
        ),
        "definition": {
            "kind": ("none", "single", "split", "triple_split", "quadruple_split")[
                len(groups)
            ],
            "components": groups,
            "single_gate_bridges": bridges,
            "bridge_scope": "single_added_gate_connecting_existing_components_only",
        },
        "centers": centers,
        "channels": channels,
        "circuitry": circuitry_summary(channels, active),
        "activated_gates": sorted(active),
        "hanging_gates": sorted(
            active - {gate for ch in channels for gate in ch["gates"]}
        ),
        "gate_sources": {
            str(gate): [
                side
                for side, values in (("personality", p), ("design", d))
                if gate in values
            ]
            for gate in sorted(active)
        },
    }
