"""Ordered assembly, lazy single-tool lookup, and contract enrichment for domain tools."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING, cast

from fatebridge.application.domain_plugin import DomainPlugin, assemble_catalog
from fatebridge.application.tool_spec import (
    _UNSET_OUTPUT_MODEL,
    _UNSET_REQUEST_MODEL,
    ToolSpec,
)
from fatebridge.core.response_models import output_model_for

if TYPE_CHECKING:
    PLUGINS: tuple[DomainPlugin, ...]
    CATALOG: list[ToolSpec]


def _enrich_builtin_spec(spec: ToolSpec) -> ToolSpec:
    if not spec.required_output_fields:
        raise ValueError(f"ToolSpec {spec.name!r} must declare required_output_fields")
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
    )


def _specs_by_name() -> dict[str, ToolSpec]:
    cached = globals().get("_SPECS_BY_NAME")
    if cached is not None:
        return cast(dict[str, ToolSpec], cached)
    all_catalog()
    return cast(dict[str, ToolSpec], globals()["_SPECS_BY_NAME"])


def get_spec(name: str) -> ToolSpec | None:
    """Resolve and enrich a single builtin ToolSpec from the catalog."""
    return _specs_by_name().get(name)


def get_specs(names: Sequence[str]) -> list[ToolSpec]:
    """Resolve known ToolSpecs in requested order."""
    by_name = _specs_by_name()
    loaded: list[ToolSpec] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        spec = by_name.get(name)
        if spec is not None:
            loaded.append(spec)
            seen.add(name)
    return loaded


def known_tool_names() -> tuple[str, ...]:
    """Return sorted known public tool names."""
    return tuple(sorted(_specs_by_name()))


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
    globals()["_SPECS_BY_NAME"] = {spec.name: spec for spec in catalog}
    return catalog


def __getattr__(name: str) -> object:
    if name in {"PLUGINS", "CATALOG"}:
        all_catalog()
        return globals()[name]
    raise AttributeError(name)


def rest_specs() -> list[ToolSpec]:
    return [s for s in all_catalog() if s.rest_path]


def mcp_specs() -> list[ToolSpec]:
    return [s for s in all_catalog() if s.expose_mcp]
