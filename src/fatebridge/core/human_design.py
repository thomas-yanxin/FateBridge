"""Human Design mechanics, separate from claims about people or future events.

Geocentric apparent tropical longitudes of date; civil UTC -> TT; no houses,
ascendant, topocentric parallax, sidereal offset or solar-clock rebasing.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Callable, Dict, Optional, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design_apparent_positions import (
    observed_coordinates,
    position_batch_id,
    record_position_batch,
    register_chart,
)
from fatebridge.core.human_design_circuitry import circuitry_summary
from fatebridge.core.human_design_classification import classification_evidence
from fatebridge.core.human_design_depth import cross_identifier
from fatebridge.core.human_design_mechanics import (
    BODY_IDS,
    CENTER_GATES,
    CHANNELS,
    GATE_CENTER,
    GATE_ORDER,
    MOTORS,
    RULESET_ID,
    RULESET_VERSION,
    VALID_PROFILES,
    _components,
    _rational_activation,
    bodygraph,
    longitude_activation,
    opposite_activation,
    positions_at_tt,
)
from fatebridge.core.human_design_natal_sources import observe_native_source
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_time import (
    epoch_context_at_tt,
    solve_design_epoch,
    solve_design_epoch_tt,
)
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

# Increasing tropical longitude. Gate 41 begins at 2 degrees Aquarius.
# Gate pairs and circuit. Integration is kept distinct from Individual circuits.


def activation_longitude_fraction(activation: Dict[str, Any]) -> Fraction:
    """Recover the classification coordinate, including a displayed opposition.

    The display float alone can round across a boundary. Complete-run checks
    must additionally bind a derived coordinate to its actual same-side source.
    """
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


def solar_root_subdivisions(solver: Dict[str, Any]) -> Dict[str, Any]:
    """Classify the root function endpoints without implying physical bounds."""
    witness = solver["numerical_precision"]
    rows = [
        {
            "jd_tt": witness[endpoint]["jd_tt"],
            "Sun": longitude_activation(witness[endpoint]["sun_longitude"]),
            "Earth": {
                "derived_from": "Sun",
                **opposite_activation(witness[endpoint]["sun_longitude"]),
            },
        }
        for endpoint in ("lower", "upper")
    ]
    changes = [
        level
        for level in ("gate", "line", "color", "tone", "base")
        if any(
            rows[0][body][level] != rows[1][body][level] for body in ("Sun", "Earth")
        )
    ]
    return {
        "solar_endpoint_subdivisions": rows,
        "observed_solar_changed_levels": changes,
        "solar_subdivision_status": (
            "observed_variation_at_final_numeric_bracket"
            if changes
            else "same_at_evaluated_numeric_endpoints"
        ),
    }


def planetary_positions(
    moment: datetime,
    node_mode: str = "true",
    *,
    require_swiss_files: bool = False,
    source_observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Use actual Swiss return flags; refuse failure or coarse orbital fallback."""
    if runtime.swe is None:
        raise RuntimeError("人类图需要 Swiss Ephemeris，未启用近似轨道回退")
    if node_mode not in {"true", "mean"}:
        raise ValueError("node_mode 必须为 true 或 mean")
    time = ephemeris_time(moment)
    if time.jd_tt is None:
        raise RuntimeError("人类图需要可用的 TT 星历时刻")
    return {
        "positions": positions_at_tt(
            time.jd_tt,
            node_mode,
            require_swiss_files=require_swiss_files,
            source_observer=source_observer,
        ),
        "time": {
            "jd_tt": time.jd_tt,
            "jd_ut1": time.jd_ut1,
            "method": time.method,
            "future_leap_seconds_assumed_unchanged": time.future_leap_seconds_assumed_unchanged,
        },
    }


def design_epoch(
    birth: datetime, *, require_swiss_files: bool = False
) -> Tuple[datetime, Dict[str, Any]]:
    """Datetime adapter; full charts preserve TT across UTC clock adjustments."""
    solved = solve_design_epoch(birth, require_swiss_files=require_swiss_files)
    if solved["datetime"] is None:
        raise ValueError(
            "设计根落在 UTC 调整区间，datetime 无法唯一表示；应使用 chart_at 的 TT 与标签状态"
        )
    return solved["datetime"], solved["solver"]


def chart_at(
    birth: datetime,
    node_mode: str = "true",
    *,
    require_swiss_files: bool = False,
    source_observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
    design_source_observer: Optional[
        Callable[[str, float, Dict[str, Any]], None]
    ] = None,
) -> Dict[str, Any]:
    if birth.utcoffset() is None:
        raise ValueError("出生瞬间必须带时区")
    birth = birth.astimezone(timezone.utc)
    solved = solve_design_epoch(birth, require_swiss_files=require_swiss_files)
    personality = planetary_positions(
        birth,
        node_mode,
        require_swiss_files=require_swiss_files,
        source_observer=source_observer,
    )
    return _assemble_chart(
        birth.isoformat(),
        solved,
        personality,
        node_mode,
        require_swiss_files,
        design_source_observer=design_source_observer,
    )


