"""Exact three-shadow reconstruction of Li2013's declared Yuan-shi cohort.

Noon symmetry and linear interpolation are historical approximations. Exact
fractions preserve their arithmetic; they do not remove observational error.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core import guolao_calendar_date_bridge as bridge
from fatebridge.core import guolao_year_labels

DATA = Path(__file__).resolve().parents[1] / "data/guolao/gnomon-epoch-v1.json"
PROFILE = "li2013_yuanshi_three_shadow_v1"
READING_PROFILE = "li2013_nlc38_triad71_reading_v1"
PROFILES = (PROFILE, READING_PROFILE)
COLLATION_DATA = DATA.with_name("gnomon-epoch-collation-v1.json")
MODES = ("before1_after2", "before2_after1")
CLOCK_POLICY = "100_ke_24_equal_half_shichen_full_ke_bins"
NOON_BASIS = "source_meridian_transit_noon_as_half_day"
SEASONS = ("winter1277", "summer1278", "winter1278", "summer1279", "winter1279")


def three_shadow_elapsed(
    days: tuple[int, ...],
    shadows: tuple[F, ...],
    *,
    mode: str,
    noon_basis: str,
) -> dict[str, Any]:
    """Elapsed source days from A's midnight; modes must be declared."""
    if len(days) != 3 or any(type(v) is not int for v in days):
        raise TypeError("三个观测日须为明确整数序号")
    if len(shadows) != 3 or any(not isinstance(v, F) for v in shadows):
        raise TypeError("三个同单位影长须为精确Fraction")
    if not days[0] < days[1] < days[2] or any(v <= 0 for v in shadows):
        raise ValueError("观测日须递增且影长为正，不排序或替换原观测")
    if mode not in MODES or noon_basis != NOON_BASIS:
        raise ValueError("须明确具名三日法和从中天到夜半的半日约定")
    a, b, c = shadows
    m = days[2] - days[0]
    if mode == MODES[0]:
        if days[2] - days[1] != 1:
            raise ValueError("前1后2型要求后两次观测相邻，不把间隔偷换为一日")
        slope = c - b
        if slope == 0:
            raise ValueError("相邻观测影差为零，不能插算或猜测节气")
        ratio = (a - c) / slope
        equal_shadow_day = F(m) + ratio
        bracketed = m - 1 <= equal_shadow_day <= m
        elapsed = F(1, 2) + equal_shadow_day / 2
    else:
        if days[1] - days[0] != 1:
            raise ValueError("前2后1型要求前两次观测相邻，不把间隔偷换为一日")
        slope = b - a
        if slope == 0:
            raise ValueError("相邻观测影差为零，不能插算或猜测节气")
        ratio = (c - a) / slope
        equal_shadow_day = ratio
        bracketed = 0 <= equal_shadow_day <= 1
        elapsed = F(1, 2) + (m + ratio) / 2
    return {
        "mode": mode,
        "noon_basis": noon_basis,
        "span_days": m,
        "adjacent_shadow_difference_exact": str(slope),
        "linear_ratio_exact": str(ratio),
        "equal_shadow_point_elapsed_from_A_noon_exact": str(equal_shadow_day),
        "equal_shadow_point_inside_adjacent_pair": bracketed,
        "elapsed_from_A_midnight_source_days_exact": str(elapsed),
        "noon_to_midnight_half_day_included": True,
        "linear_shadow_symmetry_is_exact_solar_motion": False,
        "physical_julian_day": None,
        "timezone": None,
    }


def source_clock_bin(
    branch: str, half: str, ke: int, *, clock_policy: str
) -> dict[str, Any]:
    """Declared full-ke bin; do not collapse it into its comparison midpoint.

    Zi-chu is retained before Zi-zheng on this unwrapped clock, with no guessed
    Ganzhi day rollover. Fourth-ke small subdivisions are not reconstructed.
    """
    if clock_policy != CLOCK_POLICY:
        raise ValueError("须声明百刻与二十四半时的区间约定")
    if branch not in bridge.BRANCHES or len(branch) != 1 or half not in ("初", "正"):
        raise ValueError("须明确地支及初正")
    if type(ke) is not int:
        raise TypeError("刊刻编号须为整数")
    if not 0 <= ke <= 3:
        raise ValueError("仅复原初初至三刻的完整刻区间，四刻小刻尚未裁定")
    half_index = 2 * bridge.BRANCHES.index(branch) - (half == "初")
    start = F(half_index, 24) + F(ke, 100)
    end = start + F(1, 100)
    return {
        "clock_policy": clock_policy,
        "day_reference": "unwrapped_from_zi_zheng_midnight",
        "start_source_day_fraction_exact": str(start),
        "end_source_day_fraction_exact": str(end),
        "membership": "start_inclusive_end_exclusive",
        "comparison_midpoint_source_day_fraction_exact": str((start + end) / 2),
        "midpoint_is_exact_observed_instant": False,
        "actual_solar_or_mean_clock_calibrated": False,
        "physical_julian_day": None,
        "timezone": None,
    }


