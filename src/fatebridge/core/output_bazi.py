"""Stable nested facts, with projection-compatible optional fields.

Validate existing payloads without reserialization; dynamic map keys and
extension fields remain open. Definitions follow the service builders.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import ConfigDict, model_validator

from fatebridge.core.output_base import PartialOutput


class TimingOverrides(PartialOutput):
    dayun_pillar: Optional[bool] = None
    liunian_pillar: Optional[bool] = None


class DimensionTimingContext(PartialOutput):
    analysis_date: Optional[str] = None
    dayun_pillar: Optional[str] = None
    liunian_pillar: Optional[str] = None
    source: Optional[str] = None
    # The timing engine reports fractional years (for example 28.7).
    dayun_age: Optional[float] = None
    overridden: Optional[TimingOverrides] = None


class DimensionOutput(PartialOutput):
    timing_context: Optional[DimensionTimingContext] = None


class TimingSignals(PartialOutput):
    timing_signals: Optional[List[str]] = None


class Notes(PartialOutput):
    notes: Optional[List[str]] = None


class StarPosition(PartialOutput):
    pillar: Optional[str] = None
    location: Optional[str] = None
    char: Optional[str] = None
    ten_god: Optional[str] = None


class SpouseStarPosition(PartialOutput):
    position: Optional[str] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    ten_god: Optional[str] = None
    is_primary: Optional[bool] = None


class SpouseStar(PartialOutput):
    spouse_star_type: Optional[str] = None
    spouse_star_alt: Optional[str] = None
    spouse_star_strength: Optional[str] = None
    spouse_element: Optional[str] = None
    predicted_appearance: Optional[str] = None
    spouse_star_positions: Optional[List[SpouseStarPosition]] = None


class SpousePalace(PartialOutput):
    day_branch: Optional[str] = None
    day_branch_element: Optional[str] = None
    day_branch_polarity: Optional[str] = None
    relationship_to_day_master: Optional[str] = None
    stability: Optional[str] = None
    spouse_personality_hint: Optional[str] = None
    hidden_stems: Optional[List[str]] = None
    stability_notes: Optional[List[str]] = None


class MarriageQuality(PartialOutput):
    score: Optional[int] = None
    quality_level: Optional[str] = None
    notes: Optional[List[str]] = None


class MarriageShensha(PartialOutput):
    name: Optional[str] = None
    position: Optional[str] = None
    meaning: Optional[str] = None


class MarriageTiming(PartialOutput):
    timing_signals: Optional[List[str]] = None
    marriage_tendency: Optional[str] = None
    tendency_notes: Optional[List[str]] = None


class MarriageRisk(PartialOutput):
    type: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None


class MarriageAnalysis(DimensionOutput):
    spouse_star: Optional[SpouseStar] = None
    spouse_palace: Optional[SpousePalace] = None
    marriage_quality: Optional[MarriageQuality] = None
    marriage_shensha: Optional[List[MarriageShensha]] = None
    marriage_timing: Optional[MarriageTiming] = None
    risk_factors: Optional[List[MarriageRisk]] = None
    suggestions: Optional[List[str]] = None


class CareerGod(PartialOutput):
    ten_god: Optional[str] = None
    career_type: Optional[str] = None
    traits: Optional[str] = None
    weight: Optional[float] = None
    suitable_roles: Optional[List[str]] = None


class CareerDominant(PartialOutput):
    top_gods: Optional[List[CareerGod]] = None
    primary_career_type: Optional[str] = None


class IndustryRecommendation(PartialOutput):
    element: Optional[str] = None
    direction: Optional[str] = None
    reason: Optional[str] = None
    industries: Optional[List[str]] = None


class IndustryAnalysis(PartialOutput):
    favorable_elements: Optional[List[str]] = None
    recommended_industries: Optional[List[IndustryRecommendation]] = None
    avoid_industries: Optional[List[IndustryRecommendation]] = None
    element_distribution: Optional[Dict[str, float]] = None


class CareerStructure(PartialOutput):
    score_kind: Optional[str] = None
    scope: Optional[str] = None
    score_basis: Optional[str] = None
    score: Optional[int] = None
    level: Optional[str] = None
    notes: Optional[List[str]] = None


class Entrepreneurship(PartialOutput):
    score_kind: Optional[str] = None
    scope: Optional[str] = None
    score_basis: Optional[str] = None
    score: Optional[int] = None
    tendency: Optional[str] = None
    notes: Optional[List[str]] = None


class FavorableDirection(PartialOutput):
    element: Optional[str] = None
    direction: Optional[str] = None
    reason: Optional[str] = None


class NobleDirection(PartialOutput):
    favorable_directions: Optional[List[FavorableDirection]] = None


class CareerAnalysis(DimensionOutput):
    interpretation_scope: Optional[str] = None
    dominant_ten_gods: Optional[CareerDominant] = None
    industry_analysis: Optional[IndustryAnalysis] = None
    career_structure: Optional[CareerStructure] = None
    entrepreneurship: Optional[Entrepreneurship] = None
    career_timing: Optional[TimingSignals] = None
    noble_direction: Optional[NobleDirection] = None
    suggestions: Optional[List[str]] = None


class WealthStars(PartialOutput):
    positions: Optional[List[StarPosition]] = None
    zheng_wealth_weight: Optional[float] = None
    pian_wealth_weight: Optional[float] = None
    total_weight: Optional[float] = None
    visibility: Optional[str] = None


class WealthStructure(PartialOutput):
    day_master_strength: Optional[str] = None
    pattern: Optional[str] = None
    level: Optional[str] = None
    wealth_strength: Optional[float] = None
    score: Optional[int] = None
    notes: Optional[List[str]] = None


class StorageHit(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stores: Optional[str] = None
    note: Optional[str] = None
    opened: Optional[bool] = None


class WealthStorage(PartialOutput):
    has_storage: Optional[bool] = None
    storage_hits: Optional[List[StorageHit]] = None
    summary: Optional[str] = None


class WealthStyle(PartialOutput):
    primary_style: Optional[str] = None
    recommendations: Optional[List[str]] = None


class WealthDirection(PartialOutput):
    wealth_element: Optional[str] = None
    direction: Optional[str] = None
    note: Optional[str] = None


class WealthRisk(PartialOutput):
    bijie_weight: Optional[float] = None
    risks: Optional[List[str]] = None


class WealthAnalysis(DimensionOutput):
    wealth_element: Optional[str] = None
    wealth_stars: Optional[WealthStars] = None
    wealth_structure: Optional[WealthStructure] = None
    wealth_storage: Optional[WealthStorage] = None
    wealth_style: Optional[WealthStyle] = None
    wealth_direction: Optional[WealthDirection] = None
    wealth_risk: Optional[WealthRisk] = None
    wealth_timing: Optional[TimingSignals] = None
    suggestions: Optional[List[str]] = None


class Constitution(PartialOutput):
    day_master_strength: Optional[str] = None
    climate: Optional[str] = None
    warm_strength: Optional[float] = None
    cold_strength: Optional[float] = None
    notes: Optional[List[str]] = None
    reference_scope: Optional[str] = None


class OrganFinding(PartialOutput):
    element: Optional[str] = None
    organs: Optional[str] = None
    status: Optional[str] = None
    concern: Optional[str] = None


class OrganAnalysis(PartialOutput):
    element_distribution: Optional[Dict[str, float]] = None
    findings: Optional[List[OrganFinding]] = None
    summary: Optional[str] = None
    reference_scope: Optional[str] = None


class HealthAnalysis(DimensionOutput):
    model_config = ConfigDict(
        json_schema_extra={
            "not": {
                "anyOf": [
                    {"required": ["disease_risks"]},
                    {"required": ["regimen"]},
                ]
            }
        }
    )

    @model_validator(mode="before")
    @classmethod
    def _validate_cultural_scope(cls, data: Any) -> Any:
        if isinstance(data, dict) and {"disease_risks", "regimen"} & data.keys():
            raise ValueError("健康文化结果不提供疾病风险或调理处方区块")
        return data

    constitution: Optional[Constitution] = None
    organ_analysis: Optional[OrganAnalysis] = None
    health_timing: Optional[TimingSignals] = None
    disclaimer: Optional[str] = None
    scope: Optional[str] = None
    is_medical_assessment: Optional[Literal[False]] = None


class ChildStar(PartialOutput):
    star: Optional[str] = None
    status: Optional[str] = None
    positions: Optional[List[StarPosition]] = None
    weight: Optional[float] = None


class ChildPalace(PartialOutput):
    hour_pillar: Optional[str] = None
    hour_ten_god: Optional[str] = None
    trait: Optional[str] = None
    palace_relations: Optional[List[str]] = None


class ChildAffinity(PartialOutput):
    score: Optional[int] = None
    tendency: Optional[str] = None
    notes: Optional[List[str]] = None


class ChildRelationship(PartialOutput):
    hour_ten_god: Optional[str] = None
    trait: Optional[str] = None
    achievement: Optional[List[str]] = None


class ChildrenAnalysis(DimensionOutput):
    gender_basis: Optional[str] = None
    child_star: Optional[ChildStar] = None
    child_palace: Optional[ChildPalace] = None
    affinity: Optional[ChildAffinity] = None
    relationship: Optional[ChildRelationship] = None
    children_timing: Optional[TimingSignals] = None


class StudyStars(PartialOutput):
    seal_weight: Optional[float] = None
    food_hurt_weight: Optional[float] = None
    officer_weight: Optional[float] = None
    wealth_weight: Optional[float] = None


class EducationLevel(PartialOutput):
    score: Optional[int] = None
    tier: Optional[str] = None
    notes: Optional[List[str]] = None


class Wenchang(PartialOutput):
    wenchang_branch: Optional[str] = None
    note: Optional[str] = None
    hit_pillars: Optional[List[str]] = None
    has_wenchang: Optional[bool] = None


class SubjectOrientation(PartialOutput):
    inclination: Optional[str] = None
    favorable_fields: Optional[List[str]] = None


class EducationAnalysis(DimensionOutput):
    study_stars: Optional[StudyStars] = None
    education_level: Optional[EducationLevel] = None
    wenchang: Optional[Wenchang] = None
    subject_orientation: Optional[SubjectOrientation] = None
    exam_timing: Optional[TimingSignals] = None
    suggestions: Optional[List[str]] = None


class CoreNature(PartialOutput):
    element: Optional[str] = None
    virtue: Optional[str] = None
    traits: Optional[str] = None
    shortcoming: Optional[str] = None


class PersonalityGod(PartialOutput):
    ten_god: Optional[str] = None
    traits: Optional[str] = None
    weight: Optional[float] = None


class DominantTraits(PartialOutput):
    top_gods: Optional[List[PersonalityGod]] = None
    primary: Optional[str] = None


class Disposition(PartialOutput):
    strength: Optional[str] = None
    polarity: Optional[str] = None
    notes: Optional[List[str]] = None


class PersonalityAnalysis(DimensionOutput):
    day_master: Optional[str] = None
    core_nature: Optional[CoreNature] = None
    dominant_traits: Optional[DominantTraits] = None
    disposition: Optional[Disposition] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    advice: Optional[List[str]] = None


class ParentStars(PartialOutput):
    father_star_weight: Optional[float] = None
    mother_star_weight: Optional[float] = None
    notes: Optional[List[str]] = None


class Siblings(PartialOutput):
    sibling_star_weight: Optional[float] = None
    notes: Optional[List[str]] = None


class RelativePalaces(PartialOutput):
    year_pillar: Optional[str] = None
    month_pillar: Optional[str] = None
    relations: Optional[List[str]] = None


class RelativeSupport(PartialOutput):
    seal_weight: Optional[float] = None
    peer_weight: Optional[float] = None
    notes: Optional[List[str]] = None


class RelativesAnalysis(DimensionOutput):
    parents: Optional[ParentStars] = None
    siblings: Optional[Siblings] = None
    palaces: Optional[RelativePalaces] = None
    support: Optional[RelativeSupport] = None


class PeachBlossom(PartialOutput):
    peach_branches: Optional[List[str]] = None
    hit_pillars: Optional[List[str]] = None
    count: Optional[int] = None
    note: Optional[str] = None


class HongluanTianxi(PartialOutput):
    hongluan_branch: Optional[str] = None
    tianxi_branch: Optional[str] = None
    hongluan_hits: Optional[List[str]] = None
    tianxi_hits: Optional[List[str]] = None
    notes: Optional[List[str]] = None


class OppositeSexStar(PartialOutput):
    basis: Optional[str] = None
    status: Optional[str] = None
    weight: Optional[float] = None


class RomanceAnalysis(DimensionOutput):
    gender_basis: Optional[str] = None
    peach_blossom: Optional[PeachBlossom] = None
    hongluan_tianxi: Optional[HongluanTianxi] = None
    opposite_sex_star: Optional[OppositeSexStar] = None
    peach_quality: Optional[Notes] = None
    romance_timing: Optional[TimingSignals] = None


BAZI_FIELDS: Dict[str, Any] = {
    "marriage_analysis": MarriageAnalysis,
    "career_analysis": CareerAnalysis,
    "wealth_analysis": WealthAnalysis,
    "health_analysis": HealthAnalysis,
    "children_analysis": ChildrenAnalysis,
    "education_analysis": EducationAnalysis,
    "personality_analysis": PersonalityAnalysis,
    "relatives_analysis": RelativesAnalysis,
    "romance_analysis": RomanceAnalysis,
}
