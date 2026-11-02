"""Projected output facts for the shared-position join of three actual charts."""

from typing import Dict, List, Optional

from pydantic import JsonValue

from .output_base import PartialOutput


class CorrespondenceQimen(PartialOutput):
    source_path: Optional[str] = None
    index: Optional[int] = None
    trigram: Optional[str] = None
    star: Optional[str] = None
    door: Optional[str] = None
    god: Optional[str] = None
    hosted_stars: Optional[List[str]] = None


class CorrespondenceLiurenCandidate(PartialOutput):
    source_path: Optional[str] = None
    earth_branch: Optional[str] = None
    sky_branch: Optional[str] = None
    god: Optional[str] = None


class CorrespondenceLiuren(CorrespondenceLiurenCandidate):
    status: Optional[str] = None
    reason: Optional[str] = None
    candidate_scope: Optional[str] = None
    sector_source_urls: Optional[List[str]] = None
    sector_candidates: Optional[List[CorrespondenceLiurenCandidate]] = None


class PalaceCorrespondence(PartialOutput):
    marker: Optional[str] = None
    taiyi_source_path: Optional[str] = None
    taiyi_number: Optional[int] = None
    taiyi_palace: Optional[str] = None
    trigram: Optional[str] = None
    direction: Optional[str] = None
    qimen: Optional[CorrespondenceQimen] = None
    liureng: Optional[CorrespondenceLiuren] = None


class CorrespondenceRuleset(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    sources: Optional[List[str]] = None
    conformance: Optional[str] = None


class PalaceCorrespondences(PartialOutput):
    ruleset: Optional[CorrespondenceRuleset] = None
    scope: Optional[str] = None
    entries: Optional[List[PalaceCorrespondence]] = None
    joint_judgment: Optional[str] = None
    missing_rules: Optional[List[str]] = None


class SanshiFact(PartialOutput):
    technique: Optional[str] = None
    field: Optional[str] = None
    value: Optional[JsonValue] = None


class SanshiSourceProfile(PartialOutput):
    id: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    classical_author: Optional[str] = None
    source: Optional[str] = None
    source_urls: Optional[List[str]] = None
    source_path: Optional[str] = None
    source_title: Optional[str] = None
    classical_conformance: Optional[str] = None
    classical_acceptance_passed: Optional[bool] = None
    real_world_efficacy: Optional[str] = None
    unresolved_count: Optional[int] = None


class NobleSourceComparison(PartialOutput):
    source_id: Optional[str] = None
    source_edition: Optional[str] = None
    source_url: Optional[str] = None
    facsimile_page: Optional[int] = None
    facsimile_sha256: Optional[str] = None
    source_branch: Optional[str] = None
    matches: Optional[bool] = None


class NobleSourceAssessment(PartialOutput):
    status: Optional[str] = None
    reason: Optional[str] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_freeze_sha256: Optional[str] = None
    scope: Optional[str] = None
    taiyi_mode: Optional[str] = None
    applicability: Optional[str] = None
    source_morning_evening_boundary_adjudicated: Optional[bool] = None
    whole_dangshi_method_acceptance_passed: Optional[bool] = None
    day_stem: Optional[str] = None
    day_stem_path: Optional[str] = None
    is_diurnal: Optional[bool] = None
    actual_profile: Optional[str] = None
    actual_start_branch: Optional[str] = None
    actual_trace_index: Optional[int] = None
    actual_start_path: Optional[str] = None
    actual_diurnal_path: Optional[str] = None
    diurnal_basis: Optional[str] = None
    diurnal_evidence_path: Optional[str] = None
    boundary_scope: Optional[str] = None
    comparisons: Optional[List[NobleSourceComparison]] = None


class SanshiSynthesis(PartialOutput):
    source_profiles: Optional[Dict[str, List[SanshiSourceProfile]]] = None
    method: Optional[str] = None
    status: Optional[str] = None
    time_scopes: Optional[Dict[str, str]] = None
    common_input: Optional[Dict[str, str]] = None
    facts: Optional[List[SanshiFact]] = None
    palace_correspondences: Optional[PalaceCorrespondences] = None
    noble_source_assessment: Optional[NobleSourceAssessment] = None
    agreement: Optional[str] = None
    independent_evidence_count: Optional[int] = None
    real_world_efficacy: Optional[str] = None
    limitations: Optional[List[str]] = None
