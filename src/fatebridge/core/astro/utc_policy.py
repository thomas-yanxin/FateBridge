"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import TypeAdapter
from typing_extensions import TypedDict


class LeapSecondEntry(TypedDict):
    effective_date: str
    tai_minus_utc_seconds: int


class LeapTable(TypedDict):
    source_url: str
    source_sha256: str
    bulletin: str
    expires_at: str
    entries: list[LeapSecondEntry]


class UTCDefinitionSource(TypedDict):
    source_id: str
    authority: str
    title: str
    version: str
    url: str
    locator: str
    capture_kind: Literal["saved_web_extraction", "http_response_body"]
    capture_sha256: str
    hash_scope: str


class UTCDefinitionRecord(TypedDict):
    schema_version: Literal[1]
    policy_id: str
    record_role: Literal["normative_definition_and_sources_not_epoch_application"]
    nominal_mapping_basis: str
    continuous_utc_effective_date: str
    maximum_abs_ut1_minus_utc_seconds: int
    future_actual_policy_guaranteed: Literal[False]
    clock_realization_accuracy_certified: Literal[False]
    source_refs: list[UTCDefinitionSource]
    scope: str


class UTCDefinitionEvidence(TypedDict):
    policy_id: str
    leap_table_expires_at: str


@lru_cache(maxsize=1)
def leap_table() -> LeapTable:
    return TypeAdapter(LeapTable).validate_json(
        files("fatebridge.data")
        .joinpath("knowledge/western-leap-seconds.json")
        .read_bytes(),
        strict=True,
    )


@lru_cache(maxsize=1)
def utc_definition_source() -> UTCDefinitionRecord:
    """Load the separate normative record, not a replacement offset table."""
    return TypeAdapter(UTCDefinitionRecord).validate_json(
        files("fatebridge.data")
        .joinpath("knowledge/western-utc-definition-cgpm2026-v1.json")
        .read_bytes(),
        strict=True,
    )


def utc_definition_evidence() -> UTCDefinitionEvidence:
    """Identify the reference policy and the loaded offset table's expiry."""
    return {
        "policy_id": utc_definition_source()["policy_id"],
        "leap_table_expires_at": leap_table()["expires_at"],
    }


def default_delta_t_flag(julian_day_ut1: float, swieph_flag: int) -> int:
    """One default TT policy for physical clocks and rotation adapters.

    Before1960 the civil forward path delegates to Swiss's historical UT1
    convention, which uses -1. Atomic/drifting UTC is handled explicitly from
    1960, with the existing SWIEPH model used for the modeled UT1 relation.
    A selected C04 source supplies its own TT and does not use this policy.
    """
    return -1 if julian_day_ut1 < 2436934.5 else swieph_flag
