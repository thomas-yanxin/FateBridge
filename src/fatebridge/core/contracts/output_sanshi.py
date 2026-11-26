"""Projected output facts for the shared-position join of three actual charts."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class CorrespondenceQimen(PartialOutput):
    source_path: str | None = None
    index: int | None = None
    trigram: str | None = None
    star: str | None = None
    door: str | None = None
    god: str | None = None
    hosted_stars: list[str] | None = None


class CorrespondenceLiurenCandidate(PartialOutput):
    source_path: str | None = None
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None


class CorrespondenceLiuren(CorrespondenceLiurenCandidate):
    status: str | None = None
    reason: str | None = None
    candidate_scope: str | None = None
    sector_source_urls: list[str] | None = None
    sector_candidates: list[CorrespondenceLiurenCandidate] | None = None


class PalaceCorrespondence(PartialOutput):
    marker: str | None = None
    taiyi_source_path: str | None = None
    taiyi_number: int | None = None
    taiyi_palace: str | None = None
    trigram: str | None = None
    direction: str | None = None
    qimen: CorrespondenceQimen | None = None
    liureng: CorrespondenceLiuren | None = None


class CorrespondenceRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    sources: list[str] | None = None
    conformance: str | None = None


class PalaceCorrespondences(PartialOutput):
    ruleset: CorrespondenceRuleset | None = None
    scope: str | None = None
    entries: list[PalaceCorrespondence] | None = None
    joint_judgment: str | None = None
    missing_rules: list[str] | None = None


class SanshiFact(PartialOutput):
    technique: str | None = None
    field: str | None = None
    value: JsonValue | None = None


class SanshiSourceProfile(PartialOutput):
    id: str | None = None
    version: str | None = None
    author: str | None = None
    classical_author: str | None = None
    source: str | None = None
    source_urls: list[str] | None = None
    source_path: str | None = None
    source_title: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    unresolved_count: int | None = None


class NobleSourceComparison(PartialOutput):
    source_id: str | None = None
    source_edition: str | None = None
    source_url: str | None = None
    facsimile_page: int | None = None
    facsimile_sha256: str | None = None
    source_branch: str | None = None
    matches: bool | None = None


class NobleSourceAssessment(PartialOutput):
    status: str | None = None
    reason: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_freeze_sha256: str | None = None
    scope: str | None = None
    taiyi_mode: str | None = None
    applicability: str | None = None
    source_morning_evening_boundary_adjudicated: bool | None = None
    whole_dangshi_method_acceptance_passed: bool | None = None
    day_stem: str | None = None
    day_stem_path: str | None = None
    is_diurnal: bool | None = None
    actual_profile: str | None = None
    actual_start_branch: str | None = None
    actual_trace_index: int | None = None
    actual_start_path: str | None = None
    actual_diurnal_path: str | None = None
    diurnal_basis: str | None = None
    diurnal_evidence_path: str | None = None
    boundary_scope: str | None = None
    comparisons: list[NobleSourceComparison] | None = None


class SanshiSynthesis(PartialOutput):
    source_profiles: dict[str, list[SanshiSourceProfile]] | None = None
    method: str | None = None
    status: str | None = None
    time_scopes: dict[str, str] | None = None
    common_input: dict[str, str] | None = None
    facts: list[SanshiFact] | None = None
    palace_correspondences: PalaceCorrespondences | None = None
    noble_source_assessment: NobleSourceAssessment | None = None
    agreement: str | None = None
    independent_evidence_count: int | None = None
    limitations: list[str] | None = None
