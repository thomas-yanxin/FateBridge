"""Projection-compatible source-policy facts, with explicit non-certification."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput

Count = Annotated[int, Field(ge=0)]


class ObservedPolicyFile(PartialOutput):
    filename: str


class WesternDataPolicy(PartialOutput):
    ruleset_id: Literal["fatebridge.observed_physical_data_policy.v1"] | None = None
    requested: Literal["require_data_files"] | None = None
    physical_calls_by_model: dict[Literal["swieph", "jpl"], Count] | None = None
    analytical_or_nonphysical_calls: Count | None = None
    reference_zero_calls: Count | None = None
    event_endpoint_probes: Count | None = None
    observed_file_path_count: Count | None = None
    observed_files: list[ObservedPolicyFile] | None = None
    private_worker_reports: list[WesternDataPolicy] | None = None
    scope: str | None = None
    atomic_native_read_set_proven: Literal[False] | None = None
    all_native_event_internal_models_verified: Literal[False] | None = None
    accuracy_certified: Literal[False] | None = None
