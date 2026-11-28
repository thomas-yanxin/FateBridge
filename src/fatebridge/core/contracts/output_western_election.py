"""Western election and marriage signification outputs."""

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_chart_classical import SolarConditionPolicy
from fatebridge.core.contracts.output_western_events import (
    PlanetaryEvent,
    PlanetaryEventHistory,
)
from fatebridge.core.contracts.output_western_geometry import WesternCalculationBasis
from fatebridge.core.contracts.output_western_horary_facts import HoraryMotionBasis
from fatebridge.core.receipt_models import Object


class ElectionFactor(PartialOutput):
    code: str | None = None
    body: str | None = None
    resolved_hit_axes: list[str] | None = None


class ElectionPlanet(PartialOutput):
    planet: str | None = None
    sign: str | None = None
    longitude: float | None = None
    speed: float | None = None
    retrograde: bool | None = None
    house: str | None = None
    dignity: str | None = None
    dignity_scope: str | None = None


class ElectionAxes(PartialOutput):
    ascendant_longitude: float | None = None
    midheaven_longitude: float | None = None
    first_house_cusp: float | None = None
    tenth_house_cusp: float | None = None
    policy: str | None = None


class ElectionMoon(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None
    longitude: float | None = None
    void_of_course: bool | None = None
    phase: str | None = None
    elongation_degrees: float | None = None
    solar_condition: str | None = None
    motion_basis: HoraryMotionBasis | None = None


class ElectionAscendant(PartialOutput):
    sign: str | None = None
    sign_label: str | None = None
    longitude: float | None = None
    ruler: str | None = None
    ruler_label: str | None = None
    ruler_dignity: str | None = None


class ElectionUnresolvedFactor(PartialOutput):
    code: str | None = None
    reason: str | None = None


class ElectionHouseSignificator(PartialOutput):
    house: int | None = None
    reference_point: str | None = None
    role_in_source: str | None = None
    longitude: float | None = None
    sign: str | None = None
    ruler: str | None = None
    ruler_state: ElectionPlanet | None = None


class ElectionMarriageParty(PartialOutput):
    role_in_source: str | None = None
    natural_significator: str | None = None
    lunar_contact_role: str | None = None
    lunar_significator: str | None = None
    contact_order_established: bool | None = None
    contact: PlanetaryEvent | None = None


class ElectionMarriageSignificators(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    author: str | None = None
    edition: str | None = None
    source_url: str | None = None
    source_pages: list[int] | None = None
    facsimile_url: str | None = None
    facsimile_pdf_pages: list[int] | None = None
    source_basis: str | None = None
    house_system: str | None = None
    zodiac_type: str | None = None
    houses: list[ElectionHouseSignificator] | None = None
    parties: list[ElectionMarriageParty] | None = None
    event_history: PlanetaryEventHistory | None = None
    scope: str | None = None
    full_original_text_acceptance: bool | None = None


class ElectionCandidateWindow(PartialOutput):
    datetime: str | None = None
    offset_hours: int | None = None
    score: int | None = None
    moon_void_of_course: bool | None = None
    planetary_hour_match: bool | None = None
    factor_codes: list[str] | None = None


class Election(PartialOutput):
    reference_geometry: dict[str, OpenJsonValue] | None = None
    backend_convention: dict[str, OpenJsonValue] | None = None
    system: str | None = None
    system_label: str | None = None
    significator: str | None = None
    significator_label: str | None = None
    planets: dict[str, ElectionPlanet] | None = None
    axes: ElectionAxes | None = None
    calculation_basis: WesternCalculationBasis | None = None
    solar_condition_policy: SolarConditionPolicy | None = None
    moon: ElectionMoon | None = None
    ascendant: ElectionAscendant | None = None
    condition_policy: Object | None = None
    unresolved_factors: list[ElectionUnresolvedFactor] | None = None
    dignity_scope: str | None = None
    marriage_significators: ElectionMarriageSignificators | None = None
    topic_id: str | None = None
    topic_label: str | None = None
    topic_house: int | None = None
    factors: list[ElectionFactor] | None = None
    candidate_windows: list[ElectionCandidateWindow] | None = None
    candidate_windows_total_count: int | None = None
