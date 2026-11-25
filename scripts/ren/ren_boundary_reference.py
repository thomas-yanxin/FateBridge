"""Read complete independent Ren boundary inputs without candidate imports."""

from __future__ import annotations

import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from scripts.astronomy.solar_term_reference import (
    REFERENCE_SHA256 as SOLAR_REFERENCE_SHA256,
)
from scripts.astronomy.solar_term_reference import (
    SolarTermReference,
    load_solar_term_reference,
)

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests/data/ren_boundary_sources_v1/reference.json.gz"
)
REFERENCE_SHA256 = "19b9a8679e4d4cb31ea9a0c5934f1d922c109dd94546773bd30a9aeff0b0a417"


class _FrozenSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class _SourceFields(BaseModel):
    """Type consumed source fields while preserving original text separately."""

    model_config = ConfigDict(frozen=True, extra="ignore", allow_inf_nan=False)


class SourceInput(_FrozenSource):
    sha256: str
    text: str


class SourceCalendar(_SourceFields):
    references: dict[str, str]
    day_cycle: dict[str, int | str]
    month_stems: dict[str, str]
    hour_stems: dict[str, str]
    month_starts: dict[str, str]
    general_starts: dict[str, str]


class SourceRules(_SourceFields):
    guiren: tuple[dict[str, str], ...]
    inherent: dict[str, str]
    power: dict[str, dict[str, str]]
    polarity_use: tuple[dict[str, str], ...]


class SOFACase(_SourceFields):
    utc: str
    tt_jd_parts: tuple[float, float]


class SourceSOFA(_SourceFields):
    historical_coefficients: tuple[dict[str, float | str], ...]
    cases: tuple[SOFACase, ...]


class SourceProfile(_FrozenSource):
    mode: str
    directory: str
    provider: str
    model: str


class SourceSecondProtocol(_SourceFields):
    id: str
    years: tuple[int, int]
    root_count: Literal[9624]
    guard_roots: Literal[48]
    probe_count: Literal[19248]
    profiles: dict[str, SourceProfile]
    di_fen: str
    is_diurnal: bool
    true_solar: bool
    timezone: Literal["UTC"]
    day_boundary: str
    criteria: dict[str, float | str]
    reference_maps: dict[str, dict[str, str] | tuple[str, ...]]
    clock_method: str
    clock_swiss_version: str
    clock_files: dict[str, str]
    full_goal_complete: Literal[False]


class SourceBoundaryProtocol(_SourceFields):
    cohorts: dict[str, int | tuple[int, int]]
    arms: dict[str, SourceProfile]
    kernel_sha256: str
    criteria: dict[str, float | bool | str]
    reference_maps: dict[str, dict[str, str] | tuple[str, ...]]
    full_goal_complete: Literal[False]
    new_real_world_samples: Literal[0]
    model_processes: Literal[0]


class MinuteState(_FrozenSource):
    last_term: str | None
    next_term: str | None
    bazi_year: int | None
    month_branch: str | None


class MinuteProbe(_FrozenSource):
    id: str
    year: int
    name: str
    side: Literal["floor", "next_minute"]
    civil_utc: str
    reference_root_tt: float
    reference_civil_under_frozen_policy: str
    input_jd_tt_under_frozen_policy: float
    input_time_method: str
    future_leap_seconds_assumed_unchanged: bool
    reference_state_under_frozen_policy: MinuteState


class MinuteData(_FrozenSource):
    protocol_sha256: str
    reference_sha256: str
    collector_sha256: str
    root_count: Literal[4872]
    probe_count: Literal[9744]
    rows: tuple[MinuteProbe, ...]
    native_clock_files: dict[str, str]
    scope: str


class ExpectedDecision(_FrozenSource):
    current_term: str
    next_term: str
    year: str
    month: str
    day: str
    hour: str
    month_general: str
    positions: tuple[str, str, str, str]
    seasonal_powers: tuple[str, str, str, str]
    polarity_use: str


class SecondProbe(_FrozenSource):
    id: str
    year: int
    index: int
    side: Literal["floor", "next_second"]
    civil_utc: str
    reference_jd_tt: float
    reference_civil: str
    input_jd_tt: float
    reference_clock_method: str
    tt_margin_seconds: float
    inside_root_bracket: bool
    expected: ExpectedDecision


