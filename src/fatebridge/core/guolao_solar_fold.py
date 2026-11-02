"""Explicit source numeric folding, with separate named textual readings.

Qizheng's official witness says 歲象限; Gujin37 says only 象限. A celestial
quadrant reading of the latter is a hypothesis, not an emendation of either.
No civil date, absolute mansion coordinate or winter origin is inferred.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_sunrise import DATA as NIGHT_DATA
from fatebridge.core.guolao_sunrise import load_table

DATA = Path(__file__).resolve().parents[1] / "data/guolao/solar-fold-v1.json"
PROFILES = (
    "qizheng_inner_sui_quadrant",
    "gujin37_half_year_celestial_quadrant_hypothesis",
)
TABLE_PROFILES = ("gujin37_siku", "yuanshi55_digital")


def _number(value: str) -> F:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("源常数须为十进制字符串，不混入浮点、补字或取整")
    return F(value)


@dataclass(frozen=True)
class SourceSolarFold:
    profile_id: str
    half_year: F
    threshold: F
    half_circle: F
    data_sha256: str
    night_data_sha256: str
    source_url: str

    def audit(self) -> dict[str, Any]:
        explicit = self.profile_id == PROFILES[0]
        return {
            "profile_id": self.profile_id,
            "source_url": self.source_url,
            "data_sha256": self.data_sha256,
            "source_half_year_days_exact": str(self.half_year),
            "numeric_half_period_applied_by_source_command_exact": str(self.half_year),
            "quadrant_threshold_du_exact": str(self.threshold),
            "source_half_circle_du_exact": str(self.half_circle),
            "half_circle_minus_half_year_numeric_exact": str(
                self.half_circle - self.half_year
            ),
            "threshold_left_fold_du_exact": str(self.threshold),
            "threshold_right_limit_fold_du_exact": str(self.half_year - self.threshold),
            "threshold_right_minus_left_du_exact": str(
                self.half_year - 2 * self.threshold
            ),
            "source_explicitly_says_sui_quadrant": explicit,
            "unqualified_Gujin_quadrant_reading_is_hypothesis": not explicit,
            "half_year_replaced_by_half_circle_to_force_symmetry": False,
            "source_numeric_rule_is_physical_day_degree_equivalence": False,
            "input_winter_origin_derived_or_validated": False,
            "source_calendar_or_modern_epoch_accepted": False,
            "used_in_native_birth_chart": False,
        }

    def fold(self, accumulation_du: F, *, origin_reference: str) -> dict[str, Any]:
        if not isinstance(accumulation_du, F):
            raise TypeError("积度须为明确原历古度Fraction，不接收浮点、布尔或现代JD")
        if not isinstance(origin_reference, str) or not origin_reference.strip():
            raise ValueError("须明确提供冬至加时起点依据，不推定积度原点")
        if not 0 <= accumulation_du <= 2 * self.half_year:
            raise ValueError("只接收所声明源周期内非负积度，不补前一年或自动取年余")
        reductions = accumulation_du // self.half_year
        remainder = accumulation_du - reductions * self.half_year
        initial = remainder <= self.threshold
        local = remainder if initial else self.half_year - remainder
        return {
            **self.audit(),
            "input_accumulation_historical_du_exact": str(accumulation_du),
            "declared_origin": "winter_solstice_event",
            "origin_reference": origin_reference,
            "origin_reference_independently_verified": False,
            "half_period_reductions": reductions,
            "after_half_period_reduction_exact": str(remainder),
            "initial_or_final_limit": "initial" if initial else "final",
            "folded_table_argument_du_exact": str(local),
            "threshold_equality_belongs_to_initial_limit": True,
            "solar_side_inferred_from_fold": False,
            "absolute_mansion_coordinate_accepted_without_origin_conversion": False,
            "modern_longitude_or_calendar_date_assigned": False,
        }

    def sunrise(
        self,
        accumulation_du: F,
        *,
        origin_reference: str,
        table_profile: str,
        solar_side: str,
        basis: str,
    ) -> dict[str, Any]:
        if table_profile not in TABLE_PROFILES:
            raise ValueError("须明确选择既有半夜分表，不把大都表改名为七政算表")
        if basis != "dadu_source_table" or solar_side not in ("inside", "outside"):
            raise ValueError("须明确大都表基准及太阳内外，不根据日期或折叠分支猜测")
        if (
            hashlib.sha256(NIGHT_DATA.read_bytes()).hexdigest()
            != self.night_data_sha256
        ):
            raise ValueError("半夜分表输入已改变，不能沿用同一折叠比较版本")
        folded = self.fold(accumulation_du, origin_reference=origin_reference)
        table = load_table(table_profile)
        local = F(folded["folded_table_argument_du_exact"])
        covered = 0 <= local <= table.rows[-1].argument
        result = (
            table.sunrise(local, solar_side=solar_side, basis=basis)
            if covered
            else None
        )
        return {
            "model_id": "named_source_fold_and_night_table_comparison_v1",
            "status": (
                "calculated" if covered else "folded_argument_outside_printed_table"
            ),
            "fold": folded,
            "table_profile": table_profile,
            "solar_side": solar_side,
            "basis": basis,
            "table_data_sha256": table.data_sha256,
            "table_terminal_argument_du_exact": str(table.rows[-1].argument),
            "folded_minus_table_terminal_du_exact": str(
                local - table.rows[-1].argument
            ),
            "table_argument_covered": covered,
            "table_result": result,
            "usable_source_sunrise_fraction_exact": (
                result["source_clock"]["usable_source_sunrise_fraction_exact"]
                if result is not None
                else None
            ),
            "fold_and_table_from_same_work": self.profile_id == PROFILES[1]
            and table_profile == "gujin37_siku",
            "Qizheng_full_night_table_transcribed_or_used": False,
            "cross_witness_or_hypothesis_comparison_not_full_original_replay": True,
            "source_day_origin_location_and_clock_relation_accepted": False,
            "table_gap_filled_or_fold_clamped": False,
            "physical_sunrise_validated": False,
            "phase_day_or_birth_chart_backfilled": False,
        }


def load_source_fold(profile: str) -> SourceSolarFold:
    if profile not in PROFILES:
        raise ValueError("须明确选择文献折叠版本，不按闭合或现代误差自动择优")
    blob = DATA.read_bytes()
    raw = json.loads(blob)
    if raw.get("schema") != "named_source_solar_fold_v1":
        raise ValueError("未核对的原历太阳折叠数据")
    half_year, year_quarter, half_circle, celestial_quarter = (
        _number(raw[name])
        for name in (
            "source_half_year_days",
            "source_sui_quadrant_du",
            "source_half_circle_du",
            "source_celestial_quadrant_du",
        )
    )
    if (
        half_year <= 0
        or 2 * year_quarter != half_year
        or 2 * celestial_quarter != half_circle
        or not 0 < celestial_quarter < half_year
    ):
        raise ValueError("所声明半周与象限源常数不符，不改阈值或归一化")
    explicit = profile == PROFILES[0]
    return SourceSolarFold(
        profile,
        half_year,
        year_quarter if explicit else celestial_quarter,
        half_circle,
        hashlib.sha256(blob).hexdigest(),
        raw["source_night_table_data_sha256"],
        raw["Qizheng_official_text_url"] if explicit else raw["Gujin_source_url"],
    )
