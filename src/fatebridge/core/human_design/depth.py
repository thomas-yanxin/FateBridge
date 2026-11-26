"""Human Design Rave I'Ching depth tables, Incarnation Cross names, and pure line-fixing facts."""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from importlib.resources import files
from typing import Any

NODES = frozenset({"NorthNode", "SouthNode"})
SIDES = ("personality", "design")

ANGLE_PREFIX: dict[str, str] = {
    "right": "Right Angle Cross of",
    "juxtaposition": "Juxtaposition Cross of",
    "left": "Left Angle Cross of",
}


def _load_json(filename: str) -> dict[str, Any]:
    raw = (
        files("fatebridge.data")
        .joinpath("human_design")
        .joinpath(filename)
        .read_bytes()
    )
    data: dict[str, Any] = json.loads(raw)
    return data


@lru_cache(maxsize=1)
def depth_reference() -> dict[str, Any]:
    return _load_json("rave-2001-depth.json")


@lru_cache(maxsize=1)
def _additional_polarities() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("additional-polarities-2001.json")["facts"])


def facts_for(gate: int, line: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in _additional_polarities()
        if (row["gate"], row["line"]) == (gate, line)
    ]


def _format_cross_title(raw_name: str) -> str:
    words = []
    for token in raw_name.split():
        if token.startswith("(") or token.isdigit():
            words.append(token)
        else:
            words.append(token.capitalize())
    return " ".join(words)


def cross_identifier(personality_sun_gate: int, angle: str) -> dict[str, Any]:
    """Return formatted Incarnation Cross name (e.g. Right Angle Cross of ...) and metadata."""
    row = depth_reference()["gates"][personality_sun_gate - 1]
    if row["gate"] != personality_sun_gate or angle not in row["cross_identifiers"]:
        raise ValueError("轮回交叉目录的门号或角度无效")
    raw_name = row["cross_identifiers"][angle]
    prefix = ANGLE_PREFIX[angle]
    return {
        "name": f"{prefix} {_format_cross_title(raw_name)}",
        "short_name": raw_name,
        "name_status": "primary_2001_angle_identifier",
        "source_pdf_page_one_based": row["pdf_pages_one_based"][0],
    }


def line_fixings(activations: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Compute structured Exaltation/Detriment/Juxtaposition/Unfixed states (no prose)."""
    reference = depth_reference()
    result: list[dict[str, Any]] = []
    side_items = [(side, activations[side]) for side in SIDES if side in activations]
    if len(side_items) != len(activations):
        raise ValueError("Unknown activation side")
    for side, items in side_items:
        for index, activation in enumerate(items):
            gate, line = activation["gate"], activation["line"]
            row = reference["gates"][gate - 1]
            polarity = row["line_polarities"][line - 1]
            additional = facts_for(gate, line)
            harmonics = {
                b if a == gate else a
                for a, b in (c["gates"] for c in row["channel_identifiers"])
            }
            triggers: dict[str, list[dict[str, Any]]] = {
                "exaltation": [],
                "detriment": [],
            }
            # Nodes can be fixed as recipients, never as donor planets (Grassinger 1997).
            for role in triggers:
                planets = {polarity[role + "_planet"]} - {None}
                planets.update(
                    f["additional_planet"] for f in additional if f["role"] == role
                )
                if not planets:
                    continue
                for source_side, sources in side_items:
                    for source_index, source in enumerate(sources):
                        if source["body"] not in planets or source["body"] in NODES:
                            continue
                        if source["gate"] not in harmonics | {gate}:
                            continue
                        relation = (
                            "same_line"
                            if source["gate"] == gate and source["line"] == line
                            else (
                                "same_gate_other_line"
                                if source["gate"] == gate
                                else "harmonic_gate"
                            )
                        )
                        triggers[role].append(
                            {
                                "side": source_side,
                                "body": source["body"],
                                "gate": source["gate"],
                                "line": source["line"],
                                "relation": relation,
                                "calculation_path": f"activations.{source_side}.{source_index}",
                            }
                        )
            if polarity["polarity_kind"] == "no_planet_polarity":
                state = "not_applicable_no_planet_polarity"
            elif triggers["exaltation"] and triggers["detriment"]:
                state = "juxtaposition"
            elif triggers["exaltation"]:
                state = "exaltation"
            elif triggers["detriment"]:
                state = "detriment"
            else:
                state = "unfixed"
            status = (
                state
                if polarity["polarity_kind"] == "dual"
                else (
                    "unitary_polarity"
                    if polarity["polarity_kind"] == "unitary"
                    else "no_planet_polarity_in_source"
                )
            )
            record: dict[str, Any] = {
                "side": side,
                "body": activation["body"],
                "gate": gate,
                "line": line,
                "calculation_path": f"activations.{side}.{index}",
                "gate_name": row["name"],
                **{k: v for k, v in polarity.items() if k != "line"},
                "status": status,
                "fixing_state": state,
                "recipient_kind": (
                    "node_activation"
                    if activation["body"] in NODES
                    else "planet_activation"
                ),
                "fixing_planets": triggers,
            }
            basis = [
                fact
                for fact in additional
                if any(
                    t["body"] == fact["additional_planet"]
                    for t in triggers[fact["role"]]
                )
            ]
            if basis:
                record["additional_polarity_basis"] = basis
            result.append(record)
    return result


def depth_evidence(chart: dict[str, Any]) -> dict[str, Any]:
    """Return pure structured fixing and channel facts."""
    reference = depth_reference()
    channels = []
    for actual in chart["bodygraph"]["channels"]:
        pairs = sorted(actual["gates"])
        row = reference["gates"][pairs[0] - 1]
        match = next(c for c in row["channel_identifiers"] if c["gates"] == pairs)
        channels.append(
            {
                "gates": pairs,
                "name": match["name"],
                "source_pdf_page_one_based": row["pdf_pages_one_based"][0],
            }
        )
    fixings = line_fixings(chart["activations"])
    return {
        "line_fixings": fixings,
        "fixing_summary": {
            "activation_count": len(fixings),
            "fixing_state_counts": dict(
                sorted(Counter(r["fixing_state"] for r in fixings).items())
            ),
            "node_recipient_count": sum(
                r["recipient_kind"] == "node_activation" for r in fixings
            ),
        },
        "channel_identifiers": channels,
    }
