"""Partial projection contract for the separately sourced two-eye fragment."""

from pydantic import StrictBool

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiElementalRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    source_title: str | None = None
    classical_author: str | None = None
    source_urls: list[str] | None = None


class TaiyiElementalEye(PartialOutput):
    camp: str | None = None
    role: str | None = None
    actual_path: str | None = None
    position: str | None = None
    source_name: str | None = None
    element: str | None = None


class TaiyiElementalSpatial(PartialOutput):
    status: str | None = None
    present: StrictBool | None = None
    pattern_paths: list[str] | None = None
    scope: str | None = None


class TaiyiElementalReading(PartialOutput):
    kind: str | None = None
    reading: str | None = None
    source: str | None = None
    applicability: str | None = None
    scope: str | None = None
    overall_outcome_assessed: StrictBool | None = None


class TaiyiElementalAssessment(PartialOutput):
    ruleset: TaiyiElementalRuleset | None = None
    calculation_mode: str | None = None
    source_day_usage: str | None = None
    full_daily_na_yin_method_verified: StrictBool | None = None
    role_scope: str | None = None
    method_scope: str | None = None
    scope: str | None = None
    implemented_spatial_guan: TaiyiElementalSpatial | None = None
    status: str | None = None
    reason: str | None = None
    eyes: list[TaiyiElementalEye] | None = None
    relation: str | None = None
    relation_label: str | None = None
    elemental_control: StrictBool | None = None
    controlling_camp: str | None = None
    source_interpretation: TaiyiElementalReading | None = None
