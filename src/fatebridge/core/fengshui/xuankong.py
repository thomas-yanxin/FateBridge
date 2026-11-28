"""Consolidated Zhongzhou XuanKong: natal charts, KongWang, triples, robbery, RuQiu, city gate, and interpretation."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import TypeAdapter
from typing_extensions import NotRequired

from fatebridge.core.fengshui.calendar import lichun_resolution, year_context
from fatebridge.core.fengshui.directions import (
    FacingBandResult,
    MountainEntry,
    classify_facing_band,
    raw_rule_data,
    wrap9,
)
from fatebridge.core.fengshui.models import (
    CityGateObservation,
    CityGateRequest,
    ExternalFormObservation,
    FixedLingzhengRequest,
    HousePeriod,
    LingzhengObservation,
    Placement,
    XuankongInterpretationRequest,
    XuankongRequest,
)
from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES
from fatebridge.utils.timezones import parse_timezone_name

_OUTER_DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_OPPOSITE = {d: _OUTER_DIRECTIONS[(i + 4) % 8] for i, d in enumerate(_OUTER_DIRECTIONS)}
_PARENTAL_GROUPS = ((1, 4, 7), (2, 5, 8), (3, 6, 9))
_LI_TRINE = ("S", "E", "NW")
_KAN_TRINE = ("N", "SE", "W")
_CONSECUTIVE_TRIPLES = frozenset(
    frozenset((wrap9(a), wrap9(a + 1), wrap9(a + 2))) for a in range(1, 10)
)
_HOST_GUEST_LABELS = {
    "same_element": "比和",
    "guest_generates_host": "生入",
    "guest_controls_host": "克入",
    "host_generates_guest": "生出",
    "host_controls_guest": "克出",
}


class XuankongRuleset(TypedDict):
    ruleset_id: str
    version: str
    method: str
    source_ids: list[str]
    scope: str
    title: NotRequired[str]
    source_angle_applicability_verified: NotRequired[bool]
    whole_book_conformity_established: NotRequired[bool]


class ReplacementCatalogEntry(TypedDict):
    native_star_number: int
    replacement_star_number: int
    changes_number: bool


class XuankongBundle(TypedDict):
    bundle_version: str
    ruleset: XuankongRuleset
    mountains: list[MountainEntry]
    star_home_mountains: dict[str, dict[str, str]]
    replacement_stars: dict[str, int]
    central_half_width_degrees: float
    replacement_catalog: dict[str, ReplacementCatalogEntry]


class CityGateBundle(TypedDict):
    bundle_version: str
    ruleset: XuankongRuleset
    limitations: list[str]


class InterpRuleEntry(TypedDict):
    rule_id: str
    source_ids: list[str]
    conditions: list[str]
    scope: str


class InterpBundle(TypedDict):
    bundle_version: str
    ruleset: XuankongRuleset
    star_elements: dict[str, str]
    rules: dict[str, InterpRuleEntry]
    limitations: list[str]


class FivePeriodHostingEntry(TypedDict):
    zheng_direction: str
    ling_direction: str
    ling_number: int


class LingzhengBundle(TypedDict):
    ruleset: XuankongRuleset
    five_period_hosting: dict[str, FivePeriodHostingEntry]


class TimelinessBundle(TypedDict):
    ruleset: XuankongRuleset
    phase_labels: dict[str, str | None]
    mutual_use_numbers: dict[str, list[int]]
    limitations: list[str]


class MutualGeometryBundle(TypedDict):
    format_id: str
    version: str
    source_id: str
    source_locator: str
    earlier_heaven: dict[str, str]
    later_heaven: dict[str, str]
    star_trigrams: dict[str, str]
    printed_mutual_numbers: dict[str, list[int]]
    orientation_convention: str
    scope: str


class HostGuestBundle(TypedDict):
    format_id: str
    version: str
    ruleset: XuankongRuleset
    star_elements: dict[str, str]
    fixed_earth_numbers: dict[str, int]
    host_guest_matrix: dict[str, dict[str, str]]
    role_policy: dict[str, object]
    sector_mountains: dict[str, str]
    lower_clauses: list[dict[str, object]]


class PeriodTimingWindow(TypedDict):
    start: dict[str, object]
    end: dict[str, object]
    event_year_boundary: NotRequired[dict[str, object]]


class PeriodInterval(TypedDict):
    number: int
    start_year: int
    end_year: int
    valid_from: str
    valid_until: str
    timing: PeriodTimingWindow


class PeriodContext(TypedDict):
    basis: str | None
    evidence: str | None
    qualifies_for_period_reset: bool | None
    resolution_status: Literal["resolved", "requires_confirmation"]
    number: int | None
    input_basis: str
    effective_event_year: int | None
    valid_from: str | None
    valid_until: str | None
    start_year: NotRequired[int]
    end_year: NotRequired[int]
    timing: NotRequired[dict[str, object]]
    confirmation_reason: NotRequired[str]
    event_time_context: NotRequired[dict[str, object]]
    effective_event_year_status: NotRequired[str]
    candidate_effective_event_years: NotRequired[list[int]]
    provisional_effective_event_year: NotRequired[int]
    candidate_period_numbers: NotRequired[list[int]]
    resolution_scope: NotRequired[str]


class SelectorRegion(TypedDict):
    from_degrees_exact: str
    until_degrees_exact: str
    endpoints_included: bool
    mode_reason: str


class StarTrace(TypedDict):
    seed_star_number: int
    home_star_number_for_polarity: int
    yuan: str
    mapped_mountain: str
    polarity: Literal["yang", "yin"]
    flight: Literal["forward", "reverse"]
    center_star_number: int
    replacement_applied: bool
    catalog_star_number: int | None
    five_yellow_kept_without_replacement: bool


class ChartDistribution(TypedDict):
    eval_period_number: int
    code: str
    traditional_label: str
    sitting_direction: str
    facing_direction: str
    mountain_period_star_direction: str
    facing_period_star_direction: str


class LingxingRuqiu(TypedDict):
    eval_period_number: int
    mountain_center_star: int
    facing_center_star: int
    mountain_in_center: bool
    facing_in_center: bool
    lingxing_ruqiu: bool


class CenterNumericPair(TypedDict):
    mountain_star_number: int
    facing_star_number: int
    sum: int
    matches_sum_to_ten: bool


class OppositeComparison(TypedDict):
    sum_to_ten_directions: list[str]
    all_eight_sum_to_ten: bool
    center_numeric_pair: CenterNumericPair


class TrineRobbery(TypedDict):
    directions: list[str]
    palace_triples: dict[str, list[int]]
    matched_group: list[int] | None
    roles_span_group: bool
    matched: bool


class QixingDajie(TypedDict):
    matched: bool
    li_gong_dajie: TrineRobbery
    kan_gong_dajie: TrineRobbery


class GroundRoleComparison(TypedDict):
    same_ground_directions: list[str]
    opposite_ground_directions: list[str]
    whole_ground_repeat: bool
    whole_ground_reverse: bool
    whole_period_plate_same: bool


class VolumeTwoNamedRefrain(TypedDict):
    applicable: bool
    numeric_match: bool | None
    whole_ground_repeat_present: bool
    own_role_sitting_facing_both_opposite_ground: bool


class NumericPatterns(TypedDict):
    opposite_star_comparison: OppositeComparison
    parental_triples: dict[str, bool]
    lianzhu_triples: dict[str, bool]
    qixing_dajie: QixingDajie
    ground_comparison: dict[str, dict[str, GroundRoleComparison]]
    volume_two_named_refrain: VolumeTwoNamedRefrain


class CombinationOfTenEntry(TypedDict):
    left_role: str
    right_role: str
    all_nine_sum_to_ten: bool


class NatalStructure(TypedDict):
    reference_period_number: int
    distribution: ChartDistribution
    lingxing_ruqiu: LingxingRuqiu
    combination_of_ten: list[CombinationOfTenEntry]
    classical_patterns: NumericPatterns
    eval_period_distribution: ChartDistribution
    eval_lingxing_ruqiu: LingxingRuqiu


class XuankongPalace(TypedDict):
    direction: str
    palace_number: int
    period_star_number: int
    mountain_star_number: int
    facing_star_number: int


class ChartMatrixInput(TypedDict):
    period_number: int
    facing: MountainEntry
    sitting: MountainEntry
    chart_mode: str
    period_chart: dict[str, int]
    mountain_chart: dict[str, int]
    facing_chart: dict[str, int]
    flight_path: list[str]


class BearingSupport(TypedDict):
    regions: list[SelectorRegion]
    mode_reasons: list[str]


class FlightDetails(TypedDict):
    mountain: StarTrace
    facing: StarTrace


class XuankongChart(TypedDict):
    candidate_id: str
    period_number: int
    facing: MountainEntry
    sitting: MountainEntry
    chart_mode: str
    mode_reason: str
    facing_subband: str | None
    adjacent_mountain: str | None
    kongwang: str | None
    kongwang_seam_degrees: float | None
    palaces: dict[str, XuankongPalace]
    flight_details: FlightDetails
    structure: NatalStructure
    bearing_support: NotRequired[BearingSupport]


class CityGateFormAssessment(TypedDict):
    status: str
    pattern_matches: NotRequired[dict[str, bool | None]]
    condition_match: bool | None
    candidate_only: NotRequired[bool]


class CityGateEntry(TypedDict):
    direction: str
    side: str
    gate_type: Literal["primary", "secondary"]
    gate_type_zh: Literal["正城门", "副城门"]
    mountain: MountainEntry
    same_yuan: str
    seed_star_number: int
    flight: Literal["reverse", "forward"]
    star_at_gate: int
    reference_star_reaches_gate_by_reverse_flight: bool
    usable: bool
    fixed_luoshu_pair: list[int]
    hetu_generation_pair: bool
    form_assessment: CityGateFormAssessment
    combined_condition_match: bool | None


class CityGateOrientation(TypedDict):
    orientation_candidate_id: str
    facing: MountainEntry
    sitting: MountainEntry
    bearing_regions: list[SelectorRegion]


class CityGateCandidate(TypedDict):
    orientation_candidate_id: str
    facing: MountainEntry
    candidate_only: bool
    reference_period_number: int
    gates: list[CityGateEntry]


class CityGateUnmatchedObservation(TypedDict):
    mountain: str
    evidence: str | None


class CityGateAnalysis(TypedDict):
    status: Literal["partial", "complete"]
    calculation_status: Literal["partial", "complete"]
    reference_period_context: dict[str, object]
    candidates: list[CityGateCandidate]
    missing_inputs: list[str]
    unmatched_observations: list[CityGateUnmatchedObservation]


class MutualGeometryPath(TypedDict):
    current_layout: str
    diagram_direction: str
    coincident_layout: str
    coincident_trigram: str
    coincident_star_number: int


class MutualGeometry(TypedDict):
    status: str
    printed_period_numbers: list[int]
    diagram_derived_numbers: list[int]
    paths: list[MutualGeometryPath]


class MutualUseReference(TypedDict):
    period_numbers: list[int]
    numeric_membership: bool | None
    geometry: MutualGeometry


class TimelinessClassification(TypedDict):
    phase: str
    traditional_label: str | None
    star_number: int
    current_period_number: int | None
    forward_cycle_offset: int | None
    mutual_use_reference: MutualUseReference


class LingzhengVariant(TypedDict):
    five_period_half: str | None
    zheng_direction: str
    ling_direction: str
    ling_number: int


class LingzhengFormAssessment(TypedDict):
    status: str
    observed: dict[str, bool | None]
    condition_match: bool | None


class LingzhengPalaceAnalysis(TypedDict):
    fixed_palace_number: int
    role: str
    form_assessment: LingzhengFormAssessment


class LingzhengCandidate(TypedDict):
    candidate_id: str
    candidate_only: bool
    reference_period_number: int | None
    five_period_half: str | None
    zheng_direction: str
    ling_direction: str
    ling_number: int
    palaces: dict[str, LingzhengPalaceAnalysis]


class FixedLingzhengAnalysis(TypedDict):
    status: Literal["partial", "complete"]
    reference_period_number: int | None
    candidates: list[LingzhengCandidate]
    missing_inputs: list[str]


class HostGuestRelation(TypedDict):
    operation: str
    label: str


class HostGuestRoleValue(TypedDict):
    role: str
    number: int
    element: str


class HostGuestRelationEntry(TypedDict):
    kind: str
    host: HostGuestRoleValue
    guest: HostGuestRoleValue
    operation: str
    label: str


class HostGuestAxisAnalysis(TypedDict):
    direction: str
    active_role: str
    relations: list[HostGuestRelationEntry]


class HostGuestCandidate(TypedDict):
    candidate_id: str
    natal_period_number: int
    chart_mode: str
    axes: dict[str, HostGuestAxisAnalysis]


class HostGuestAnalysis(TypedDict):
    status: Literal["computed_relations", "no_computed_chart"]
    candidates: list[HostGuestCandidate]


class ExternalFormEvaluation(TypedDict):
    status: str
    star_number: int
    observed: bool | None
    condition_match: bool | None


class StarTimelinessEntry(TypedDict):
    star_number: int
    status: Literal["unknown", "current", "not_current"]
    author_classification: NotRequired[TimelinessClassification]


class OrderedPairInfo(TypedDict):
    mountain_element: str
    facing_element: str
    relationship: str


class InterpPalaceEntry(TypedDict):
    direction: str
    period_star_number: int
    mountain_star_number: int
    facing_star_number: int
    ordered_pair: OrderedPairInfo
    timeliness: dict[str, StarTimelinessEntry]
    external_form_analysis: dict[str, ExternalFormEvaluation]


class InterpPlacementFinding(TypedDict):
    object_id: str | None
    purpose: str
    status: str
    direction: NotRequired[str]
    selected_star_role: NotRequired[str]
    selected_star_number: NotRequired[int]
    condition_match: NotRequired[bool | None]


class InterpCandidate(TypedDict):
    candidate_id: str
    candidate_only: bool
    natal_period_number: int
    palaces: dict[str, InterpPalaceEntry]
    placement_findings: list[InterpPlacementFinding]
    eval_period_distribution: NotRequired[ChartDistribution]
    eval_lingxing_ruqiu: NotRequired[LingxingRuqiu]


class NatalInterpretationResult(TypedDict):
    status: Literal["partial", "complete"]
    ruleset_id: str
    current_period_context: dict[str, object]
    candidates: list[InterpCandidate]
    missing_inputs: list[str]
    timeliness_ruleset_id: NotRequired[str]
    fixed_lingzheng_analysis: NotRequired[FixedLingzhengAnalysis]
    host_guest_analysis: NotRequired[HostGuestAnalysis]


class XuankongNatalResult(TypedDict):
    status: Literal["partial", "complete"]
    subject_id: str
    period_context: PeriodContext | None
    orientation_context: dict[str, object]
    chart: XuankongChart | None
    candidates: list[XuankongChart]
    missing_inputs: list[str]
    city_gate_analysis: NotRequired[CityGateAnalysis]
    interpretation: NotRequired[NatalInterpretationResult]


_XUANKONG_BUNDLE_ADAPTER = TypeAdapter(XuankongBundle)
_CITY_GATE_BUNDLE_ADAPTER = TypeAdapter(CityGateBundle)
_INTERP_BUNDLE_ADAPTER = TypeAdapter(InterpBundle)
_LINGZHENG_BUNDLE_ADAPTER = TypeAdapter(LingzhengBundle)
_TIMELINESS_BUNDLE_ADAPTER = TypeAdapter(TimelinessBundle)
_GEOMETRY_BUNDLE_ADAPTER = TypeAdapter(MutualGeometryBundle)
_HOST_GUEST_BUNDLE_ADAPTER = TypeAdapter(HostGuestBundle)


@lru_cache(maxsize=1)
def _bundle() -> XuankongBundle:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "xuankong-v1.json"
    bundle = _XUANKONG_BUNDLE_ADAPTER.validate_json(path.read_bytes())
    validate_replacement_catalog(bundle)
    return bundle


@lru_cache(maxsize=1)
def _city_gate_bundle() -> CityGateBundle:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "city-gate-v1.json"
    return _CITY_GATE_BUNDLE_ADAPTER.validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _interp_bundle() -> InterpBundle:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "natal-interpretation-v1.json"
    )
    return _INTERP_BUNDLE_ADAPTER.validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _lingzheng_bundle() -> LingzhengBundle:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "fixed-lingzheng-v1.json"
    return _LINGZHENG_BUNDLE_ADAPTER.validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _timeliness_bundle() -> TimelinessBundle:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "wang-timeliness-v1.json"
    return _TIMELINESS_BUNDLE_ADAPTER.validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _geometry_bundle() -> MutualGeometryBundle:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "wang-mutual-geometry-v1.json"
    )
    return _GEOMETRY_BUNDLE_ADAPTER.validate_json(path.read_bytes())


@lru_cache(maxsize=1)
def _host_guest_bundle() -> HostGuestBundle:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "host-guest-v1.json"
    return _HOST_GUEST_BUNDLE_ADAPTER.validate_json(path.read_bytes())


def validate_replacement_catalog(bundle: XuankongBundle) -> None:
    mountains = bundle["mountains"]
    catalog = bundle.get("replacement_catalog", {})
    if (
        len(mountains) != 24
        or len(catalog) != 24
        or set(catalog) != {m["name"] for m in mountains}
    ):
        raise ValueError("替星表须完整登记二十四山，缺项不能默认保留原星")
    directions = raw_rule_data("directions")
    changed = {}
    for mountain in mountains:
        name = mountain["name"]
        entry = catalog[name]
        original = directions[mountain["direction"]]["palace_number"]
        star = entry.get("replacement_star_number")
        if (
            type(star) is not int
            or star not in (1, 2, 6, 7, 9)
            or type(entry.get("native_star_number")) is not int
            or entry["native_star_number"] != original
            or type(entry.get("changes_number")) is not bool
            or entry["changes_number"] != (star != original)
        ):
            raise ValueError(f"替星表{name}原星、替星或改数状态冲突")
        if star != original:
            changed[name] = star
    if len(changed) != 13 or changed != bundle["replacement_stars"]:
        raise ValueError("完整替星表须与十三改数山位及十一同数山位一致")


def _period_timing_entry(res: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in res.items() if k not in {"civil_point", "time_basis"}}


def _period_interval(index: int, timezone_name: str) -> PeriodInterval:
    start = 1864 + index * 20
    first = lichun_resolution(start, timezone_name)
    last = lichun_resolution(start + 20, timezone_name)
    return {
        "number": index % 9 + 1,
        "start_year": start,
        "end_year": start + 19,
        "valid_from": str(first["moment"]),
        "valid_until": str(last["moment"]),
        "timing": {
            "start": _period_timing_entry(first),
            "end": _period_timing_entry(last),
        },
    }


def period_context(period: HousePeriod) -> PeriodContext:
    if period.period_number is not None:
        return {
            "basis": period.basis,
            "evidence": period.evidence,
            "qualifies_for_period_reset": period.qualifies_for_period_reset,
            "resolution_status": "resolved",
            "number": period.period_number,
            "input_basis": "confirmed_period_number",
            "effective_event_year": None,
            "valid_from": None,
            "valid_until": None,
        }
    time = year_context(period.event_year, period.event_at, period.timezone_name)
    year_uncertain = time.get("effective_year_status") == "requires_confirmation"
    years: list[int] = (
        time["candidate_effective_years"]
        if year_uncertain
        else [time["effective_year"]]
    )
    indices = sorted({(year - 1864) // 20 for year in years})
    event_boundary = None
    if period.event_at is not None:
        local_year = period.event_at.astimezone(
            parse_timezone_name(period.timezone_name)
        ).year
        event_boundary = lichun_resolution(local_year, period.timezone_name)
    if len(indices) > 1:
        reason = str(time.get("boundary_resolution", {}).get("uncertainty_reason", ""))
        prefixes = (
            "moshier",
            "de441_solar",
            "analytic_solar",
            "vsop2013_solar",
            "aa1996_solar",
        )
        matched_prefix = next((p for p in prefixes if reason.startswith(p)), None)
        if matched_prefix:
            confirmation_reason = (
                f"{matched_prefix}_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("de440_"):
            confirmation_reason = (
                reason.removesuffix("_guard_not_accuracy_certification")
                + "_precision_guard_in_period_changeover_year"
            )
        else:
            confirmation_reason = "approximate_lichun_in_period_changeover_year"
        uncertain_res: PeriodContext = {
            "basis": period.basis,
            "evidence": period.evidence,
            "qualifies_for_period_reset": period.qualifies_for_period_reset,
            "resolution_status": "requires_confirmation",
            "number": None,
            "input_basis": "aware_datetime",
            "effective_event_year": None,
            "event_time_context": time,
            "timing": {
                "event_year_boundary": event_boundary,
                "candidate_period_intervals": [
                    _period_interval(i, period.timezone_name) for i in indices
                ],
            },
            "confirmation_reason": confirmation_reason,
            "valid_from": None,
            "valid_until": None,
        }
        if year_uncertain:
            uncertain_res["effective_event_year_status"] = "requires_confirmation"
            uncertain_res["candidate_effective_event_years"] = list(years)
            uncertain_res["provisional_effective_event_year"] = time[
                "provisional_effective_year"
            ]
            uncertain_res["candidate_period_numbers"] = [
                index % 9 + 1 for index in indices
            ]
        return uncertain_res
    window = _period_interval(indices[0], period.timezone_name)
    timing: dict[str, object] = dict(window["timing"])
    if event_boundary is not None:
        timing["event_year_boundary"] = event_boundary
    resolved: PeriodContext = {
        "basis": period.basis,
        "evidence": period.evidence,
        "qualifies_for_period_reset": period.qualifies_for_period_reset,
        "resolution_status": "resolved",
        "number": window["number"],
        "input_basis": str(time["input_basis"]),
        "effective_event_year": time["effective_year"],
        "start_year": window["start_year"],
        "end_year": window["end_year"],
        "valid_from": window["valid_from"],
        "valid_until": window["valid_until"],
        "timing": timing,
    }
    if year_uncertain:
        resolved["event_time_context"] = time
        resolved["effective_event_year"] = None
        resolved["effective_event_year_status"] = "requires_confirmation"
        resolved["candidate_effective_event_years"] = list(years)
        resolved["provisional_effective_event_year"] = time[
            "provisional_effective_year"
        ]
        resolved["candidate_period_numbers"] = [index % 9 + 1 for index in indices]
        resolved["resolution_scope"] = "period_number_only_event_year_unconfirmed"
    return resolved


def _fly(center: int, yang: bool = True) -> dict[str, int]:
    step = 1 if yang else -1
    return {
        d: wrap9(center + i * step) for i, d in enumerate(raw_rule_data("flight_path"))
    }


def _selector(angle: float) -> tuple[int, str, str]:
    mountains = _bundle()["mountains"]
    index = int(((angle + 7.5) % 360) // 15)
    mountain = mountains[index]
    offset = (angle - mountain["center_degrees"] + 180) % 360 - 180
    if abs(offset) < _bundle()["central_half_width_degrees"]:
        return index, "lower", "central_nine_degrees"
    neighbour = mountains[(index + (1 if offset > 0 else -1)) % 24]
    if (
        mountain["direction"] == neighbour["direction"]
        and mountain["polarity"] == neighbour["polarity"]
    ):
        return index, "lower", "same_palace_same_polarity_no_replacement"
    return index, "replacement", "cross_palace_or_different_polarity"


def _selector_regions(
    angle: float, uncertainty: float
) -> list[tuple[tuple[int, str, str], SelectorRegion]]:
    center_angle, radius = Fraction(angle), Fraction(uncertainty)
    lower, upper = center_angle - radius, center_angle + radius
    regions: list[tuple[tuple[int, str, str], SelectorRegion]] = []
    for i in range(-1, 26):
        center = i * 15
        for left, right, midpoint in ((-7.5, -4.5, -6), (-4.5, 4.5, 0), (4.5, 7.5, 6)):
            start, end = max(lower, center + Fraction(left)), min(
                upper, center + Fraction(right)
            )
            if start <= end:
                selector = _selector((center + midpoint) % 360)
                regions.append(
                    (
                        selector,
                        {
                            "from_degrees_exact": str(start),
                            "until_degrees_exact": str(end),
                            "endpoints_included": True,
                            "mode_reason": selector[2],
                        },
                    )
                )
    return regions


def _star_trace(
    seed: int, physical: MountainEntry, period: int, mode: str
) -> StarTrace:
    rules = _bundle()
    home_star = period if seed == 5 else seed
    assert home_star != 5
    mapped = rules["star_home_mountains"][str(home_star)][physical["yuan"]]
    mapped_mountain = next(m for m in rules["mountains"] if m["name"] == mapped)
    yang = mapped_mountain["polarity"] == "yang"
    replacement = rules["replacement_catalog"][mapped]["replacement_star_number"]
    center = replacement if (mode == "replacement" and seed != 5) else seed
    return {
        "seed_star_number": seed,
        "home_star_number_for_polarity": home_star,
        "yuan": physical["yuan"],
        "mapped_mountain": mapped,
        "polarity": "yang" if yang else "yin",
        "flight": "forward" if yang else "reverse",
        "center_star_number": center,
        "replacement_applied": center != seed,
        "catalog_star_number": replacement if seed != 5 else None,
        "five_yellow_kept_without_replacement": seed == 5,
    }


def _period_distribution(
    sitting: str,
    facing: str,
    mountain_chart: Mapping[str, int],
    facing_chart: Mapping[str, int],
    eval_period: int,
) -> ChartDistribution:
    mountain_at = next(d for d, n in mountain_chart.items() if n == eval_period)
    facing_at = next(d for d, n in facing_chart.items() if n == eval_period)
    labels = {
        (sitting, facing): ("at_sitting_and_facing", "到山到向"),
        (facing, sitting): ("reversed_sitting_and_facing", "上山下水"),
        (sitting, sitting): ("both_at_sitting", "双星到坐"),
        (facing, facing): ("both_at_facing", "双星到向"),
    }
    code, label = labels.get((mountain_at, facing_at), ("other", "其他星位结构"))
    return {
        "eval_period_number": eval_period,
        "code": code,
        "traditional_label": label,
        "sitting_direction": sitting,
        "facing_direction": facing,
        "mountain_period_star_direction": mountain_at,
        "facing_period_star_direction": facing_at,
    }


def _lingxing_ruqiu(m_center: int, f_center: int, eval_period: int) -> LingxingRuqiu:
    return {
        "eval_period_number": eval_period,
        "mountain_center_star": m_center,
        "facing_center_star": f_center,
        "mountain_in_center": m_center == eval_period,
        "facing_in_center": f_center == eval_period,
        "lingxing_ruqiu": (m_center == eval_period or f_center == eval_period),
    }


def _opposite_comparison(chart: ChartMatrixInput) -> OppositeComparison:
    sum_to_ten_dirs = []
    for d in _OUTER_DIRECTIONS:
        opp = _OPPOSITE[d]
        if chart["mountain_chart"][d] + chart["facing_chart"][opp] == 10:
            sum_to_ten_dirs.append(d)
    cm, cf = chart["mountain_chart"]["C"], chart["facing_chart"]["C"]
    return {
        "sum_to_ten_directions": sum_to_ten_dirs,
        "all_eight_sum_to_ten": len(sum_to_ten_dirs) == 8,
        "center_numeric_pair": {
            "mountain_star_number": cm,
            "facing_star_number": cf,
            "sum": cm + cf,
            "matches_sum_to_ten": cm + cf == 10,
        },
    }


def _trine_robbery(
    triples: dict[str, list[int]], directions: tuple[str, ...]
) -> TrineRobbery:
    groups = [
        next((list(g) for g in _PARENTAL_GROUPS if sorted(triples[d]) == list(g)), None)
        for d in directions
    ]
    same_group = (
        groups[0]
        if groups[0] is not None and all(g == groups[0] for g in groups)
        else None
    )
    roles_span = False
    if same_group is not None:
        roles_span = all(
            sorted(triples[d][idx] for d in directions) == same_group
            for idx in range(3)
        )
    return {
        "directions": list(directions),
        "palace_triples": {d: triples[d] for d in directions},
        "matched_group": same_group,
        "roles_span_group": roles_span,
        "matched": same_group is not None and roles_span,
    }


def numeric_patterns(chart: ChartMatrixInput) -> NumericPatterns:
    directions_map = raw_rule_data("directions")
    ground = {d: p["palace_number"] for d, p in directions_map.items()}
    ground["C"] = 5
    flight_path = chart["flight_path"]

    triples = {
        d: [
            chart["period_chart"][d],
            chart["mountain_chart"][d],
            chart["facing_chart"][d],
        ]
        for d in flight_path
    }
    parental_match = all(
        any(sorted(triples[d]) == list(g) for g in _PARENTAL_GROUPS)
        for d in flight_path
    )
    lianzhu_match = all(
        len(set(triples[d])) == 3 and frozenset(triples[d]) in _CONSECUTIVE_TRIPLES
        for d in flight_path
    )

    li_robbery = _trine_robbery(triples, _LI_TRINE)
    kan_robbery = _trine_robbery(triples, _KAN_TRINE)
    qixing_dajie_match = parental_match and (
        li_robbery["matched"] or kan_robbery["matched"]
    )

    ground_roles: dict[str, GroundRoleComparison] = {}
    for role, vals in (
        ("mountain", chart["mountain_chart"]),
        ("facing", chart["facing_chart"]),
    ):
        ground_roles[role] = {
            "same_ground_directions": [d for d in flight_path if vals[d] == ground[d]],
            "opposite_ground_directions": [
                d for d in flight_path if d != "C" and vals[d] == 10 - ground[d]
            ],
            "whole_ground_repeat": all(vals[d] == ground[d] for d in flight_path),
            "whole_ground_reverse": all(vals[d] == 10 - ground[d] for d in flight_path),
            "whole_period_plate_same": vals == chart["period_chart"],
        }

    sitting_dir, facing_dir = (
        chart["sitting"]["direction"],
        chart["facing"]["direction"],
    )
    opposite_endpoints = (
        chart["mountain_chart"][sitting_dir] + ground[sitting_dir] == 10
        and chart["facing_chart"][facing_dir] + ground[facing_dir] == 10
    )
    full_repeat = any(v["whole_ground_repeat"] for v in ground_roles.values())

    return {
        "opposite_star_comparison": _opposite_comparison(chart),
        "parental_triples": {"all_nine_match": parental_match},
        "lianzhu_triples": {"all_nine_match": lianzhu_match},
        "qixing_dajie": {
            "matched": qixing_dajie_match,
            "li_gong_dajie": li_robbery,
            "kan_gong_dajie": kan_robbery,
        },
        "ground_comparison": {"roles": ground_roles},
        "volume_two_named_refrain": {
            "applicable": chart["chart_mode"] == "lower",
            "numeric_match": (
                (full_repeat or opposite_endpoints)
                if chart["chart_mode"] == "lower"
                else None
            ),
            "whole_ground_repeat_present": full_repeat,
            "own_role_sitting_facing_both_opposite_ground": opposite_endpoints,
        },
    }


def natal_structure(
    chart: ChartMatrixInput, current_period: int | None = None
) -> NatalStructure:
    natal_period = chart["period_number"]
    role_charts = (
        ("period", chart["period_chart"]),
        ("mountain", chart["mountain_chart"]),
        ("facing", chart["facing_chart"]),
    )
    ten: list[CombinationOfTenEntry] = [
        {
            "left_role": left,
            "right_role": right,
            "all_nine_sum_to_ten": all(
                left_chart[d] + right_chart[d] == 10 for d in chart["flight_path"]
            ),
        }
        for (left, left_chart), (right, right_chart) in combinations(role_charts, 2)
    ]
    eval_period = current_period if current_period is not None else natal_period
    sitting_dir = chart["sitting"]["direction"]
    facing_dir = chart["facing"]["direction"]
    distribution = _period_distribution(
        sitting_dir,
        facing_dir,
        chart["mountain_chart"],
        chart["facing_chart"],
        natal_period,
    )
    ruqiu = _lingxing_ruqiu(
        chart["mountain_chart"]["C"], chart["facing_chart"]["C"], natal_period
    )
    if eval_period != natal_period:
        eval_distribution = _period_distribution(
            sitting_dir,
            facing_dir,
            chart["mountain_chart"],
            chart["facing_chart"],
            eval_period,
        )
        eval_ruqiu = _lingxing_ruqiu(
            chart["mountain_chart"]["C"], chart["facing_chart"]["C"], eval_period
        )
    else:
        eval_distribution = distribution
        eval_ruqiu = ruqiu
    return {
        "reference_period_number": natal_period,
        "distribution": distribution,
        "lingxing_ruqiu": ruqiu,
        "combination_of_ten": ten,
        "classical_patterns": numeric_patterns(chart),
        "eval_period_distribution": eval_distribution,
        "eval_lingxing_ruqiu": eval_ruqiu,
    }


def _chart(
    period: int,
    selector: tuple[int, str, str],
    *,
    current_period: int | None = None,
    band: FacingBandResult | None = None,
) -> XuankongChart:
    index, mode, reason = selector
    mountains = _bundle()["mountains"]
    directions_map = raw_rule_data("directions")
    flight_path = raw_rule_data("flight_path")
    facing, sitting = mountains[index], mountains[(index + 12) % 24]
    base = _fly(period)
    mountain = _star_trace(base[sitting["direction"]], sitting, period, mode)
    water = _star_trace(base[facing["direction"]], facing, period, mode)
    mountain_chart = _fly(
        mountain["center_star_number"], mountain["polarity"] == "yang"
    )
    facing_chart = _fly(water["center_star_number"], water["polarity"] == "yang")
    palaces: dict[str, XuankongPalace] = {
        d: {
            "direction": d,
            "palace_number": (
                directions_map[d]["palace_number"] if d in directions_map else 5
            ),
            "period_star_number": base[d],
            "mountain_star_number": mountain_chart[d],
            "facing_star_number": facing_chart[d],
        }
        for d in base
    }
    return {
        "candidate_id": f"{period}:{sitting['name']}-{facing['name']}:{mode}",
        "period_number": period,
        "facing": facing,
        "sitting": sitting,
        "chart_mode": mode,
        "mode_reason": reason,
        "facing_subband": band["facing_subband"] if band else None,
        "adjacent_mountain": band["adjacent_mountain"] if band else None,
        "kongwang": band["kongwang"] if band else None,
        "kongwang_seam_degrees": band["kongwang_seam_degrees"] if band else None,
        "palaces": palaces,
        "flight_details": {"mountain": mountain, "facing": water},
        "structure": natal_structure(
            {
                "period_number": period,
                "facing": facing,
                "sitting": sitting,
                "chart_mode": mode,
                "period_chart": base,
                "mountain_chart": mountain_chart,
                "facing_chart": facing_chart,
                "flight_path": list(flight_path),
            },
            current_period=current_period,
        ),
    }


def _conjunction(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def _city_gate_form(
    observation: CityGateObservation | None,
) -> CityGateFormAssessment:
    if observation is None:
        return {"status": "not_requested", "condition_match": None}
    water = observation.water_present
    if water is None and any(
        getattr(observation, name) is True
        for name in (
            "sole_opening_with_water",
            "three_way_water_junction_present",
            "water_reflects_towards_site",
        )
    ):
        water = True
    if (
        observation.multiple_openings_present is True
        or observation.water_present is False
    ):
        match: bool | None = False
        patterns: dict[str, bool | None] = {}
    else:
        patterns = {
            "encircled_sole_water_opening": _conjunction(
                [
                    observation.encircling_form_present,
                    observation.sole_opening_with_water,
                ]
            ),
            "reflecting_three_way_water": _conjunction(
                [
                    water,
                    observation.three_way_water_junction_present,
                    observation.water_reflects_towards_site,
                    (
                        None
                        if observation.multiple_openings_present is None
                        else not observation.multiple_openings_present
                    ),
                ]
            ),
        }
        match = (
            True
            if True in patterns.values()
            else None if None in patterns.values() else False
        )
    image = observation.observation_basis == "image_observed"
    status = (
        "candidate_only"
        if image
        else (
            "needs_confirmation"
            if match is None
            else (
                "selected_pattern_matched" if match else "selected_pattern_not_matched"
            )
        )
    )
    return {
        "status": status,
        "pattern_matches": patterns,
        "condition_match": None if image else match,
        "candidate_only": image,
    }


def analyze_city_gate(
    config: CityGateRequest,
    orientations: list[CityGateOrientation],
    registry: XuankongBundle,
) -> CityGateAnalysis:
    _city_gate_bundle()
    period = config.reference_period_number
    if period is None:
        return {
            "status": "partial",
            "calculation_status": "partial",
            "reference_period_context": {
                "number": None,
                "evidence": config.period_evidence,
            },
            "candidates": [],
            "missing_inputs": ["city_gate.reference_period_number"],
            "unmatched_observations": [
                {"mountain": o.mountain, "evidence": o.evidence}
                for o in config.observations
            ],
        }
    path = raw_rule_data("flight_path")
    directions = raw_rule_data("directions")
    ring = list(directions)
    mountains = registry["mountains"]
    by_name = {m["name"]: m for m in mountains}
    base = {d: wrap9(period + i) for i, d in enumerate(path)}
    observations: dict[str, CityGateObservation] = {
        o.mountain: o for o in config.observations
    }
    ambiguous = len(orientations) > 1
    candidates: list[CityGateCandidate] = []
    used: set[str] = set()
    for orientation in orientations:
        facing = orientation["facing"]
        gates: list[CityGateEntry] = []
        index = ring.index(facing["direction"])
        for side, direction in (
            ("counterclockwise", ring[(index - 1) % 8]),
            ("clockwise", ring[(index + 1) % 8]),
        ):
            physical = next(
                m
                for m in mountains
                if m["direction"] == direction and m["yuan"] == facing["yuan"]
            )
            seed = base[direction]
            home = period if seed == 5 else seed
            assert home != 5
            mapped = by_name[registry["star_home_mountains"][str(home)][facing["yuan"]]]
            reverse = mapped["polarity"] == "yin"
            flight = {
                d: wrap9(seed + (-i if reverse else i)) for i, d in enumerate(path)
            }
            numeric_match = reverse and flight[direction] == period
            pair = sorted(
                (
                    directions[facing["direction"]]["palace_number"],
                    directions[direction]["palace_number"],
                )
            )
            hetu_pair = pair in ([1, 6], [2, 7], [3, 8], [4, 9])
            form = _city_gate_form(observations.get(physical["name"]))
            if physical["name"] in observations:
                used.add(physical["name"])
            gates.append(
                {
                    "direction": direction,
                    "side": side,
                    "gate_type": "primary" if hetu_pair else "secondary",
                    "gate_type_zh": "正城门" if hetu_pair else "副城门",
                    "mountain": physical,
                    "same_yuan": facing["yuan"],
                    "seed_star_number": seed,
                    "flight": "reverse" if reverse else "forward",
                    "star_at_gate": flight[direction],
                    "reference_star_reaches_gate_by_reverse_flight": numeric_match,
                    "usable": numeric_match,
                    "fixed_luoshu_pair": pair,
                    "hetu_generation_pair": hetu_pair,
                    "form_assessment": form,
                    "combined_condition_match": (
                        None
                        if ambiguous
                        else _conjunction([numeric_match, form["condition_match"]])
                    ),
                }
            )
        candidates.append(
            {
                "orientation_candidate_id": orientation["orientation_candidate_id"],
                "facing": facing,
                "candidate_only": ambiguous,
                "reference_period_number": period,
                "gates": gates,
            }
        )
    missing: list[str] = []
    if not orientations:
        missing.append("city_gate.confirmed_magnetic_house_facing")
    elif ambiguous:
        missing.append("city_gate.unambiguous_facing_mountain")
    for c in candidates:
        for gate in c["gates"]:
            if gate["form_assessment"]["status"] in {
                "candidate_only",
                "needs_confirmation",
            }:
                missing.append(
                    f"city_gate.observations.{gate['mountain']['name']}.source_pattern_confirmation"
                )
    return {
        "status": "partial" if missing else "complete",
        "calculation_status": "complete" if orientations else "partial",
        "reference_period_context": {
            "number": period,
            "evidence": config.period_evidence,
        },
        "candidates": candidates,
        "missing_inputs": list(dict.fromkeys(missing)),
        "unmatched_observations": [
            {"mountain": m, "evidence": observations[m].evidence}
            for m in observations
            if m not in used
        ],
    }


def _describe_mutual_geometry(number: int, current: int | None) -> MutualGeometry:
    data = _geometry_bundle()
    members = (
        [] if current is None else list(data["printed_mutual_numbers"][str(current)])
    )
    paths: list[MutualGeometryPath] = []
    if current is None:
        status = "unknown_evaluation_period"
    elif current == 5:
        status = "literal_table_only_no_fifth_trigram"
    else:
        status = "derived_from_two_diagram_overlaps"
        trigram = data["star_trigrams"][str(current)]
        numbers = {v: int(k) for k, v in data["star_trigrams"].items()}
        for origin, other in (
            ("later_heaven", "earlier_heaven"),
            ("earlier_heaven", "later_heaven"),
        ):
            origin_map = (
                data["later_heaven"]
                if origin == "later_heaven"
                else data["earlier_heaven"]
            )
            other_map = (
                data["earlier_heaven"]
                if other == "earlier_heaven"
                else data["later_heaven"]
            )
            direction = next(d for d, t in origin_map.items() if t == trigram)
            paired = other_map[direction]
            paths.append(
                {
                    "current_layout": origin,
                    "diagram_direction": direction,
                    "coincident_layout": other,
                    "coincident_trigram": paired,
                    "coincident_star_number": numbers[paired],
                }
            )
    derived = (
        [current, *(p["coincident_star_number"] for p in paths)]
        if paths and current is not None
        else []
    )
    return {
        "status": status,
        "printed_period_numbers": members,
        "diagram_derived_numbers": derived,
        "paths": paths,
    }


def _classify_timeliness(number: int, current: int | None) -> TimelinessClassification:
    data = _timeliness_bundle()
    offset = None if current is None else (number - current) % 9
    phase = (
        "unknown"
        if offset is None
        else (
            "prosperous"
            if offset == 0
            else (
                "growing"
                if offset in (1, 2)
                else "declining" if offset in (7, 8) else "dormant"
            )
        )
    )
    members = [] if current is None else list(data["mutual_use_numbers"][str(current)])
    return {
        "phase": phase,
        "traditional_label": data["phase_labels"][phase],
        "star_number": number,
        "current_period_number": current,
        "forward_cycle_offset": offset,
        "mutual_use_reference": {
            "period_numbers": members,
            "numeric_membership": None if current is None else number in members,
            "geometry": _describe_mutual_geometry(number, current),
        },
    }


def _analyze_fixed_lingzheng(
    config: FixedLingzhengRequest, current: int | None, natal: XuankongNatalResult
) -> FixedLingzhengAnalysis:
    directions = raw_rule_data("directions")
    by_number = {p["palace_number"]: d for d, p in directions.items()}
    observations: dict[str, LingzhengObservation] = {
        o.direction: o for o in config.observations
    }
    natal_chart = natal["chart"]
    charts: list[XuankongChart] = (
        [natal_chart] if natal_chart is not None else natal["candidates"]
    )
    variants: list[LingzhengVariant] = []
    missing: list[str] = []
    if not charts:
        missing.append("interpretation.fixed_lingzheng.computed_natal_for_comparison")
    if current is None:
        missing.append("interpretation.current_period_number")
    elif current == 5:
        halves = (
            [config.five_period_half]
            if config.five_period_half
            else ["first_decade", "second_decade"]
        )
        if config.five_period_half is None:
            missing.append("interpretation.fixed_lingzheng.five_period_half")
        hosting = _lingzheng_bundle()["five_period_hosting"]
        for half in halves:
            host = hosting[half]
            variants.append(
                {
                    "five_period_half": half,
                    "zheng_direction": host["zheng_direction"],
                    "ling_direction": host["ling_direction"],
                    "ling_number": host["ling_number"],
                }
            )
    else:
        variants.append(
            {
                "five_period_half": None,
                "zheng_direction": by_number[current],
                "ling_direction": by_number[10 - current],
                "ling_number": 10 - current,
            }
        )
    ambiguous = len(variants) > 1
    results: list[LingzhengCandidate] = []
    for variant in variants:
        fixed_id = (
            f"fixed_period_{current}_{variant['five_period_half'] or 'whole_period'}"
        )
        palaces: dict[str, LingzhengPalaceAnalysis] = {}
        for direction in directions:
            role = (
                "zheng"
                if direction == variant["zheng_direction"]
                else (
                    "ling" if direction == variant["ling_direction"] else "not_selected"
                )
            )
            obs = observations.get(direction)
            reqs = (
                ["high_solid_terrain_present"]
                if role == "zheng"
                else (
                    ["low_lying_terrain_present", "river_water_present"]
                    if role == "ling"
                    else []
                )
            )
            facts: dict[str, bool | None] = {
                k: getattr(obs, k) if obs else None for k in reqs
            }
            match = (
                False
                if False in facts.values()
                else None if not facts or None in facts.values() else True
            )
            image = obs is not None and obs.observation_basis == "image_observed"
            cond_status = (
                "not_selected"
                if not reqs
                else (
                    "candidate_only"
                    if (ambiguous or image)
                    else (
                        "needs_confirmation"
                        if match is None
                        else (
                            "selected_presence_matched"
                            if match
                            else "selected_presence_not_matched"
                        )
                    )
                )
            )
            if cond_status in {"needs_confirmation", "candidate_only"}:
                prefix = f"interpretation.fixed_lingzheng.observations.{direction}"
                missing.extend(f"{prefix}.{k}" for k, v in facts.items() if v is None)
                if image:
                    missing.append(f"{prefix}.user_or_measurement_confirmation")
            palaces[direction] = {
                "fixed_palace_number": directions[direction]["palace_number"],
                "role": role,
                "form_assessment": {
                    "status": cond_status,
                    "observed": facts,
                    "condition_match": None if (ambiguous or image) else match,
                },
            }
        results.append(
            {
                "candidate_id": fixed_id,
                "candidate_only": ambiguous,
                "reference_period_number": current,
                "five_period_half": variant["five_period_half"],
                "zheng_direction": variant["zheng_direction"],
                "ling_direction": variant["ling_direction"],
                "ling_number": variant["ling_number"],
                "palaces": palaces,
            }
        )
    return {
        "status": "partial" if missing else "complete",
        "reference_period_number": current,
        "candidates": results,
        "missing_inputs": list(dict.fromkeys(missing)),
    }


def _host_guest_relation(
    host_num: int, guest_num: int, elements: dict[str, str]
) -> HostGuestRelation:
    h, g = elements[str(host_num)], elements[str(guest_num)]
    if h == g:
        op = "same_element"
    elif ELEMENT_GENERATES[g] == h:
        op = "guest_generates_host"
    elif ELEMENT_CONTROLS[g] == h:
        op = "guest_controls_host"
    elif ELEMENT_GENERATES[h] == g:
        op = "host_generates_guest"
    else:
        op = "host_controls_guest"
    return {"operation": op, "label": _HOST_GUEST_LABELS[op]}


def _analyze_host_guest(natal: XuankongNatalResult) -> HostGuestAnalysis:
    data = _host_guest_bundle()
    elements = data["star_elements"]
    earth = data["fixed_earth_numbers"]
    natal_chart = natal["chart"]
    charts: list[XuankongChart] = (
        [natal_chart] if natal_chart is not None else natal["candidates"]
    )
    candidates: list[HostGuestCandidate] = []
    for chart in charts:
        axes: dict[str, HostGuestAxisAnalysis] = {}
        for axis, role, other in (
            ("sitting", "mountain", "facing"),
            ("facing", "facing", "mountain"),
        ):
            direction = (
                chart["sitting"]["direction"]
                if axis == "sitting"
                else chart["facing"]["direction"]
            )
            palace = chart["palaces"][direction]
            raw_nums = {
                "earth": earth[direction],
                "period": palace["period_star_number"],
                "mountain": palace["mountain_star_number"],
                "facing": palace["facing_star_number"],
            }
            relations: list[HostGuestRelationEntry] = []
            for kind, h, g in (
                ("earth_period", "earth", "period"),
                ("period_mountain", "period", "mountain"),
                ("period_facing", "period", "facing"),
                ("axis_pair", role, other),
            ):
                rel = _host_guest_relation(raw_nums[h], raw_nums[g], elements)
                relations.append(
                    {
                        "kind": kind,
                        "host": {
                            "role": h,
                            "number": raw_nums[h],
                            "element": elements[str(raw_nums[h])],
                        },
                        "guest": {
                            "role": g,
                            "number": raw_nums[g],
                            "element": elements[str(raw_nums[g])],
                        },
                        "operation": rel["operation"],
                        "label": rel["label"],
                    }
                )
            axes[axis] = {
                "direction": direction,
                "active_role": role,
                "relations": relations,
            }
        candidates.append(
            {
                "candidate_id": chart["candidate_id"],
                "natal_period_number": chart["period_number"],
                "chart_mode": chart["chart_mode"],
                "axes": axes,
            }
        )
    return {
        "status": "computed_relations" if charts else "no_computed_chart",
        "candidates": candidates,
    }


def _ordered_relationship(mountain: str, facing: str) -> str:
    if mountain == facing:
        return "same_element"
    if ELEMENT_GENERATES[mountain] == facing:
        return "mountain_generates_facing"
    if ELEMENT_GENERATES[facing] == mountain:
        return "facing_generates_mountain"
    if ELEMENT_CONTROLS[mountain] == facing:
        return "mountain_controls_facing"
    return "facing_controls_mountain"


def analyze_natal_interpretation(
    config: XuankongInterpretationRequest,
    natal: XuankongNatalResult,
    placements: list[Placement],
) -> NatalInterpretationResult:
    current = config.current_period_number
    author_profile = config.timeliness_ruleset_id is not None
    observations: dict[str, ExternalFormObservation] = {
        o.direction: o for o in config.external_forms
    }
    natal_chart = natal["chart"]
    charts: list[XuankongChart] = (
        [natal_chart] if natal_chart is not None else natal["candidates"]
    )
    ambiguous = len(charts) > 1
    missing: list[str] = []
    if current is None:
        missing.append("interpretation.current_period_number")
    if not charts:
        missing.extend(
            natal.get("missing_inputs", []) or ["xuankong_natal.computed_chart"]
        )
    elif ambiguous:
        missing.append("xuankong_natal.unambiguous_bearing")

    elements = _interp_bundle()["star_elements"]
    candidates: list[InterpCandidate] = []
    for chart in charts:
        palaces: dict[str, InterpPalaceEntry] = {}
        for direction, palace in chart["palaces"].items():
            m_num, f_num = palace["mountain_star_number"], palace["facing_star_number"]
            m_elem, f_elem = elements[str(m_num)], elements[str(f_num)]
            ext: dict[str, ExternalFormEvaluation] = {}
            for key, role, num in (
                ("mountain", "mountain", m_num),
                ("water", "facing", f_num),
            ):
                field = "mountain_present" if role == "mountain" else "water_present"
                obs = observations.get(direction)
                observed: bool | None = getattr(obs, field) if obs is not None else None
                image = obs is not None and obs.observation_basis == "image_observed"
                if direction == "C":
                    st = "not_applicable_center"
                elif current is None:
                    st = "needs_current_period"
                elif num != current:
                    st = "rule_not_covered_not_inauspicious"
                elif observed is None:
                    st = "needs_confirmation"
                    missing.append(f"interpretation.external_forms.{direction}.{field}")
                elif image:
                    st = "candidate_only"
                    missing.append(
                        f"interpretation.external_forms.{direction}.user_or_measurement_confirmation"
                    )
                else:
                    st = (
                        "matches_presence_requirement"
                        if observed
                        else "required_form_absent"
                    )
                ext[key] = {
                    "status": st,
                    "star_number": num,
                    "observed": observed,
                    "condition_match": (
                        observed
                        if st
                        in {"matches_presence_requirement", "required_form_absent"}
                        else None
                    ),
                }
            timeliness_info: dict[str, StarTimelinessEntry] = {}
            for role, num in (("mountain", m_num), ("facing", f_num)):
                t: StarTimelinessEntry = {
                    "star_number": num,
                    "status": (
                        "unknown"
                        if current is None
                        else ("current" if num == current else "not_current")
                    ),
                }
                if author_profile:
                    t["author_classification"] = _classify_timeliness(num, current)
                timeliness_info[role] = t
            palaces[direction] = {
                "direction": direction,
                "period_star_number": palace["period_star_number"],
                "mountain_star_number": m_num,
                "facing_star_number": f_num,
                "ordered_pair": {
                    "mountain_element": m_elem,
                    "facing_element": f_elem,
                    "relationship": _ordered_relationship(m_elem, f_elem),
                },
                "timeliness": timeliness_info,
                "external_form_analysis": ext,
            }
        findings: list[InterpPlacementFinding] = []
        for placement in placements:
            if placement.purpose not in {"bed", "door"}:
                findings.append(
                    {
                        "object_id": placement.object_id,
                        "purpose": placement.purpose,
                        "status": "unsupported",
                    }
                )
                continue
            if placement.location_direction is None:
                findings.append(
                    {
                        "object_id": placement.object_id,
                        "purpose": placement.purpose,
                        "status": "needs_location",
                    }
                )
                missing.append(f"placements.{placement.object_id}.location_direction")
                continue
            role = "mountain" if placement.purpose == "bed" else "facing"
            pal = palaces[placement.location_direction]
            ext_cond = pal["external_form_analysis"][
                "mountain" if role == "mountain" else "water"
            ]
            selected_star_number = (
                pal["mountain_star_number"]
                if role == "mountain"
                else pal["facing_star_number"]
            )
            findings.append(
                {
                    "object_id": placement.object_id,
                    "purpose": placement.purpose,
                    "direction": placement.location_direction,
                    "selected_star_role": role,
                    "selected_star_number": selected_star_number,
                    "status": ext_cond["status"],
                    "condition_match": (
                        ext_cond["condition_match"] if not ambiguous else None
                    ),
                }
            )
        cand_entry: InterpCandidate = {
            "candidate_id": chart["candidate_id"],
            "candidate_only": ambiguous,
            "natal_period_number": chart["period_number"],
            "palaces": palaces,
            "placement_findings": findings,
        }
        if current is not None:
            mountain_map = {
                d: p["mountain_star_number"] for d, p in chart["palaces"].items()
            }
            facing_map = {
                d: p["facing_star_number"] for d, p in chart["palaces"].items()
            }
            cand_entry["eval_period_distribution"] = _period_distribution(
                chart["sitting"]["direction"],
                chart["facing"]["direction"],
                mountain_map,
                facing_map,
                current,
            )
            cand_entry["eval_lingxing_ruqiu"] = _lingxing_ruqiu(
                mountain_map["C"], facing_map["C"], current
            )
        candidates.append(cand_entry)

    fixed = (
        _analyze_fixed_lingzheng(config.fixed_lingzheng, current, natal)
        if config.fixed_lingzheng
        else None
    )
    if fixed is not None:
        missing.extend(fixed["missing_inputs"])
    host_guest = _analyze_host_guest(natal) if config.host_guest_ruleset_id else None

    result: NatalInterpretationResult = {
        "status": "partial" if missing or not charts else "complete",
        "ruleset_id": config.ruleset_id,
        "current_period_context": {
            "number": current,
            "evidence": config.period_evidence,
        },
        "candidates": candidates,
        "missing_inputs": list(dict.fromkeys(missing)),
    }
    if author_profile and config.timeliness_ruleset_id is not None:
        result["timeliness_ruleset_id"] = config.timeliness_ruleset_id
    if fixed is not None:
        result["fixed_lingzheng_analysis"] = fixed
    if host_guest is not None:
        result["host_guest_analysis"] = host_guest
    return result


def xuankong_natal(req: XuankongRequest) -> XuankongNatalResult:
    house = req.house
    missing: list[str] = []
    if house is None or house.facing_degrees is None:
        missing.append("xuankong_natal.house.facing_degrees_magnetic")
    if req.period is None:
        missing.append("xuankong_natal.period")
    period = period_context(req.period) if req.period is not None else None
    if period is not None and period["resolution_status"] != "resolved":
        missing.append("xuankong_natal.period.effective_year_or_period_confirmation")

    eval_period = req.current_period_number or (
        req.interpretation.current_period_number if req.interpretation else None
    )
    band = (
        classify_facing_band(house.facing_degrees)
        if house is not None and house.facing_degrees is not None
        else None
    )
    orientation_ctx: dict[str, object] = {
        "facing_degrees": (
            house.facing_degrees % 360
            if house and house.facing_degrees is not None
            else None
        ),
        "north_reference": house.north_reference if house else None,
        "uncertainty_degrees": req.effective_bearing_uncertainty,
        "confirmed_sitting_trigram": house.sitting_trigram if house else None,
        "facing_subband": band["facing_subband"] if band else None,
        "adjacent_mountain": band["adjacent_mountain"] if band else None,
        "kongwang": band["kongwang"] if band else None,
        "kongwang_seam_degrees": band["kongwang_seam_degrees"] if band else None,
    }
    if house is not None and house.facing_mountain is not None:
        orientation_ctx["facing_mountain"] = house.facing_mountain
    result: XuankongNatalResult = {
        "status": "partial",
        "subject_id": house.object_id if house is not None else "house",
        "period_context": period,
        "orientation_context": orientation_ctx,
        "chart": None,
        "candidates": [],
        "missing_inputs": missing,
    }
    if req.city_gate is not None:
        orientations: dict[int, CityGateOrientation] = {}
        if house is not None and house.facing_degrees is not None:
            mountains = _bundle()["mountains"]
            directions_map = raw_rule_data("directions")
            for selector, region in _selector_regions(
                house.facing_degrees % 360, req.effective_bearing_uncertainty
            ):
                index, _, _ = selector
                facing, sitting = mountains[index], mountains[(index + 12) % 24]
                if (
                    house.sitting_trigram is not None
                    and directions_map[sitting["direction"]]["trigram"]
                    != house.sitting_trigram
                ):
                    continue
                if index not in orientations:
                    orientations[index] = {
                        "orientation_candidate_id": f"city-gate-facing:{facing['name']}",
                        "facing": facing,
                        "sitting": sitting,
                        "bearing_regions": [],
                    }
                orientations[index]["bearing_regions"].append(region)
        elif house is not None and house.facing_mountain is not None:
            mountains = _bundle()["mountains"]
            m_idx = [m["name"] for m in mountains].index(house.facing_mountain)
            facing, sitting = mountains[m_idx], mountains[(m_idx + 12) % 24]
            orientations[m_idx] = {
                "orientation_candidate_id": f"city-gate-facing:{facing['name']}",
                "facing": facing,
                "sitting": sitting,
                "bearing_regions": [],
            }
        result["city_gate_analysis"] = analyze_city_gate(
            req.city_gate, list(orientations.values()), _bundle()
        )
    if missing:
        if (
            house is not None
            and house.facing_degrees is None
            and house.facing_mountain is not None
            and period is not None
            and period["resolution_status"] == "resolved"
        ):
            period_num = period["number"]
            assert period_num is not None
            mountains = _bundle()["mountains"]
            m_idx = [m["name"] for m in mountains].index(house.facing_mountain)
            result["candidates"] = [
                _chart(
                    period_num,
                    (m_idx, "lower", "facing_mountain_lower_candidate"),
                    current_period=eval_period,
                ),
                _chart(
                    period_num,
                    (m_idx, "replacement", "facing_mountain_replacement_candidate"),
                    current_period=eval_period,
                ),
            ]
        return result

    assert house is not None and house.facing_degrees is not None and period is not None
    period_num = period["number"]
    assert period_num is not None
    supported: dict[tuple[int, str], XuankongChart] = {}
    for selector, region in _selector_regions(
        house.facing_degrees % 360, req.effective_bearing_uncertainty
    ):
        key = selector[:2]
        if key not in supported:
            chart = _chart(period_num, selector, current_period=eval_period, band=band)
            if req.effective_bearing_uncertainty > 0:
                chart["bearing_support"] = {"regions": [], "mode_reasons": []}
            supported[key] = chart
        bearing_support = supported[key].get("bearing_support")
        if bearing_support is not None:
            bearing_support["regions"].append(region)
            if selector[2] not in bearing_support["mode_reasons"]:
                bearing_support["mode_reasons"].append(selector[2])
    candidates = list(supported.values())
    if house.sitting_trigram is not None:
        directions_map = raw_rule_data("directions")
        candidates = [
            c
            for c in candidates
            if directions_map[c["sitting"]["direction"]]["trigram"]
            == house.sitting_trigram
        ]
    if len(candidates) == 1:
        result["status"] = "complete"
        result["chart"] = candidates[0]
        result["candidates"] = []
    else:
        result["candidates"] = candidates
        result["missing_inputs"] = ["xuankong_natal.unambiguous_bearing"]
    return result
