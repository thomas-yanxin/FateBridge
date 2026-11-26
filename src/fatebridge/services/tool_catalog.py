"""Ordered assembly and contract enrichment for domain tools."""

from __future__ import annotations

from dataclasses import replace
from functools import partial

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
from fatebridge.services.catalog.astrology import SPECS as ASTROLOGY_SPECS
from fatebridge.services.catalog.bazi import SPECS as BAZI_SPECS
from fatebridge.services.catalog.compatibility import SPECS as COMPATIBILITY_SPECS
from fatebridge.services.catalog.detail_views import traditional_detail_view
from fatebridge.services.catalog.divination import SPECS as DIVINATION_SPECS
from fatebridge.services.catalog.fengshui import SPECS as FENGSHUI_SPECS
from fatebridge.services.catalog.psychometrics import SPECS as PSYCHOMETRICS_SPECS
from fatebridge.services.catalog.reference import SPECS as REFERENCE_SPECS
from fatebridge.services.catalog.sanshi import SPECS as SANSHI_SPECS
from fatebridge.services.catalog.timing import SPECS as TIMING_SPECS
from fatebridge.services.catalog.western_events import SPECS as WESTERN_EVENTS_SPECS
from fatebridge.services.catalog.western_lifespan import SPECS as WESTERN_LIFESPAN_SPECS
from fatebridge.services.catalog.western_timing import SPECS as WESTERN_TIMING_SPECS
from fatebridge.services.catalog.ziwei import SPECS as ZIWEI_SPECS

PLUGINS: tuple[DomainPlugin, ...] = (
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
        detail_view=spec.detail_view or traditional_detail_view,
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


CATALOG: list[ToolSpec] = [
    _enrich_builtin_spec(spec) for spec in assemble_catalog(PLUGINS)
]


def rest_specs() -> list[ToolSpec]:
    return [s for s in CATALOG if s.rest_path]


def mcp_specs() -> list[ToolSpec]:
    return [s for s in CATALOG if s.expose_mcp]
