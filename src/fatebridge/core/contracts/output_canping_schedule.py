"""Projection-compatible source and date-policy receipts for Canping schedules."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.numerology.canping_schedule_basis import (
    APPLIED,
    LEGACY,
    SUMMARIES,
    clause_role,
    clock_policy_for_rules,
    date_mapping_statement,
    reading_source_citations,
    source_readings,
)


def _exact_false(value: object) -> Literal[False]:
    if value is not False:
        raise ValueError("未完成的原典／效验状态不能提升或以0代替false。")
    return value


_KnownFalse = Annotated[Literal[False], BeforeValidator(_exact_false)]
_Profile = Literal["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
_ClockPolicy = Literal[
    "explicit_fixed_offset_assumption; no_regional_future_rules",
    "pinned_regional_rules; subject_to_future_legislation",
]
_ClauseRole = Literal[
    "applied_rule",
    "supplementary_ziping_background",
    "source_context",
    "comparison_not_applied",
]


class CanpingScheduleSource(PartialOutput):
    title: str | None = None
    edition: str | None = None


class CanpingReadingCitation(PartialOutput):
    source_id: Literal["heluo_najda", "sanming_nlc"] | None = None
    pdf_pages: list[int] | None = None
    roles: list[_ClauseRole] | None = None

    @model_validator(mode="after")
    def coherent_citation(self) -> "CanpingReadingCitation":
        if self.source_id is None:
            return self

        data = source_readings()
        pages = sorted(
            {c["pdf_page"] for c in data["clauses"] if c["source_id"] == self.source_id}
        )
        if self.pdf_pages is not None and self.pdf_pages != pages:
            raise ValueError("阅读引文的PDF页码不能跨书替换。")
        possible_roles = [
            next(
                c["roles"]
                for c in reading_source_citations(p)
                if c["source_id"] == self.source_id
            )
            for p in APPLIED
        ]
        if self.roles is not None and self.roles not in possible_roles:
            raise ValueError("阅读引文角色未登记。")
        return self


class CanpingReadingContext(PartialOutput):
    profile_id: _Profile | None = None
    future_clock_policy: _ClockPolicy | None = None
    timezone_spec: str | None = None
    date_mapping_statement: str | None = None
    source_citations: list[CanpingReadingCitation] | None = None

    @model_validator(mode="after")
    def coherent_reading_context(self) -> "CanpingReadingContext":

        if self.profile_id is not None:
            if self.date_mapping_statement is not None and (
                self.profile_id == LEGACY
                or (
                    self.future_clock_policy is not None
                    and self.timezone_spec is not None
                )
            ):
                expected = date_mapping_statement(
                    self.profile_id, self.future_clock_policy, self.timezone_spec
                )
                if self.date_mapping_statement != expected:
                    raise ValueError("阅读日期条件与所选方法及钟制不符。")
            if self.source_citations is not None:
                expected_by_source = {
                    c["source_id"]: c for c in reading_source_citations(self.profile_id)
                }
                for c in self.source_citations:
                    if c.source_id is not None and c.roles is not None:
                        if c.roles != expected_by_source[c.source_id]["roles"]:
                            raise ValueError("阅读引文角色与所选方法不符。")
        if self.source_citations is not None:
            ids = [
                c.source_id for c in self.source_citations if c.source_id is not None
            ]
            if len(ids) != len(set(ids)):
                raise ValueError("阅读引文不能重复来源。")
        return self


class CanpingScheduleClause(PartialOutput):
    id: str | None = None
    source_id: Literal["heluo_najda", "sanming_nlc"] | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: str | None = None
    locator: str | None = None
    text: str | None = None
    kind: str | None = None
    role: (
        Literal[
            "applied_rule",
            "supplementary_ziping_background",
            "source_context",
            "comparison_not_applied",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def coherent_source_excerpt(self) -> "CanpingScheduleClause":
        if self.id is None:
            return self

        entry = next(
            (x for x in source_readings()["clauses"] if x["id"] == self.id), None
        )
        if entry is None:
            raise ValueError("未登记的配运原句。")
        for key in ("source_id", "pdf_page", "printed_page", "locator", "text", "kind"):
            value = getattr(self, key)
            if value is not None and value != entry[key]:
                raise ValueError("配运原句及其出处不能互换或改写。")
        return self


class CanpingScheduleBasis(PartialOutput):
    policy_id: Literal["canping_schedule_source_mapping_v1"] | None = None
    profile_id: _Profile | None = None
    corpus_id: Literal["canping_schedule_clauses_v1"] | None = None
    corpus_version: str | None = None
    review_status: str | None = None
    sources: dict[str, CanpingScheduleSource] | None = None
    clauses: list[CanpingScheduleClause] | None = None
    applied_clause_ids: list[str] | None = None
    bridge_step_years: Literal[10] | None = None
    target_excerpt_ten_year_step_explicitly_collated: _KnownFalse | None = None
    has_actual_date_mapping: bool | None = None
    datetime_mapping_is_original_source_formula: _KnownFalse | None = None
    calendar_mapping: dict[str, str] | None = None
    age_conversion_result: dict[str, JsonValue] | None = None
    actual_start_at: str | None = None
    timezone_spec: str | None = None
    timezone_rules: dict[str, JsonValue] | None = None
    future_clock_policy: (
        Literal[
            "explicit_fixed_offset_assumption; no_regional_future_rules",
            "pinned_regional_rules; subject_to_future_legislation",
        ]
        | None
    ) = None
    reading_context: CanpingReadingContext | None = None
    summary: str | None = None

    @model_validator(mode="after")
    def coherent_selected_policy(self) -> "CanpingScheduleBasis":

        data = source_readings()
        for field, expected in (
            ("corpus_version", data["version"]),
            ("review_status", data["review_status"]),
        ):
            value = getattr(self, field)
            if value is not None and value != expected:
                raise ValueError("配运来源身份与所选版本不一致。")
        if self.summary is not None:
            possible = (
                [SUMMARIES[self.profile_id]]
                if self.profile_id is not None
                else list(SUMMARIES.values())
            )
            if self.summary not in possible:
                raise ValueError("配运摘要与实际方法或已核范围不一致。")
        if self.sources is not None:
            for source_id, source in self.sources.items():
                expected_source = data["sources"].get(source_id)
                if expected_source is None:
                    raise ValueError("未登记的配运书目来源。")
                for key, expected in expected_source.items():
                    if (
                        key in source.model_fields_set
                        and getattr(source, key) != expected
                    ):
                        raise ValueError("配运书名、版本或书影身份不能互换。")
        if self.timezone_rules is not None:
            expected_policy = clock_policy_for_rules(self.timezone_rules)
            if (
                self.future_clock_policy is not None
                and expected_policy is not None
                and self.future_clock_policy != expected_policy
            ):
                raise ValueError("未来钟面政策与本次时区规则不一致。")
        if self.reading_context is not None:
            for field in ("profile_id", "future_clock_policy", "timezone_spec"):
                outer = getattr(self, field)
                inner = getattr(self.reading_context, field)
                if outer is not None and inner is not None and outer != inner:
                    raise ValueError("阅读上下文与同次配运回执不符。")

        if self.profile_id is not None:
            if (
                self.has_actual_date_mapping is not None
                and self.has_actual_date_mapping
                != (self.profile_id != "legacy_minggong_v1")
            ):
                raise ValueError("旧命宫排法没有已核实际日期映射。")
            if (
                self.applied_clause_ids is not None
                and self.applied_clause_ids != APPLIED[self.profile_id]
            ):
                raise ValueError("实际采用的配运规则与所选方法不一致。")
            if self.clauses is not None:
                for c in self.clauses:
                    if c.id is not None and c.role is not None:
                        entry = next(x for x in data["clauses"] if x["id"] == c.id)
                        if c.role != clause_role(self.profile_id, entry):
                            raise ValueError("配运原句的本次角色与实际方法不一致。")
        if self.clauses is not None:
            ids = [c.id for c in self.clauses if c.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("配运原句不能重复计数。")
        return self
