"""Liuren board, calendar and annual-fate contracts."""

from typing import Literal

from pydantic import Field, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import BranchName, Object
from fatebridge.core.contracts.output_liuren_auxiliary import LiurenAuxiliaryStars
from fatebridge.core.contracts.output_liuren_branches import (
    LiurenBranchRelations,
    align_branch_relations,
)
from fatebridge.core.contracts.output_liuren_cross_harmony import (
    LiurenCrossHarmony,
    align_cross_harmony,
)
from fatebridge.core.contracts.output_liuren_day_placements import (
    LiurenDayPlacements,
    align_day_placements,
)
from fatebridge.core.contracts.output_liuren_emptiness import LiurenEmptinessEvidence
from fatebridge.core.contracts.output_liuren_god_yin import LiurenGodYin, align_god_yin
from fatebridge.core.contracts.output_liuren_life import (
    LiurenLifeStage,
    LiurenLifeStages,
)
from fatebridge.core.contracts.output_liuren_progression import (
    LiurenProgression,
    align_progression,
)
from fatebridge.core.contracts.output_liuren_seasonal import (
    LiurenSeasonalEvidence,
    align_seasonal,
)
from fatebridge.core.contracts.output_liuren_selection import validate_selection
from fatebridge.core.contracts.output_liuren_transmission_relations import (
    LiurenTransmissionRelations,
    compare_present_relations,
)
from fatebridge.core.contracts.output_liuren_year_fate import LiurenYearFate
from fatebridge.core.contracts.output_ren_clock import (
    RenCivilClockResolution,
    RenRunyearAgeCalendar,
)
from fatebridge.core.contracts.output_ren_term_dates import (
    RenPublishedDateReference,
    align_published_date,
)
from fatebridge.core.metaphysics.liureng_transmission_relations import (
    transmission_relations,
)
from fatebridge.core.metaphysics.liureng_trine_seasonal import nominal_seasonal_evidence
from fatebridge.core.metaphysics.ren_term_longitude import validate_term_longitude
from fatebridge.core.metaphysics.ren_term_point import validate_term_point
from fatebridge.utils.civil_time import ZonedCalendar


class LiurenLesson(PartialOutput):
    anchor_branch: str | None = None
    index: int | None = None
    lower_branch: str | None = None
    upper_branch: str | None = None
    upper_day_stem_life_stage: LiurenLifeStage | None = None
    relation: str | None = None
    relations: dict[str, str] | None = Field(
        default=None,
        description="兼容优先标签仅列同支、合、冲、害；平不表示无刑破。并存支位条件见liureng.branch_relations。",
    )
    style_basis: str | None = None
    style_hint: str | None = None
    text: str | None = None
    upper_lower_relation: str | None = None
    use_candidate: bool | None = None


class LiurenTransmission(PartialOutput):
    branch: str | None = None
    ganzhi: str | None = None
    god: str | None = None
    relation: str | None = None
    dun_stem: str | None = None
    xun_kong: bool | None = None
    earth_branch: str | None = None
    seated_kong: bool | None = None
    day_stem_life_stage: LiurenLifeStage | None = None
    seated_day_stem_life_stage: LiurenLifeStage | None = None


class LiurenTransmissions(PartialOutput):
    initial: LiurenTransmission | None = None
    middle: LiurenTransmission | None = None
    final: LiurenTransmission | None = None
    method: str | None = None


class LiurenBoardRow(PartialOutput):
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None


class LiurenPattern(PartialOutput):
    basis: str | None = None
    name: str | None = None


class RenDiurnalEvidence(PartialOutput):
    method_id: str | None = None
    hour_branch: str | None = None
    explicit_choice: bool | None = None
    is_diurnal: bool | None = None
    selection_source: str | None = None
    fixed_day_branches: list[str] | None = None
    stellar_visibility_observed: None = None
    astronomical_boundary_computed: bool | None = None
    solar_altitude_threshold_degrees: None = None
    basis: str | None = None
    scope: str | None = None


class LiurenMeta(PartialOutput):
    guiren_profile: str | None = None
    current_term: str | None = None
    month_general_basis: str | None = None
    guiren_earth_branch: str | None = None
    is_diurnal: bool | None = None
    lunar_display: str | None = None
    questioner_gender: str | None = None
    selected_lesson_index: int | None = None
    selected_lesson_relation: str | None = None
    diurnal_basis: str | None = None
    diurnal_evidence: RenDiurnalEvidence | None = None


class RenRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_urls: list[str] | None = None
    source_kind: str | None = None
    classical_conformance: str | None = None
    classical_acceptance_passed: bool | None = None
    conventions: dict[str, str] | None = None
    unresolved: list[str] | None = None


class RenRuleTrace(PartialOutput):
    rule_id: str | None = None
    source_section: str | None = None
    source_url: str | None = None
    result: Object | None = None


class LiurenSourceNote(PartialOutput):
    annotation: str | None = None
    original_pdf_page: int | None = None
    source_url: str | None = None
    kind: str | None = None
    explanation: str | None = None
    scope: str | None = None


class LiurenClassification(PartialOutput):
    ruleset_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    labels: list[str] | None = None
    detail: str | None = None
    transmission_method: str | None = None
    lower_thief_lessons: list[int] | None = None
    upper_killer_lessons: list[int] | None = None
    initial_self_punishment: bool | None = None
    closing_punishment: bool | None = None
    selected_lesson: int | None = None
    basis: str | None = None
    scope: str | None = None
    source_note: LiurenSourceNote | None = None


class RenTermDependency(PartialOutput):
    published_date_reference: RenPublishedDateReference | None = None
    role: str | None = None
    name: str | None = None
    civil_moment: str | None = None
    local_clock_status: Literal["undefined"] | None = None
    provider: str | None = None
    ephemeris_model: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None
    solar_model_details: dict[str, OpenJsonValue] | None = None
    solver_time_scale: str | None = None
    civil_time_method: str | None = None
    future_leap_seconds_assumed_unchanged: bool | None = None
    leap_table_expires_at: str | None = None
    leap_table_source: str | None = None

    @model_validator(mode="after")
    def published_date_matches_dependency(self) -> "RenTermDependency":

        align_published_date(self)
        validate_term_point(
            self.solar_model_details,
            (
                ZonedCalendar.from_isoformat(self.civil_moment)
                if self.civil_moment is not None
                else None
            ),
            complete=False,
        )
        validate_term_longitude(
            name=self.name,
            provider=self.provider,
            model=self.ephemeris_model,
            flags=self.ephemeris_retflags,
            library_version=self.ephemeris_library_version,
            details=self.solar_model_details,
            complete=False,
        )
        return self


class RenSolarLongitudeDefinition(PartialOutput):
    origin: Literal["geocentric"] | None = None
    position: Literal["apparent"] | None = None
    plane: Literal["ecliptic_of_date"] | None = None
    equinox: Literal["true_of_date"] | None = None
    astronomical_model: (
        Literal[
            "Swiss_Ephemeris_default_IERS2010_Astronomical_Almanac",
            "fatebridge_analytic_solar_v1",
            "per_dependency_named_models",
        ]
        | None
    ) = None
    horizons_frame_equivalence_certified: Literal[False] | None = None
    source_url: str | None = None
    source_section: str | None = None
    scope: str | None = None


class RenCalendarPolicy(PartialOutput):
    mode: str | None = None
    civil_datetime: str | None = None
    civil_instant_utc: str | None = None
    civil_clock_resolution: RenCivilClockResolution | None = None
    day_hour_clock: str | None = None
    corrected_clock: str | None = None
    day_boundary: str | None = None
    effective_day_date: str | None = None
    effective_day_ganzhi: str | None = None
    year_month_clock: str | None = None
    month_general_clock: str | None = None
    month_general_override: str | None = None
    month_boundary: str | None = None
    month_general_boundary: str | None = None
    solar_term_dependencies: list[RenTermDependency] | None = None
    solar_longitude_definition: RenSolarLongitudeDefinition | None = None
    precision_status: str | None = None
    scope: str | None = None