class SecondData(_FrozenSource):
    production_imports: Literal[False]
    root_count: Literal[9624]
    rows: tuple[SecondProbe, ...]
    reference_clock_sofa_checks: tuple[dict[str, float | str | bool], ...]
    inside_root_bracket_ids: tuple[str, ...]
    minimum_abs_tt_margin_seconds: float
    new_independent_physical_events: Literal[0]


class BoundarySourcePacket(_FrozenSource):
    schema_id: Literal["ren_boundary_sources_v1"]
    solar_reference_sha256: str
    producer_source: str
    producer_sha256: str
    helper_source: str
    helper_sha256: str
    software_versions: dict[str, str]
    source_inputs: dict[str, SourceInput]
    second_protocol: SourceSecondProtocol
    boundary_protocol: SourceBoundaryProtocol
    seconds: SecondData
    legacy_identity_observations: tuple[dict[str, str | bool], ...]
    scope: str


@dataclass(frozen=True, slots=True)
class RenBoundaryReference:
    packet: BoundarySourcePacket
    solar: SolarTermReference
    minutes: MinuteData
    calendar: SourceCalendar
    rules: SourceRules
    sofa: SourceSOFA

    @property
    def source_summary(self) -> dict[str, object]:
        return {
            "kind": "independently_reproduced_ren_boundary_sources_v1",
            "reference_packet_sha256": REFERENCE_SHA256,
            "solar_reference_sha256": self.packet.solar_reference_sha256,
            "producer_sha256": self.packet.producer_sha256,
            "helper_sha256": self.packet.helper_sha256,
            "legacy_identity_observations": self.packet.legacy_identity_observations,
            "legacy_scope": "The listed observations were captured at packet generation, not by inspecting later filesystem changes. Missing original provenance and process-report identities are not claimed restored.",
        }


def load_ren_boundary_reference(path: Path = REFERENCE_PATH) -> RenBoundaryReference:
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Frozen independent Ren reference identity changed")
    else:
        pass
    packet = BoundarySourcePacket.model_validate_json(
        gzip.decompress(packed), strict=True
    )
    for text, expected in [
        (packet.producer_source, packet.producer_sha256),
        (packet.helper_source, packet.helper_sha256),
        *((item.text, item.sha256) for item in packet.source_inputs.values()),
    ]:
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != expected:
            raise ValueError("Frozen independent Ren source identity changed")
        else:
            pass
    if packet.solar_reference_sha256 != SOLAR_REFERENCE_SHA256:
        raise ValueError("Frozen independent Ren solar source identity changed")
    else:
        pass
    solar = load_solar_term_reference()
    minutes = MinuteData.model_validate_json(
        packet.source_inputs["minute_data"].text, strict=True
    )
    calendar = SourceCalendar.model_validate_json(
        packet.source_inputs["calendar"].text, strict=True
    )
    rules = SourceRules.model_validate_json(
        packet.source_inputs["rules"].text, strict=True
    )
    sofa = SourceSOFA.model_validate_json(
        packet.source_inputs["sofa"].text, strict=True
    )
    second_roots = tuple(r for r in solar.rows if 1800 <= r.year <= 2200)
    expected_seconds = tuple(
        f"{root.year}-{root.name}-{side}"
        for root in second_roots
        for side in ["floor", "next_second"]
    )
    if tuple(row.id for row in packet.seconds.rows) != expected_seconds:
        raise ValueError("Frozen independent Ren cohort needs all19248 ordered seconds")
    else:
        pass
    expected_minutes = tuple(
        f"{root.year}-{root.name}-{side}"
        for root in solar.rows
        if 1899 <= root.year <= 2101
        for side in ["floor", "next_minute"]
    )
    if tuple(row.id for row in minutes.rows) != expected_minutes:
        raise ValueError("Frozen independent Ren cohort needs all9744 ordered minutes")
    else:
        pass
    for root, pair in zip(
        second_roots, zip(packet.seconds.rows[::2], packet.seconds.rows[1::2])
    ):
        for row in pair:
            low, high = root.bracket_tt
            if (
                row.reference_jd_tt != root.jd_tt
                or row.year != root.year
                or row.index != root.index
                or row.inside_root_bracket != (low <= row.input_jd_tt <= high)
            ):
                raise ValueError("Frozen independent Ren root or uncertainty changed")
            else:
                pass
    if packet.seconds.inside_root_bracket_ids != tuple(
        r.id for r in packet.seconds.rows if r.inside_root_bracket
    ):
        raise ValueError("Frozen independent Ren uncertainty inventory changed")
    else:
        pass
    return RenBoundaryReference(packet, solar, minutes, calendar, rules, sofa)
