"""Optional, projection-safe scoped penalty presence and effect qualifiers."""

from typing import Any, Dict, List, Optional

from fatebridge.core.output_base import PartialOutput


class PenaltyActor(PartialOutput):
    location: Optional[str] = None
    position: Optional[int] = None
    branch: Optional[str] = None
    presence_condition_match: Optional[bool] = None
    activity_source_path: Optional[str] = None
    reason: Optional[str] = None


class PenaltyLine(PartialOutput):
    position: Optional[int] = None
    branch: Optional[str] = None
    subject_kind: Optional[str] = None
    applicable: Optional[bool] = None
    condition_match: Optional[bool] = None
    effect_condition_match: Optional[bool] = None
    yin_generation_allowed: Optional[bool] = None
    day_yin_growth_applicable: Optional[bool] = None
    day_yin_growth_allowed: Optional[bool] = None
    actors: Optional[List[PenaltyActor]] = None
    ignored_actors: Optional[List[PenaltyActor]] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None


class PenaltyConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    clauses: Optional[List[Dict[str, Any]]] = None
    quotation_errata: Optional[Dict[str, Any]] = None
    precedence: Optional[Dict[str, Any]] = None
    lines: Optional[List[PenaltyLine]] = None
    focus: Optional[PenaltyLine] = None
    scope: Optional[str] = None
