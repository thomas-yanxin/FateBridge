"""Shared Human Design service orchestration and compact projection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design.cycles import calculate_cycle_context, cycle_summary
from fatebridge.core.human_design.depth import depth_evidence
from fatebridge.core.human_design.mechanics import (
    BODY_IDS,
    composite_bodygraph,
    positions_at_tt,
    transit_overlay,
)
from fatebridge.core.human_design.sensitivity import (
    assess_birth_interval,
    unassessed_interval,
)
from fatebridge.core.human_design.time import (
    chart_at,
    chart_at_tt,
    resolve_birth_clock,
)
from fatebridge.utils.errors import calculation_guard


def compact_human_design(result: dict[str, Any]) -> dict[str, Any]:
    """Return a clean <6 KB structured compact view of a Human Design chart."""
    bg = result["bodygraph"]
    vars_data = result["variables"]
    compact_vars = {
        "code": vars_data.get("code"),
        "arrows": [
            {
                "component": a["component"],
                "tone": a["tone"],
                "orientation": a["orientation"],
                "letter": a["letter"],
            }
            for a in vars_data.get("arrows", [])
        ],
        "phs_determination": vars_data.get("phs_determination"),
        "environment": vars_data.get("environment"),
        "motivation": (
            {
                "color": vars_data["motivation"].get("color"),
                "source_term": vars_data["motivation"].get("source_term"),
                "transference": vars_data["motivation"].get("transference"),
            }
            if vars_data.get("motivation")
            else None
        ),
        "view": (
            {
                "color": vars_data["view"].get("color"),
                "source_term": vars_data["view"].get("source_term"),
                "distraction": vars_data["view"].get("distraction"),
            }
            if vars_data.get("view")
            else None
        ),
        "cognition": vars_data.get("cognition"),
        "sense": vars_data.get("sense"),
    }
    compact_activations = {
        side: [
            {
                "body": a["body"],
                "lon": round(a["longitude"], 4),
                "gate": a["gate"],
                "line": a["line"],
                "color": a["color"],
                "tone": a["tone"],
                "base": a["base"],
            }
            for a in items
        ]
        for side, items in result["activations"].items()
    }
    fixings = [
        {
            "side": r["side"],
            "body": r["body"],
            "gate": r["gate"],
            "line": r["line"],
            "fixing_state": r["fixing_state"],
        }
        for r in result.get("depth_evidence", {}).get("line_fixings", [])
        if r["fixing_state"] not in {"unfixed", "not_applicable_no_planet_polarity"}
    ]
    out: dict[str, Any] = {
        "engine": result["engine"],
        "name": result.get("name"),
        "birth_utc": result["birth_utc"],
        "design_utc": result["design_utc"],
        "profile": result["profile"],
        "incarnation_cross": {
            "name": result["incarnation_cross"]["name"],
            "angle": result["incarnation_cross"]["angle"],
            "gates": result["incarnation_cross"]["gates"],
        },
        "bodygraph": {
            "type": bg["type"],
            "subtype": bg["subtype"],
            "authority": bg["authority"],
            "strategy": bg["strategy"],
            "definition": bg["definition"],
            "centers": {c: info["status"] for c, info in bg["centers"].items()},
            "channels": [
                {"id": c["id"], "circuit": c["circuit"]} for c in bg["channels"]
            ],
            "circuitry": bg["circuitry"]["group_channel_counts"],
            "activated_gates": bg["activated_gates"],
            "hanging_gates": bg["hanging_gates"],
        },
        "activations": compact_activations,
        "variables": compact_vars,
        "line_fixings": fixings,
        "summary": result.get("summary"),
    }
    if result.get("cycle_summary", {}).get("status") not in (None, "not_requested"):
        out["cycle_summary"] = result["cycle_summary"]
    if "transit_overlay" in result:
        out["transit_overlay"] = result["transit_overlay"]
    if "composite" in result:
        out["composite"] = result["composite"]
    return out


def _single_chart(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_timezone: str,
    birth_second: int = 0,
    node_mode: str = "true",
    require_swiss_files: bool = False,
) -> tuple[Any, dict[str, Any]]:
    clock = resolve_birth_clock(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        birth_timezone=birth_timezone,
    )
    if clock.leap_second:
        assert clock.jd_tt is not None
        chart = chart_at_tt(
            clock.jd_tt, node_mode, require_swiss_files=require_swiss_files
        )
        chart["birth_clock_evidence"] = clock.evidence
        chart["birth_utc"] = clock.utc_label
        chart["time_scales"]["personality"].update(
            utc_is_leap_second=True, utc_label_status="inserted_UTC_leap_second"
        )
        chart["design_solver"]["civil_elapsed_days"] = None
    else:
        chart = chart_at(
            clock.utc_anchor, node_mode, require_swiss_files=require_swiss_files
        )
    return clock, chart


@calculation_guard("人类图计算")
@runtime.preserve_ephemeris_path()
def calculate_human_design(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_timezone: str,
    birth_second: int = 0,
    name: str | None = None,
    node_mode: str = "true",
    require_swiss_files: bool = False,
    birth_time_uncertainty_minutes: int = 0,
    cycle_reference_datetime: str | None = None,
    transit_datetime: str | None = None,
    partner: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute a complete deterministic Human Design chart in-process (<10 ms)."""
    clock, chart = _single_chart(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        birth_timezone=birth_timezone,
        node_mode=node_mode,
        require_swiss_files=require_swiss_files,
    )
    cycles = (
        calculate_cycle_context(
            chart, cycle_reference_datetime, require_swiss_files=require_swiss_files
        )
        if cycle_reference_datetime is not None
        else {"status": "not_requested"}
    )
    sensitivity = (
        assess_birth_interval(
            chart,
            birth_time_uncertainty_minutes,
            node_mode,
            require_swiss_files=require_swiss_files,
        )
        if birth_time_uncertainty_minutes
        else unassessed_interval()
    )
    depth = depth_evidence(chart)
    models = sorted(
        {
            a["ephemeris_model"]
            for values in chart["activations"].values()
            for a in values
            if a["body"] in BODY_IDS
        }
    )
    bg = chart["bodygraph"]
    result: dict[str, Any] = {
        "engine": "human_design_swiss_ephemeris",
        "method_id": "human_design_public_mechanics_v2",
        "name": name,
        **chart,
        "depth_evidence": depth,
        "cycle_context": cycles,
        "cycle_summary": cycle_summary(cycles, chart["profile"]),
        "time_sensitivity": sensitivity,
        "calculation_policy": {
            "calendar": "proleptic_gregorian",
            "birth_local": clock.local_label,
            "birth_timezone": birth_timezone,
            "node_mode": node_mode,
            "ephemeris_model": "+".join(models),
            "ephemeris_version": runtime.swe.version if runtime.swe else None,
            "require_swiss_files": require_swiss_files,
            "gate_41_start_degrees": 302.0,
        },
        "summary": (
            f"人类图：{bg['type']}"
            + (f"（{bg['subtype']}）" if bg["subtype"] else "")
            + f"，内在权威 {bg['authority']}，人生角色 {chart['profile']}，"
            f"{chart['incarnation_cross']['name']}，Variable {chart['variables']['code']}。"
        ),
    }
    if transit_datetime is not None:
        dt = datetime.fromisoformat(transit_datetime.replace("Z", "+00:00"))
        if dt.utcoffset() is None:
            raise ValueError("transit_datetime 必须带时区")
        t_tt = ephemeris_time(dt.astimezone(timezone.utc)).jd_tt
        if t_tt is None:
            raise RuntimeError("行运时刻无可用 TT")
        t_pos = positions_at_tt(
            t_tt, node_mode, require_swiss_files=require_swiss_files
        )
        result["transit_overlay"] = {
            "transit_utc": dt.astimezone(timezone.utc).isoformat(),
            **transit_overlay(chart, t_pos),
        }
    if partner is not None:
        _, partner_chart = _single_chart(
            birth_year=partner["birth_year"],
            birth_month=partner["birth_month"],
            birth_day=partner["birth_day"],
            birth_hour=partner["birth_hour"],
            birth_minute=partner["birth_minute"],
            birth_second=partner.get("birth_second", 0),
            birth_timezone=partner["birth_timezone"],
            node_mode=node_mode,
            require_swiss_files=require_swiss_files,
        )
        result["composite"] = composite_bodygraph(chart, partner_chart)
    return result
