"""Optional first-cycle contacts, with replayable finite TT search witnesses.

This is a contact finder, not an age classifier or a full cycle-chart reading.
Retrograde contacts are retained. The longitude is unwrapped from birth, so an
early revisit of the natal degree is not mistaken for a completed revolution.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import timezone
from fractions import Fraction
from typing import Any, Callable

from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.human_design_cycle_sources import (
    CycleBirthSources,
    CycleSourceTrace,
    cycle_source_summary,
)
from fatebridge.core.human_design_cycle_summary import FORMAT as SUMMARY_FORMAT
from fatebridge.core.human_design_cycle_summary import compact_cycle_summary
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_reference_clock import (
    LEAP_REFERENCE,
    reference_datetime,
)
from fatebridge.core.human_design_reference_order import (
    reference_ordering,
    validate_reference_precision,
)
from fatebridge.core.human_design_references import reference_bytes
from fatebridge.core.human_design_time import epoch_context_at_tt
from fatebridge.utils.errors import EphemerisSourceError

HORIZON_DAYS = 65 * 365.25
STEP_DAYS = 2.0
ROOT_SECONDS = 0.0002
STATION_SECONDS = 0.01
RESIDUAL_DEGREES = 1e-7
PHASE_METHOD = "exact_binary_longitude_increments_with_integer_winding_v1"
ROOT_METHOD = "human_design_adjacent_float_cycle_contact_v1"
STATION_METHOD = "human_design_adjacent_float_cycle_station_v1"
COORDINATE_EXTREMUM_METHOD = "human_design_bounded_observed_coordinate_extremum_v1"
NUMERICAL_SCOPE = "交会/速度驻点收敛至观测零值或相邻TT；速度零点不等于返回黄经极值，另在同一变号区间作有限坐标探查，只以严格更极端的已观察坐标补充分段。连续已观察零端点合为一候选，不认证其连续零区间；motion取原生速度符号，另列搜索段相位方向。黄经量化可掩盖极近峰值，不认证连续根数量、物理精度或传统首末触优先性。"
SUMMARY_NUMERICAL_SCOPE = "零值/相邻TT加有限坐标极值探查；原生速度与搜索段相位方向分别列出，量化近峰、连续根数及物理精度未认证。"
REFERENCE_CONTACT_METHOD = "source_defined_reference_TT_vs_binary64_contact_brackets_v1"
REFERENCE_CONTACT_SCOPE = "按已声明时标的精确有理TT，将参考民用钟与已报告的闭合二进制TT数值括区比较，避免微秒标签先舍入到单个JD后混入括区。只说明参考输入与数值区间的先后，不认证真实物理交会、未来闰秒、连续根数量、首末触传统优先或第六线当前阶段。"
ARITHMETIC_SCOPE = "展开角与残差由实际返回黄经的精确二进制有理数求差，不逐段累加舍入后的浮点角差；这不提高原星历或出生钟精度，交会数值区间不认证物理时刻误差，也不裁定传统多次交会的取舍。"
BODIES = {"Saturn": (6, 360.0), "Uranus": (7, 180.0), "Chiron": (15, 360.0)}
SOURCE_URLS = [
    "https://jovianarchive.com/pages/human-design-dictionary",
    "https://jovianarchive.com/blogs/chart-interpretations-components/the-six-lines-of-the-hexagram",
    "https://jovianarchive.com/pages/cycle-analysis-in-human-design",
    "https://www.astro.com/swisseph/swephprg.htm",
]
SCOPE = "人格出生黄经起算；65儒略年内以2日TT网格、已观测速度变号及区间内有限坐标极值探查，细查首轮360°回归/180°对冲。连续已观察零端点合为一候选，原生速度符号与搜索段相位方向分别保留。65年仅为搜索上限，非寿命/阶段年龄；采样不认证连续穷尽。天王星出生原点有公开明文；土星/凯龙起点及各项首末触优先未定，不指定唯一传统阶段。"
PHASE_SCOPE = "仅列原有第六线教学顺序；不由年龄、交会日期或人格/设计起点约定分配当前阶段，不将教学转成现实成熟度、健康、寿命或事件预测。"
Row = list[float | int]
Reader = Callable[[float], Row]


def cycle_ruleset() -> dict[str, Any]:
    raw = reference_bytes("cycles-2026-reference.json")
    reference = json.loads(raw)
    return {
        "id": "human_design_first_cycle_contacts_v1",
        "version": ("1.6.0"),
        "author": "FateBridge computational implementation",
        "source_author": reference["author"],
        "source_catalog_sha256": (hashlib.sha256(raw).hexdigest()),
    }


def origin_source_evidence(body: str) -> dict[str, Any]:
    """Keep explicit birth wording separate from unresolved return conventions."""
    if body not in BODIES:
        raise ValueError("Unknown Human Design cycle body")
    raw = reference_bytes("cycles-2026-reference.json")
    reference = json.loads(raw)
    fact = reference["event_origin_evidence"][body]
    source_key = fact["source_key"]
    return {
        "body": body,
        **fact,
        "source": reference["sources"][source_key] if source_key is not None else None,
        "source_catalog_sha256": hashlib.sha256(raw).hexdigest(),
        "scope": "逐天体来源口径；出生原点明文及其人格侧映射分别列出，不外推到其他回归、逆行首末触优先性或唯一传统阶段。",
    }


class CycleUnavailable(Exception):
    def __init__(self, reason: str, jd_tt: float) -> None:
        self.reason, self.jd_tt = reason, jd_tt
        super().__init__(reason)


def reference_epoch(value: str) -> tuple[str, float]:
    """Require an explicit, aware instant. Never infer the current clock."""
    validate_reference_precision(value)
    leap = LEAP_REFERENCE.fullmatch(value)
    if leap is not None:
        y, m, d, h, minute, fraction, offset = leap.groups()
        clock = resolve_birth_clock(
            birth_year=int(y),
            birth_month=int(m),
            birth_day=int(d),
            birth_hour=int(h),
            birth_minute=int(minute),
            birth_second=60,
            birth_timezone="UTC" if offset == "Z" else offset,
        )
        assert clock.jd_tt is not None
        micros = int((fraction or "").ljust(6, "0"))
        label = clock.utc_label[:20] + f"{micros:06d}+00:00"
        return label, clock.jd_tt + (micros / 1e6) / 86400
    moment = reference_datetime(value)
    if moment.utcoffset() is None:
        raise ValueError("cycle_reference_datetime 必须带明确时区或UTC偏移")
    moment = moment.astimezone(timezone.utc)
    if not 1800 <= moment.year <= 2600:
        raise ValueError("cycle_reference_datetime 的UTC年份须在1800至2600之间")
    tt = ephemeris_time(moment).jd_tt
    if tt is None:
        raise ValueError("cycle_reference_datetime 无可用TT")
    return moment.isoformat(), tt


def _increment(longitude: float, previous: float) -> Fraction:
    # Exact increments telescope to current - natal + 360 * integer winding.
    # Adding rounded binary64 increments for decades moves the root bracket.
    return (Fraction(longitude) - Fraction(previous) + 180) % 360 - 180


def validate_row(row: Row, jd_tt: float, require_swiss_files: bool) -> str:
    if (
        len(row) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[:3])
        or row[0] != jd_tt
        or not 0 <= row[1] < 360
    ):
        raise ValueError("周期见证坐标无效")
    model = position_flag_model(row[3])  # type: ignore[arg-type]
    if require_swiss_files and model != "swieph":
        raise CycleUnavailable("required_swiss_backend_unavailable", jd_tt)
    return model


def coordinate_extremum_probe(
    left: Row, right: Row, station_rows: list[Row], read: Reader
) -> tuple[Row, dict[str, Any]]:
    """Observe a coordinate extremum; the native speed is only a locator.

    Golden-section probes are finite and do not establish unimodality, a
    continuous extremum, or physical accuracy. All requests remain witnesses.
    Retaining the original station split unless a strictly better coordinate
    was observed also preserves unresolved rounded-peak controls.
    """
    maximize = left[2] > 0
    sign = -1 if maximize else 1
    anchor = float(left[1])

    def value(row: Row) -> Fraction:
        return sign * _increment(float(row[1]), anchor)

    samples = {float(row[0]): row for row in [left, right, *station_rows]}
    baseline = min(station_rows, key=lambda row: (value(row), row[0]))
    lo, hi = float(left[0]), float(right[0])
    iterations = 0
    for iterations in range(1, 129):
        if math.nextafter(lo, math.inf) >= hi:
            break
        # Fixed binary64 constants, with no platform transcendental call.
        a = lo + (hi - lo) * 0.3819660112501051
        b = lo + (hi - lo) * 0.6180339887498949
        if not lo < a <= b < hi:
            break
        ra, rb = read(a), read(b)
        samples[a], samples[b] = ra, rb
        if a == b:
            break
        av, bv = value(ra), value(rb)
        if av < bv:
            hi = b
        elif av > bv:
            lo = a
        else:
            lo, hi = a, b
    chosen = min(samples.values(), key=lambda row: (value(row), row[0]))
    return chosen, {
        "method_id": COORDINATE_EXTREMUM_METHOD,
        "kind": "maximum" if maximize else "minimum",
        "initial_interval_jd_tt": [left[0], right[0]],
        "final_probe_interval_jd_tt": [lo, hi],
        "iterations": iterations,
        "observed_sample_count": len(samples),
        "selected_sample": chosen,
        "strictly_extends_speed_station_coordinates": value(chosen) < value(baseline),
        "continuous_extremum_certified": False,
        "physical_accuracy_certified": False,
    }


def derive_body_contacts(
    body: str, birth_tt: float, read: Reader, *, require_swiss_files: bool = False
) -> dict[str, Any]:
    """Replayable numerical derivation. Reader owns native calls or witnesses."""
    _, target = BODIES[body]
    target_exact = Fraction(target)
    contacts: list[dict[str, Any]] = []
    stations: list[dict[str, Any]] = []
    end = birth_tt + HORIZON_DAYS
    first: Row | None = None
    model: str | None = None
    covered_end: float | None = None
    zero_component_contact_index: int | None = None
    segments: list[list[tuple[Row, Fraction]]] = []
    refinements: list[tuple[int, int, Row, Row, Fraction, list[Row]]] = []

    def at(t: float) -> Row:
        nonlocal model
        row = read(t)
        actual = validate_row(row, t, require_swiss_files)
        if model is None:
            model = actual
        elif actual != model:
            raise CycleUnavailable("native_model_changed_within_search", t)
        return row

    def station(left: Row, right: Row) -> tuple[Row, Row, Row]:
        lo, hi = left, right
        while math.nextafter(float(lo[0]), math.inf) < hi[0]:
            t = float(lo[0] + (hi[0] - lo[0]) / 2)
            if t in (lo[0], hi[0]):
                break
            mid = at(t)
            if mid[2] == 0:
                lo = hi = mid
                break
            if (mid[2] > 0) == (lo[2] > 0):
                lo = mid
            else:
                hi = mid
        chosen = min((lo, hi), key=lambda row: (abs(row[2]), row[0]))
        if (hi[0] - lo[0]) * 86400 > STATION_SECONDS:
            raise CycleUnavailable("station_bracket_did_not_converge", float(chosen[0]))
        return chosen, lo, hi

    def crossing(left: Row, lp: Fraction, right: Row, rp: Fraction) -> dict[str, Any]:
        lo, hi, lv, hv = left, right, lp - target_exact, rp - target_exact
        for _ in range(128):
            if lv == 0:
                hi, hv = lo, lv
                break
            if hv == 0:
                lo, lv = hi, hv
                break
            if math.nextafter(float(lo[0]), math.inf) >= hi[0]:
                break
            t = float(lo[0] + (hi[0] - lo[0]) / 2)
            if t in (lo[0], hi[0]):
                break
            mid = at(t)
            mv = lv + _increment(float(mid[1]), float(lo[1]))
            if (mv > 0) == (lv > 0):
                lo, lv = mid, mv
            else:
                hi, hv = mid, mv
        solved, residual = min(
            ((lo, lv), (hi, hv)), key=lambda item: (abs(item[1]), item[0][0])
        )
        t = float(solved[0])
        if (hi[0] - lo[0]) * 86400 > ROOT_SECONDS or (
            lo[0] != hi[0] and math.nextafter(float(lo[0]), math.inf) != hi[0]
        ):
            raise CycleUnavailable("contact_bracket_did_not_converge", t)
        if abs(residual) > RESIDUAL_DEGREES:
            raise CycleUnavailable("angular_root_residual_exceeded", t)
        return {
            "jd_tt": t,
            "longitude": solved[1],
            "longitude_speed": solved[2],
            "return_flags": solved[3],
            "motion": (
                "direct"
                if solved[2] > 0
                else "retrograde" if solved[2] < 0 else "stationary"
            ),
            "motion_evidence": {
                "motion_basis": "native_returned_longitude_speed_sign",
                "search_segment_jd_tt": [left[0], right[0]],
                "search_segment_phase_trend": (
                    "increasing" if rp > lp else "decreasing" if rp < lp else "equal"
                ),
                "opposite_nonzero_endpoint_residuals": (lp - target_exact)
                * (rp - target_exact)
                < 0,
                "native_speed_agrees_with_segment_trend": (
                    (solved[2] > 0 and rp > lp)
                    or (solved[2] < 0 and rp < lp)
                    or (solved[2] == 0 and rp == lp)
                ),
                "instantaneous_coordinate_derivative_certified": False,
            },
            "residual_degrees": float(residual),
            "exact_residual": {
                "numerator": str(residual.numerator),
                "denominator": str(residual.denominator),
            },
            "phase_arithmetic_method": PHASE_METHOD,
            "root_method": ROOT_METHOD,
            "bracket_jd_tt": [lo[0], hi[0]],
            "bracket_residual_degrees": [float(lv), float(hv)],
            "bracket_exact_residuals": [
                {"numerator": str(v.numerator), "denominator": str(v.denominator)}
                for v in (lv, hv)
            ],
            "bracket_width_seconds": (hi[0] - lo[0]) * 86400,
        }

    def visit_points(points: list[tuple[Row, Fraction]]) -> None:
        nonlocal zero_component_contact_index
        for (a, ap), (b, bp) in zip(points, points[1:]):
            if ap != target_exact:
                zero_component_contact_index = None
            if ap == bp == target_exact:
                # Consecutive observed zeroes form one candidate. They do not
                # prove a continuous zero plateau or two physical roots.
                if zero_component_contact_index is None:
                    contacts.append(crossing(a, ap, a, ap))
                    zero_component_contact_index = len(contacts) - 1
                continue
            if min(ap, bp) <= target <= max(ap, bp) and ap != bp:
                event = crossing(a, ap, b, bp)
                zero_endpoint = event["exact_residual"]["numerator"] == "0" and (
                    ap == target_exact or bp == target_exact
                )
                shares_zero_component = (
                    zero_endpoint
                    and ap == target_exact
                    and zero_component_contact_index is not None
                )
                if not shares_zero_component:
                    contacts.append(event)
                if zero_endpoint and bp == target_exact:
                    if not shares_zero_component:
                        zero_component_contact_index = len(contacts) - 1
                else:
                    zero_component_contact_index = None
            if bp != target_exact:
                zero_component_contact_index = None

    failure: dict[str, Any] | None = None
    try:
        first = at(birth_tt)
        left, phase = first, Fraction(0)
        covered_end = birth_tt
        k = 1
        while k <= math.ceil(HORIZON_DAYS / STEP_DAYS):
            t = min(birth_tt + k * STEP_DAYS, end)
            right = at(t)
            points = [(left, phase)]
            zero_speed_samples = []
            # A sampled zero can sit between the positive and negative
            # endpoint velocities. Keep those grid samples and defer the
            # interval until the next nonzero velocity or search boundary.
            while right[2] == 0 and right[0] < end:
                zero_speed_samples.append(right)
                k += 1
                t = min(birth_tt + k * STEP_DAYS, end)
                right = at(t)
            previous, right_phase = left, phase
            for sample in [*zero_speed_samples, right]:
                delta = _increment(float(sample[1]), float(previous[1]))
                if abs(delta) >= 90:
                    raise CycleUnavailable("sample_longitude_jump", float(sample[0]))
                right_phase += delta
                if sample[0] != right[0]:
                    points.append((sample, right_phase))
                previous = sample
            if left[2] * right[2] < 0 or (right[2] == 0 and left[2] != 0):
                turning, station_lo, station_hi = station(left, right)
                turning_phase = phase + _increment(float(turning[1]), float(left[1]))
                station_residual = turning_phase - target_exact
                stations.append(
                    {
                        "jd_tt": turning[0],
                        "phase_degrees": float(turning_phase),
                        "longitude_speed": turning[2],
                        "method_id": STATION_METHOD,
                        "bracket_jd_tt": [station_lo[0], station_hi[0]],
                        "bracket_longitude_speeds": [station_lo[2], station_hi[2]],
                        "bracket_width_seconds": (station_hi[0] - station_lo[0])
                        * 86400,
                        "target_phase_exact_residual": {
                            "numerator": str(station_residual.numerator),
                            "denominator": str(station_residual.denominator),
                        },
                        "continuous_contact_multiplicity_certified": False,
                    }
                )
                for sample in (station_lo, station_hi):
                    if sample[0] != points[-1][0][0]:
                        points.append(
                            (
                                sample,
                                phase + _increment(float(sample[1]), float(left[1])),
                            )
                        )
                refinements.append(
                    (
                        len(stations) - 1,
                        len(segments),
                        left,
                        right,
                        phase,
                        [turning, station_lo, station_hi],
                    )
                )
            points.append((right, right_phase))
            points = sorted(
                {float(row[0]): (row, p) for row, p in points}.values(),
                key=lambda pair: pair[0][0],
            )
            visit_points(points)
            segments.append(points)
            left, phase, covered_end = right, right_phase, t
            k += 1
        # Complete the baseline observation sequence before any supplementary
        # native calls. Its cached coordinates/roots remain available exactly.
        changed = False
        for station_index, segment_index, a, b, ap, station_rows in refinements:
            coordinate, probe = coordinate_extremum_probe(a, b, station_rows, at)
            phase_at_coordinate = ap + _increment(float(coordinate[1]), float(a[1]))
            station_phases = [
                ap + _increment(float(row[1]), float(a[1])) for row in station_rows
            ]
            old_extremum = (max if a[2] > 0 else min)(station_phases)
            target_inside_gain = (
                min(old_extremum, phase_at_coordinate)
                <= target_exact
                <= max(old_extremum, phase_at_coordinate)
            )
            use_coordinate = bool(
                probe["strictly_extends_speed_station_coordinates"]
                and target_inside_gain
            )
            probe["target_inside_observed_extremum_gain"] = target_inside_gain
            probe["used_for_additional_contact_segmentation"] = use_coordinate
            probe["baseline_observation_prefix_preserved"] = True
            stations[station_index]["coordinate_probe"] = probe
            if use_coordinate:
                points = [*segments[segment_index], (coordinate, phase_at_coordinate)]
                segments[segment_index] = sorted(
                    {float(row[0]): (row, p) for row, p in points}.values(),
                    key=lambda pair: pair[0][0],
                )
                changed = True
        if changed:
            contacts = []
            zero_component_contact_index = None
            for points in segments:
                visit_points(points)
    except CycleUnavailable as exc:
        failure = {"reason": exc.reason, "jd_tt": exc.jd_tt}
    return {
        "body": body,
        "native_body_id": BODIES[body][0],
        "target_arc_degrees": target,
        "birth_jd_tt": birth_tt,
        "natal_longitude": first[1] if first is not None else None,
        "phase_arithmetic_method": PHASE_METHOD,
        "root_method": ROOT_METHOD,
        "station_method": STATION_METHOD,
        "numerical_scope": NUMERICAL_SCOPE,
        "native_return_flag_model": model,
        "body_orbit_source": (
            "swiss_main_asteroid_file"
            if body == "Chiron"
            else "native_planet_ephemeris"
        ),
        "native_flag_scope": (
            "native Earth/correction backend flag; Chiron orbit still requires a Swiss asteroid file"
            if body == "Chiron"
            else "native physical planet backend"
        ),
        "status": (
            "sampled_search_completed"
            if failure is None
            else "partial" if covered_end is not None else "unavailable"
        ),
        "search_start_jd_tt": birth_tt,
        "search_end_jd_tt": end,
        "covered_end_jd_tt": covered_end,
        "failure": failure,
        "contacts": contacts,
        "observed_station_count": len(stations),
        "station_witnesses": stations,
    }


def reference_contact_relation(
    row: dict[str, Any], reference_tt: float | Fraction
) -> str:
    """Compare a declared reference and reported brackets without a sky call."""
    contacts = row["contacts"]
    if row["status"] != "sampled_search_completed":
        return "not_assessed_incomplete_search"
    if not contacts:
        return "no_contact_observed_in_search"
    if reference_tt < contacts[0]["bracket_jd_tt"][0]:
        return "before_first_observed_contact"
    if reference_tt > contacts[-1]["bracket_jd_tt"][1]:
        return "after_last_observed_contact"
    if any(
        a["bracket_jd_tt"][0] <= reference_tt <= a["bracket_jd_tt"][1] for a in contacts
    ):
        return "within_numerical_contact_bracket"
    return "between_observed_contacts"


def reference_contact_policy() -> dict[str, Any]:
    return {
        "method_id": REFERENCE_CONTACT_METHOD,
        "reference_axis": "source_defined_exact_TT_rational",
        "contact_axis": "reported_binary64_TT_bracket_endpoints",
        "reference_path": "cycle_context.reference_ordering.reference.exact_jd_tt",
        "interval_policy": "closed_reported_numerical_brackets",
        "physical_accuracy_certified": False,
        "scope": REFERENCE_CONTACT_SCOPE,
    }


def summary_conventions(
    source: dict[str, Any], ordering: dict[str, Any]
) -> dict[str, Any]:
    """Retain the full convention descriptions in the complete calculation."""
    return {
        "summary_format": SUMMARY_FORMAT,
        "reference_contact_ordering": reference_contact_policy(),
        "arithmetic_scope": ARITHMETIC_SCOPE,
        "numerical_scope": SUMMARY_NUMERICAL_SCOPE,
        "sixth_line_scope": PHASE_SCOPE,
        "source_evidence_scope": cycle_source_summary(source)["scope"],
        "reference_ordering_scope": ordering["scope"],
        "scope": SCOPE,
    }


def _cycle_summary_facts(context: dict[str, Any], profile: str) -> dict[str, Any]:
    scope = SCOPE
    if context["status"] == "not_requested":
        return {
            "status": "not_requested",
            "reference_utc": None,
            "bodies": [],
            "sixth_line": {
                "applicable": "6" in profile.split("/"),
                "phase_status": "not_assessed",
                "current_phase": None,
            },
            "scope": scope,
        }
    if context["ruleset"] != cycle_ruleset():
        raise ValueError("Unknown cycle reference/contact comparison ruleset")
    reference_tt: float | Fraction = context["reference_jd_tt"]
    ratio = context["reference_ordering"]["reference"]["exact_jd_tt"]
    reference_tt = Fraction(int(ratio["numerator"]), int(ratio["denominator"]))
    summaries = []
    contact_keys = (
        "jd_tt",
        "utc_label",
        "utc_label_status",
        "future_leap_seconds_assumed_unchanged",
        "motion",
        "bracket_width_seconds",
        "residual_degrees",
    ) + (("motion_evidence",))
    for row in context["bodies"]:
        contacts = row["contacts"]
        relative = reference_contact_relation(row, reference_tt)
        summaries.append(
            {
                "body": row["body"],
                "status": row["status"],
                "failure": row["failure"],
                "contact_count": len(contacts),
                "reference_relation": relative,
                "contacts": [
                    {
                        k: event.get(k) if k == "motion_evidence" else event[k]
                        for k in contact_keys
                    }
                    for event in contacts
                ],
                "native_return_flag_model": row["native_return_flag_model"],
                "body_orbit_source": row["body_orbit_source"],
                "native_flag_scope": row["native_flag_scope"],
            }
        )
    sixth = "6" in profile.split("/")
    result = {
        "status": context["status"],
        "reference_utc": context["reference_utc"],
        "reference_ordering": {
            key: context["reference_ordering"][key]
            for key in ("method_id", "relation", "input_resolution_seconds", "scope")
        },
        "phase_arithmetic_method": PHASE_METHOD,
        "root_method": ROOT_METHOD,
        "station_method": STATION_METHOD,
        "numerical_scope": (SUMMARY_NUMERICAL_SCOPE),
        "arithmetic_scope": ARITHMETIC_SCOPE,
        "bodies": summaries,
        "sixth_line": {
            "applicable": sixth,
            "phase_status": (
                "unassigned_source_contact_conventions_unresolved"
                if sixth
                else "not_applicable_no_sixth_profile_line"
            ),
            "current_phase": None,
            "traditional_phase_order": (
                [
                    "experience_before_saturn_return",
                    "observation_between_saturn_and_kiron_returns",
                    "role_model_after_kiron_return",
                ]
                if sixth
                else []
            ),
            "scope": PHASE_SCOPE,
        },
        "scope": scope,
        "source_urls": SOURCE_URLS,
        "timing_accuracy_certified": False,
        "source_evidence": cycle_source_summary(context["source_evidence"]),
    }
    result["reference_contact_ordering"] = reference_contact_policy()
    return result


def cycle_summary(context: dict[str, Any], profile: str) -> dict[str, Any]:
    facts = _cycle_summary_facts(context, profile)
    if context["status"] == "not_requested":
        return facts
    return compact_cycle_summary(facts)


def _native_reader(
    body: str,
    require_swiss_files: bool,
    trace: dict[float, Row],
    failures: dict[float, str],
    *,
    source_trace: CycleSourceTrace | None = None,
    source_indices: dict[float, int] | None = None,
) -> Reader:
    def read(t: float) -> Row:
        if source_trace is not None:
            source_trace.check_configuration()
        if t in trace:
            return trace[t]
        if t in failures:
            raise CycleUnavailable(failures[t], t)
        if runtime.swe is None:
            raise RuntimeError("人类图周期需要 Swiss Ephemeris")
        try:
            coords, flags = runtime.ephemeris_call(
                "calc",
                t,
                BODIES[body][0],
                runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
            )
        except EphemerisSourceError:
            raise
        except runtime.swe.Error:
            failures[t] = "native_ephemeris_unavailable"
            raise CycleUnavailable("native_ephemeris_unavailable", t) from None
        row: Row = [t, float(coords[0]), float(coords[3]), flags]
        model = validate_row(row, t, False)
        if source_trace is not None:
            index = source_trace.observe(body, model)
            if source_indices is None:
                raise ValueError(
                    "Cycle source indices are required with a source trace"
                )
            source_indices[t] = index
        trace[t] = row
        return row

    return read


def attach_contact_labels(row: dict[str, Any]) -> None:
    for event in row["contacts"]:
        epoch = epoch_context_at_tt(
            event["jd_tt"], method="human_design_first_cycle_contact_TT"
        )
        context = epoch["time"]
        event.update(
            {
                "utc_label": epoch["utc_label"],
                **{
                    k: context[k]
                    for k in (
                        "utc_label_status",
                        "future_leap_seconds_assumed_unchanged",
                    )
                },
            }
        )


@runtime.preserve_ephemeris_path()
def calculate_cycle_context(
    chart: dict[str, Any],
    reference: str | None,
    *,
    require_swiss_files: bool,
    birth_sources: CycleBirthSources | None = None,
) -> dict[str, Any]:
    if reference is None:
        return {"status": "not_requested"}
    birth_tt = chart["time_scales"]["personality"]["jd_tt"]
    sources = birth_sources.trace if birth_sources is not None else CycleSourceTrace()
    traces: dict[str, dict[float, Row]] = {b: {} for b in BODIES}
    failures_by_body: dict[str, dict[float, str]] = {b: {} for b in BODIES}
    indices_by_body: dict[str, dict[float, int]] = {b: {} for b in BODIES}
    if birth_sources is not None:
        if birth_sources.jd_tt != birth_tt or set(birth_sources.rows) != {
            "Saturn",
            "Uranus",
        }:
            raise EphemerisSourceError("nominal_source_mismatch")
        for body, seed_row in birth_sources.rows.items():
            traces[body][birth_tt] = list(seed_row)
            indices_by_body[body][birth_tt] = birth_sources.indices[body]
    readers = {
        body: _native_reader(
            body,
            require_swiss_files,
            traces[body],
            failures_by_body[body],
            source_trace=sources,
            source_indices=indices_by_body[body],
        )
        for body in BODIES
    }
    # Establish one coherent native natal epoch before any multi-decade scan.
    # Re-entering the same TT after a long scan can change a Swiss cached
    # Uranus result by microarcseconds at1800. Keep exact natal binding; do not
    # hide a source mismatch by widening its equality tolerance.
    for body in BODIES:
        try:
            readers[body](birth_tt)
        except CycleUnavailable:
            # Preserve the single attempted unavailable observation for replay.
            pass
    # Civil-time conversion resets native caches. Preserve the coherent birth
    # observations first; all later root evaluations still use continuous TT.
    label, reference_tt = reference_epoch(reference)
    birth_label = chart["birth_utc"]
    if chart["time_scales"]["personality"]["method"].startswith("continuous_TT"):
        birth_label = None
    ordering = reference_ordering(birth_label, birth_tt, label, reference_tt)
    if ordering["relation"] == "before":
        raise ValueError("周期评估时刻不能早于出生瞬间")
    bodies = []
    for body in BODIES:
        trace = traces[body]
        failures = failures_by_body[body]
        source_indices = indices_by_body[body]
        row = derive_body_contacts(
            body,
            birth_tt,
            readers[body],
            require_swiss_files=require_swiss_files,
        )
        row["origin_source_evidence"] = origin_source_evidence(body)
        if body != "Chiron" and row["natal_longitude"] is not None:
            activation = next(
                a for a in chart["activations"]["personality"] if a["body"] == body
            )
            if (row["natal_longitude"], row["native_return_flag_model"]) != (
                activation["longitude"],
                activation["ephemeris_model"],
            ):
                raise EphemerisSourceError("nominal_source_mismatch")
        attach_contact_labels(row)
        row["evaluation_witnesses"] = [trace[t] for t in sorted(trace)]
        row["evaluation_source_context_indices"] = [
            source_indices[t] for t in sorted(trace)
        ]
        row["unavailable_evaluations"] = [
            {"jd_tt": t, "reason": v} for t, v in sorted(failures.items())
        ]
        bodies.append(row)
    source_evidence = sources.finish()
    return {
        "method_id": "human_design_first_cycle_contacts_v1",
        "status": (
            "computed_finite_search"
            if all(r["status"] == "sampled_search_completed" for r in bodies)
            else "partial"
        ),
        "reference_utc": label,
        "reference_jd_tt": reference_tt,
        "birth_jd_tt": birth_tt,
        "reference_ordering": ordering,
        "origin": "personality_birth_longitude_explicit_computational_convention",
        "step_days_tt": STEP_DAYS,
        "horizon_days_tt": HORIZON_DAYS,
        "continuous_completeness_certified": False,
        "timing_accuracy_certified": False,
        "require_swiss_files": require_swiss_files,
        "source_urls": SOURCE_URLS,
        "ruleset": dict(cycle_ruleset()),
        "scope": SCOPE,
        "bodies": bodies,
        "source_evidence": source_evidence,
        "summary_format": SUMMARY_FORMAT,
        "summary_conventions": summary_conventions(source_evidence, ordering),
    }
