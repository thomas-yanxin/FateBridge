"""Named source-day bridge with explicit origin and side reconstructions.

Gujin36 defines noon accumulation relative to a solstice event. Applying the
same coordinate subtraction to midnight is declared as a reconstruction.
Calendar-event time and position must agree before choosing a night-table side.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_daily_solar import POLICIES
from fatebridge.core.guolao_midnight_anchors import PROFILE as ANCHOR_PROFILE
from fatebridge.core.guolao_midnight_anchors import (
    RATE_POLICIES,
    RecomputedMidnightSolar,
    load_recomputed_midnight,
)
from fatebridge.core.guolao_solar_fold import PROFILES as FOLD_PROFILES
from fatebridge.core.guolao_solar_fold import (
    TABLE_PROFILES,
    SourceSolarFold,
    load_source_fold,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/source-solar-day-v1.json"
PROFILE = "gujin318_source_solar_day_reconstruction_v1"
SIDE_POLICY = "gujin43_time_and_position_intervals_reconstruction"
INPUTS = (
    "daily-solar-motion-v1.json",
    "solar-generation-v1.json",
    "midnight-anchors-v1.json",
    "half-night-tables-v1.json",
    "solar-fold-v1.json",
)


@dataclass(frozen=True)
class NamedSourceSolarDay:
    anchor_model: RecomputedMidnightSolar
    daily_policy: str
    fold_model: SourceSolarFold
    table_profile: str
    policy_data_sha256: str
    input_hashes_json: str
    origin_definition_url: str
    first_midnight: F
    event_times: tuple[F, ...]
    event_positions: tuple[F, ...]

    def side_at(self, source_day: F, position_du: F) -> dict[str, Any]:
        if not isinstance(source_day, F) or not isinstance(position_du, F):
            raise TypeError("源时刻及坐标须为明确Fraction，不从民用日期或浮点猜测")
        time_side = position_side = None
        if source_day < self.event_times[0]:
            status = "before_named_winter_event"
        elif source_day > self.event_times[-1]:
            status = "after_named_next_winter_event"
        elif not self.event_positions[0] <= position_du <= self.event_positions[-1]:
            status = "solar_position_outside_named_event_frame"
        elif source_day in (
            self.event_times[1],
            self.event_times[3],
        ) or position_du in (self.event_positions[1], self.event_positions[3]):
            status = "exact_equinox_boundary_unassigned"
        else:
            time_side = (
                "inside"
                if self.event_times[1] < source_day < self.event_times[3]
                else "outside"
            )
            position_side = (
                "inside"
                if self.event_positions[1] < position_du < self.event_positions[3]
                else "outside"
            )
            status = (
                "consistent_reconstruction"
                if time_side == position_side
                else "source_time_position_side_disagreement"
            )
        return {
            "policy": SIDE_POLICY,
            "status": status,
            "source_day_exact": str(source_day),
            "solar_position_du_exact": str(position_du),
            "time_interval_side": time_side,
            "coordinate_interval_side": position_side,
            "selected_side": (
                time_side if status == "consistent_reconstruction" else None
            ),
            "reconstruction_classically_or_physically_accepted": False,
            "cardinal_midnight_segment_name_used_as_solar_side": False,
            "disagreement_resolved_by_selecting_favorable_side": False,
        }

    def audit(self) -> dict[str, Any]:
        critical = (
            F(),
            self.fold_model.threshold,
            self.fold_model.half_year,
            self.fold_model.half_year + self.fold_model.threshold,
            2 * self.fold_model.half_year,
        )
        return {
            "model_id": PROFILE,
            "profile_id": PROFILE,
            "policy_data_sha256": self.policy_data_sha256,
            "input_data_sha256": json.loads(self.input_hashes_json),
            "anchor_rate_policy": self.anchor_model.rate_policy,
            "daily_difference_policy": self.daily_policy,
            "fold_profile": self.fold_model.profile_id,
            "night_table_profile": self.table_profile,
            "side_policy": SIDE_POLICY,
            "basis": "dadu_source_table",
            "origin_definition_url": self.origin_definition_url,
            "origin_transfer_from_noon_to_midnight_is_reconstruction": True,
            "source_winter_event_position_du_exact": str(self.event_positions[0]),
            "cardinal_event_frames": [
                {
                    "index": i,
                    "source_day_exact": str(t),
                    "position_from_ji_start_du_exact": str(pos),
                    "accumulation_from_winter_event_du_exact": str(
                        pos - self.event_positions[0]
                    ),
                    "fold_critical_value_exact": str(c),
                    "event_accumulation_minus_fold_critical_du_exact": str(
                        pos - self.event_positions[0] - c
                    ),
                }
                for i, (t, pos, c) in enumerate(
                    zip(self.event_times, self.event_positions, critical, strict=True)
                )
            ],
            "source_midnight_component_output_is_retained_without_rewriting": True,
            "automatic_previous_year_origin_added": False,
            "source_side_and_origin_reconstructions_accepted": False,
            "same_source_day_location_and_clock_relation_accepted": False,
            "modern_calendar_date_assigned": False,
            "physical_sunrise_validated": False,
            "phase_day_or_birth_chart_backfilled": False,
        }

    def day(self, index: int) -> dict[str, Any]:
        if type(index) is not int:
            raise TypeError("仅接收具名原历整数日序，不强转布尔、浮点或现代JD")
        midnight = self.anchor_model.day(index, policy=self.daily_policy)
        source_time = self.first_midnight + index
        position = F(midnight["midnight_unwrapped_from_ji_start_du_exact"])
        relative = position - self.event_positions[0]
        side = self.side_at(source_time, position)
        result = None
        status = side["status"]
        if status == "consistent_reconstruction":
            if not 0 <= relative <= 2 * self.fold_model.half_year:
                status = "relative_accumulation_outside_declared_fold_cycle"
            else:
                result = self.fold_model.sunrise(
                    relative,
                    origin_reference=f"{self.origin_definition_url};midnight_transfer_reconstruction;data={self.policy_data_sha256}",
                    table_profile=self.table_profile,
                    solar_side=side["selected_side"],
                    basis="dadu_source_table",
                )
                status = result["status"]
        return {
            "model_id": PROFILE,
            "profile_id": PROFILE,
            "status": status,
            "policy_data_sha256": self.policy_data_sha256,
            "anchor_rate_policy": self.anchor_model.rate_policy,
            "daily_difference_policy": self.daily_policy,
            "fold_profile": self.fold_model.profile_id,
            "night_table_profile": self.table_profile,
            "side_policy": SIDE_POLICY,
            "basis": "dadu_source_table",
            "source_day_index": index,
            "source_midnight_day_exact": str(source_time),
            "source_midnight_result": midnight,
            "coordinate_transfer": {
                "input_frame": "unwrapped_from_ji_start",
                "output_frame": "relative_to_same_named_winter_solstice_event",
                "input_position_du_exact": str(position),
                "subtracted_winter_event_position_du_exact": str(
                    self.event_positions[0]
                ),
                "relative_accumulation_du_exact": str(relative),
                "origin_definition_url": self.origin_definition_url,
                "noon_origin_definition_transferred_to_midnight_as_reconstruction": True,
                "previous_year_or_modulo_repair_applied": False,
            },
            "solar_side_reconstruction": side,
            "fold_and_sunrise_result": result,
            "folded_sunrise_argument": (
                result["fold"]["folded_table_argument_du_exact"] if result else None
            ),
            "usable_source_sunrise_fraction_exact": (
                result["usable_source_sunrise_fraction_exact"] if result else None
            ),
            "source_side_and_origin_reconstructions_accepted": False,
            "same_source_day_location_and_clock_relation_accepted": False,
            "modern_calendar_date_assigned": False,
            "physical_sunrise_validated": False,
            "phase_day_or_birth_chart_backfilled": False,
        }


def load_named_source_solar_day(
    profile: str,
    *,
    anchor_rate_policy: str,
    daily_policy: str,
    fold_profile: str,
    table_profile: str,
    side_policy: str,
    basis: str,
) -> NamedSourceSolarDay:
    if (
        profile != PROFILE
        or anchor_rate_policy not in RATE_POLICIES
        or daily_policy not in POLICIES
        or fold_profile not in FOLD_PROFILES
        or table_profile not in TABLE_PROFILES
        or side_policy != SIDE_POLICY
        or basis != "dadu_source_table"
    ):
        raise ValueError(
            "须明确具名算例、选率、日差、折叠、半夜分表、内外重构及大都基准"
        )
    blob = DATA.read_bytes()
    raw = json.loads(blob)
    if raw.get("schema") != PROFILE or raw.get("profile_id") != PROFILE:
        raise ValueError("未核对的原历日太阳衔接版本")
    if (
        raw.get("origin_policy")
        != "subtract_same_named_winter_event_unwrapped_coordinate"
        or raw.get("side_policy") != SIDE_POLICY
    ):
        raise ValueError("源积度起点或内外口径改变，不能沿用同一版本")
    hashes = raw["input_data_sha256"]
    if set(hashes) != set(INPUTS):
        raise ValueError("源组件输入指纹不全，不能静默混用版本")
    for name in INPUTS:
        if (
            hashlib.sha256((DATA.parent / name).read_bytes()).hexdigest()
            != hashes[name]
        ):
            raise ValueError(f"源组件{name}已变化，不自动重新基准化整条计算链")
    source = json.loads((DATA.parent / "daily-solar-motion-v1.json").read_bytes())
    first = F(source["source_first_midnight_day"])
    operands = source["source_subtraction_components"]
    times = tuple(
        first + offset + F(fraction)
        for offset, fraction in zip(
            source["integer_day_offsets"],
            operands["event_fraction_of_source_day"],
            strict=True,
        )
    )
    positions = tuple(F(v) for v in operands["event_unwrapped_du"])
    if (
        len(times) != 5
        or len(positions) != 5
        or any(
            b <= a for values in (times, positions) for a, b in zip(values, values[1:])
        )
    ):
        raise ValueError("具名四正源时刻或位置顺序不符，不重排或补缺")
    return NamedSourceSolarDay(
        load_recomputed_midnight(ANCHOR_PROFILE, rate_policy=anchor_rate_policy),
        daily_policy,
        load_source_fold(fold_profile),
        table_profile,
        hashlib.sha256(blob).hexdigest(),
        json.dumps(hashes, sort_keys=True),
        raw["origin_definition_url"],
        first,
        times,
        positions,
    )
