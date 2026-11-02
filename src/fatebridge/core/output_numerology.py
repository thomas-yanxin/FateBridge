"""Projection-compatible evidence contracts for Heluo and Canping."""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BeforeValidator, Field, FiniteFloat, JsonValue, model_validator

from fatebridge.core.output_base import PartialOutput


class NumerologyRuleset(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_status: Optional[str] = None
    authorship_status: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_content_sha256: Optional[str] = None


class NumerologyValidation(PartialOutput):
    calendar: Optional[str] = None
    classical: Optional[str] = None
    interpretation: Optional[str] = None
    prediction: Optional[str] = None


class NumerologyRuleTrace(PartialOutput):
    rule_id: Optional[str] = None
    source_section: Optional[str] = None
    facts: Optional[Dict[str, JsonValue]] = None


class NumerologyCalendarPolicy(PartialOutput):
    input_calendar: Optional[Literal["proleptic_gregorian"]] = None
    automatic_reform_cutover: Optional[Literal[False]] = None
    historical_lunar_date_conversion: Optional[Literal[False]] = None
    historical_official_calendar_reconstruction: Optional[Literal[False]] = None


def _uncertified_clock_precision(value: Any) -> Any:
    if value is not False:
        raise ValueError("钟时文本分量不能认证出生记录精度。")
    return value


class NumerologyClockInput(PartialOutput):
    policy_id: Optional[Literal["numerology_clock_text_provenance_v1"]] = None
    supplied_text: Optional[str] = None
    normalized_clock: Optional[str] = None
    supplied_components: Optional[
        List[Literal["hour", "minute", "second", "fractional_second"]]
    ] = None
    omitted_components: Optional[List[Literal["second", "fractional_second"]]] = None
    fractional_digits: Optional[int] = Field(default=None, ge=0, le=6)
    calculation_defaults: Optional[Dict[Literal["second", "microsecond"], int]] = None
    uncertainty_interval: None = None
    observed_precision_certified: Optional[
        Annotated[Literal[False], BeforeValidator(_uncertified_clock_precision)]
    ] = None
    scope: Optional[str] = None
    statement: Optional[str] = None

    @model_validator(mode="after")
    def coherent_supplied_components(self) -> "NumerologyClockInput":
        from fatebridge.core.numerology_clock_input import (
            CLOCK_INPUT_SCOPE,
            clock_input_representation,
        )
        from fatebridge.core.numerology_clock_policy import require_birth_clock

        if self.scope is not None and self.scope != CLOCK_INPUT_SCOPE:
            raise ValueError("出生钟时分量的范围声明不一致。")
        if self.calculation_defaults is not None and any(
            v != 0 for v in self.calculation_defaults.values()
        ):
            raise ValueError("未给钟时分量的计算参考值须为零。")
        for components in (self.supplied_components, self.omitted_components):
            if components is not None and len(components) != len(set(components)):
                raise ValueError("钟时分量不能重复。")
        if self.normalized_clock is not None and (
            require_birth_clock(self.normalized_clock) != self.normalized_clock
        ):
            raise ValueError("计算参考钟面须为归一化格式。")
        if self.supplied_text is not None:
            expected = clock_input_representation(self.supplied_text)
            for k in self.model_fields_set:
                if k in expected and getattr(self, k) != expected[k]:
                    raise ValueError("所给钟时文本与分量回执不一致。")
        if self.supplied_components is not None and self.omitted_components is not None:
            if set(self.supplied_components) & set(self.omitted_components):
                raise ValueError("同一钟时分量不能同时为已给和未给。")
        return self


class NumerologyBirthClock(PartialOutput):
    policy_id: Optional[str] = None
    mode: Optional[Literal["civil", "apparent_solar"]] = None
    calendar_policy: Optional[NumerologyCalendarPolicy] = None
    timezone_policy_id: Optional[str] = None
    timezone_spec: Optional[str] = None
    timezone_default_policy: Optional[str] = None
    timezone_rules: Optional[Dict[str, JsonValue]] = None
    civil_utc_offset_seconds: Optional[
        Union[
            Annotated[int, Field(gt=-86400, lt=86400)],
            Annotated[FiniteFloat, Field(gt=-86400, lt=86400)],
        ]
    ] = Field(
        default=None,
        description="Actual UTC offset in seconds, retaining fractional seconds at datetime microsecond resolution; integral offsets remain integers.",
    )
    civil_daylight_saving_seconds: Optional[int] = None
    civil_datetime: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    calculation_wall_clock: Optional[str] = None
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    longitude_source: Optional[Literal["lon", "gps_lon"]] = None
    longitude_used: Optional[bool] = None
    longitude_selection_policy: Optional[str] = None
    total_correction_minutes: Optional[float] = None
    pillar_clock_policy: Optional[str] = None
    precision_scope: Optional[str] = None
    input_representation: Optional[NumerologyClockInput] = None
    birth_utc_offset_policy_id: Optional[
        Literal["numerology_confirmed_civil_offset_v1"]
    ] = None
    requested_utc_offset: Optional[str] = None
    civil_utc_offset: Optional[str] = None
    civil_fold: Optional[int] = Field(default=None, ge=0, le=1)
    civil_time_ambiguous: Optional[bool] = None
    offset_selection_scope: Optional[str] = None

    @model_validator(mode="after")
    def coherent_selected_birth_offset(self) -> "NumerologyBirthClock":
        """Check present receipts, without needing siblings lost in projection.

        Revalidating a stored receipt against today's IANA rules would change
        its historical meaning. Compare its recorded offsets and UTC instant;
        the separately recorded TZif digest identifies the rules used then.
        """
        from datetime import timezone

        from fatebridge.core.numerology_inputs import normalize_numerology_utc_offset
        from fatebridge.utils.civil_clock import format_utc_offset, parse_iso_datetime

        offsets = [
            normalize_numerology_utc_offset(value)
            for value in (self.requested_utc_offset, self.civil_utc_offset)
            if value is not None
        ]
        if len(set(offsets)) > 1:
            raise ValueError("出生偏移回执与已确认偏移不一致。")
        civil = (
            parse_iso_datetime(self.civil_datetime)
            if self.civil_datetime is not None
            else None
        )
        if civil is not None:
            if (
                self.input_representation is not None
                and self.input_representation.normalized_clock is not None
            ):
                from datetime import time

                if civil.time() != time.fromisoformat(
                    self.input_representation.normalized_clock
                ):
                    raise ValueError("出生民用钟面与所给分量的计算参考值不一致。")
            offset = civil.utcoffset()
            if offset is None:
                raise ValueError("出生民用时刻回执须带实际偏移。")
            if offsets and offsets[0] != format_utc_offset(offset):
                raise ValueError("出生民用时刻与偏移回执不一致。")
            if (
                self.civil_utc_offset_seconds is not None
                and self.civil_utc_offset_seconds != offset.total_seconds()
            ):
                raise ValueError("出生民用时刻与偏移秒数不一致。")
        if self.birth_instant_utc is not None:
            actual = parse_iso_datetime(self.birth_instant_utc)
            if actual.utcoffset() is None:
                raise ValueError("出生UTC瞬间回执须带时区。")
            if civil is not None and actual.astimezone(
                timezone.utc
            ) != civil.astimezone(timezone.utc):
                raise ValueError("出生民用时刻与UTC瞬间回执不一致。")
        if self.civil_time_ambiguous is False and self.civil_fold == 1:
            raise ValueError("非重复出生钟时不能标记第二次出现。")
        return self


class HeluoNajiaCollation(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    sha256: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    review_status: Optional[str] = None
    pure_trigram_tables: Optional[int] = Field(default=None, ge=0, le=8)
    pure_table_assignment_slots: Optional[int] = Field(default=None, ge=0, le=48)
    pure_table_borrowed_slots: Optional[int] = Field(default=None, ge=0, le=12)
    directly_collated_hexagrams: Optional[int] = Field(default=None, ge=0, le=64)
    other_hexagrams_not_individually_collated: Optional[int] = Field(
        default=None, ge=0, le=64
    )
    direct_assignment_observations: Optional[int] = Field(default=None, ge=0)
    borrowed_assignment_observations: Optional[int] = Field(default=None, ge=0)
    source_pdf_pages: Optional[List[int]] = None
    source_order_issues: Optional[List[Dict[str, JsonValue]]] = None
    unquantified_timing_najia_clauses: Optional[List[Dict[str, JsonValue]]] = None
    complete_assessment: Optional[Literal[False]] = None
    scope: Optional[str] = None


class NumerologyPillarLink(PartialOutput):
    target: Optional[Literal["month", "hour"]] = None
    basis: Optional[Literal["year", "day"]] = None
    basis_pillar: Optional[str] = None
    basis_stem: Optional[str] = None
    source_stem_group: Optional[str] = None
    head_pillar: Optional[str] = None
    branch_step: Optional[int] = Field(default=None, ge=0, le=11)
    actual_pillar: Optional[str] = None
    expected_pillar: Optional[str] = None
    matches: Optional[bool] = None

    @model_validator(mode="after")
    def coherent_stem_link(self) -> "NumerologyPillarLink":
        from fatebridge.core.numerology_pillars import (
            CYCLE,
            GAN,
            LINK_GROUPS,
            LINK_HEADS,
            ZHI,
        )

        for value in (
            self.basis_pillar,
            self.head_pillar,
            self.actual_pillar,
            self.expected_pillar,
        ):
            if value is not None and value not in CYCLE:
                raise ValueError("干支衔接证据须用有效六十甲子。")
        if (
            self.target is not None
            and self.basis is not None
            and self.basis != {"month": "year", "hour": "day"}[self.target]
        ):
            raise ValueError("月干须据年干，时干须据所用日干。")
        if self.basis_stem is not None:
            if self.basis_stem not in GAN or len(self.basis_stem) != 1:
                raise ValueError("所用基准干无效。")
            if (
                self.basis_pillar is not None
                and self.basis_stem != self.basis_pillar[0]
            ):
                raise ValueError("基准干不能替成公历年干或未换日日干。")
            if (
                self.source_stem_group is not None
                and self.basis_stem not in self.source_stem_group
            ):
                raise ValueError("原句干组不含实际基准干。")
            if (
                self.target is not None
                and self.head_pillar is not None
                and self.head_pillar
                != LINK_HEADS[self.target][GAN.index(self.basis_stem)]
            ):
                raise ValueError("实际基准干对应的原句头干不一致。")
            if (
                self.source_stem_group is not None
                and self.source_stem_group != LINK_GROUPS[GAN.index(self.basis_stem)]
            ):
                raise ValueError("原句干组不能任意扩大。")
        if (
            self.target is not None
            and self.head_pillar is not None
            and self.actual_pillar is not None
            and self.branch_step is not None
        ):
            order = "寅卯辰巳午未申酉戌亥子丑" if self.target == "month" else ZHI
            if (
                self.head_pillar[1] != order[0]
                or order.index(self.actual_pillar[1]) != self.branch_step
            ):
                raise ValueError("月、时支序或起头支不一致。")
        if (
            self.head_pillar is not None
            and self.branch_step is not None
            and self.expected_pillar is not None
        ):
            if (
                self.expected_pillar[0]
                != GAN[(GAN.index(self.head_pillar[0]) + self.branch_step) % 10]
            ):
                raise ValueError("顺行干序与原句头干不一致。")
        if self.actual_pillar is not None and self.expected_pillar is not None:
            if self.actual_pillar[1] != self.expected_pillar[1] or (
                self.matches is not None
                and self.matches != (self.actual_pillar == self.expected_pillar)
            ):
                raise ValueError("干支衔接匹配标记或实际支不一致。")
        return self


class NumerologyPillarLinks(PartialOutput):
    ruleset_id: Optional[Literal["heluo_volume7_pillar_links_v1"]] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    authorship_status: Optional[str] = None
    collation_sha256: Optional[str] = None
    pillars: Optional[Dict[str, str]] = None
    links: Optional[List[NumerologyPillarLink]] = None
    all_links_match: Optional[bool] = None
    basis_policy: Optional[
        Literal[
            "actual_selected_year_and_day_pillars; no_civil_year_or_unrolled_day_substitution"
        ]
    ] = None
    scope: Optional[str] = None
    complete_calendar_assessment: Optional[Literal[False]] = None
    constraint: Optional[str] = None

    @model_validator(mode="after")
    def coherent_pillar_facts(self) -> "NumerologyPillarLinks":
        if self.links is not None:
            if len(self.links) != 2:
                raise ValueError("应保留起月、起时两条衔接证据。")
            for row, target, basis in zip(
                self.links, ("month", "hour"), ("year", "day")
            ):
                if row.target is not None and row.target != target:
                    raise ValueError("起月起时记录不能互换。")
                if self.pillars is not None:
                    if (
                        basis in self.pillars
                        and row.basis_pillar is not None
                        and row.basis_pillar != self.pillars[basis]
                    ):
                        raise ValueError("衔接证据基准柱不属于本次四柱。")
                    if (
                        target in self.pillars
                        and row.actual_pillar is not None
                        and row.actual_pillar != self.pillars[target]
                    ):
                        raise ValueError("衔接证据实际柱不属于本次四柱。")
            if self.all_links_match is not None and all(
                r.matches is not None for r in self.links
            ):
                if self.all_links_match != all(r.matches for r in self.links):
                    raise ValueError("衔接总标记与两条实际结果不一致。")
        return self


class NumerologyEvidence(PartialOutput):
    rulesets: Optional[List[NumerologyRuleset]] = None
    corpus_sha256: Optional[str] = None
    corpus_status: Optional[str] = None
    najia_collation: Optional[HeluoNajiaCollation] = None
    yaoci_collation: Optional[Dict[str, JsonValue]] = None
    commentary_collation: Optional[Dict[str, JsonValue]] = None
    canping_text_collation: Optional[Dict[str, JsonValue]] = None
    validation_status: Optional[NumerologyValidation] = None
    interpretation_constraints: Optional[List[str]] = None
    unresolved_rules: Optional[List[str]] = None
    selected_texts: Optional[List[Dict[str, JsonValue]]] = None
    rule_trace: Optional[List[NumerologyRuleTrace]] = None
    birth_clock: Optional[NumerologyBirthClock] = None
    pillar_links: Optional[NumerologyPillarLinks] = None


class CanpingTextWitness(PartialOutput):
    element: Optional[str] = None
    number: Optional[int] = None
    kind: Optional[Literal["male", "female", "luck"]] = None
    text: Optional[str] = None
    pdf_pages: Optional[List[int]] = None
    body_pdf_page: Optional[int] = None
    source_occurrence_id: Optional[str] = Field(default=None, min_length=1)
    header_pdf_page: Optional[int] = Field(default=None, gt=0)
    number_occurrence_count: Optional[int] = Field(default=None, gt=0)
    number_occurrence_ambiguous: Optional[bool] = None
    reading_uncertainties: Optional[List[str]] = None
    source_corpus_id: Optional[str] = None
    text_status: Optional[str] = None
    relation: Optional[
        Literal[
            "same_text",
            "different_text",
            "selected_reading_uncertain",
            "witness_reading_uncertain",
            "both_readings_uncertain",
        ]
    ] = None
    replaces_selected_text: Optional[Literal[False]] = None
    inherited_reading_matches: Optional[bool] = None


class CanpingReadingRevision(PartialOutput):
    rereading_id: Optional[str] = None
    previous_collation_version: Optional[str] = None
    previous_text: Optional[str] = None
    previous_cell_status: Optional[Literal["source_reading_uncertain"]] = None
    source_pdf_page: Optional[int] = Field(default=None, gt=0)
    note: Optional[str] = None


class CanpingNumberReadingEvidence(PartialOutput):
    element: Optional[str] = None
    provisional_number: Optional[int] = None
    pdf_page: Optional[int] = Field(default=None, gt=0)
    observed_header: Optional[str] = None
    obstruction_kind: Optional[Literal["seal_overprint", "faded_digit"]] = None
    note: Optional[str] = None
    resolution_status: Optional[Literal["unresolved"]] = None
    witness_id: Optional[str] = None
    body_evidence_basis: Optional[
        Literal["prior_literal_transcription_not_new_body_collation"]
    ] = None


class CanpingTextSelection(PartialOutput):
    element: Optional[str] = None
    number: Optional[int] = None
    kind: Optional[Literal["male", "female", "luck"]] = None
    column: Optional[str] = None
    corpus_key: Optional[str] = None
    row_status: Optional[str] = None
    cell_status: Optional[str] = None
    corrected_number: Optional[int] = None
    collation_id: Optional[str] = None
    source_pdf_page: Optional[int] = None
    reading_notes: Optional[List[str]] = None
    reading_uncertainties: Optional[List[str]] = None
    number_reading_uncertainties: Optional[List[str]] = None
    number_attribution_status: Optional[Literal["provisional_inherited_key"]] = None
    reading_revision: Optional[CanpingReadingRevision] = None
    body_reading_status: Optional[
        Literal[
            "source_body_visually_read",
            "source_body_printed_blank",
            "source_body_printed_partial_blank",
            "source_body_reading_uncertain",
        ]
    ] = None
    number_reading_evidence: Optional[CanpingNumberReadingEvidence] = None
    editorial_unknown_marker: Optional[str] = None
    witnesses: Optional[List[CanpingTextWitness]] = None
    inherited_text: Optional[str] = None
    inherited_number: Optional[int] = None
    unapplied_note: Optional[Dict[str, JsonValue]] = None


class CanpingPairResolution(PartialOutput):
    same_number: Optional[bool] = None
    distinct_numbers: Optional[int] = None
    local_text_availability: Optional[str] = None
    source_rule_pdf_page: Optional[int] = None
    independent_evidence_count: Optional[int] = None
    scope: Optional[str] = None


class HeluoNajiaSource(PartialOutput):
    basis: Optional[Literal["hexagram_entry", "pure_trigram_rule"]] = None
    source_hexagram: Optional[str] = None
    source_pdf_page: Optional[int] = Field(default=None, ge=1)
    source_assignment_index: Optional[int] = Field(default=None, ge=1, le=6)


class HeluoNajiaLine(PartialOutput):
    pos: Optional[int] = Field(default=None, ge=1, le=6)
    trigram: Optional[str] = None
    direct: Optional[str] = None
    borrowed: Optional[List[str]] = None
    source: Optional[HeluoNajiaSource] = None


class HeluoNajiaMatch(PartialOutput):
    pos: Optional[int] = Field(default=None, ge=1, le=6)
    kind: Optional[Literal["direct", "borrowed"]] = None


class HeluoNajiaAssessment(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    year_ganzhi: Optional[str] = None
    lines: Optional[List[HeluoNajiaLine]] = None
    matches: Optional[List[HeluoNajiaMatch]] = None
    present: Optional[bool] = None

    source_scope: Optional[str] = None
    source_issues: Optional[List[Dict[str, JsonValue]]] = None


class HeluoNumberFact(PartialOutput):
    value: Optional[int] = Field(default=None, gt=0)
    reference: Optional[int] = None
    difference: Optional[int] = None
    comparison: Optional[Literal["正数", "不足", "有余"]] = None
    extreme_band: Optional[Literal["至弱", "太过"]] = None
    extreme_band_status: Optional[str] = None
    weak_range: Optional[List[int]] = None
    high_lower_bound: Optional[int] = None
    high_upper_bound: Optional[int] = None
    source_pdf_pages: Optional[List[int]] = None
    scope: Optional[str] = None


class HeluoNumericalCondition(PartialOutput):
    rule_id: Optional[str] = None
    label: Optional[str] = None
    source_pdf_page: Optional[int] = None
    condition: Optional[str] = None
    matched: Optional[bool] = None


class HeluoSeasonWindow(PartialOutput):
    rule_id: Optional[str] = None
    label: Optional[str] = None
    axis: Optional[Literal["tian", "di"]] = None
    source_pdf_page: Optional[int] = None
    start_term: Optional[str] = None
    end_term: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    start_provider: Optional[str] = None
    end_provider: Optional[str] = None
    start_source: Optional[Dict[str, JsonValue]] = None
    end_source: Optional[Dict[str, JsonValue]] = None
    active: Optional[bool] = None
    numeric_condition: Optional[str] = None
    numeric_band_match: Optional[bool] = None
    numeric_band_status: Optional[str] = None
    scope: Optional[str] = None


class HeluoSeasonalNumbers(PartialOutput):
    context_timezone: Optional[str] = None
    context_local_year: Optional[int] = None
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    assessment_status: Optional[str] = None
    numbers: Optional[Dict[str, HeluoNumberFact]] = None
    numerical_conditions: Optional[List[HeluoNumericalCondition]] = None
    matched_pattern_ids: Optional[List[str]] = None
    seasonal_status: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    seasonal_windows: Optional[List[HeluoSeasonWindow]] = None
    overlap_policy: Optional[str] = None
    boundary_policy: Optional[str] = None
    complete_assessment: Optional[Literal[False]] = None
    unresolved: Optional[List[str]] = None


class HeluoNatalNajiaClause(PartialOutput):
    rule_id: Optional[str] = None
    source_pdf_page: Optional[int] = Field(default=None, ge=1)
    literal: Optional[str] = None
    month_numbers: Optional[List[Annotated[int, Field(ge=1, le=12)]]] = None
    month_label_match: Optional[bool] = None
    najia: Optional[HeluoNajiaAssessment] = None
    qualifier_status: Optional[
        Literal["current_phase_facts_available", "not_evaluated_missing_najia"]
    ] = None
    connector_status: Optional[Literal["source_ji_scope_unresolved"]] = None
    match: None = None
    scope: Optional[str] = None


class HeluoAdditionalMonthWindow(PartialOutput):
    rule_id: Optional[str] = None
    source_pdf_page: Optional[int] = Field(default=None, ge=1)
    literal: Optional[str] = None
    kind: Optional[Literal["continuous_range", "discrete_months", "season_set"]] = None
    meaning: Optional[
        Literal[
            "timely", "untimely", "named_favorable_months", "named_months_with_najia"
        ]
    ] = None
    month_numbers: Optional[List[Annotated[int, Field(ge=1, le=12)]]] = None
    uncertain_month_numbers: Optional[List[Annotated[int, Field(ge=1, le=12)]]] = None
    month_label_match: Optional[bool] = None
    qualifiers: Optional[List[str]] = None
    natal_najia_clause_id: Optional[str] = None
    qualifier_status: Optional[Literal["none", "not_evaluated"]] = None
    first_month_number: Optional[int] = Field(default=None, ge=1, le=12)
    last_month_number: Optional[int] = Field(default=None, ge=1, le=12)
    first_month_inclusive: Optional[bool] = None
    last_month_inclusive: Optional[bool] = None
    match: Optional[bool] = None
    status: Optional[str] = None


class HeluoMonthSourceReading(PartialOutput):
    section: Optional[Literal["hexagram_intro", "volume_one_table"]] = None
    month_number: Optional[int] = Field(default=None, ge=1, le=12)
    source_pdf_page: Optional[int] = Field(default=None, ge=1)
    literal: Optional[str] = Field(
        default=None,
        description="卷首月号读标，卦名沿用系统规范字形并线性化；不是原页逐字转写。卦条未收逐字引文时为null。",
    )
    month_label_match: Optional[bool] = None
    status: Optional[Literal["explicit_month", "month_not_explicit"]] = None


class HeluoMonthAssignmentConflict(PartialOutput):
    gua: Optional[str] = None
    intro_month: Optional[int] = Field(default=None, ge=1, le=12)
    intro_pdf_page: Optional[int] = Field(default=None, ge=1)
    table_month: Optional[int] = Field(default=None, ge=1, le=12)
    table_pdf_page: Optional[int] = Field(default=None, ge=1)


class HeluoAssignedMonth(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    assigned_month_number: Optional[int] = Field(default=None, ge=1, le=12)
    assigned_month_branch: Optional[str] = None
    assigned_month_match: Optional[bool] = None
    selected_month_source: Optional[Literal["hexagram_intro", "volume_one_table"]] = (
        None
    )
    source_readings: Optional[List[HeluoMonthSourceReading]] = None
    source_months_agree: Optional[bool] = None
    source_consensus_match: Optional[bool] = None
    source_status: Optional[str] = None
    source_pdf_page: Optional[int] = Field(default=None, ge=1)
    additional_windows: Optional[List[HeluoAdditionalMonthWindow]] = None
    natal_najia_clause: Optional[HeluoNatalNajiaClause] = None
    opposed_month_conditions: Optional[bool] = None
    conflict_rule_ids: Optional[List[str]] = None


class HeluoMonthAffinity(PartialOutput):
    assignment_method: Optional[
        Literal["intro_preferred_v1", "volume_one_table_v1"]
    ] = None
    volume_one_explicit_months: Optional[int] = Field(default=None, ge=0, le=64)
    volume_one_collation_sha256: Optional[str] = None
    intro_fact_sha256: Optional[str] = None
    volume_one_fact_sha256: Optional[str] = None
    source_assignment_conflicts: Optional[List[HeluoMonthAssignmentConflict]] = None
    source_consensus_match: Optional[bool] = Field(
        default=None,
        description="逐阶段两处来源对本月匹配结论的三值或；不是比较两个完整方法的deTime是否相同。缺号或阶段分歧保留null。",
    )
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    collation_version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    collation_sha256: Optional[str] = None
    review_status: Optional[str] = None
    reviewed_hexagram_introductions: Optional[int] = Field(default=None, ge=0, le=64)
    explicit_assigned_months: Optional[int] = Field(default=None, ge=0, le=64)
    additional_month_clauses: Optional[int] = Field(default=None, ge=0)
    registered_natal_najia_clauses: Optional[int] = Field(default=None, ge=0, le=64)
    birth_month_branch: Optional[str] = None
    birth_month_number: Optional[int] = Field(default=None, ge=1, le=12)
    month_number_policy: Optional[str] = None
    phases: Optional[List[HeluoAssignedMonth]] = None
    complete_assessment: Optional[Literal[False]] = None
    scope: Optional[str] = None
    unresolved: Optional[List[str]] = None


class HeluoBodyRelation(PartialOutput):
    body_id: Optional[str] = None
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    kind: Optional[Literal["lower", "lower_nuclear", "upper_nuclear", "upper"]] = None
    line_positions: Optional[List[Annotated[int, Field(ge=1, le=6)]]] = None
    trigram: Optional[str] = None
    element: Optional[Literal["金", "木", "水", "火", "土"]] = None
    relation: Optional[
        Literal[
            "same_element",
            "body_generates_nayin",
            "nayin_generates_body",
            "body_controls_nayin",
            "nayin_controls_body",
        ]
    ] = None
    yuanqi_kinds: Optional[List[Literal["tian", "di"]]] = None


class HeluoGeneratingQi(PartialOutput):
    source_pdf_page: Optional[int] = None
    direction: Optional[Literal["body_generates_nayin"]] = None
    body_ids: Optional[List[str]] = None
    relation_present: Optional[bool] = None
    yuanqi_absence_required: Optional[Literal[True]] = None
    condition_match: Optional[bool] = None


class HeluoMutualGeneration(PartialOutput):
    source_pdf_page: Optional[int] = None
    body_generates_nayin_ids: Optional[List[str]] = None
    nayin_generates_body_ids: Optional[List[str]] = None
    relation_present: Optional[bool] = None
    scope: Optional[str] = None


class HeluoBodyEvidence(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    assessment_status: Optional[str] = None
    year_ganzhi: Optional[str] = None
    nayin: Optional[str] = None
    nayin_element: Optional[Literal["金", "木", "水", "火", "土"]] = None
    nayin_policy: Optional[str] = None
    body_scope_policy: Optional[str] = None
    bodies: Optional[List[HeluoBodyRelation]] = None
    same_element_body_ids: Optional[List[str]] = None
    yuanqi_absent: Optional[bool] = None
    generating_qi: Optional[HeluoGeneratingQi] = None
    mutual_generation: Optional[HeluoMutualGeneration] = None
    present: None = None
    complete_assessment: Optional[Literal[False]] = None
    review_status: Optional[str] = None
    unresolved: Optional[List[str]] = None


class HeluoDayStemMapping(PartialOutput):
    gua: Optional[str] = None
    present: Optional[bool] = None


class HeluoQiBody(PartialOutput):
    body_id: Optional[str] = None
    gua: Optional[str] = None
    kind: Optional[Literal["lower", "lower_nuclear", "upper_nuclear", "upper"]] = None
    line_positions: Optional[List[Annotated[int, Field(ge=1, le=6)]]] = None
    trigram: Optional[str] = None


class HeluoQiMatch(PartialOutput):
    trigrams: Optional[List[str]] = None
    direct_body_ids: Optional[List[str]] = None
    nuclear_body_ids: Optional[List[str]] = None
    present: Optional[bool] = None


class HeluoQiMatches(PartialOutput):
    yuan_tian: Optional[HeluoQiMatch] = None
    yuan_di: Optional[HeluoQiMatch] = None
    fan_yuan_tian: Optional[HeluoQiMatch] = None
    fan_yuan_di: Optional[HeluoQiMatch] = None
    huagong: Optional[HeluoQiMatch] = None
    fanhua: Optional[HeluoQiMatch] = None


class HeluoQiPhase(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    bodies: Optional[List[HeluoQiBody]] = None
    matches: Optional[HeluoQiMatches] = None


class HeluoQiTransition(PartialOutput):
    kind: Optional[
        Literal[
            "yuan_tian", "yuan_di", "fan_yuan_tian", "fan_yuan_di", "huagong", "fanhua"
        ]
    ] = None
    xian_present: Optional[bool] = None
    hou_present: Optional[bool] = None
    change: Optional[
        Literal["retained", "lost", "gained", "absent", "not_evaluated"]
    ] = None


class HeluoYuanqiOppositionCondition(PartialOutput):
    kind: Optional[Literal["tian", "di"]] = None
    yuan_trigram: Optional[str] = None
    fan_trigram: Optional[str] = None
    yuan_body_ids: Optional[List[str]] = None
    fan_body_ids: Optional[List[str]] = None
    yuan_absent: Optional[bool] = None
    fan_present: Optional[bool] = None
    condition_match: Optional[bool] = None
    direct_only_condition_match: Optional[bool] = None
    rescue_match: Literal[None] = None

    @model_validator(mode="after")
    def preserve_known_premises(self) -> "HeluoYuanqiOppositionCondition":
        if self.yuan_body_ids is not None and self.yuan_absent is not None:
            if self.yuan_absent != (not self.yuan_body_ids):
                raise ValueError("元气缺席须与实际卦体位置一致。")
        if self.fan_body_ids is not None and self.fan_present is not None:
            if self.fan_present != bool(self.fan_body_ids):
                raise ValueError("反候选命中须与实际卦体位置一致。")
        if all(
            v is not None
            for v in (self.yuan_absent, self.fan_present, self.condition_match)
        ):
            if self.condition_match != (self.yuan_absent and self.fan_present):
                raise ValueError("无正而有反式不能省略无正前提。")
        return self


class HeluoYuanqiOppositionPhase(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    conditions: Optional[List[HeluoYuanqiOppositionCondition]] = None


class HeluoYuanqiOpposition(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    year_context_literal: Optional[str] = None
    absence_literal: Optional[str] = None
    rescue_literal: Optional[str] = None
    collation_sha256: Optional[str] = None
    content_sha256: Optional[str] = None
    year_ganzhi: Optional[str] = None
    body_scope_policy: Optional[str] = None
    direct_only_policy: Optional[str] = None
    phases: Optional[List[HeluoYuanqiOppositionPhase]] = None
    full_rescue_assessment: Optional[Literal[False]] = None
    unresolved: Optional[List[str]] = None
    scope: Optional[str] = None


class HeluoPhaseQi(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    candidate_basis: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    fanhua_rule_ids: Optional[List[str]] = None
    phases: Optional[List[HeluoQiPhase]] = None
    transitions: Optional[List[HeluoQiTransition]] = None
    yuanqi_opposition: Optional[HeluoYuanqiOpposition] = None
    complete_assessment: Optional[Literal[False]] = None
    scope: Optional[str] = None
    unresolved: Optional[List[str]] = None


class HeluoYuantangPlacement(PartialOutput):
    rule_id: Optional[str] = None
    hour_zhi: Optional[str] = None
    hour_half: Optional[Literal["yang", "yin"]] = None
    hour_index: Optional[int] = Field(default=None, ge=1, le=6)
    matching_positions: Optional[List[int]] = None
    other_positions: Optional[List[int]] = None
    slot_positions: Optional[List[int]] = None
    selected_pos: Optional[int] = Field(default=None, ge=1, le=6)
    pure_direction: Optional[Literal["ascending", "descending"]] = None
    source_pdf_pages: Optional[List[int]] = None


class HeluoHalfYearCounterfactual(PartialOutput):
    yang_ling: Optional[bool] = None
    xian_yuan: Optional[int] = Field(default=None, ge=1, le=6)
    hou_name: Optional[str] = None
    hou_yuan: Optional[int] = Field(default=None, ge=1, le=6)
    hou_lines: Optional[List[int]] = None


class HeluoHalfYearResolution(PartialOutput):
    value: Optional[bool] = None
    basis: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    candidate_values: Optional[List[bool]] = None
    yuantang_depends_on_half_year: Optional[bool] = None
    houtian_depends_on_half_year: Optional[bool] = None
    counterfactuals: Optional[List[HeluoHalfYearCounterfactual]] = None
    result_selection: Optional[
        Literal["resolved_half_year", "invariant_under_both_halves"]
    ] = None


class HeluoYuantangDerivation(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    gender: Optional[Literal["男", "女"]] = None
    half_year: Optional[HeluoHalfYearResolution] = None
    placement: Optional[HeluoYuantangPlacement] = None
    houtian_transform: Optional[Dict[str, JsonValue]] = None
    scope: Optional[str] = None


class HeluoRulerMinisterSeat(PartialOutput):
    source_pdf_page: Optional[int] = None
    positions: Optional[List[int]] = None
    match: Optional[bool] = None
    scope: Optional[str] = None


class HeluoZhongzong(PartialOutput):
    source_pdf_page: Optional[int] = None
    yang_count: Optional[int] = Field(default=None, ge=0, le=6)
    yin_count: Optional[int] = Field(default=None, ge=0, le=6)
    minority_polarity: Optional[Literal["yin", "yang"]] = None
    minority_pos: Optional[int] = Field(default=None, ge=1, le=6)
    match: Optional[bool] = None


class HeluoSourceYouyuan(PartialOutput):
    rule_id: Optional[Literal["wenming_yin_yuantang_yang_corresponding_v1"]] = None
    source_pdf_page: Optional[int] = None
    selected_pos: Optional[int] = Field(default=None, ge=1, le=6)
    selected_yang: Optional[bool] = None
    corresponding_pos: Optional[int] = Field(default=None, ge=1, le=6)
    corresponding_yang: Optional[bool] = None
    polarity_opposed: Optional[bool] = None
    required_selected_yang: Optional[Literal[False]] = None
    required_corresponding_yang: Optional[Literal[True]] = None
    clause_match: Optional[bool] = None
    scope: Optional[
        Literal[
            "named_primary_yin_line_yang_corresponding_clause_only; not_full_ten_condition_verdict"
        ]
    ] = None

    @model_validator(mode="after")
    def coherent_correspondence_and_clause(self) -> "HeluoSourceYouyuan":
        if self.selected_pos is not None and self.corresponding_pos is not None:
            expected = (
                self.selected_pos + 3
                if self.selected_pos <= 3
                else self.selected_pos - 3
            )
            if self.corresponding_pos != expected:
                raise ValueError("有援原句须使用同卦实际对应爻位。")
        if self.selected_yang is not None and self.corresponding_yang is not None:
            if self.polarity_opposed is not None and self.polarity_opposed != (
                self.selected_yang != self.corresponding_yang
            ):
                raise ValueError("相应阴阳事实不一致。")
            if self.clause_match is not None and self.clause_match != (
                not self.selected_yang and self.corresponding_yang
            ):
                raise ValueError("有援所选主本原句不能用通用相应或反向相应替代。")
        return self


class HeluoLineConditionRow(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    lines: Optional[List[Annotated[int, Field(ge=0, le=1)]]] = None
    pos: Optional[int] = Field(default=None, ge=1, le=6)
    yang: Optional[bool] = None
    position_polarity_match: Optional[bool] = None
    position_preference_order: Optional[int] = Field(default=None, ge=1, le=4)
    ruler_minister_seat: Optional[HeluoRulerMinisterSeat] = None
    zhongzong: Optional[HeluoZhongzong] = None
    source_youyuan: Optional[HeluoSourceYouyuan] = None

    @model_validator(mode="after")
    def coherent_selected_phase_support(self) -> "HeluoLineConditionRow":
        aid = self.source_youyuan
        if aid is None:
            return self
        if (
            self.pos is not None
            and aid.selected_pos is not None
            and self.pos != aid.selected_pos
        ):
            raise ValueError("有援原句的元堂须属于本阶段。")
        if (
            self.yang is not None
            and aid.selected_yang is not None
            and self.yang != aid.selected_yang
        ):
            raise ValueError("有援原句的元堂阴阳须属于本阶段。")
        if self.lines is not None:
            if len(self.lines) != 6:
                raise ValueError("有援原句需要同卦六爻事实。")
            for pos, yang in [
                (aid.selected_pos, aid.selected_yang),
                (aid.corresponding_pos, aid.corresponding_yang),
            ]:
                if (
                    pos is not None
                    and yang is not None
                    and bool(self.lines[pos - 1]) != yang
                ):
                    raise ValueError("有援原句的爻阴阳与本阶段六爻不一致。")
        return self


class HeluoSourceDangwei(PartialOutput):
    source_pdf_page: Optional[int] = None
    literal_condition: Optional[str] = None
    status: Optional[Literal["yinyue_definition_pending"]] = None
    month_polarity: None = None
    match: None = None
    line_index_parity_substituted: Optional[Literal[False]] = None
    solstice_half_year_substituted: Optional[Literal[False]] = None


class HeluoLineConditions(PartialOutput):
    ruleset_id: Optional[str] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    collation_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    literal_clauses: Optional[Dict[str, Dict[str, JsonValue]]] = None
    position_preference_policy: Optional[str] = None
    phases: Optional[List[HeluoLineConditionRow]] = None
    source_dangwei: Optional[HeluoSourceDangwei] = None
    complete_assessment: Optional[Literal[False]] = None
    ten_condition_score: None = None
    scope: Optional[str] = None
    constraints: Optional[List[str]] = None


class HeluoStructureRecord(PartialOutput):
    kind: Optional[
        Literal[
            "lower",
            "upper",
            "lower_reversed",
            "upper_reversed",
            "upper_nuclear",
            "lower_nuclear",
            "third_to_top",
            "reverse_then_third_to_top",
        ]
    ] = None
    arity: Optional[Literal[3, 6]] = None
    original_positions: Optional[List[Annotated[int, Field(ge=1, le=6)]]] = None
    lines: Optional[List[Annotated[int, Field(ge=0, le=1)]]] = None
    name: Optional[str] = None

    @model_validator(mode="after")
    def coherent_operator(self) -> "HeluoStructureRecord":
        from fatebridge.core.heluo_structure import OPERATORS, _name

        if self.kind is not None:
            expected = dict(OPERATORS)[self.kind]
            if self.arity is not None and self.arity != len(expected):
                raise ValueError("卦体结构的三爻体与六爻卦不能混用。")
            if self.original_positions is not None and self.original_positions != list(
                expected
            ):
                raise ValueError("卦体结构须保留实际取爻次序。")
        if self.lines is not None:
            if len(self.lines) not in (3, 6) or (
                self.arity is not None and len(self.lines) != self.arity
            ):
                raise ValueError("卦体结构爻数不一致。")
            if self.name is not None and _name(self.lines) != self.name:
                raise ValueError("卦体结构名称与爻形不一致。")
        return self


class HeluoWholeReversal(PartialOutput):
    original_positions: Optional[List[Annotated[int, Field(ge=1, le=6)]]] = None
    lines: Optional[List[Annotated[int, Field(ge=0, le=1)]]] = None
    name: Optional[str] = None

    @model_validator(mode="after")
    def coherent_reversal(self) -> "HeluoWholeReversal":
        from fatebridge.core.heluo_structure import _name

        if self.original_positions is not None and self.original_positions != [
            6,
            5,
            4,
            3,
            2,
            1,
        ]:
            raise ValueError("全卦倒序须保留六爻次序。")
        if self.lines is not None:
            if len(self.lines) != 6 or (
                self.name is not None and _name(self.lines) != self.name
            ):
                raise ValueError("全卦倒序名称与六爻不一致。")
        return self


class HeluoStructurePhase(PartialOutput):
    phase: Optional[Literal["xian", "hou"]] = None
    gua: Optional[str] = None
    input_lines: Optional[List[Annotated[int, Field(ge=0, le=1)]]] = None
    records: Optional[List[HeluoStructureRecord]] = None
    record_count: Optional[Literal[8]] = None
    whole_reversal: Optional[HeluoWholeReversal] = None
    literal_case_match: Optional[bool] = None
    literal_names_reproduced: Optional[bool] = None
    source_application: Optional[
        Literal[
            "named_jian_paragraph",
            "permutation_derivation; not_this_hexagrams_literal_source_example",
        ]
    ] = None

    @model_validator(mode="after")
    def coherent_phase(self) -> "HeluoStructurePhase":
        from fatebridge.core.heluo_structure import OPERATORS, _name

        if self.gua is not None and self.literal_case_match is not None:
            if self.literal_case_match != (self.gua == "風山漸"):
                raise ValueError("不能把其他卦标为所核渐卦原例。")
        if (
            self.literal_case_match is False
            and self.literal_names_reproduced is not None
        ):
            raise ValueError("其他卦的推演不冒充新增原例核对。")
        if self.literal_case_match is not None and self.source_application is not None:
            expected_basis = (
                "named_jian_paragraph"
                if self.literal_case_match
                else "permutation_derivation; not_this_hexagrams_literal_source_example"
            )
            if self.source_application != expected_basis:
                raise ValueError("原例与算子推演的来源标签不一致。")
        if self.records is not None:
            if len(self.records) != 8:
                raise ValueError("所列结构应保留八条记录，包括重复名称。")
            for row, (kind, _) in zip(self.records, OPERATORS):
                if row.kind is not None and row.kind != kind:
                    raise ValueError("结构记录次序不一致。")
            if (
                self.literal_case_match is True
                and self.literal_names_reproduced is not None
                and all(row.name is not None for row in self.records)
                and self.whole_reversal is not None
                and self.whole_reversal.name is not None
            ):
                reproduced = [row.name for row in self.records] == [
                    "艮",
                    "巽",
                    "震",
                    "兌",
                    "離",
                    "坎",
                    "天地否",
                    "地天泰",
                ] and self.whole_reversal.name == "雷澤歸妹"
                if self.literal_names_reproduced != reproduced:
                    raise ValueError("原例复现标记与实际结构名称不一致。")
        if self.input_lines is not None:
            if len(self.input_lines) != 6 or (
                self.gua is not None and _name(self.input_lines) != self.gua
            ):
                raise ValueError("同阶段卦名与输入六爻不一致。")
            for row in self.records or []:
                if row.original_positions is not None and row.lines is not None:
                    if row.lines != [
                        self.input_lines[p - 1] for p in row.original_positions
                    ]:
                        raise ValueError("结构记录不能借用另一阶段爻形或翻转阴阳。")
            if (
                self.whole_reversal is not None
                and self.whole_reversal.lines is not None
            ):
                if self.whole_reversal.lines != self.input_lines[::-1]:
                    raise ValueError("全卦倒序不能变爻。")
        return self


class HeluoFiveMingTerminology(PartialOutput):
    symbol_readings: Optional[Dict[str, str]] = None
    source_pdf_pages: Optional[List[int]] = None
    selected_pillar: None = None
    nayin_substituted: Optional[Literal[False]] = None
    scope: Optional[
        Literal["literal_symbol_lists_only; no_global_person_element_selection"]
    ] = None


class HeluoBodyStructure(PartialOutput):
    ruleset_id: Optional[Literal["heluo_wenming_jian_structure_v1"]] = None
    version: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    calculation_source_pdf_pages: Optional[List[int]] = None
    collation_sha256: Optional[str] = None
    review_status: Optional[str] = None
    wording_variants: Optional[List[Dict[str, str]]] = None
    phases: Optional[List[HeluoStructurePhase]] = None
    five_ming_terminology: Optional[HeluoFiveMingTerminology] = None
    scope: Optional[str] = None
    complete_futi_assessment: Optional[Literal[False]] = None
    complete_assessment: Optional[Literal[False]] = None
    constraints: Optional[List[str]] = None


class HeluoJudge(PartialOutput):
    assessment_status: Optional[str] = None
    xie_policy: Optional[str] = None
    deSheng_policy: Optional[str] = None
    deTime_policy: Optional[str] = None
    deTi_policy: Optional[str] = None
    najia: Optional[List[HeluoNajiaAssessment]] = None
    deSheng: Optional[bool] = None
    deTime: Optional[bool] = None
    month_affinity: Optional[HeluoMonthAffinity] = None
    xie: Optional[bool] = None
    yuan: Optional[Dict[str, JsonValue]] = None
    fanYuan: Optional[Dict[str, JsonValue]] = None
    fanYuan_policy: Optional[str] = None
    huagong: Optional[Dict[str, JsonValue]] = None
    fanhua: Optional[Dict[str, JsonValue]] = None
    qi_phases: Optional[HeluoPhaseQi] = None
    deTi: Optional[HeluoBodyEvidence] = None
    day_stem_mapping: Optional[HeluoDayStemMapping] = None
    erShu: Optional[Dict[str, JsonValue]] = None
    seasonal_numbers: Optional[HeluoSeasonalNumbers] = None
    yuanTang: Optional[Dict[str, JsonValue]] = None
    line_conditions: Optional[HeluoLineConditions] = None
    body_structure: Optional[HeluoBodyStructure] = None


class HeluoTimingRow(PartialOutput):
    gua: Optional[str] = None
    lines: Optional[List[int]] = None
    pos: Optional[int] = None
    changed_pos: Optional[int] = None
    input_lines: Optional[List[int]] = None
    ordinal_in_period: Optional[int] = None
    age: Optional[int] = None
    year_label: Optional[int] = None
    ganzhi: Optional[str] = None
    phase: Optional[str] = None
    period_index: Optional[int] = None
    period_pos: Optional[int] = None
    period_start_yang: Optional[bool] = None
    month_index: Optional[int] = None
    parent_month_index: Optional[int] = None
    rule_id: Optional[str] = None
    block_index: Optional[int] = None
    day_index: Optional[int] = None


def _boolean_without_numeric_coercion(value: Any) -> Any:
    if type(value) is not bool:
        raise ValueError("布尔事实不能用0/1或字符串替代。")
    return value


def _not_a_boolean_number(value: Any) -> Any:
    if type(value) is bool:
        raise ValueError("刻数不能用布尔替代。")
    return value


_KnownTrue = Annotated[
    Literal[True], BeforeValidator(_boolean_without_numeric_coercion)
]
_KnownFalse = Annotated[
    Literal[False], BeforeValidator(_boolean_without_numeric_coercion)
]


class HeluoTimingYearContext(PartialOutput):
    cycle_year: Optional[int] = None
    birth_ganzhi: Optional[str] = None
    expected_ganzhi: Optional[str] = None
    matches: Optional[_KnownTrue] = None
    basis: Optional[
        Literal["selected_pillar_year_label; not_civil_birth_year_substitution"]
    ] = None

    @model_validator(mode="after")
    def consistent_year(self) -> "HeluoTimingYearContext":
        from fatebridge.core.heluo_timing import CYCLE

        for gz in (self.birth_ganzhi, self.expected_ganzhi):
            if gz is not None and gz not in CYCLE:
                raise ValueError("岁运年上下文须用有效六十甲子。")
            if (
                gz is not None
                and self.cycle_year is not None
                and gz != CYCLE[(self.cycle_year - 4) % 60]
            ):
                raise ValueError("岁运年标签与年柱不一致。")
        if (
            self.birth_ganzhi is not None
            and self.expected_ganzhi is not None
            and self.birth_ganzhi != self.expected_ganzhi
        ):
            raise ValueError("岁运实际与预期年柱不一致。")
        return self


class HeluoClockRatio(PartialOutput):
    numerator: Optional[int] = None
    denominator: Optional[int] = Field(default=None, gt=0)


class HeluoClockBranch(PartialOutput):
    branch: Optional[
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    ] = None
    length_ke: Optional[Literal[8, 9]] = None

    @model_validator(mode="after")
    def source_length(self) -> "HeluoClockBranch":
        if (
            self.branch is not None
            and self.length_ke is not None
            and self.length_ke != (9 if self.branch in "寅申巳亥" else 8)
        ):
            raise ValueError("卷一九刻支组不能换成等长或其他支组。")
        return self


class HeluoClockDailyExtra(PartialOutput):
    ke: Optional[Annotated[Literal[1], BeforeValidator(_not_a_boolean_number)]] = None
    fen: Optional[Literal[7]] = None
    fen_per_ke: None = None


class HeluoClockAnnualExtra(PartialOutput):
    nominal_days: Optional[Literal[360]] = None
    printed_days: Optional[Literal[365]] = None
    monthly_extra_shi: Optional[Literal[5]] = None
    months: Optional[Literal[12]] = None
    annual_extra_shi: Optional[Literal[60]] = None


class HeluoClockProjection(PartialOutput):
    extra_ke_per_nominal_day: Optional[HeluoClockRatio] = None
    fen_per_ke_required_for_numeric_closure: Optional[HeluoClockRatio] = None
    derived_only: Optional[_KnownTrue] = None
    source_fen_scale_verified: Optional[_KnownFalse] = None

    @model_validator(mode="after")
    def only_a_conditional_projection(self) -> "HeluoClockProjection":
        for value, n, d in (
            (self.extra_ke_per_nominal_day, 25, 18),
            (self.fen_per_ke_required_for_numeric_closure, 18, 1),
        ):
            if (
                value is not None
                and value.numerator is not None
                and value.denominator is not None
                and (value.numerator, value.denominator) != (n, d)
            ):
                raise ValueError("等时条件推算与所列年余量不一致。")
        return self


class HeluoClockBranchShift(PartialOutput):
    year_blocks: Optional[Literal[60]] = None
    extra_shi: Optional[Literal[60]] = None
    extra_ke: Optional[Literal[500]] = None
    total_source_days: Optional[HeluoClockRatio] = None
    origin_basis: Optional[
        Literal["full_cycles_total_invariant; no_physical_origin_selected"]
    ] = None
    branch_start_only: Optional[_KnownTrue] = None
    derived_only: Optional[_KnownTrue] = None
    source_fen_scale_selected: Optional[_KnownFalse] = None
    daily_internal_distribution_resolved: Optional[_KnownFalse] = None

    @model_validator(mode="after")
    def conditional_total(self) -> "HeluoClockBranchShift":
        value = self.total_source_days
        if (
            value is not None
            and value.numerator is not None
            and value.denominator is not None
            and (value.numerator, value.denominator) != (365, 1)
        ):
            raise ValueError("六十支移位的源刻总量与所列大数年不一致。")
        return self


class HeluoSourceClock(PartialOutput):
    ruleset_id: Optional[Literal["heluo_wenming_baike_clock_v1"]] = None
    version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    review_status: Optional[str] = None
    scope: Optional[str] = None
    loaded_sha256: Optional[str] = None
    day_ke: Optional[Literal[100]] = None
    base_ke: Optional[Literal[96]] = None
    extra_ke: Optional[Literal[4]] = None
    branch_lengths: Optional[List[HeluoClockBranch]] = None
    extra_branches_in_printed_order: Optional[List[str]] = None
    physical_origin_branch: None = None
    daily_extra_literal: Optional[HeluoClockDailyExtra] = None
    annual_extra_literal: Optional[HeluoClockAnnualExtra] = None
    branch_shift_projection: Optional[HeluoClockBranchShift] = None
    equal_shi_projection: Optional[HeluoClockProjection] = None
    physical_clock_applied: Optional[_KnownFalse] = None
    calendar_mapping_complete: Optional[_KnownFalse] = None
    constraints: Optional[List[str]] = None

    @model_validator(mode="after")
    def source_counts_and_unresolved_origin(self) -> "HeluoSourceClock":
        if (
            self.extra_branches_in_printed_order is not None
            and self.extra_branches_in_printed_order != ["寅", "申", "巳", "亥"]
        ):
            raise ValueError("应保留原印寅申巳亥组及次序。")
        if self.branch_lengths is not None:
            if len(self.branch_lengths) != 12:
                raise ValueError("百刻循环须保留十二支。")
            if all(b.branch is not None for b in self.branch_lengths) and [
                b.branch for b in self.branch_lengths
            ] != list("子丑寅卯辰巳午未申酉戌亥"):
                raise ValueError("展示用循环支序不能混换。")
            if (
                all(b.length_ke is not None for b in self.branch_lengths)
                and sum(
                    b.length_ke for b in self.branch_lengths if b.length_ke is not None
                )
                != 100
            ):
                raise ValueError("十二支原刻总数须为一百。")
        return self


class HeluoTiming(PartialOutput):
    year_context: Optional[HeluoTimingYearContext] = None
    source_clock: Optional[HeluoSourceClock] = None
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_pdf_sha256: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    scope: Optional[str] = None
    calendar_policy: Optional[Dict[str, str]] = None
    annual_rows: Optional[List[HeluoTimingRow]] = None
    selected_annual: Optional[HeluoTimingRow] = None
    monthly_rows: Optional[List[HeluoTimingRow]] = None
    selected_month: Optional[HeluoTimingRow] = None
    daily_template: Optional[List[HeluoTimingRow]] = None
    selected_day: Optional[HeluoTimingRow] = None
    selected_texts: Optional[List[Dict[str, JsonValue]]] = None
    prediction_validation: Optional[str] = None
