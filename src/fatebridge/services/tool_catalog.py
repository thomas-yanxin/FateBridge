"""Ordered assembly and contract enrichment for domain tools."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from fatebridge.application.domain_plugin import DomainPlugin, assemble_catalog
from fatebridge.application.tool_spec import (
    EvidenceViews,
    EvidenceViewsBuilder,
    RunService,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.physical_ephemeris_policy import data_file_policy
from fatebridge.core.reproducibility import ReproducibilityPolicy, policy_for
from fatebridge.core.requests.western_policy import supports_western_policy_model
from fatebridge.core.response_models import output_model_for, required_output_fields_for
from fatebridge.services.catalog.astrology import SPECS as ASTROLOGY_SPECS
from fatebridge.services.catalog.bazi import SPECS as BAZI_SPECS
from fatebridge.services.catalog.compatibility import SPECS as COMPATIBILITY_SPECS
from fatebridge.services.catalog.detail_views import traditional_detail_view
from fatebridge.services.catalog.divination import SPECS as DIVINATION_SPECS
from fatebridge.services.catalog.fengshui import SPECS as FENGSHUI_SPECS
from fatebridge.services.catalog.metaphysics import SPECS as METAPHYSICS_SPECS
from fatebridge.services.catalog.psychometrics import SPECS as PSYCHOMETRICS_SPECS
from fatebridge.services.catalog.reference import SPECS as REFERENCE_SPECS
from fatebridge.services.catalog.timing import SPECS as TIMING_SPECS
from fatebridge.services.catalog.western_events import SPECS as WESTERN_EVENTS_SPECS
from fatebridge.services.catalog.western_lifespan import SPECS as WESTERN_LIFESPAN_SPECS
from fatebridge.services.catalog.western_timing import SPECS as WESTERN_TIMING_SPECS
from fatebridge.services.method_registration import register_methods
from fatebridge.utils.errors import EphemerisSourceError, handle_calculation_error

PLUGINS: tuple[DomainPlugin, ...] = (
    DomainPlugin("bazi", tuple(BAZI_SPECS)),
    DomainPlugin("compatibility", tuple(COMPATIBILITY_SPECS)),
    DomainPlugin("timing", tuple(TIMING_SPECS)),
    DomainPlugin("divination", tuple(DIVINATION_SPECS)),
    DomainPlugin("metaphysics", tuple(METAPHYSICS_SPECS)),
    DomainPlugin("reference", tuple(REFERENCE_SPECS)),
    DomainPlugin("astrology", tuple(ASTROLOGY_SPECS)),
    DomainPlugin("western_timing", tuple(WESTERN_TIMING_SPECS)),
    DomainPlugin("western_lifespan", tuple(WESTERN_LIFESPAN_SPECS)),
    DomainPlugin("western_events", tuple(WESTERN_EVENTS_SPECS)),
    DomainPlugin("fengshui", tuple(FENGSHUI_SPECS)),
    DomainPlugin("psychometrics", tuple(PSYCHOMETRICS_SPECS)),
)


def _western_ephemeris_execution_wrapper(
    spec: ToolSpec,
    request: BaseModel,
    run: RunService,
) -> ServiceResult:

    mode = getattr(request, "ephemeris_policy", "auto")
    try:
        with data_file_policy(mode) as policy:
            result = run()
        if policy is not None and "error" not in result:
            return {**result, "ephemeris_data_policy": policy.receipt()}
        return result
    except EphemerisSourceError as error:
        if mode == "auto":
            raise
        return handle_calculation_error(error, spec.operation_label_zh)


def _with_western_data_files_view(
    previous: EvidenceViewsBuilder | None,
) -> EvidenceViewsBuilder:
    def build(views: EvidenceViews | None) -> EvidenceViews | None:
        if previous is not None:
            views = previous(views)
        views = views or {}
        views["data_files"] = {
            "fields": ["ephemeris_data_policy"],
            "scope": "Available when ephemeris_policy=require_data_files. Read the actual observed physical models, file sources, reference zeros and private-worker reports. Native event-internal reads, fixed-star catalogue formulae and absolute accuracy are not certified. This card does not set the input policy.",
        }
        return views

    return build


def _enrich_builtin_spec(spec: ToolSpec) -> ToolSpec:
    western_policy = supports_western_policy_model(spec.request_model)
    updated = replace(
        spec,
        detail_view=spec.detail_view or traditional_detail_view,
        output_model=spec.output_model
        or output_model_for(spec.key, western_data_policy=western_policy),
        required_output_fields=spec.required_output_fields
        or required_output_fields_for(spec.key),
        uses_astronomy_runtime=(
            spec.uses_astronomy_runtime if spec.family == "psychometrics" else True
        ),
        execution_wrapper=(
            spec.execution_wrapper
            or (_western_ephemeris_execution_wrapper if western_policy else None)
        ),
        evidence_views_builder=(
            _with_western_data_files_view(spec.evidence_views_builder)
            if western_policy
            else spec.evidence_views_builder
        ),
        reproducibility=(
            policy_for(spec.key, spec.request_model)
            if spec.reproducibility == ReproducibilityPolicy()
            else spec.reproducibility
        ),
    )
    if not updated.methods:
        updated = replace(updated, methods=register_methods(updated))
    return updated


CATALOG: list[ToolSpec] = [
    _enrich_builtin_spec(spec) for spec in assemble_catalog(PLUGINS)
]


def rest_specs() -> list[ToolSpec]:
    return [s for s in CATALOG if s.rest_path]


def mcp_specs() -> list[ToolSpec]:
    return [s for s in CATALOG if s.mcp_name]