def chart_at_tt(
    birth_jd_tt: float,
    node_mode: str = "true",
    *,
    require_swiss_files: bool = False,
    backend: str = "swieph",
    source_observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
    design_source_observer: Optional[
        Callable[[str, float, Dict[str, Any]], None]
    ] = None,
) -> Dict[str, Any]:
    """TT instants, including leap-second births, avoid rounding via datetime."""
    if not math.isfinite(birth_jd_tt):
        raise ValueError("出生 TT 必须为有限数值")
    context = epoch_context_at_tt(birth_jd_tt, method="continuous_TT_interval_sample")
    solved = solve_design_epoch_tt(
        birth_jd_tt, require_swiss_files=require_swiss_files, backend=backend
    )
    personality = {
        "positions": positions_at_tt(
            birth_jd_tt,
            node_mode,
            require_swiss_files=require_swiss_files,
            backend=backend,
            source_observer=source_observer,
        ),
        "time": context["time"],
    }
    return _assemble_chart(
        context["utc_label"],
        solved,
        personality,
        node_mode,
        require_swiss_files,
        backend,
        design_source_observer=design_source_observer,
    )


def _assemble_chart(
    birth_utc: Optional[str],
    solved: Dict[str, Any],
    personality: Dict[str, Any],
    node_mode: str,
    require_swiss_files: bool,
    backend: str = "swieph",
    *,
    design_source_observer: Optional[
        Callable[[str, float, Dict[str, Any]], None]
    ] = None,
) -> Dict[str, Any]:
    sides = {}
    batch_refs = {}
    times = {}
    for side in ("personality", "design"):
        data = (
            personality
            if side == "personality"
            else {
                "positions": positions_at_tt(
                    solved["time"]["jd_tt"],
                    node_mode,
                    require_swiss_files=require_swiss_files,
                    backend=backend,
                    source_observer=design_source_observer,
                ),
                "time": solved["time"],
            }
        )
        batch_id = position_batch_id(data["positions"])
        if batch_id is not None:
            batch_refs[side] = batch_id
        sides[side] = [
            {
                "body": body,
                **state,
                **_rational_activation(activation_longitude_fraction(state)),
            }
            for body, state in data["positions"].items()
        ]
        times[side] = data["time"]
    graph = bodygraph(
        (p["gate"] for p in sides["personality"]), (p["gate"] for p in sides["design"])
    )
    suns = {
        side: next(a for a in items if a["body"] == "Sun")
        for side, items in sides.items()
    }
    profile = f"{suns['personality']['line']}/{suns['design']['line']}"
    if profile not in VALID_PROFILES:
        raise RuntimeError("太阳弧与人生角色不一致，拒绝输出无效 Profile")
    solver = {
        **solved["solver"],
        "numerical_precision": {
            **solved["solver"]["numerical_precision"],
            **solar_root_subdivisions(solved["solver"]),
        },
    }
    from fatebridge.core.human_design_root_bodies import (
        assess_design_root_bodies,
        root_body_summary,
    )

    solver["numerical_precision"]["design_body_endpoint_assessment"] = (
        assess_design_root_bodies(
            solver,
            sides["personality"],
            sides["design"],
            node_mode,
            require_swiss_files=require_swiss_files,
            backend=backend,
        )
    )
    solver["numerical_precision"]["other_bodies_bracket_sensitivity_assessed"] = True
    solver["numerical_precision"]["design_body_endpoint_summary"] = root_body_summary(
        solver["numerical_precision"]["design_body_endpoint_assessment"]
    )
    from fatebridge.core.human_design_root_family import assess_family, family_summary

    solver["numerical_precision"]["local_root_family"] = assess_family(
        solver,
        sides["personality"],
        sides["design"],
        node_mode,
        require_swiss_files=require_swiss_files,
        backend=backend,
    )
    solver["numerical_precision"]["local_root_family_summary"] = family_summary(
        solver["numerical_precision"]["local_root_family"]
    )
    cross = [
        next(a["gate"] for a in sides[side] if a["body"] == body)
        for side, body in (
            ("personality", "Sun"),
            ("personality", "Earth"),
            ("design", "Sun"),
            ("design", "Earth"),
        )
    ]
    register_chart(sides, batch_refs)
    return {
        "birth_utc": birth_utc,
        "design_utc": solved["utc_label"],
        "design_solver": solver,
        "time_scales": times,
        "activations": sides,
        "variables": variables_from_activations(sides),
        "bodygraph": graph,
        "profile": profile,
        "incarnation_cross": {
            "gates": cross,
            "order": [
                "personality_sun",
                "personality_earth",
                "design_sun",
                "design_earth",
            ],
            "angle": (
                "juxtaposition"
                if profile == "4/1"
                else "right" if suns["personality"]["line"] <= 4 else "left"
            ),
            **cross_identifier(
                cross[0],
                (
                    "juxtaposition"
                    if profile == "4/1"
                    else "right" if suns["personality"]["line"] <= 4 else "left"
                ),
            ),
        },
    }
