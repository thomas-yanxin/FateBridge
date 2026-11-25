"""Shared Human Design orchestration for REST, MCP and CLI."""

from typing import Any, Callable, Dict, Optional

from fatebridge.core.astro import runtime
from fatebridge.core.astro.source_session import coherent_ephemeris_sources
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.human_design.human_design import chart_at, chart_at_tt
from fatebridge.core.human_design.human_design_apparent_positions import (
    guard_apparent_positions,
)
from fatebridge.core.human_design.human_design_backend import compare_full_backends
from fatebridge.core.human_design.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.human_design.human_design_clock_observation import (
    observe_human_design_clocks,
)
from fatebridge.core.human_design.human_design_cycle_origins import (
    calculate_origin_comparison,
)
from fatebridge.core.human_design.human_design_cycle_sources import CycleBirthSources
from fatebridge.core.human_design.human_design_cycles import (
    calculate_cycle_context,
    cycle_summary,
)
from fatebridge.core.human_design.human_design_evidence import evidence
from fatebridge.core.human_design.human_design_execution import isolated_human_design
from fatebridge.core.human_design.human_design_interval_summary import (
    unassessed_interval,
)
from fatebridge.core.human_design.human_design_mechanics import BODY_IDS
from fatebridge.core.human_design.human_design_natal_sources import guard_natal_sources
from fatebridge.core.human_design.human_design_node_comparisons import (
    node_convention_report,
)
from fatebridge.core.human_design.human_design_point_mass import (
    point_mass_positions,
    solve_point_mass_design_root,
)
from fatebridge.core.human_design.human_design_precision import compare_node_backends
from fatebridge.core.human_design.human_design_references import (
    coherent_human_design_references,
)
from fatebridge.core.human_design.human_design_sensitivity import assess_birth_interval
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError, calculation_guard


