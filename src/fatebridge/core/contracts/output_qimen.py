"""Qimen Dunjia structured output contracts."""

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import PartialOutput

Object = dict[str, JsonValue]


class QimenRuleset(PartialOutput):
    id: str | None = None
    version: str | None = None
    title: str | None = None
    author: str | None = None
    classical_author: str | None = None
    classical_conformance: str | None = None
    ju_method: str | None = None


class QimenCalendarPolicy(PartialOutput):
    timezone: str | None = None
    timezone_rules: Object | None = None
    civil_clock_resolution: Object | None = None
    civil_datetime: str | None = None
    corrected_datetime: str | None = None
    hour_clock: str | None = None
    day_boundary: str | None = None
    ju_term: str | None = None
    ju_method: str | None = None
    solar_term_provider: str | None = None


class QimenPattern(PartialOutput):
    rule_id: str | None = None
    name: str | None = None
    palace: str | None = None
    facts: Object | None = None
    coexisting_conflicts: list[str] | None = None


class QimenStructure(PartialOutput):
    hour_branch_tomb: bool | None = None
    stars_fuyin: bool | None = None
    stars_fanyin: bool | None = None
    doors_fuyin: bool | None = None
    doors_fanyin: bool | None = None
    stems_fuyin: bool | None = None
    stems_fanyin: bool | None = None
    five_not_meet: bool | None = None
    tian_xian_time: bool | None = None


class QimenAssessment(PartialOutput):
    calculation_scope: str | None = None
    classical_conformance: str | None = None
