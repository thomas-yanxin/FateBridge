"""Ordered assembly and contract enrichment for domain tools."""

from __future__ import annotations

from dataclasses import replace
from typing import List

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy, policy_for
from fatebridge.core.requests.western_policy import supports_western_policy_model
from fatebridge.core.response_models import output_model_for, required_output_fields_for
from fatebridge.services.catalog.astrology import SPECS as ASTROLOGY_SPECS
from fatebridge.services.catalog.bazi import SPECS as BAZI_SPECS
from fatebridge.services.catalog.compatibility import SPECS as COMPATIBILITY_SPECS
from fatebridge.services.catalog.divination import SPECS as DIVINATION_SPECS
from fatebridge.services.catalog.fengshui import SPECS as FENGSHUI_SPECS
from fatebridge.services.catalog.metaphysics import SPECS as METAPHYSICS_SPECS
from fatebridge.services.catalog.reference import SPECS as REFERENCE_SPECS
from fatebridge.services.catalog.timing import SPECS as TIMING_SPECS
from fatebridge.services.catalog.western_events import SPECS as WESTERN_EVENTS_SPECS
from fatebridge.services.catalog.western_lifespan import SPECS as WESTERN_LIFESPAN_SPECS
from fatebridge.services.catalog.western_timing import SPECS as WESTERN_TIMING_SPECS

CATALOG: List[ToolSpec] = [
    *BAZI_SPECS,
    *COMPATIBILITY_SPECS,
    *TIMING_SPECS,
    *DIVINATION_SPECS,
    *METAPHYSICS_SPECS,
    *REFERENCE_SPECS,
    *ASTROLOGY_SPECS,
    *WESTERN_TIMING_SPECS,
    *WESTERN_LIFESPAN_SPECS,
    *WESTERN_EVENTS_SPECS,
    *FENGSHUI_SPECS,
]

CATALOG = [
    replace(
        spec,
        output_model=spec.output_model
        or output_model_for(
            spec.key,
            western_data_policy=supports_western_policy_model(spec.request_model),
        ),
        required_output_fields=spec.required_output_fields
        or required_output_fields_for(spec.key),
    )
    for spec in CATALOG
]

CATALOG = [
    replace(
        spec,
        reproducibility=(
            policy_for(spec.key, spec.request_model)
            if spec.reproducibility == ReproducibilityPolicy()
            else spec.reproducibility
        ),
    )
    for spec in CATALOG
]


def rest_specs() -> List[ToolSpec]:
    return [s for s in CATALOG if s.rest_path]


def mcp_specs() -> List[ToolSpec]:
    return [s for s in CATALOG if s.mcp_name]
