"""Core Human Design bodygraph mechanics, Rave Mandala, Variables, PHS, and Composite/Transit helpers."""

from __future__ import annotations

import heapq
import math
from collections import Counter
from fractions import Fraction
from typing import Any, Iterable, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

RULESET_ID = "human_design_public_mechanics_v2"
RULESET_VERSION = "2.0.0"

GATE_ORDER: tuple[int, ...] = (
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

CENTER_GATES: dict[str, tuple[int, ...]] = {
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

GATE_CENTER: dict[int, str] = {
    gate: center for center, gates in CENTER_GATES.items() for gate in gates
}

CHANNELS: tuple[tuple[int, int, str], ...] = (
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

MOTORS = frozenset({"ego", "sacral", "solar_plexus", "root"})

BODY_IDS: dict[str, int] = {
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

VALID_PROFILES = frozenset(
    {"1/3", "1/4", "2/4", "2/5", "3/5", "3/6", "4/6", "4/1", "5/1", "5/2", "6/2", "6/3"}
)

INTEGRATION_PAIRS = frozenset({(10, 20), (10, 57), (20, 34), (34, 57)})
INTEGRATION_GATES = frozenset({10, 20, 34, 57})
CIRCUIT_GROUP: dict[str, str] = {
    "individual_knowing": "individual",
    "individual_centering": "individual",
    "collective_understanding": "collective",
    "collective_sensing": "collective",
    "tribal_ego": "tribal",
    "tribal_defense": "tribal",
    "integration": "individual",
}

STRATEGY_BY_TYPE: dict[str, str] = {
    "generator": "wait_to_respond",
    "manifestor": "inform_before_acting",
    "projector": "wait_for_invitation",
    "reflector": "wait_a_lunar_cycle",
}

# Variable Color & Tone Lookup Tables (Jovian Archive / Ra Uru Hu)
PHS_DETERMINATION: dict[int, tuple[str, str, str]] = {
    1: ("Appetite", "Consecutive", "Alternating"),
    2: ("Taste", "Open", "Closed"),
    3: ("Thirst", "Hot", "Cold"),
    4: ("Touch", "Calm", "Nervous"),
    5: ("Sound", "High", "Low"),
    6: ("Light", "Direct", "Indirect"),
}

ENVIRONMENT_TYPES: dict[int, tuple[str, str, str]] = {
    1: ("Caves", "Selective", "Blending"),
    2: ("Markets", "Internal", "External"),
    3: ("Kitchens", "Wet", "Dry"),
    4: ("Mountains", "Active", "Passive"),
    5: ("Valleys", "Narrow", "Wide"),
    6: ("Shores", "Natural", "Artificial"),
}

MOTIVATION_TERMS: dict[int, tuple[str, str]] = {
    1: ("Fear", "Need"),
    2: ("Hope", "Guilt"),
    3: ("Desire", "Innocence"),
    4: ("Need", "Fear"),
    5: ("Guilt", "Hope"),
    6: ("Innocence", "Desire"),
}

VIEW_TERMS: dict[int, tuple[str, str]] = {
    1: ("Survival", "Wanting"),
    2: ("Possibility", "Probability"),
    3: ("Power", "Personal"),
    4: ("Wanting", "Survival"),
    5: ("Probability", "Possibility"),
    6: ("Personal", "Power"),
}

COGNITION_TERMS: dict[int, str] = {
    1: "Smell",
    2: "Taste",
    3: "Outer Vision",
    4: "Inner Vision",
    5: "Feeling",
    6: "Touch",
}

SENSE_TERMS: dict[int, str] = {
    1: "Security",
    2: "Uncertainty",
    3: "Action",
    4: "Meditation",
    5: "Judgment",
    6: "Acceptance",
}

VARIABLE_COMPONENTS: tuple[tuple[str, str, tuple[str, str], str], ...] = (
    ("design_sun_earth", "design", ("Sun", "Earth"), "top_left"),
    ("design_nodes", "design", ("NorthNode", "SouthNode"), "bottom_left"),
    ("personality_sun_earth", "personality", ("Sun", "Earth"), "top_right"),
    ("personality_nodes", "personality", ("NorthNode", "SouthNode"), "bottom_right"),
)
NOTATION_ORDER: tuple[str, ...] = (
    "personality_sun_earth",
    "personality_nodes",
    "design_sun_earth",
    "design_nodes",
)


def position_flag_model(return_flags: int) -> str:
    """Validate Swiss Ephemeris calc return flags and map to backend name."""
    if runtime.swe is None:
        raise RuntimeError("人类图需要 Swiss Ephemeris")
    if type(return_flags) is not int or return_flags < 0:
        raise ValueError("Swiss Ephemeris 返回旗标无效")
    model = runtime.ephemeris_model_from_retflag(return_flags)
    if model not in {"swieph", "moshier", "jpl"}:
        raise ValueError("Swiss Ephemeris 返回未识别的星历后端标记")
    return model


def _rational_activation(normalized: Fraction) -> dict[str, Any]:
    units = ((normalized - 302) % 360) * 192  # 1 base = 18.75 arcseconds
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


def longitude_activation(longitude: float) -> dict[str, Any]:
    """Half-open Rave Mandala sectors with exact rational boundary classification."""
    if not math.isfinite(longitude):
        raise ValueError("人类图黄经必须为有限数值")
    return _rational_activation(Fraction(longitude) % 360)


def opposite_activation(source_longitude: float) -> dict[str, Any]:
    """Classify exact 180-degree opposition before rounding display float."""
    if not math.isfinite(source_longitude):
        raise ValueError("人类图对点来源黄经必须为有限数值")
    return {
        **_rational_activation((Fraction(source_longitude) + 180) % 360),
        "derivation_source_longitude": source_longitude,
    }


def activation_longitude_fraction(activation: dict[str, Any]) -> Fraction:
    """Recover exact rational longitude, handling derived 180-degree oppositions."""
    if activation.get("derived_from") is not None:
        if activation["derived_from"] not in {"Sun", "NorthNode"}:
            raise ValueError("人类图对点来源必须为 Sun 或 NorthNode")
        source = activation["derivation_source_longitude"]
        if not math.isfinite(source):
            raise ValueError("人类图对点来源黄经必须为有限数值")
        return (Fraction(source) + 180) % 360
    if "derivation_source_longitude" in activation:
        raise ValueError("人类图对点来源数值必须同时标明 derived_from")
    longitude = activation["longitude"]
    if not math.isfinite(longitude):
        raise ValueError("人类图黄经必须为有限数值")
    return Fraction(longitude) % 360


def positions_at_tt(
    jd_tt: float,
    node_mode: str,
    *,
    require_swiss_files: bool = False,
    backend: str = "swieph",
) -> dict[str, Any]:
    """Compute geocentric tropical ecliptic coordinates directly under EPHEMERIS_LOCK."""
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
    base_flag = (
        runtime.swe.FLG_MOSEPH if backend == "moshier" else runtime.swe.FLG_SWIEPH
    ) | runtime.swe.FLG_SPEED
    positions: dict[str, Any] = {}
    for body, body_id in ids.items():
        coords, flags = runtime.ephemeris_call("calc", jd_tt, body_id, base_flag)
        model = position_flag_model(flags)
        if not all(math.isfinite(float(coords[i])) for i in (0, 3)):
            raise RuntimeError(f"Swiss Ephemeris 未返回有效的 {body} 位置")
        if require_swiss_files and model != "swieph":
            raise RuntimeError("要求 Swiss Ephemeris 数据文件，但实际后端发生降级")
        if backend == "moshier" and model != "moshier":
            raise RuntimeError("整盘参考后端未实际采用 Moshier")
        positions[body] = {
            "longitude": float(coords[0]) % 360.0,
            "longitude_speed": float(coords[3]),
            "ephemeris_model": native_factor_model(body_id, flags),
            "return_flags": int(flags),
            **({"native_return_flag_model": model} if body == "NorthNode" else {}),
        }
    for body, opposite in (("Earth", "Sun"), ("SouthNode", "NorthNode")):
        source_longitude = positions[opposite]["longitude"]
        positions[body] = {
            **positions[opposite],
            "longitude": float((Fraction(source_longitude) + 180) % 360) % 360.0,
            "derived_from": opposite,
            "derivation_source_longitude": source_longitude,
        }
    return positions


def _components(active: set[int]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for a, b, _ in CHANNELS:
        if {a, b} <= active:
            x, y = GATE_CENTER[a], GATE_CENTER[b]
            graph.setdefault(x, set()).add(y)
            graph.setdefault(y, set()).add(x)
    remaining = set(graph)
    groups: list[list[str]] = []
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


def circuitry_summary(
    channels: Sequence[dict[str, Any]], active_gates: Iterable[int]
) -> dict[str, Any]:
    counts = Counter(channel["circuit"] for channel in channels)
    circuits = [
        {
            "id": circuit,
            "group": CIRCUIT_GROUP[circuit],
            "channel_ids": [ch["id"] for ch in channels if ch["circuit"] == circuit],
            "channel_count": counts[circuit],
        }
        for circuit in sorted(counts)
    ]
    integration = [
        ch["id"] for ch in channels if tuple(sorted(ch["gates"])) in INTEGRATION_PAIRS
    ]
    return {
        "defined_channel_count": len(channels),
        "circuits": circuits,
        "group_channel_counts": {
            group: sum(counts[c] for c, g in CIRCUIT_GROUP.items() if g == group)
            for group in ("individual", "collective", "tribal")
        },
        "integration": {
            "activated_gates": sorted(set(active_gates) & INTEGRATION_GATES),
            "completed_channel_ids": integration,
            "all_four_channels_complete": len(integration) == 4,
        },
    }


def bodygraph(personality: Iterable[int], design: Iterable[int]) -> dict[str, Any]:
    """Compute Type, Authority, Strategy, Definition, Centers, Channels, and Circuitry."""
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
    channels: list[dict[str, Any]] = []
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
    completed = {gate for ch in channels for gate in ch["gates"]}
    centers = {
        center: {
            "status": "defined" if center in defined else "undefined",
            "activated_gates": sorted(set(gates) & active),
        }
        for center, gates in CENTER_GATES.items()
    }
    def_kind = {0: "none", 1: "single", 2: "split", 3: "triple", 4: "quadruple"}.get(
        len(groups), "split"
    )
    single_gate_bridges: list[int] = []
    if len(groups) > 1:
        for candidate in sorted(set(GATE_CENTER) - active):
            if len(_components(active | {candidate})) < len(groups):
                single_gate_bridges.append(candidate)
    return {
        "type": type_id,
        "subtype": subtype,
        "authority": authority,
        "strategy": STRATEGY_BY_TYPE[type_id],
        "motor_to_throat": motor_path,
        "definition": {
            "kind": def_kind,
            "components": groups,
            "single_gate_bridges": single_gate_bridges,
        },
        "centers": centers,
        "channels": channels,
        "circuitry": circuitry_summary(channels, active),
        "activated_gates": sorted(active),
        "hanging_gates": sorted(active - completed),
        "gate_sources": {
            str(g): [
                *(["personality"] if g in p else []),
                *(["design"] if g in d else []),
            ]
            for g in sorted(active)
        },
    }


def definition_bridging(graph: dict[str, Any]) -> dict[str, Any]:
    """Compute exact minimum absent-gate bridge sets for split definitions."""
    active = set(graph["activated_gates"])
    groups = graph["definition"]["components"]
    if len(groups) <= 1:
        return {
            "status": "not_applicable_no_split",
            "original_components": groups,
            "original_component_count": len(groups),
            "single_gate_merges": [],
            "minimum_added_gate_count": None,
            "minimum_solution_count": 0,
            "minimum_solutions": [],
        }
    names = sorted(set(GATE_CENTER.values()))
    center_bits = {name: 1 << idx for idx, name in enumerate(names)}
    edges = [
        (
            sum(1 << (g - 1) for g in (a, b)),
            center_bits[GATE_CENTER[a]],
            center_bits[GATE_CENTER[b]],
        )
        for a, b, _ in CHANNELS
    ]
    adjacency: dict[int, list[tuple[int, int]]] = {b: [] for b in center_bits.values()}
    for gates, a, b in edges:
        adjacency[a].append((gates, b))
        adjacency[b].append((gates, a))
    active_mask = sum(1 << (g - 1) for g in active)
    required = sum(center_bits[c] for group in groups for c in group)
    start = sum(center_bits[c] for c in groups[0])

    def reachable(mask: int) -> int:
        known = start
        pending = [bit for bit in center_bits.values() if bit & start]
        while pending:
            for gates, neighbor in adjacency[pending.pop()]:
                if not known & neighbor and mask & gates == gates:
                    known |= neighbor
                    pending.append(neighbor)
        return known

    best: int | None = None
    solutions: list[list[int]] = []
    seen = {0}
    pending_heap = [(0, 0)]
    while pending_heap:
        count, added = heapq.heappop(pending_heap)
        if best is not None and count > best:
            break
        region = reachable(active_mask | added)
        if region & required == required:
            best = count
            solutions.append([g for g in range(1, 65) if added & (1 << (g - 1))])
            continue
        for gates, a, b in edges:
            if bool(region & a) == bool(region & b):
                continue
            candidate = added | (gates & ~active_mask)
            if candidate in seen:
                continue
            cost = candidate.bit_count()
            if best is not None and cost > best:
                continue
            seen.add(candidate)
            heapq.heappush(pending_heap, (cost, candidate))

    def witness(added_gates: list[int]) -> dict[str, Any]:
        augmented = active | set(added_gates)
        return {
            "added_gates": added_gates,
            "newly_completed_channel_ids": [
                f"{a}-{b}"
                for a, b, _ in CHANNELS
                if {a, b} <= augmented and not {a, b} <= active
            ],
            "result_components": _components(augmented),
        }

    solutions.sort()
    witnesses = [witness(g) for g in solutions]
    return {
        "status": "computed_exact_graph_minimum",
        "original_components": groups,
        "original_component_count": len(groups),
        "single_gate_merges": [
            witness([g]) for g in graph["definition"]["single_gate_bridges"]
        ],
        "minimum_added_gate_count": best,
        "minimum_solution_count": len(witnesses),
        "minimum_solutions": witnesses,
    }


def _pair_subdivision(
    activations: dict[str, Any], side: str, pair: tuple[str, str], field: str
) -> tuple[int | None, list[dict[str, Any]], str]:
    items = activations.get(side, [])
    matches = [
        [(i, a) for i, a in enumerate(items) if a.get("body") == b] for b in pair
    ]
    valid = all(
        len(found) == 1
        and type(found[0][1].get(field)) is int
        and 1 <= found[0][1][field] <= 6
        for found in matches
    )
    if not valid:
        return None, [], "missing_or_invalid_pair"
    v0 = matches[0][0][1][field]
    v1 = matches[1][0][1][field]
    basis = [
        {
            "path": f"activations.{side}.{found[0][0]}.{field}",
            "value": found[0][1][field],
        }
        for found in matches
    ]
    if v0 != v1:
        return None, basis, "inconsistent_pair"
    return v0, basis, "computed"


def variables_from_activations(activations: dict[str, Any]) -> dict[str, Any]:
    """Compute Variables (PRR DLL), PHS Determination, Environment, Motivation, View, Cognition, Sense."""
    arrows: list[dict[str, Any]] = []
    for component, side, pair, position in VARIABLE_COMPONENTS:
        tone, basis, status = _pair_subdivision(activations, side, pair, "tone")
        orientation = ("left" if tone <= 3 else "right") if tone is not None else None
        arrows.append(
            {
                "component": component,
                "side": side,
                "body_pair": list(pair),
                "position": position,
                "status": status,
                "tone": tone,
                "orientation": orientation,
                "letter": orientation[0].upper() if orientation else None,
                "pair_tones_consistent": status == "computed",
                "basis": basis,
            }
        )
    by_id = {a["component"]: a for a in arrows}
    computed = all(a["status"] == "computed" for a in arrows)
    code = (
        f"P{by_id['personality_sun_earth']['letter']}{by_id['personality_nodes']['letter']} "
        f"D{by_id['design_sun_earth']['letter']}{by_id['design_nodes']['letter']}"
        if computed
        else None
    )

    d_sun_color, _, _ = _pair_subdivision(
        activations, "design", ("Sun", "Earth"), "color"
    )
    d_node_color, _, _ = _pair_subdivision(
        activations, "design", ("NorthNode", "SouthNode"), "color"
    )
    p_sun_color, p_sun_basis, p_sun_status = _pair_subdivision(
        activations, "personality", ("Sun", "Earth"), "color"
    )
    p_node_color, p_node_basis, p_node_status = _pair_subdivision(
        activations, "personality", ("NorthNode", "SouthNode"), "color"
    )
    d_sun_tone = by_id["design_sun_earth"]["tone"]
    p_sun_tone = by_id["personality_sun_earth"]["tone"]

    phs_det: dict[str, Any] | None = None
    if d_sun_color is not None:
        base_name, left_sub, right_sub = PHS_DETERMINATION[d_sun_color]
        orient = by_id["design_sun_earth"]["orientation"]
        sub = (
            left_sub if orient == "left" else (right_sub if orient == "right" else None)
        )
        phs_det = {
            "color": d_sun_color,
            "tone": d_sun_tone,
            "determination": base_name,
            "sub_type": sub,
            "label": f"{sub} {base_name}" if sub else base_name,
        }

    environment: dict[str, Any] | None = None
    if d_node_color is not None:
        base_name, left_sub, right_sub = ENVIRONMENT_TYPES[d_node_color]
        orient = by_id["design_nodes"]["orientation"]
        sub = (
            left_sub if orient == "left" else (right_sub if orient == "right" else None)
        )
        environment = {
            "color": d_node_color,
            "tone": by_id["design_nodes"]["tone"],
            "environment": base_name,
            "sub_type": sub,
            "label": f"{sub} {base_name}" if sub else base_name,
        }

    motivation = (
        {
            "status": p_sun_status,
            "color": p_sun_color,
            "source_term": MOTIVATION_TERMS[p_sun_color][0] if p_sun_color else None,
            "transference": MOTIVATION_TERMS[p_sun_color][1] if p_sun_color else None,
            "basis": p_sun_basis,
        }
        if p_sun_color is not None
        else {
            "status": p_sun_status,
            "color": None,
            "source_term": None,
            "basis": p_sun_basis,
        }
    )
    view = (
        {
            "status": p_node_status,
            "color": p_node_color,
            "source_term": VIEW_TERMS[p_node_color][0] if p_node_color else None,
            "distraction": VIEW_TERMS[p_node_color][1] if p_node_color else None,
            "basis": p_node_basis,
        }
        if p_node_color is not None
        else {
            "status": p_node_status,
            "color": None,
            "source_term": None,
            "basis": p_node_basis,
        }
    )
    cognition = (
        {"tone": d_sun_tone, "name": COGNITION_TERMS[d_sun_tone]}
        if d_sun_tone is not None
        else None
    )
    sense = (
        {"tone": p_sun_tone, "name": SENSE_TERMS[p_sun_tone]}
        if p_sun_tone is not None
        else None
    )

    return {
        "status": "computed" if computed else "incomplete_or_inconsistent",
        "code": code,
        "arrows": arrows,
        "notation_order": list(NOTATION_ORDER),
        "phs_determination": phs_det,
        "environment": environment,
        "motivation": motivation,
        "view": view,
        "cognition": cognition,
        "sense": sense,
        "personality_colors": {
            "status": (
                "computed"
                if p_sun_status == "computed" and p_node_status == "computed"
                else "incomplete_or_inconsistent"
            ),
            "motivation": motivation,
            "view": view,
        },
    }


def composite_bodygraph(
    chart_a: dict[str, Any], chart_b: dict[str, Any]
) -> dict[str, Any]:
    """Classify connection channels (electromagnetic, dominance, compromise, companionship)."""
    gates_a = set(chart_a["bodygraph"]["activated_gates"])
    gates_b = set(chart_b["bodygraph"]["activated_gates"])
    ch_a = {ch["id"] for ch in chart_a["bodygraph"]["channels"]}
    ch_b = {ch["id"] for ch in chart_b["bodygraph"]["channels"]}
    combined = bodygraph(gates_a, gates_b)
    electromagnetic: list[str] = []
    dominance_a: list[str] = []
    dominance_b: list[str] = []
    compromise_a: list[str] = []
    compromise_b: list[str] = []
    companionship: list[str] = []
    for ch in combined["channels"]:
        cid = ch["id"]
        a_gate, b_gate = ch["gates"]
        in_a, in_b = cid in ch_a, cid in ch_b
        if in_a and in_b:
            companionship.append(cid)
        elif in_a and not in_b:
            if (a_gate in gates_b) or (b_gate in gates_b):
                compromise_a.append(cid)
            else:
                dominance_a.append(cid)
        elif in_b and not in_a:
            if (a_gate in gates_a) or (b_gate in gates_a):
                compromise_b.append(cid)
            else:
                dominance_b.append(cid)
        else:
            electromagnetic.append(cid)
    return {
        "composite_bodygraph": combined,
        "connection_channels": {
            "electromagnetic": electromagnetic,
            "dominance_person_a": dominance_a,
            "dominance_person_b": dominance_b,
            "compromise_person_a": compromise_a,
            "compromise_person_b": compromise_b,
            "companionship": companionship,
        },
    }


def transit_overlay(
    natal_chart: dict[str, Any], transit_positions: dict[str, Any]
) -> dict[str, Any]:
    """Overlay momentary transit gates onto a natal bodygraph."""
    natal_gates = set(natal_chart["bodygraph"]["activated_gates"])
    natal_channels = {ch["id"] for ch in natal_chart["bodygraph"]["channels"]}
    transit_activations = [
        {
            "body": body,
            **state,
            **_rational_activation(activation_longitude_fraction(state)),
        }
        for body, state in transit_positions.items()
    ]
    transit_gates = {a["gate"] for a in transit_activations}
    combined = bodygraph(natal_gates, transit_gates)
    newly_activated_channels = [
        ch["id"] for ch in combined["channels"] if ch["id"] not in natal_channels
    ]
    newly_defined_centers = sorted(
        center
        for center, info in combined["centers"].items()
        if info["status"] == "defined"
        and natal_chart["bodygraph"]["centers"][center]["status"] == "undefined"
    )
    return {
        "transit_activations": transit_activations,
        "transit_gates": sorted(transit_gates),
        "newly_activated_channels": newly_activated_channels,
        "newly_defined_centers": newly_defined_centers,
        "combined_type": combined["type"],
        "combined_authority": combined["authority"],
    }
