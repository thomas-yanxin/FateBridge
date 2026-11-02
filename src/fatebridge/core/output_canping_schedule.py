"""Projection-compatible source and date-policy receipts for Canping schedules."""

from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BeforeValidator, ConfigDict, Field, JsonValue, model_validator

from fatebridge.core.canping_scope_rendering import (
    ScopeRevision,
    registered_scope_digests,
    registered_scope_statements,
    scope_rendering_receipt,
    scope_rendering_schema,
    scope_statement_matches_receipt,
    scope_statement_schema,
)
from fatebridge.core.output_base import PartialOutput


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
    title: Optional[str] = None
    url: Optional[str] = None
    pdf_sha256: Optional[str] = None
    edition: Optional[str] = None


class CanpingReadingCitation(CanpingScheduleSource):
    source_id: Optional[Literal["heluo_najda", "sanming_nlc"]] = None
    pdf_pages: Optional[List[int]] = None
    roles: Optional[List[_ClauseRole]] = None

    @model_validator(mode="after")
    def coherent_citation(self) -> "CanpingReadingCitation":
        if self.source_id is None:
            return self
        from fatebridge.core.canping_schedule_basis import (
            APPLIED,
            reading_source_citations,
            source_readings,
        )

        data = source_readings()
        for field, expected in data["sources"][self.source_id].items():
            if field in self.model_fields_set and getattr(self, field) != expected:
                raise ValueError("阅读引文的书名、版本或书影身份与所核来源不符。")
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
    profile_id: Optional[_Profile] = None
    future_clock_policy: Optional[_ClockPolicy] = None
    timezone_spec: Optional[str] = None
    date_mapping_statement: Optional[str] = None
    source_citations: Optional[List[CanpingReadingCitation]] = None

    @model_validator(mode="after")
    def coherent_reading_context(self) -> "CanpingReadingContext":
        from fatebridge.core.canping_schedule_basis import (
            LEGACY,
            date_mapping_statement,
            reading_source_citations,
        )

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
    id: Optional[str] = None
    source_id: Optional[Literal["heluo_najda", "sanming_nlc"]] = None
    pdf_page: Optional[int] = Field(default=None, ge=1)
    printed_page: Optional[str] = None
    locator: Optional[str] = None
    text: Optional[str] = None
    kind: Optional[str] = None
    role: Optional[
        Literal[
            "applied_rule",
            "supplementary_ziping_background",
            "source_context",
            "comparison_not_applied",
        ]
    ] = None

    @model_validator(mode="after")
    def coherent_source_excerpt(self) -> "CanpingScheduleClause":
        if self.id is None:
            return self
        from fatebridge.core.canping_schedule_basis import source_readings

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


class CanpingScopeRendering(PartialOutput):
    """A software-text revision does not replace the original-book identity."""

    model_config = ConfigDict(json_schema_extra=scope_rendering_schema())

    policy_id: Optional[Literal["canping_scope_rendering_v1"]] = None
    revision: Optional[ScopeRevision] = None
    text_sha256: Optional[str] = Field(
        default=None,
        json_schema_extra={"enum": [*registered_scope_digests(), None]},
    )
    layer: Optional[Literal["software_explanatory_scope"]] = None

    @model_validator(mode="after")
    def coherent_revision(self) -> "CanpingScopeRendering":
        if self.text_sha256 is not None:
            if self.text_sha256 not in registered_scope_digests():
                raise ValueError("范围说明文字的内容身份未登记。")
            if self.revision is not None and self.text_sha256 != (
                scope_rendering_receipt(self.revision)["text_sha256"]
            ):
                raise ValueError("范围说明文字与其软件版本不一致。")
        return self


class CanpingScheduleBasis(PartialOutput):
    model_config = ConfigDict(json_schema_extra=scope_statement_schema())

    policy_id: Optional[Literal["canping_schedule_source_mapping_v1"]] = None
    profile_id: Optional[_Profile] = None
    corpus_id: Optional[Literal["canping_schedule_clauses_v1"]] = None
    corpus_version: Optional[str] = None
    source_content_sha256: Optional[str] = None
    source_file_sha256: Optional[str] = None
    review_status: Optional[str] = None
    sources: Optional[Dict[str, CanpingScheduleSource]] = None
    clauses: Optional[List[CanpingScheduleClause]] = None
    applied_clause_ids: Optional[List[str]] = None
    bridge_step_years: Optional[Literal[10]] = None
    target_excerpt_ten_year_step_explicitly_collated: Optional[_KnownFalse] = None
    has_actual_date_mapping: Optional[bool] = None
    datetime_mapping_is_original_source_formula: Optional[_KnownFalse] = None
    calendar_mapping: Optional[Dict[str, str]] = None
    age_conversion_result: Optional[Dict[str, JsonValue]] = None
    actual_start_at: Optional[str] = None
    timezone_spec: Optional[str] = None
    timezone_rules: Optional[Dict[str, JsonValue]] = None
    future_clock_policy: Optional[
        Literal[
            "explicit_fixed_offset_assumption; no_regional_future_rules",
            "pinned_regional_rules; subject_to_future_legislation",
        ]
    ] = None
    reading_context: Optional[CanpingReadingContext] = None
    summary: Optional[str] = None
    scope_statement: Optional[str] = Field(
        default=None,
        json_schema_extra={"enum": [*registered_scope_statements(), None]},
    )
    scope_rendering: Optional[CanpingScopeRendering] = None
    whole_book_alignment_established: Optional[_KnownFalse] = None
    real_world_efficacy_validated: Optional[_KnownFalse] = None

    @model_validator(mode="after")
    def coherent_selected_policy(self) -> "CanpingScheduleBasis":
        from fatebridge.core.canping_schedule_basis import (
            APPLIED,
            CONTENT_SHA256,
            SUMMARIES,
            clause_role,
            clock_policy_for_rules,
            source_readings,
        )

        data = source_readings()
        for field, expected in (
            ("corpus_version", data["version"]),
            ("source_file_sha256", data["_file_sha256"]),
            ("review_status", data["review_status"]),
        ):
            value = getattr(self, field)
            if value is not None and value != expected:
                raise ValueError("配运来源身份与所选版本不一致。")
        if self.scope_statement is not None:
            supplied = (
                self.scope_rendering.model_dump(
                    exclude_unset=True, include=set(CanpingScopeRendering.model_fields)
                )
                if self.scope_rendering is not None
                else {}
            )
            if not scope_statement_matches_receipt(self.scope_statement, supplied):
                raise ValueError("范围说明文字或其软件版本不一致。")
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
                    value = getattr(source, key)
                    if key in source.model_fields_set and value != expected:
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

        if (
            self.source_content_sha256 is not None
            and self.source_content_sha256 != CONTENT_SHA256
        ):
            raise ValueError("配运原句的内容身份不符。")
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
