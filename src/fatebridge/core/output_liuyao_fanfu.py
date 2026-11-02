"""Projection-safe optional fields for distinct Fan/Fu structural domains."""

from typing import Any, Dict, List, Optional

from .output_base import PartialOutput


class FanfuRegion(PartialOutput):
    region: Optional[str] = None
    base_trigram_code: Optional[str] = None
    changed_trigram_code: Optional[str] = None
    trigram_changed: Optional[bool] = None
    base_branches: Optional[List[str]] = None
    changed_chart_branches: Optional[List[str]] = None
    nazhi_relation: Optional[str] = None
    moving_positions: Optional[List[int]] = None
    static_comparison_positions: Optional[List[int]] = None
    source_url: Optional[str] = None
    scope: Optional[str] = None


class FanfuLine(PartialOutput):
    position: Optional[int] = None
    original_branch: Optional[str] = None
    changed_branch: Optional[str] = None
    nazhi_relation: Optional[str] = None


class FanfuBodyExample(PartialOutput):
    base_code: Optional[str] = None
    changed_code: Optional[str] = None
    kind: Optional[str] = None
    pdf_page: Optional[int] = None
    source_url: Optional[str] = None
    basis: Optional[str] = None


class FanfuEvidence(PartialOutput):
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    regions: Optional[List[FanfuRegion]] = None
    moving_line_relations: Optional[List[FanfuLine]] = None
    explicit_body_example: Optional[FanfuBodyExample] = None
    body_classification: Optional[str] = None
    efficacy: Optional[str] = None
    textual_issues: Optional[List[Dict[str, Any]]] = None
    scope: Optional[str] = None