class GnomonEpoch:
    def __init__(
        self,
        source: dict[str, Any],
        fingerprint: str,
        profile: str,
        reading: dict[str, Any] | None = None,
        reading_fingerprint: str | None = None,
    ):
        self.source = source
        self.fingerprint = fingerprint
        self.profile = profile
        self.reading = reading
        self.reading_fingerprint = reading_fingerprint
        self.date_bridge = bridge.load_calendar_date_bridge(bridge.PROFILE)
        self.observations = {
            int(v["observation_id"]): v for v in source["observations"]
        }

    def triad(self, season: str, case_id: int) -> dict[str, Any]:
        if season not in SEASONS:
            raise ValueError("未支持的具名二至，不能换样本以凑合结果")
        if type(case_id) is not int:
            raise TypeError("刊表算例编号须为整数")
        matches = [
            v
            for v in self.source["triads"]
            if v["season"] == season and int(v["case_id"]) == case_id
        ]
        if len(matches) != 1:
            raise ValueError("未找到唯一具名三日组，不补观测或挑近似组")
        published_row = matches[0]
        row = dict(published_row)
        if self.reading is not None and season == "winter1279" and case_id == 25:
            row["A"] = str(self.reading["declared_A"])
        observations = [self.observations[int(row[k])] for k in ("A", "B", "C")]
        labels = [
            list(map(int, v["printed_calendar_date"].split("-"))) for v in observations
        ]
        days = tuple(
            bridge.calendar_label_noon_jdn(*v, calendar=bridge.CALENDARS[1])
            for v in labels
        )
        arithmetic = three_shadow_elapsed(
            days,
            tuple(F(v["shadow_zhang"]) for v in observations),
            mode=row["mode"],
            noon_basis=NOON_BASIS,
        )
        serial = F(days[0]) + F(arithmetic["elapsed_from_A_midnight_source_days_exact"])
        cycle = (serial - self.date_bridge.anchor_serial) % 60
        result = {
            "profile_id": self.profile,
            "source_data_sha256": self.fingerprint,
            "published_row": published_row,
            "observations": observations,
            "calendar_policy": self.source["method_policy"]["source_calendar_policy"],
            "arithmetic": arithmetic,
            "span_matches_published": arithmetic["span_days"] == int(row["span_days"]),
            "conditional_label_serial_with_source_fraction_exact": str(serial),
            "source_cycle_day_exact": str(cycle),
            "printed_cycle_day": row["printed_cycle_day"],
            "calculated_minus_printed_source_days_exact": str(
                cycle - F(row["printed_cycle_day"])
            ),
            "within_published_half_unit": abs(cycle - F(row["printed_cycle_day"]))
            <= F(1, 20000),
            "source_day_fraction_exact": str(serial % 1),
            "conditional_julian_date": bridge.calendar_label_from_noon_jdn(
                serial.numerator // serial.denominator, calendar=bridge.CALENDARS[1]
            ),
            "same_source_noons_equivalent_to_equal_TT_intervals": False,
            "source_clock_to_modern_epoch_calibrated": False,
            "physical_julian_day": None,
            "timezone": None,
        }
        if self.reading is not None:
            result["declared_reading"] = {
                "collation_source_data_sha256": self.reading_fingerprint,
                "applied_row": row,
                "published_row_changed": False,
                "observed_after_first_domain_comparison": True,
                "primary_witness": self.reading["primary_witness"],
            }
        return result

    def season_mean(self, season: str) -> dict[str, Any]:
        if season not in SEASONS:
            raise ValueError("未支持的具名二至")
        rows = [
            self.triad(season, int(v["case_id"]))
            for v in self.source["triads"]
            if v["season"] == season
        ]
        mean_serial = sum(
            (F(v["conditional_label_serial_with_source_fraction_exact"]) for v in rows),
            F(),
        ) / len(rows)
        cycle = (mean_serial - self.date_bridge.anchor_serial) % 60
        reference = next(
            v for v in self.source["season_means"] if v["season"] == season
        )
        clock = source_clock_bin(
            reference["branch"],
            reference["half"],
            int(reference["ke"]),
            clock_policy=CLOCK_POLICY,
        )
        fraction = cycle - int(F(reference["printed_mean_cycle_day"]))
        lower = F(clock["start_source_day_fraction_exact"])
        upper = F(clock["end_source_day_fraction_exact"])
        return {
            "profile_id": self.profile,
            "source_data_sha256": self.fingerprint,
            "collation_source_data_sha256": self.reading_fingerprint,
            "season": season,
            "triad_count": len(rows),
            "all_rows_retained_no_error_based_selection": True,
            "mean_source_cycle_day_exact": str(cycle),
            "published_reference": reference,
            "mean_minus_published_mean_source_days_exact": str(
                cycle - F(reference["printed_mean_cycle_day"])
            ),
            "mean_within_published_half_unit": abs(
                cycle - F(reference["printed_mean_cycle_day"])
            )
            <= F(1, 20000),
            "printed_clock_bin": clock,
            "mean_inside_printed_clock_bin": lower <= fraction < upper,
            "mean_minus_clock_midpoint_nominal_minutes_exact": str(
                (fraction - F(clock["comparison_midpoint_source_day_fraction_exact"]))
                * 1440
            ),
            "published_modern_minus_mean_nominal_minutes_exact": str(
                (F(reference["printed_modern_cycle_day"]) - cycle) * 1440
            ),
            "paper_modern_values_recomputed_with_independent_ephemeris": False,
            "triads_are_independent_observations_of_season_time": False,
            "physical_epoch_calibrated": False,
        }


