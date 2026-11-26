"""Qimen palace and bureau output contracts."""

from typing import Annotated

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import Object
from fatebridge.core.contracts.output_qimen import (
    QimenAssessment,
    QimenCalendarPolicy,
    QimenPalaceEvidence,
    QimenPattern,
    QimenRuleset,
    QimenRuleTrace,
    QimenStructure,
)


class QimenHexagram(PartialOutput):
    binary_code: str | None = None
    name: str | None = None


class QimenPalace(PartialOutput):
    god_sequence_index: int | None = None
    index: Annotated[int | None, FULL_FACT] = None
    direction: str | None = None
    element: str | None = None
    heaven_origin_trigram: str | None = None
    heaven_stems: list[str] | None = None
    earth_stems: list[str] | None = None
    hosted_stars: list[str] | None = None
    evidence: QimenPalaceEvidence | None = None
    name: str | None = None
    content_palace: str | None = None
    content_trigram: str | None = None
    trigram: str | None = None
    door: str | None = None
    door_hexagram: QimenHexagram | None = None
    earth_stem: str | None = None
    heaven_stem: str | None = None
    god: str | None = None
    star: str | None = None


class QimenLeader(PartialOutput):
    code: str | None = None
    content_palace: str | None = None
    content_trigram: str | None = None
    palace: str | None = None
    trigram: str | None = None
    star: str | None = None
    door: str | None = None


class QimenOptions(PartialOutput):
    ju_method: str | None = None
    god_profile: str | None = None
    season_profile: str | None = None
    layout: str | None = None
    palaceShift: int | None = None
    reverse: bool | None = None


class Qimen(PartialOutput):
    stem_context: Object | None = None
    god_profile: str | None = None
    season_profile: str | None = None
    rule_profiles: Object | None = None
    ju_method: str | None = None
    ju_decision: Object | None = None
    ju_term: str | None = None
    day_ganzhi: str | None = None
    time_ganzhi: str | None = None
    day_xun_head: str | None = None
    day_kongwang: str | None = None
    rulesets: Annotated[list[QimenRuleset] | None, FULL_FACT] = None
    rule_trace: Annotated[list[QimenRuleTrace] | None, FULL_FACT] = None
    calendar_policy: Annotated[QimenCalendarPolicy | None, FULL_FACT] = None
    structure: QimenStructure | None = None
    patterns: list[QimenPattern] | None = None
    assessment: QimenAssessment | None = None
    source_disagreements: list[dict[str, JsonValue]] | None = None
    engine: str | None = None
    dun_type: Annotated[str | None, FULL_FACT] = None
    fu_tou: str | None = None
    fushi_hexagram: QimenHexagram | None = None
    ju_number: Annotated[int | None, FULL_FACT] = None
    ju_text: str | None = None
    kongwang: str | None = None
    layout: str | None = None
    options_applied: QimenOptions | None = None
    palaces: Annotated[list[QimenPalace] | None, FULL_FACT] = Field(
        default=None,
        min_length=9,
        max_length=9,
        json_schema_extra={"x-fatebridge-full-result-unique-by": "index"},
    )
    reference: str | None = None
    xun_head: str | None = None
    yuan: str | None = None
    yuan_order: str | None = None
    zhifu: QimenLeader | None = None
    zhishi: QimenLeader | None = None