class Liuren(PartialOutput):
    god_yin: LiurenGodYin | None = None
    seasonal_evidence: LiurenSeasonalEvidence | None = None
    transmission_progression: LiurenProgression | None = None
    branch_relations: LiurenBranchRelations | None = None
    day_placement_patterns: LiurenDayPlacements | None = None
    cross_harmony: LiurenCrossHarmony | None = None
    emptiness_evidence: LiurenEmptinessEvidence | None = None
    transmission_relations: LiurenTransmissionRelations | None = None

    @model_validator(mode="after")
    def yin_matches_its_board(self) -> "Liuren":
        align_god_yin(self)
        return self

    engine: str | None = None
    board_order: str | None = None
    board_style: str | None = None
    board_style_detail: str | None = None
    guiren_system: str | None = None
    kongwang: str | None = None
    meta: LiurenMeta | None = None
    month_general: BranchName | None = None
    overview: list[str] | None = None
    patterns: list[LiurenPattern] | None = None
    four_lessons: list[LiurenLesson] | None = None
    three_transmissions: LiurenTransmissions | None = None
    twelve_board: list[LiurenBoardRow] | None = None
    month_building_element: str | None = None
    life_stages: LiurenLifeStages | None = None
    auxiliary_stars: LiurenAuxiliaryStars | None = None
    xun_head: str | None = None
    guiren_order: str | None = None
    ruleset: RenRuleset | None = None
    rule_trace: list[RenRuleTrace] | None = None
    classification: LiurenClassification | None = None
    calendar_policy: RenCalendarPolicy | None = None

    @model_validator(mode="after")
    def selection_follows_present_board(self, info: ValidationInfo) -> "Liuren":

        if not (info.context and info.context.get("full_result")):
            validate_selection(self.model_dump(exclude_unset=True))
        return self

    @model_validator(mode="after")
    def branch_relations_match_present_board(self) -> "Liuren":
        align_seasonal(self)
        align_branch_relations(self)
        align_day_placements(self)
        align_cross_harmony(self)
        align_progression(self)
        return self

    @model_validator(mode="after")
    def empty_evidence_matches_present_board(self) -> "Liuren":
        evidence = self.emptiness_evidence
        if evidence is None or evidence.rows is None:
            return self
        by_earth = {r.earth_branch: r for r in evidence.rows}
        by_sky = {r.sky_branch: r for r in evidence.rows}
        for row in self.twelve_board or []:
            if row.earth_branch is not None and row.sky_branch is not None:
                if (
                    row.earth_branch not in by_earth
                    or by_earth[row.earth_branch].sky_branch != row.sky_branch
                ):
                    raise ValueError("六壬空亡依据与同时返回的天地盘不一致")
        if self.three_transmissions is not None:
            for position in ("initial", "middle", "final"):
                item = getattr(self.three_transmissions, position)
                if item is None or item.branch is None:
                    continue
                if item.branch not in by_sky:
                    raise ValueError("六壬空亡依据中的三传支位无效")
                empty_row = by_sky[item.branch]
                for name, expected in (
                    ("earth_branch", empty_row.earth_branch),
                    ("xun_kong", empty_row.sky_xun_kong),
                    ("seated_kong", empty_row.earth_xun_kong),
                ):
                    actual = getattr(item, name)
                    if actual is not None and actual != expected:
                        raise ValueError("六壬空亡依据与同时返回的三传不一致")
        return self

    @model_validator(mode="after")
    def transmission_relationships_match_same_board(self) -> "Liuren":
        if self.transmission_relations and self.seasonal_evidence:

            month = self.seasonal_evidence.month_branch
            for trine in self.transmission_relations.trines or []:
                if month and trine.nominal_element and trine.nominal_seasonal_evidence:
                    compare_present_relations(
                        trine.nominal_seasonal_evidence.model_dump(exclude_unset=True),
                        nominal_seasonal_evidence(month, trine.nominal_element),
                    )
        if (
            self.transmission_relations is None
            or self.four_lessons is None
            or self.three_transmissions is None
        ):
            return self
        day = self.transmission_relations.day_ganzhi
        if day is None or any(
            lesson.index is None or lesson.upper_branch is None
            for lesson in self.four_lessons
        ):
            return self
        transmissions = self.three_transmissions.model_dump(exclude_unset=True)
        if any(
            not isinstance(transmissions.get(p), dict)
            or any(k not in transmissions[p] for k in ("branch", "god", "earth_branch"))
            for p in ("initial", "middle", "final")
        ):
            return self

        expected = transmission_relations(
            day_ganzhi=day,
            lessons=[
                lesson.model_dump(exclude_unset=True) for lesson in self.four_lessons
            ],
            transmissions=transmissions,
            month_branch=(
                self.seasonal_evidence.month_branch if self.seasonal_evidence else None
            ),
        )
        compare_present_relations(
            self.transmission_relations.model_dump(exclude_unset=True), expected
        )
        return self


class Runyear(PartialOutput):
    age: int | None = None
    engine: str | None = None
    ganzhi: str | None = None
    gender: str | None = None
    age_basis: str | None = None
    rule_id: str | None = None
    source_url: str | None = None
    source_section: str | None = None
    birth_lunar_year: int | None = None
    birth_civil_clock: RenCivilClockResolution | None = None
    year_fate: LiurenYearFate | None = None
    age_calendar: RenRunyearAgeCalendar | None = None
    status: str | None = None
    reason: str | None = None
