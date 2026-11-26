"""Typed source-comparison facts for compare_bazi_sources."""

from __future__ import annotations

from typing import Literal

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput

Grade = Literal["强", "中和", "弱"]


class SourceAnnotationComparison(PartialOutput):
    status: str | None = None
    computed_strength: Grade | None = None
    literal_match_count: int | None = None
    known_annotation_count: int | None = None
    unknown_or_unannotated_count: int | None = None
    agreeing_known_count: int | None = None
    differing_known_count: int | None = None
    retained_expected_strengths: list[Grade] | None = None
    records: list[dict[str, OpenJsonValue]] | None = None
    reference_index: dict[str, OpenJsonValue] | None = None
    calculation_overridden: Literal[False] | None = None


class SourceCurrentCalculation(PartialOutput):
    strength_level: Grade | None = None
    day_master: dict[str, OpenJsonValue] | None = None
    favorable_elements: list[str] | None = None
    dominant_structure: dict[str, OpenJsonValue] | None = None


class LiteralSourceInputContext(PartialOutput):
    pillars: list[str] | None = None
    valid_sexagenary_characters: bool | None = None
    input_kind: Literal["literal_four_pillars"] | None = None
    birth_datetime_reconstructed: Literal[False] | None = None
