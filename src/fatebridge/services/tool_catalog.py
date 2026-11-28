"""Ordered assembly, lazy single-tool lookup, and contract enrichment for domain tools."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from functools import partial
from importlib import import_module
from typing import TYPE_CHECKING, cast

from fatebridge.application.domain_plugin import DomainPlugin, assemble_catalog
from fatebridge.application.tool_spec import (
    _UNSET_OUTPUT_MODEL,
    _UNSET_REQUEST_MODEL,
    ToolSpec,
)
from fatebridge.core.response_models import (
    output_fields_for,
    output_model_for,
    required_output_fields_for,
)

if TYPE_CHECKING:
    PLUGINS: tuple[DomainPlugin, ...]
    CATALOG: list[ToolSpec]


_TOOL_MODULE_BY_NAME: dict[str, str] = {
    "age_point": "fatebridge.services.catalog.western_lifespan",
    "astrology_chart": "fatebridge.services.catalog.astrology",
    "balbillus_periods": "fatebridge.services.catalog.western_lifespan",
    "bazi_birth_chart": "fatebridge.services.catalog.bazi",
    "bazi_career": "fatebridge.services.catalog.bazi",
    "bazi_children": "fatebridge.services.catalog.bazi",
    "bazi_compatibility": "fatebridge.services.catalog.compatibility",
    "bazi_daily_timing": "fatebridge.services.catalog.timing",
    "bazi_education": "fatebridge.services.catalog.bazi",
    "bazi_health": "fatebridge.services.catalog.bazi",
    "bazi_hourly_timing": "fatebridge.services.catalog.timing",
    "bazi_luck_cycles": "fatebridge.services.catalog.timing",
    "bazi_marriage": "fatebridge.services.catalog.bazi",
    "bazi_monthly_timing": "fatebridge.services.catalog.timing",
    "bazi_overview": "fatebridge.services.catalog.bazi",
    "bazi_personality": "fatebridge.services.catalog.bazi",
    "bazi_relatives": "fatebridge.services.catalog.bazi",
    "bazi_romance": "fatebridge.services.catalog.bazi",
    "bazi_timing": "fatebridge.services.catalog.timing",
    "bazi_wealth": "fatebridge.services.catalog.bazi",
    "bazi_yearly_timing": "fatebridge.services.catalog.timing",
    "bounds_directions": "fatebridge.services.catalog.western_lifespan",
    "canping": "fatebridge.services.catalog.divination",
    "chart_for_year": "fatebridge.services.catalog.western_timing",
    "combine_four_gua": "fatebridge.services.catalog.divination",
    "compare_bazi_sources": "fatebridge.services.catalog.bazi",
    "decennials": "fatebridge.services.catalog.western_timing",
    "declination_progressions": "fatebridge.services.catalog.western_lifespan",
    "evaluate_election_time": "fatebridge.services.catalog.western_events",
    "fengshui_annual_stars": "fatebridge.services.catalog.fengshui",
    "fengshui_assess": "fatebridge.services.catalog.fengshui",
    "fengshui_bazhai": "fatebridge.services.catalog.fengshui",
    "fengshui_directions": "fatebridge.services.catalog.fengshui",
    "fengshui_jinsuo": "fatebridge.services.catalog.fengshui",
    "fengshui_minggua": "fatebridge.services.catalog.fengshui",
    "fengshui_monthly_stars": "fatebridge.services.catalog.fengshui",
    "fengshui_xuankong_house_chart": "fatebridge.services.catalog.fengshui",
    "firdaria": "fatebridge.services.catalog.western_timing",
    "gua_lookup": "fatebridge.services.catalog.divination",
    "guolao_chart": "fatebridge.services.catalog.astrology",
    "hamburg_midpoint_chart": "fatebridge.services.catalog.astrology",
    "harmonic_chart": "fatebridge.services.catalog.western_lifespan",
    "hellenistic_chart": "fatebridge.services.catalog.astrology",
    "heluo": "fatebridge.services.catalog.divination",
    "horary_chart": "fatebridge.services.catalog.western_events",
    "human_design": "fatebridge.services.catalog.astrology",
    "interpret_astrology_dice": "fatebridge.services.catalog.divination",
    "ipip_big_five": "fatebridge.services.catalog.psychometrics",
    "jinkou": "fatebridge.services.catalog.sanshi",
    "knowledge_catalog": "fatebridge.services.catalog.reference",
    "knowledge_read": "fatebridge.services.catalog.reference",
    "liuren_chart": "fatebridge.services.catalog.sanshi",
    "liuren_yearly_timing": "fatebridge.services.catalog.sanshi",
    "liuyao": "fatebridge.services.catalog.divination",
    "lunar_calendar_time": "fatebridge.services.catalog.timing",
    "lunar_phase_progressions": "fatebridge.services.catalog.western_lifespan",
    "lunar_return": "fatebridge.services.catalog.western_timing",
    "meihua_cast": "fatebridge.services.catalog.divination",
    "meihua_time_cast": "fatebridge.services.catalog.divination",
    "mundane_ingress_chart": "fatebridge.services.catalog.western_events",
    "numeric_aspect_periods": "fatebridge.services.catalog.western_lifespan",
    "persian_directions": "fatebridge.services.catalog.western_lifespan",
    "place_lookup": "fatebridge.services.catalog.reference",
    "planetary_ages": "fatebridge.services.catalog.western_lifespan",
    "planetary_arc_directions": "fatebridge.services.catalog.western_lifespan",
    "planetary_periods_129_years": "fatebridge.services.catalog.western_lifespan",
    "planetary_returns": "fatebridge.services.catalog.western_events",
    "primary_directions": "fatebridge.services.catalog.western_timing",
    "primary_directions_chart": "fatebridge.services.catalog.western_timing",
    "profection": "fatebridge.services.catalog.western_timing",
    "qimen": "fatebridge.services.catalog.sanshi",
    "relationship_chart": "fatebridge.services.catalog.astrology",
    "sanshi_combined_chart": "fatebridge.services.catalog.divination",
    "sidereal_progressions": "fatebridge.services.catalog.western_lifespan",
    "solar_arc": "fatebridge.services.catalog.western_timing",
    "solar_return": "fatebridge.services.catalog.western_timing",
    "solar_term_timeline": "fatebridge.services.catalog.timing",
    "solar_terms_for_year": "fatebridge.services.catalog.timing",
    "sukuyo_compatibility": "fatebridge.services.catalog.divination",
    "suzhan": "fatebridge.services.catalog.divination",
    "taiyi": "fatebridge.services.catalog.sanshi",
    "thirteen_sector_chart": "fatebridge.services.catalog.astrology",
    "transit_chart": "fatebridge.services.catalog.western_timing",
    "triplicity_ruler_periods": "fatebridge.services.catalog.western_lifespan",
    "vedic_chart": "fatebridge.services.catalog.astrology",
    "vimshottari_dasha": "fatebridge.services.catalog.astrology",
    "western_timing": "fatebridge.services.catalog.western_timing",
    "ziwei_birth_chart": "fatebridge.services.catalog.ziwei",
    "ziwei_rules": "fatebridge.services.catalog.ziwei",
    "ziwei_timing": "fatebridge.services.catalog.ziwei",
    "zodiacal_releasing": "fatebridge.services.catalog.western_timing",
}

_LAZY_MODULE_CACHE: dict[str, dict[str, ToolSpec]] = {}


def _enrich_builtin_spec(spec: ToolSpec) -> ToolSpec:
    spec_dict = object.__getattribute__(spec, "__dict__")
    has_explicit_output = (
        spec_dict.get("output_model", _UNSET_OUTPUT_MODEL) is not _UNSET_OUTPUT_MODEL
    )
    has_explicit_request = (
        spec_dict.get("request_model", _UNSET_REQUEST_MODEL) is not _UNSET_REQUEST_MODEL
    )
    return replace(
        spec,
        request_model=(
            spec.request_model if has_explicit_request else _UNSET_REQUEST_MODEL
        ),
        output_model=(
            spec.output_model if has_explicit_output else _UNSET_OUTPUT_MODEL
        ),
        output_model_loader=(
            spec.output_model_loader or partial(output_model_for, spec.name)
        ),
        required_output_fields=spec.required_output_fields
        or required_output_fields_for(spec.name),
        output_fields=spec.output_fields or tuple(output_fields_for(spec.name) or ()),
    )


def get_spec(name: str) -> ToolSpec | None:
    """Resolve and enrich a single builtin ToolSpec by importing only its catalog module."""
    module_name = _TOOL_MODULE_BY_NAME.get(name)
    if module_name is None:
        return None
    cached_specs = _LAZY_MODULE_CACHE.get(module_name)
    if cached_specs is None:
        module = import_module(module_name)
        raw_specs = cast(Sequence[ToolSpec], getattr(module, "SPECS"))
        cached_specs = {spec.name: _enrich_builtin_spec(spec) for spec in raw_specs}
        _LAZY_MODULE_CACHE[module_name] = cached_specs
    return cached_specs.get(name)


def get_specs(names: Sequence[str]) -> list[ToolSpec]:
    """Resolve known ToolSpecs in requested order without loading unrelated modules."""
    loaded: list[ToolSpec] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        spec = get_spec(name)
        if spec is not None:
            loaded.append(spec)
            seen.add(name)
    return loaded


def known_tool_names() -> tuple[str, ...]:
    """Return sorted known public tool names without importing catalog modules."""
    return tuple(sorted(_TOOL_MODULE_BY_NAME))


def _load_full_catalog() -> tuple[tuple[DomainPlugin, ...], list[ToolSpec]]:
    from fatebridge.services.catalog.astrology import SPECS as ASTROLOGY_SPECS
    from fatebridge.services.catalog.bazi import SPECS as BAZI_SPECS
    from fatebridge.services.catalog.compatibility import SPECS as COMPATIBILITY_SPECS
    from fatebridge.services.catalog.divination import SPECS as DIVINATION_SPECS
    from fatebridge.services.catalog.fengshui import SPECS as FENGSHUI_SPECS
    from fatebridge.services.catalog.psychometrics import SPECS as PSYCHOMETRICS_SPECS
    from fatebridge.services.catalog.reference import SPECS as REFERENCE_SPECS
    from fatebridge.services.catalog.sanshi import SPECS as SANSHI_SPECS
    from fatebridge.services.catalog.timing import SPECS as TIMING_SPECS
    from fatebridge.services.catalog.western_events import SPECS as WESTERN_EVENTS_SPECS
    from fatebridge.services.catalog.western_lifespan import (
        SPECS as WESTERN_LIFESPAN_SPECS,
    )
    from fatebridge.services.catalog.western_timing import SPECS as WESTERN_TIMING_SPECS
    from fatebridge.services.catalog.ziwei import SPECS as ZIWEI_SPECS

    plugins: tuple[DomainPlugin, ...] = (
        DomainPlugin("bazi", tuple(BAZI_SPECS)),
        DomainPlugin("compatibility", tuple(COMPATIBILITY_SPECS)),
        DomainPlugin("timing", tuple(TIMING_SPECS)),
        DomainPlugin("divination", tuple(DIVINATION_SPECS)),
        DomainPlugin("metaphysics", (*ZIWEI_SPECS, *SANSHI_SPECS)),
        DomainPlugin("reference", tuple(REFERENCE_SPECS)),
        DomainPlugin("astrology", tuple(ASTROLOGY_SPECS)),
        DomainPlugin("western_timing", tuple(WESTERN_TIMING_SPECS)),
        DomainPlugin("western_lifespan", tuple(WESTERN_LIFESPAN_SPECS)),
        DomainPlugin("western_events", tuple(WESTERN_EVENTS_SPECS)),
        DomainPlugin("fengshui", tuple(FENGSHUI_SPECS)),
        DomainPlugin("psychometrics", tuple(PSYCHOMETRICS_SPECS)),
    )
    catalog = [_enrich_builtin_spec(spec) for spec in assemble_catalog(plugins)]
    return plugins, catalog


def all_catalog() -> list[ToolSpec]:
    """Return the full enriched catalog, materializing it on first access."""
    cached = globals().get("CATALOG")
    if cached is not None:
        return cast(list[ToolSpec], cached)
    plugins, catalog = _load_full_catalog()
    globals()["PLUGINS"] = plugins
    globals()["CATALOG"] = catalog
    return catalog


def __getattr__(name: str) -> object:
    if name in {"PLUGINS", "CATALOG"}:
        plugins, catalog = _load_full_catalog()
        globals()["PLUGINS"] = plugins
        globals()["CATALOG"] = catalog
        return plugins if name == "PLUGINS" else catalog
    raise AttributeError(name)


def rest_specs() -> list[ToolSpec]:
    return [s for s in all_catalog() if s.rest_path]


def mcp_specs() -> list[ToolSpec]:
    return [s for s in all_catalog() if s.expose_mcp]
