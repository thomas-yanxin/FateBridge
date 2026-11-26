"""Projection-safe optional fields for distinct Fan/Fu structural domains."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class FanfuRegion(PartialOutput):
    region: str | None = None
    base_trigram_code: str | None = None
    changed_trigram_code: str | None = None
    trigram_changed: bool | None = None
    base_branches: list[str] | None = None
    changed_chart_branches: list[str] | None = None
    nazhi_relation: str | None = None
    moving_positions: list[int] | None = None
    static_comparison_positions: list[int] | None = None
    source_url: str | None = None
    scope: str | None = None


class FanfuLine(PartialOutput):
    position: int | None = None
    original_branch: str | None = None
    changed_branch: str | None = None
    nazhi_relation: str | None = None


class FanfuBodyExample(PartialOutput):
    base_code: str | None = None
    changed_code: str | None = None
    kind: str | None = None
    pdf_page: int | None = None
    source_url: str | None = None
    basis: str | None = None


class FanfuEvidence(PartialOutput):
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_url: str | None = None
    regions: list[FanfuRegion] | None = None
    moving_line_relations: list[FanfuLine] | None = None
    explicit_body_example: FanfuBodyExample | None = None
    body_classification: str | None = None
    efficacy: str | None = None
    textual_issues: list[dict[str, OpenJsonValue]] | None = None
    scope: str | None = None
