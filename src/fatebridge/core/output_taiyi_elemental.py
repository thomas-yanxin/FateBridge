"""Partial projection contract for the separately sourced two-eye fragment."""

from typing import List, Optional

from pydantic import StrictBool

from .output_base import PartialOutput


class TaiyiElementalRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    source_title: Optional[str] = None
    classical_author: Optional[str] = None
    source_manifest_sha256: Optional[str] = None
    catalog_sha256: Optional[str] = None
    source_urls: Optional[List[str]] = None


class TaiyiElementalEye(PartialOutput):
    camp: Optional[str] = None
    role: Optional[str] = None
    actual_path: Optional[str] = None
    position: Optional[str] = None
    source_name: Optional[str] = None
    element: Optional[str] = None


class TaiyiElementalSpatial(PartialOutput):
    status: Optional[str] = None
    present: Optional[StrictBool] = None
    pattern_paths: Optional[List[str]] = None
    scope: Optional[str] = None


class TaiyiElementalReading(PartialOutput):
    kind: Optional[str] = None
    reading: Optional[str] = None
    source: Optional[str] = None
    applicability: Optional[str] = None
    scope: Optional[str] = None
    overall_outcome_assessed: Optional[StrictBool] = None


class TaiyiElementalAssessment(PartialOutput):
    ruleset: Optional[TaiyiElementalRuleset] = None
    calculation_mode: Optional[str] = None
    source_day_usage: Optional[str] = None
    full_daily_na_yin_method_verified: Optional[StrictBool] = None
    role_scope: Optional[str] = None
    method_scope: Optional[str] = None
    scope: Optional[str] = None
    real_world_efficacy: Optional[str] = None
    implemented_spatial_guan: Optional[TaiyiElementalSpatial] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    eyes: Optional[List[TaiyiElementalEye]] = None
    relation: Optional[str] = None
    relation_label: Optional[str] = None
    elemental_control: Optional[StrictBool] = None
    controlling_camp: Optional[str] = None
    source_interpretation: Optional[TaiyiElementalReading] = None
