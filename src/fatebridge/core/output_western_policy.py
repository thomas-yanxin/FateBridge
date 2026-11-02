"""Projection-compatible source-policy facts, with explicit non-certification."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from fatebridge.core.output_base import PartialOutput

Count = Annotated[int, Field(ge=0)]


class ObservedPolicyFile(PartialOutput):
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class WesternDataPolicy(PartialOutput):
    ruleset_id: Optional[Literal["fatebridge.observed_physical_data_policy.v1"]] = None
    requested: Optional[Literal["require_data_files"]] = None
    physical_calls_by_model: Optional[dict[Literal["swieph", "jpl"], Count]] = None
    analytical_or_nonphysical_calls: Optional[Count] = None
    reference_zero_calls: Optional[Count] = None
    event_endpoint_probes: Optional[Count] = None
    observed_file_path_count: Optional[Count] = None
    observed_files: Optional[list[ObservedPolicyFile]] = None
    private_worker_reports: Optional[list[WesternDataPolicy]] = None
    scope: Optional[str] = None
    atomic_native_read_set_proven: Optional[Literal[False]] = None
    all_native_event_internal_models_verified: Optional[Literal[False]] = None
    accuracy_certified: Optional[Literal[False]] = None