@calculation_guard("人类图计算")
@isolated_human_design
@coherent_ephemeris_sources
@runtime.preserve_ephemeris_path()
@coherent_human_design_references()
@guard_apparent_positions
@guard_natal_sources
@observe_human_design_clocks
def calculate_human_design(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_timezone: str,
    birth_second: int = 0,
    name: Optional[str] = None,
    node_mode: str = "true",
    require_swiss_files: bool = False,
    birth_time_uncertainty_minutes: int = 0,
    cycle_reference_datetime: Optional[str] = None,
    compare_cycle_origins: bool = False,
    compare_apparent_models: bool = False,
) -> Dict[str, Any]:
    clock = resolve_birth_clock(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        birth_timezone=birth_timezone,
    )
    selected_path = configured_ephemeris_path()
    selected_jpl = configured_jpl_file()
    birth_sources = (
        CycleBirthSources()
        if cycle_reference_datetime is not None or compare_cycle_origins
        else None
    )
    design_sources = CycleBirthSources() if compare_cycle_origins else None

    def natal_chart(
        mode: str,
        observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
        design_observer: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if clock.leap_second:
            assert clock.jd_tt is not None
            return chart_at_tt(
                clock.jd_tt,
                mode,
                require_swiss_files=require_swiss_files,
                source_observer=observer,
                design_source_observer=design_observer,
            )
        else:
            pass
        return chart_at(
            clock.utc_anchor,
            mode,
            require_swiss_files=require_swiss_files,
            source_observer=observer,
            design_source_observer=design_observer,
        )

    chart = natal_chart(
        node_mode,
        birth_sources.observe if birth_sources is not None else None,
        design_sources.observe if design_sources is not None else None,
    )
    if clock.evidence is not None:
        chart["birth_clock_evidence"] = clock.evidence
        # A binary64 TT can share its display with another civil microsecond
        # or midnight. Preserve the confirmed input, not its lossy inverse.
        chart["birth_utc"] = clock.utc_label
        chart["time_scales"]["personality"].update(
            method=clock.evidence["method_id"],
            utc_is_leap_second=True,
            utc_label_status="inserted_UTC_leap_second",
            future_leap_seconds_assumed_unchanged=False,
        )
        chart["design_solver"]["civil_elapsed_days"] = None
    else:
        pass
    cycles = (
        calculate_cycle_context(
            chart,
            cycle_reference_datetime,
            require_swiss_files=require_swiss_files,
            birth_sources=birth_sources,
        )
        if birth_sources is not None
        else {"status": "not_requested"}
    )
    origin_comparison = (
        calculate_origin_comparison(
            chart,
            cycles,
            require_swiss_files=require_swiss_files,
            origin_sources=design_sources,
        )
        if design_sources is not None
        else None
    )
    models = sorted(
        {
            a["ephemeris_model"]
            for values in chart["activations"].values()
            for a in values
            if a["body"] in BODY_IDS
        }
    )
    sensitivity = unassessed_interval()
    if birth_time_uncertainty_minutes:
        sensitivity = assess_birth_interval(
            chart,
            birth_time_uncertainty_minutes,
            node_mode,
            require_swiss_files=require_swiss_files,
        )
    else:
        pass
    comparison_reports: dict[str, dict[str, Any]] = {}
    if compare_apparent_models:
        alternative = natal_chart("mean" if node_mode == "true" else "true")
        comparison_reports = {
            "node_convention_comparison": node_convention_report(
                chart, alternative, node_mode
            ),
            "node_backend_comparison": compare_node_backends(chart, node_mode),
            "ephemeris_backend_comparison": compare_full_backends(chart, node_mode),
        }

        candidate_root = solve_point_mass_design_root(
            chart["time_scales"]["personality"]["jd_tt"]
        )
        root_available = candidate_root["status"] == "computed"
        chart["apparent_model_comparison"] = {
            "status": "requested",
            "same_tt_as_native_chart": True,
            "same_tt_scope": "epochs",
            "design_root_recomputed": root_available,
            "native_activations_replaced": False,
            "epochs": {
                side: point_mass_positions(chart["time_scales"][side]["jd_tt"])
                for side in ("personality", "design")
            },
            "candidate_design_root": candidate_root,
        }
        if candidate_root["status"] == "computed":
            candidate_jd_tt = candidate_root["design_jd_tt"]
            chart["apparent_model_comparison"].update(
                candidate_design_epoch=point_mass_positions(candidate_jd_tt),
                candidate_minus_native_root_seconds=(
                    candidate_jd_tt - chart["time_scales"]["design"]["jd_tt"]
                )
                * 86400,
            )
        else:
            pass
    else:
        pass
    if (
        configured_ephemeris_path() != selected_path
        or configured_jpl_file() != selected_jpl
    ):
        raise EphemerisSourceError("physical_configuration_changed")
    else:
        pass
    if birth_sources is not None:
        # Keep original source files pinned through the comparison passes.
        birth_sources.trace.finish()
    else:
        pass
    if design_sources is not None:
        design_sources.trace.finish()
    else:
        pass
    chart["time_sensitivity"] = sensitivity
    chart.update(comparison_reports)
    return {
        "engine": "human_design_swiss_ephemeris",
        "method_id": "human_design_public_mechanics_v1",
        "name": name,
        **chart,
        **evidence(chart),
        "cycle_context": cycles,
        "cycle_summary": cycle_summary(cycles, chart["profile"]),
        **(
            {"cycle_origin_comparison": origin_comparison}
            if origin_comparison is not None
            else {}
        ),
        "calculation_policy": {
            "calendar": "proleptic_gregorian",
            "birth_local": clock.local_label,
            "birth_timezone": birth_timezone,
            "birth_time_uncertainty_minutes": birth_time_uncertainty_minutes,
            **({"compare_cycle_origins": True} if compare_cycle_origins else {}),
            **({"compare_apparent_models": True} if compare_apparent_models else {}),
            "position_frame": "geocentric_apparent_tropical_ecliptic_of_date",
            "position_frame_scope": "physical_bodies",
            "lunar_node_frame": "geocentric_tropical_ecliptic_of_date_mathematical_point",
            "solar_clock_rebasing": False,
            "node_mode": node_mode,
            "ephemeris_model": "+".join(models),
            "ephemeris_model_scope": "physical_bodies",
            "physical_backend_policy": ("strict_jpl" if selected_jpl else "auto"),
            "nonphysical_factor_models": {
                side: {
                    a["body"]: a["ephemeris_model"]
                    for a in values
                    if a["body"] not in BODY_IDS
                }
                for side, values in chart["activations"].items()
            },
            "ephemeris_version": runtime.swe.version,
            "require_swiss_files": require_swiss_files,
            "gate_41_start_degrees": 302.0,
            "boundary_policy": "half_open_no_preclassification_rounding",
        },
    }
