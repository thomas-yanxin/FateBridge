"""Lossless native scalar layout and pure activation reconstruction."""

import math
from typing import Any

from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design_mechanics import (
    BODY_IDS,
    longitude_activation,
    opposite_activation,
)
from fatebridge.core.human_design_provenance import position_flag_model

DIRECT_BODIES = (*BODY_IDS, "NorthNode")
SCALARS = ("longitude", "longitude_speed", "return_flags")


def pack_native_positions(rows: list[dict[str, Any]]) -> list[list[float | int]]:
    by_body = {r["body"]: r for r in rows}
    if len(by_body) != len(rows) or set(by_body) != {
        *DIRECT_BODIES,
        "Earth",
        "SouthNode",
    }:
        raise ValueError("Incomplete or duplicate activation body set")
    return [[by_body[b][k] for k in SCALARS] for b in DIRECT_BODIES]


def decode_native_positions(
    native: list[list[float | int]],
    node_mode: str,
    *,
    require_swiss_files: bool,
    physical_backend_policy: str = "auto",
) -> list[dict[str, Any]]:
    if node_mode not in {"true", "mean"} or physical_backend_policy not in {
        "auto",
        "strict_jpl",
    }:
        raise ValueError("Invalid native position policy")
    if not isinstance(native, list) or len(native) != len(DIRECT_BODIES):
        raise ValueError("Incomplete native positions")
    rows = []
    for body, values in zip(DIRECT_BODIES, native):
        if (
            not isinstance(values, list)
            or len(values) != 3
            or any(type(v) is not float or not math.isfinite(v) for v in values[:2])
            or not 0 <= values[0] < 360
        ):
            raise ValueError("Invalid native position scalars")
        model = position_flag_model(values[2])
        if require_swiss_files and model != "swieph":
            raise ValueError("Native positions violate Swiss policy")
        if (
            body in BODY_IDS
            and physical_backend_policy == "strict_jpl"
            and model != "jpl"
        ):
            raise ValueError("Native positions violate strict JPL policy")
        rows.append(
            {
                "body": body,
                "longitude_speed": values[1],
                "return_flags": values[2],
                "ephemeris_model": (
                    ANALYTICAL_MEAN_NODE_MODEL
                    if body == "NorthNode" and node_mode == "mean"
                    else model
                ),
                **({"native_return_flag_model": model} if body == "NorthNode" else {}),
                **longitude_activation(values[0]),
            }
        )
    for body, source in (("Earth", "Sun"), ("SouthNode", "NorthNode")):
        original = next(r for r in rows if r["body"] == source)
        rows.append(
            {
                **original,
                "body": body,
                "derived_from": source,
                **opposite_activation(original["longitude"]),
            }
        )
    return rows
