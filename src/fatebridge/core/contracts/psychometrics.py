"""Public output contracts for psychometric assessments."""

from __future__ import annotations

from typing import Literal

from pydantic import JsonValue

from fatebridge.core.contracts.base import PartialOutput, ProjectedOutput
from fatebridge.core.psychometrics.ipip_big_five import (
    BigFiveDomain,
    DomainStatus,
    ScaleStatus,
)
from fatebridge.core.receipt_models import RunMetadata


class IpipScaleProvenance(PartialOutput):
    method_id: str | None = None
    scale_id: str | None = None
    scale_name: str | None = None
    scale_name_zh: str | None = None
    author: str | None = None
    license: str | None = None
    scale_url: str | None = None
    scoring_url: str | None = None
    domains: dict[str, dict[str, JsonValue]] | None = None
    response_scale: dict[str, str] | None = None
    reverse_scoring_rule: str | None = None
    missing_item_policy: str | None = None
    min_answered_per_domain: int | None = None
    items_per_domain: int | None = None
    total_items: int | None = None


class IpipItemDefinitionOutput(PartialOutput):
    item_id: int
    domain: BigFiveDomain
    keying: Literal[1, -1]
    text: str
    gloss_zh: str


class IpipDomainScoreOutput(PartialOutput):
    domain: BigFiveDomain | None = None
    domain_label_zh: str | None = None
    factor: int | None = None
    status: DomainStatus | None = None
    answered_count: int | None = None
    missing_count: int | None = None
    total_items: int | None = None
    missing_item_ids: list[int] | None = None
    raw_sum: int | None = None
    prorated_sum: float | None = None
    mean: float | None = None


class IpipItemBreakdownOutput(PartialOutput):
    item_id: int
    domain: BigFiveDomain
    keying: Literal[1, -1]
    raw_score: int | None = None
    scored_value: int | None = None
    status: Literal["answered", "missing"]


class IpipBigFiveOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    mode: Literal["score", "list_items"] | None = None
    scale_id: str | None = None
    status: ScaleStatus | None = None
    domain_filter: BigFiveDomain | None = None
    item_count: int | None = None
    items: list[IpipItemDefinitionOutput] | None = None
    answered_count: int | None = None
    missing_count: int | None = None
    total_items: int | None = None
    domains: dict[str, IpipDomainScoreOutput] | None = None
    item_breakdown: list[IpipItemBreakdownOutput] | None = None
    provenance: IpipScaleProvenance | None = None
    summary: str | None = None
