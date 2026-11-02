"""Independent published phase-interval residuals, with no fitted absolute epoch.

NASA UT minute tables are a computed astronomical reference, not direct historical
observations. A coarse independent Sun season anchor only fixes cycle order.
Missing/alignment-uncertain slots remain visible; no residual threshold is fitted.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
)
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_phases import KINDS, source_lunar_phase

DATA = (
    Path(__file__).resolve().parents[1]
    / "data/guolao/nasa-phase-interval-reference-v1.json"
)
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
CELL = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2})(?:\s+([TAHPtnp]))?")


def calendar_jd(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, *, calendar: str
) -> F:
    """Exact noon-based JD; NASA's hybrid civil calendar is selected explicitly."""
    if any(type(v) is not int for v in (year, month, day, hour, minute)):
        raise TypeError("历日各项须为整数，不隐式转换")
    if year < 1 or not 1 <= month <= 12 or not 0 <= hour < 24 or not 0 <= minute < 60:
        raise ValueError("本参考转换只处理正年及有效日内时分")
    if calendar not in ("julian", "gregorian"):
        raise ValueError("须明确儒略历或格里高利历，不以年份猜调用者输入")
    leap = year % 4 == 0 and (
        calendar == "julian" or year % 100 != 0 or year % 400 == 0
    )
    lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not 1 <= day <= lengths[month - 1]:
        raise ValueError("该历制下日期不存在，不自动进位")
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4
    jdn += -32083 if calendar == "julian" else -(y // 100) + y // 400 - 32045
    return F(jdn) - F(1, 2) + F(hour * 60 + minute, 1440)


class _Pre(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.blocks: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            if self.inside:
                raise ValueError("不接收嵌套pre表格")
            self.inside = True
            self.blocks.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.blocks[-1].append(data)


def parse_nasa_century(raw: bytes, start: int) -> dict[str, Any]:
    """Read every fixed-width phase cell; never use a model to fill blank cells."""
    parser = _Pre()
    parser.feed(raw.decode("utf-8"))
    current = None
    events = []
    deltas: dict[int, int] = {}
    for block in parser.blocks:
        for line in "".join(block).splitlines():
            if not line.strip() or "Year" in line and "New Moon" in line:
                continue
            year_field = line[:8].strip()
            if year_field:
                if not re.fullmatch(r"\d{4}", year_field):
                    raise ValueError(f"未识别年份栏：{line!r}")
                current = int(year_field)
                if not start <= current < start + 100:
                    raise ValueError("表内年份超出具名百年范围")
            if current is None:
                raise ValueError("缺年份，不沿用其他页面年份")
            dt = line[76:].strip()
            if dt:
                found = re.fullmatch(r"(\d{2})h(\d{2})m", dt)
                if not found:
                    raise ValueError(f"未识别ΔT：{dt!r}")
                value = int(found[1]) * 60 + int(found[2])
                if current in deltas and deltas[current] != value:
                    raise ValueError("同年ΔT读数冲突，不择值")
                deltas[current] = value
            for index, kind in enumerate(KINDS):
                cell = line[8 + 17 * index : 8 + 17 * (index + 1)].strip()
                if not cell:
                    continue
                match = CELL.fullmatch(cell)
                if not match or match[1] not in MONTHS:
                    raise ValueError(f"未识别相位格：{current} {kind} {cell!r}")
                month, day, hour, minute = MONTHS.index(match[1]) + 1, *map(
                    int, match.group(2, 3, 4)
                )
                mark = match[5]
                allowed = "TAHP" if index == 0 else "tnp" if index == 2 else ""
                if mark and mark not in allowed:
                    raise ValueError("食类标记与相位列不符")
                date = current, month, day
                if (1582, 10, 4) < date < (1582, 10, 15):
                    raise ValueError("NASA混合历制的改历缺日不能补造")
                calendar = "julian" if date <= (1582, 10, 4) else "gregorian"
                jd = calendar_jd(current, month, day, hour, minute, calendar=calendar)
                events.append(
                    {
                        "event_id": f"{current:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{kind}",
                        "year": current,
                        "month": month,
                        "day": day,
                        "hour": hour,
                        "minute": minute,
                        "calendar": calendar,
                        "phase_kind": kind,
                        "eclipse_mark": mark,
                        "jd_ut_exact": str(jd),
                        "source_century_start": start,
                    }
                )
    events.sort(key=lambda e: F(e["jd_ut_exact"]))
    if len({e["event_id"] for e in events}) != len(events):
        raise ValueError("参考事件重复，不能去重后掩盖原始重复")
    annual = Counter(e["year"] for e in events)
    if sorted(annual) != list(range(start, start + 100)) or any(
        not 48 <= v <= 51 for v in annual.values()
    ):
        raise ValueError("未完整读取百年相位，不跳过缺行")
    if sorted(deltas) != list(range(start, start + 100)):
        raise ValueError("缺年度ΔT记录")
    beginning = calendar_jd(
        start, 1, 1, calendar="julian" if start < 1583 else "gregorian"
    )
    ending = calendar_jd(
        start + 100, 1, 1, calendar="julian" if start + 100 < 1583 else "gregorian"
    )
    if (
        not 0 <= F(events[0]["jd_ut_exact"]) - beginning < 11
        or not 0 < ending - F(events[-1]["jd_ut_exact"]) < 11
    ):
        raise ValueError("百年起止端相位覆盖不完整，不把丢失的首尾格当成正常空格")
    for a, b in zip(events, events[1:]):
        gap = F(b["jd_ut_exact"]) - F(a["jd_ut_exact"])
        if (
            KINDS[(KINDS.index(a["phase_kind"]) + 1) % 4] != b["phase_kind"]
            or not 4 < gap < 11
        ):
            raise ValueError("相位顺序或间隔异常，不能排序替代缺失事件")
    return {
        "century_start": start,
        "events": events,
        "delta_t_minutes_by_year": {str(k): v for k, v in sorted(deltas.items())},
        "html_sha256": hashlib.sha256(raw).hexdigest(),
    }


def winter_anchor(winter_year: int, delta_t_minutes: int) -> dict[str, Any]:
    """Moshier Sun only, TT to NASA-header UT at minute display resolution."""
    import swisseph as swe

    a = float(calendar_jd(winter_year, 12, 15, calendar="gregorian"))
    b = float(calendar_jd(winter_year, 12, 30, calendar="gregorian"))

    def longitude(jd: float) -> float:
        position, flag = ephemeris_call("calc", jd, swe.SUN, swe.FLG_MOSEPH)
        if ephemeris_model_from_retflag(flag) != "moshier":
            raise ValueError("季节对齐未使用声明的Moshier模型，不静默改用其他星历")
        return float(position[0]) - 270

    if not longitude(a) < 0 < longitude(b):
        raise ValueError("独立冬至未被预定12月窗口夹住，不移动窗口追拟结果")
    for _ in range(64):
        mid = (a + b) / 2
        if mid == a or mid == b:
            break
        if longitude(mid) < 0:
            a = mid
        else:
            b = mid
    tt_minute = round((a + b) / 2 * 1440)
    return {
        "backend": "moshier_sun_only",
        "winter_year": winter_year,
        "tt_jd_minute_count": tt_minute,
        "delta_t_from_nasa_annual_header_minutes": delta_t_minutes,
        "approximate_ut_jd_exact": str(F(tt_minute - delta_t_minutes, 1440)),
        "anchor_display_and_alignment_resolution_minutes": 1,
        "absolute_source_epoch_calibrated": False,
    }


def _display(value: F) -> str:
    with localcontext() as ctx:
        ctx.prec = 70
        return format(Decimal(value.numerator) / Decimal(value.denominator), ".6f")


def compare_phase_intervals(reference: dict[str, Any], elapsed: int) -> dict[str, Any]:
    if type(elapsed) is not int or elapsed not in reference["source_elapsed_years"]:
        raise ValueError("仅比较事先声明的年份，不自动挑选吻合年份")
    source_year = elapsed + 1281
    winter_year = source_year - 1
    anchor = winter_anchor(
        winter_year, reference["delta_t_minutes_by_year"][str(winter_year)]
    )
    winter = F(anchor["approximate_ut_jd_exact"])
    events = reference["events"]
    new_moons = [e for e in events if e["phase_kind"] == "new_moon"]
    prior = [e for e in new_moons if F(e["jd_ut_exact"]) < winter]
    following = [e for e in new_moons if F(e["jd_ut_exact"]) >= winter]
    if not prior or not following:
        raise ValueError("固定参考窗口缺冬至两侧新月，不从模型补参考")
    previous, next_moon = prior[-1], following[0]
    start = next(
        i for i, e in enumerate(events) if e["event_id"] == previous["event_id"]
    )
    selected = events[start : start + 72]
    if len(selected) != 72 or [e["phase_kind"] for e in selected] != [
        KINDS[i % 4] for i in range(72)
    ]:
        raise ValueError("参考相位链不完整，不用其他循环填洞")
    if any(
        not 4 < F(b["jd_ut_exact"]) - F(a["jd_ut_exact"]) < 11
        for a, b in zip(selected, selected[1:])
    ):
        raise ValueError("固定窗口内参考链有断口，不跨窗口拼接相位")
    middle = shoushi_winter_cycle(elapsed).zhongji_days
    source = [source_lunar_phase(middle, i) for i in range(72)]
    gap = -F(source[0]["mean_phase_offset_from_winter_days_exact"])
    mean_guard = F(2) < gap < F("29.530593") - 2
    ref_guard = (
        winter - F(previous["jd_ut_exact"]) > 2
        and F(next_moon["jd_ut_exact"]) - winter > 2
    )
    aligned = mean_guard and ref_guard
    offsets = [e["research_phase_offset_from_winter_days_exact"] for e in source]
    rows = []
    residuals = []
    for index, (computed, expected, value) in enumerate(
        zip(source, selected, offsets, strict=True)
    ):
        residual = span = actual_span = None
        if index == 0:
            status = "anchor_excluded_from_interval_statistics"
        elif value is None:
            status = "source_time_unavailable"
        elif offsets[0] is None:
            status = "source_anchor_time_unavailable"
        elif not aligned:
            status = "cycle_alignment_unresolved"
        else:
            span = F(value) - F(offsets[0])
            actual_span = F(expected["jd_ut_exact"]) - F(selected[0]["jd_ut_exact"])
            residual = (span - actual_span) * 1440
            residuals.append(residual)
            status = "interval_residual_measured"
        rows.append(
            {
                "phase_index": index,
                "phase_kind": computed["phase_kind"],
                "reference_event_id": expected["event_id"],
                "reference_calendar": expected["calendar"],
                "source_phase_offset_days_exact": value,
                "source_phase_time_available": value is not None,
                "source_anchor_time_available": offsets[0] is not None,
                "cycle_alignment_resolved": aligned,
                "source_interval_days_exact": str(span) if span is not None else None,
                "reference_ut_interval_days_exact": (
                    str(actual_span) if actual_span is not None else None
                ),
                "residual_minutes_exact": (
                    str(residual) if residual is not None else None
                ),
                "residual_minutes_display": (
                    _display(residual) if residual is not None else None
                ),
                "status": status,
            }
        )
    absolute = sorted(abs(v) for v in residuals)
    summary = None
    if absolute:
        n = len(absolute)
        median = (
            absolute[n // 2] if n % 2 else (absolute[n // 2 - 1] + absolute[n // 2]) / 2
        )
        summary = {
            "compared_intervals": n,
            "mean_absolute_minutes": _display(sum(absolute, F()) / n),
            "median_absolute_minutes": _display(median),
            "maximum_absolute_minutes": _display(absolute[-1]),
        }
    return {
        "model_id": "guolao_nasa_relative_phase_interval_comparison_v1",
        "elapsed_years": elapsed,
        "source_year": source_year,
        "independent_winter_alignment": anchor,
        "source_mean_gap_days_exact": str(gap),
        "source_mean_guard_passed": mean_guard,
        "reference_guard_passed": ref_guard,
        "cycle_alignment_resolved_under_declared_policy": aligned,
        "reference_new_moon_before_winter": previous["event_id"],
        "reference_new_moon_after_winter": next_moon["event_id"],
        "declared_positions": 72,
        "source_unavailable_phase_indices_independent_of_alignment": [
            i for i, value in enumerate(offsets) if value is None
        ],
        "planned_nonanchor_interval_positions": 71,
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "descriptive_residuals": summary,
        "rows": rows,
        "anchor_zero_counted_as_accurate": False,
        "absolute_source_epoch_fitted_or_calibrated": False,
        "missing_or_unaligned_slots_counted_as_passes": False,
        "physical_absolute_phase_time_validated": False,
        "independent_direct_observation_claimed": False,
        "real_world_prediction_subjects": 0,
    }


def audit_phase_reference() -> dict[str, Any]:
    raw = DATA.read_bytes()
    reference = json.loads(raw)
    cases = [
        compare_phase_intervals(reference, year)
        for year in reference["source_elapsed_years"]
    ]
    counts: Counter[str] = Counter()
    for case in cases:
        counts.update(case["status_counts"])
    return {
        "model_id": "guolao_nasa_phase_interval_reference_audit_v1",
        "reference_data_sha256": hashlib.sha256(raw).hexdigest(),
        "declared_cases": len(cases),
        "declared_positions": len(cases) * 72,
        "planned_nonanchor_interval_positions": len(cases) * 71,
        "source_time_unavailable_independent_of_alignment": sum(
            len(case["source_unavailable_phase_indices_independent_of_alignment"])
            for case in cases
        ),
        "counts": dict(sorted(counts.items())),
        "descriptive_interval_residuals_by_phase_minutes": {
            kind: residual_summary(
                [
                    F(row["residual_minutes_exact"])
                    for case in cases
                    for row in case["rows"]
                    if row["phase_kind"] == kind
                    and row["status"] == "interval_residual_measured"
                ]
            )
            for kind in KINDS
        },
        "cases": cases,
        "retrospectively_fitted_pass_tolerance": None,
        "physical_absolute_phase_time_validated": False,
        "real_world_prediction_subjects": 0,
    }


def residual_summary(residuals: list[F]) -> dict[str, Any] | None:
    """Descriptive residuals only: no fitted acceptance threshold."""
    absolute = sorted(abs(v) for v in residuals)
    if not absolute:
        return None
    n = len(absolute)
    median = (
        absolute[n // 2] if n % 2 else (absolute[n // 2 - 1] + absolute[n // 2]) / 2
    )
    return {
        "sample_count": n,
        "mean_signed_minutes": _display(sum(residuals, F()) / n),
        "mean_absolute_minutes": _display(sum(absolute, F()) / n),
        "median_absolute_minutes": _display(median),
        "maximum_absolute_minutes": _display(absolute[-1]),
    }


def audit_modern_phase_reference() -> dict[str, Any]:
    """Diagnostic model agreement in fixed TT windows, not an unseen holdout.

    The reference's UT and annual Delta-T headers are both minute rounded. Their
    sum is a coarse TT reference, not an independently observed exact event TT.
    """
    from fatebridge.core.lunar_phase_events import phase_events_tt

    raw = DATA.read_bytes()
    reference = json.loads(raw)
    intervals: list[tuple[F, F]] = []
    for n in reference["source_elapsed_years"]:
        year = n + 1281
        start = calendar_jd(year - 1, 11, 1, calendar="gregorian")
        end = calendar_jd(year + 1, 7, 1, calendar="gregorian")
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = intervals[-1][0], max(end, intervals[-1][1])
        else:
            intervals.append((start, end))
    cases = []
    all_residuals: dict[str, list[F]] = {k: [] for k in KINDS}
    for start, end in intervals:
        computed = phase_events_tt(float(start), float(end))
        expected = []
        for e in reference["events"]:
            tt = F(e["jd_ut_exact"]) + F(
                reference["delta_t_minutes_by_year"][str(e["year"])], 1440
            )
            if start <= tt < end:
                expected.append({**e, "coarse_reference_tt_jd_exact": str(tt)})
        complete = [e["phase_kind"] for e in computed["events"]] == [
            e["phase_kind"] for e in expected
        ]
        rows = []
        if complete:
            for actual, ref in zip(computed["events"], expected, strict=True):
                residual = (
                    F(actual["julian_day_tt_exact"])
                    - F(ref["coarse_reference_tt_jd_exact"])
                ) * 1440
                all_residuals[actual["phase_kind"]].append(residual)
                rows.append(
                    {
                        **actual,
                        "reference_event_id": ref["event_id"],
                        "coarse_reference_tt_jd_exact": ref[
                            "coarse_reference_tt_jd_exact"
                        ],
                        "residual_minutes_exact": str(residual),
                        "residual_minutes_display": _display(residual),
                    }
                )
        cases.append(
            {
                "window_tt_jd_exact": [str(start), str(end)],
                "status": (
                    "ordinal_phase_sequence_complete"
                    if complete
                    else "reference_model_sequence_mismatch"
                ),
                "computed_count": len(computed["events"]),
                "reference_count": len(expected),
                "rows": rows,
                "unmatched_computed_events": [] if complete else computed["events"],
                "unmatched_reference_events": [] if complete else expected,
            }
        )
    return {
        "model_id": "guolao_modern_moshier_nasa_phase_diagnostic_v1",
        "reference_data_sha256": hashlib.sha256(raw).hexdigest(),
        "source_windows_before_merge": len(reference["source_elapsed_years"]),
        "merged_windows": len(cases),
        "reference_unique_events": len(reference["events"]),
        "compared_unique_events": sum(len(v) for v in all_residuals.values()),
        "unresolved_windows": sum(
            c["status"] != "ordinal_phase_sequence_complete" for c in cases
        ),
        "descriptive_absolute_event_residuals_by_phase_minutes": {
            k: residual_summary(v) for k, v in all_residuals.items()
        },
        "cases": cases,
        "comparison_timescale": "TT relative to NASA UT plus minute-rounded annual DeltaT header",
        "same_reference_previously_used_for_source_diagnosis": True,
        "unseen_holdout_claimed": False,
        "retrospectively_fitted_pass_tolerance": None,
        "source_parameters_changed_or_model_substituted_in_source_profile": False,
        "direct_observations": False,
        "real_world_prediction_subjects": 0,
    }
