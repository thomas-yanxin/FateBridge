"""Numerology birth, clock and pillar evidence."""

from datetime import time
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, FiniteFloat, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.numerology.numerology_clock_input import (
    CLOCK_INPUT_SCOPE,
    clock_input_representation,
)
from fatebridge.core.numerology.numerology_clock_policy import require_birth_clock
from fatebridge.core.numerology.numerology_inputs import normalize_numerology_utc_offset
from fatebridge.core.numerology.numerology_pillars import (
    CYCLE,
    GAN,
    LINK_GROUPS,
    LINK_HEADS,
    ZHI,
)
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.iso_clock import parse_iso_datetime


class NumerologyRuleset(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_status: str | None = None
    authorship_status: str | None = None


class NumerologyValidation(PartialOutput):
    calendar: str | None = None
    classical: str | None = None
    interpretation: str | None = None
    prediction: str | None = None


class NumerologyRuleTrace(PartialOutput):
    rule_id: str | None = None
    source_section: str | None = None
    fact_path: str | None = None
    facts: dict[str, JsonValue] | None = None


class NumerologyCalendarPolicy(PartialOutput):
    input_calendar: Literal["proleptic_gregorian"] | None = None
    automatic_reform_cutover: Literal[False] | None = None
    historical_lunar_date_conversion: Literal[False] | None = None
    historical_official_calendar_reconstruction: Literal[False] | None = None


def _uncertified_clock_precision(value: object) -> Literal[False]:
    if value is not False:
        raise ValueError("钟时文本分量不能认证出生记录精度。")
    return value


class NumerologyClockInput(PartialOutput):
    policy_id: Literal["numerology_clock_text_provenance_v1"] | None = None
    supplied_text: str | None = None
    normalized_clock: str | None = None
    supplied_components: (
        list[Literal["hour", "minute", "second", "fractional_second"]] | None
    ) = None
    omitted_components: list[Literal["second", "fractional_second"]] | None = None
    fractional_digits: int | None = Field(default=None, ge=0, le=6)
    calculation_defaults: dict[Literal["second", "microsecond"], int] | None = None
    uncertainty_interval: None = None
    observed_precision_certified: (
        Annotated[Literal[False], BeforeValidator(_uncertified_clock_precision)] | None
    ) = None
    scope: str | None = None
    statement: str | None = None

    @model_validator(mode="after")
    def coherent_supplied_components(self) -> "NumerologyClockInput":

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
    policy_id: str | None = None
    mode: Literal["civil", "apparent_solar"] | None = None
    calendar_policy: NumerologyCalendarPolicy | None = None
    timezone_policy_id: str | None = None
    timezone_spec: str | None = None
    timezone_default_policy: str | None = None
    timezone_rules: dict[str, JsonValue] | None = None
    civil_utc_offset_seconds: (
        Annotated[int, Field(gt=-86400, lt=86400)]
        | Annotated[FiniteFloat, Field(gt=-86400, lt=86400)]
        | None
    ) = Field(
        default=None,
        description="Actual UTC offset in seconds, retaining fractional seconds at datetime microsecond resolution; integral offsets remain integers.",
    )
    civil_daylight_saving_seconds: int | None = None
    civil_datetime: str | None = None
    birth_instant_utc: str | None = None
    calculation_wall_clock: str | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    longitude_source: Literal["lon", "gps_lon"] | None = None
    longitude_used: bool | None = None
    longitude_selection_policy: str | None = None
    total_correction_minutes: float | None = None
    pillar_clock_policy: str | None = None
    precision_scope: str | None = None
    input_representation: NumerologyClockInput | None = None
    birth_utc_offset_policy_id: (
        Literal["numerology_confirmed_civil_offset_v1"] | None
    ) = None
    requested_utc_offset: str | None = None
    civil_utc_offset: str | None = None
    civil_fold: int | None = Field(default=None, ge=0, le=1)
    civil_time_ambiguous: bool | None = None
    offset_selection_scope: str | None = None

    @model_validator(mode="after")
    def coherent_selected_birth_offset(self) -> "NumerologyBirthClock":
        """Check present receipts, without needing siblings lost in projection.

        Revalidating a stored receipt against today's IANA rules would change
        its historical meaning. Compare its recorded offsets and UTC instant;
        the separately recorded TZif rules identify the rules used then.
        """

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
            actual = ZonedCalendar.from_isoformat(self.birth_instant_utc)
            if civil is not None and actual.utc != utc_calendar(civil):
                raise ValueError("出生民用时刻与UTC瞬间回执不一致。")
        if self.civil_time_ambiguous is False and self.civil_fold == 1:
            raise ValueError("非重复出生钟时不能标记第二次出现。")
        return self


class HeluoNajiaCollation(PartialOutput):
    ruleset_id: str | None = None
    version: str | None = None
    source_url: str | None = None
    review_status: str | None = None
    pure_trigram_tables: int | None = Field(default=None, ge=0, le=8)
    pure_table_assignment_slots: int | None = Field(default=None, ge=0, le=48)
    pure_table_borrowed_slots: int | None = Field(default=None, ge=0, le=12)
    directly_collated_hexagrams: int | None = Field(default=None, ge=0, le=64)
    other_hexagrams_not_individually_collated: int | None = Field(
        default=None, ge=0, le=64
    )
    direct_assignment_observations: int | None = Field(default=None, ge=0)
    borrowed_assignment_observations: int | None = Field(default=None, ge=0)
    source_pdf_pages: list[int] | None = None
    source_order_issues: list[dict[str, JsonValue]] | None = None
    unquantified_timing_najia_clauses: list[dict[str, JsonValue]] | None = None
    complete_assessment: Literal[False] | None = None
    scope: str | None = None


class NumerologyPillarLink(PartialOutput):
    target: Literal["month", "hour"] | None = None
    basis: Literal["year", "day"] | None = None
    basis_pillar: str | None = None
    basis_stem: str | None = None
    source_stem_group: str | None = None
    head_pillar: str | None = None
    branch_step: int | None = Field(default=None, ge=0, le=11)
    actual_pillar: str | None = None
    expected_pillar: str | None = None
    matches: bool | None = None

    @model_validator(mode="after")
    def coherent_stem_link(self) -> "NumerologyPillarLink":

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
    ruleset_id: Literal["heluo_volume7_pillar_links_v1"] | None = None
    version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    review_status: str | None = None
    authorship_status: str | None = None
    pillars: dict[str, str] | None = None
    links: list[NumerologyPillarLink] | None = None
    all_links_match: bool | None = None
    basis_policy: (
        Literal[
            "actual_selected_year_and_day_pillars; no_civil_year_or_unrolled_day_substitution"
        ]
        | None
    ) = None
    scope: str | None = None
    complete_calendar_assessment: Literal[False] | None = None
    constraint: str | None = None

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
    rulesets: list[NumerologyRuleset] | None = None
    corpus_status: str | None = None
    najia_collation: HeluoNajiaCollation | None = None
    yaoci_collation: dict[str, JsonValue] | None = None
    commentary_collation: dict[str, JsonValue] | None = None
    canping_text_collation: dict[str, JsonValue] | None = None
    validation_status: NumerologyValidation | None = None
    interpretation_constraints: list[str] | None = None
    unresolved_rules: list[str] | None = None
    selected_texts: list[dict[str, JsonValue]] | None = None
    rule_trace: list[NumerologyRuleTrace] | None = None
    birth_clock: NumerologyBirthClock | None = None
    pillar_links: NumerologyPillarLinks | None = None