def load_gnomon_epoch(profile: str) -> GnomonEpoch:
    if profile not in PROFILES:
        raise ValueError("须选择具名三日法资料，不能匿名替换观测")
    blob = DATA.read_bytes()
    source = json.loads(blob)
    policy = source["method_policy"]
    if (
        source["profile_id"] != PROFILE
        or source["schema"] != PROFILE
        or policy["source_noon_offset_day"] != "1/2"
        or policy["clock_policy"] != CLOCK_POLICY
        or policy["paper_table2_comparison_half_unit_day"] != "1/20000"
        or policy["paper_table3_mean_comparison_half_unit_day"] != "1/20000"
        or policy["source_calendar_policy"]
        != "proleptic_julian_reconstruction_of_published_pre1582_public_calendar_dates"
        or source["date_bridge_data_sha256"]
        != hashlib.sha256(bridge.DATA.read_bytes()).hexdigest()
        or source["source_year_data_sha256"]
        != hashlib.sha256(guolao_year_labels.DATA.read_bytes()).hexdigest()
        or len(source["observations"]) != 98
        or len(source["triads"]) != 75
        or len(source["season_means"]) != 6
        or source["used_in_native_birth_chart"] is not False
        or source["physical_epoch_calibrated"] is not False
    ):
        raise ValueError("具名来源、日界或完整样本数改变，不改常数或删组以凑合结果")
    fingerprint = hashlib.sha256(blob).hexdigest()
    reading = None
    reading_fingerprint = None
    if profile == READING_PROFILE:
        reading_blob = COLLATION_DATA.read_bytes()
        reading_fingerprint = hashlib.sha256(reading_blob).hexdigest()
        reading = json.loads(reading_blob)
        if (
            reading["profile_id"] != READING_PROFILE
            or reading["base_data_sha256"] != fingerprint
            or reading["printed_A"] != 77
            or reading["declared_A"] != 71
            or reading["season"] != "winter1279"
            or reading["case_id"] != 25
            or reading["observed_after_first_domain_comparison"] is not True
            or reading["paper_row_replaced_in_base_data"] is not False
            or reading["physical_epoch_calibrated"] is not False
        ):
            raise ValueError("原页校读声明与固定来源不一致，不静默改刊值")
    return GnomonEpoch(source, fingerprint, profile, reading, reading_fingerprint)
