"""Named historical half-night tables and explicit local-solstice arithmetic.

Inputs are already folded source angles, not modern solar longitudes. A daily
midnight solar argument and its location/clock relation are not inferred here.
Printed rates, short terminal intervals and empty cells remain literal.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data/guolao/half-night-tables-v1.json"
FIELDS = (
    "argument_du",
    "declination_du",
    "declination_drop_fen",
    "summer_half_night_fen",
    "winter_half_night_fen",
    "day_night_difference_fen",
)


def _fraction(value: F, name: str) -> None:
    if not isinstance(value, F):
        raise TypeError(f"{name}须为明确单位的Fraction，不接收浮点、布尔或默认值")


def _side(value: str) -> None:
    if value not in ("inside", "outside"):
        raise ValueError("须明确黄道在赤道内或外，不从现代月份猜测")


def _clock(night: F) -> dict[str, Any]:
    valid = 0 <= night <= 5000
    sunrise = night / 10000
    return {
        "source_half_night_fen_exact": str(night),
        "source_night_ke_exact": str(night / 50),
        "source_day_ke_exact": str(100 - night / 50),
        "raw_source_sunrise_fraction_exact": str(sunrise),
        "source_clock_within_day_range": valid,
        "usable_source_sunrise_fraction_exact": str(sunrise) if valid else None,
        "source_sunset_fraction_exact": str(1 - sunrise) if valid else None,
        "source_dawn_fraction_exact": str(sunrise - F(1, 40)) if valid else None,
        "source_dusk_fraction_exact": str(1 - sunrise + F(1, 40)) if valid else None,
        "dawn_dusk_within_same_source_day": valid and F(1, 40) <= sunrise <= F(1, 2),
        "dawn_dusk_fen": "250",
        "utc_or_modern_civil_date_assigned": False,
        "physical_sunrise_validated": False,
    }


@dataclass(frozen=True)
class NightRow:
    argument: F
    declination: F | None
    drop_fen: F | None
    summer: F
    winter: F
    difference: F | None


@dataclass(frozen=True)
class SourceNightTable:
    profile_id: str
    source_url: str
    locator: str
    data_sha256: str
    rows: tuple[NightRow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(self.rows))
        if len(self.rows) != 93:
            raise ValueError("须保留93个原表位置，不删空行或用别本补行")
        for index, row in enumerate(self.rows):
            for v in (row.argument, row.summer, row.winter):
                _fraction(v, "原表角度及半夜分")
            if index < 92 and row.argument != index:
                raise ValueError("原表前92个积度须依序为0至91，不排序补缺")
            if not 0 <= row.summer <= 5000 or not 0 <= row.winter <= 5000:
                raise ValueError("原表半夜分超出日周范围")
            if index < 92 and any(
                v is None for v in (row.declination, row.drop_fen, row.difference)
            ):
                raise ValueError("非表尾缺必需源值，不能填充")
            for optional_value in (row.declination, row.drop_fen, row.difference):
                if optional_value is not None:
                    _fraction(optional_value, "内外度及刊差")
        if not 91 < self.rows[-1].argument < 92:
            raise ValueError("须保留原表的短末段，不伸展为整度或理论象限")
        if any(
            v is not None
            for v in (
                self.rows[-1].declination,
                self.rows[-1].drop_fen,
                self.rows[-1].difference,
            )
        ):
            raise ValueError("末格刊空须为None，不能按几何补成零")

    def segment_residual(self, index: int) -> dict[str, Any]:
        row, after = self.rows[index : index + 2]
        assert (
            row.drop_fen is not None
            and row.difference is not None
            and row.declination is not None
        )
        width = after.argument - row.argument
        declination_limit = row.declination - width * row.drop_fen / 100
        return {
            "index": index,
            "width_du_exact": str(width),
            "summer_half_night_anchor_residual_fen_exact": str(
                row.summer + width * row.difference - after.summer
            ),
            "winter_half_night_anchor_residual_fen_exact": str(
                row.winter - width * row.difference - after.winter
            ),
            "declination_at_next_argument_from_left_exact": str(declination_limit),
            "declination_next_anchor_exact": (
                str(after.declination) if after.declination is not None else None
            ),
            "declination_anchor_residual_du_exact": (
                str(declination_limit - after.declination)
                if after.declination is not None
                else None
            ),
            "last_declination_blank_not_assumed_zero": after.declination is None,
        }

    def audit(self) -> dict[str, Any]:
        residuals = [self.segment_residual(i) for i in range(92)]
        return {
            "profile_id": self.profile_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "data_sha256": self.data_sha256,
            "rows": 93,
            "required_numeric_cells": 555,
            "printed_empty_cells": 3,
            "terminal_argument_du_exact": str(self.rows[-1].argument),
            "theoretical_quadrant_du_exact": "730515/8000",
            "uncovered_tail_to_theoretical_quadrant_du_exact": str(
                F("91.314375") - self.rows[-1].argument
            ),
            "all_half_night_pairs_sum_to_5000": all(
                r.summer + r.winter == 5000 for r in self.rows
            ),
            "segment_residuals": residuals,
            "rates_replaced_by_anchor_differences": False,
            "terminal_segment_rescaled_to_force_closure": False,
            "full_midnight_solar_argument_chain_restored": False,
            "half_year_days_and_half_circle_du_interchangeable": False,
            "physical_sunrise_validated": False,
            "used_in_native_birth_chart": False,
        }

    def sunrise(
        self, local_argument_du: F, *, solar_side: str, basis: str
    ) -> dict[str, Any]:
        _fraction(local_argument_du, "已折叠原历黄道积度")
        _side(solar_side)
        if basis != "dadu_source_table":
            raise ValueError("须明确采用原表大都基准，不能自动用于其他出生地点")
        if not 0 <= local_argument_du <= self.rows[-1].argument:
            raise ValueError("超出所选原表刊载范围，不补齐理论象限、不取模或外推")
        index = bisect_right([r.argument for r in self.rows], local_argument_du) - 1
        row = self.rows[index]
        offset = local_argument_du - row.argument
        declination = row.declination
        night = row.summer if solar_side == "inside" else row.winter
        residual = None
        if index < 92:
            assert (
                row.difference is not None
                and row.drop_fen is not None
                and row.declination is not None
            )
            night += offset * row.difference * (1 if solar_side == "inside" else -1)
            declination = row.declination - offset * row.drop_fen / 100
            residual = self.segment_residual(index)
        return {
            "model_id": "named_source_half_night_interpolation_v1",
            "profile_id": self.profile_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "data_sha256": self.data_sha256,
            "basis": basis,
            "solar_side": solar_side,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "local_argument_du_exact": str(local_argument_du),
            "row_index": index,
            "offset_within_printed_interval_du_exact": str(offset),
            "declination_ancient_du_exact": (
                str(declination) if declination is not None else None
            ),
            "declination_usable_for_local_formula": declination is not None
            and declination >= 0,
            "printed_declination_drop_fen_exact": (
                str(row.drop_fen) if row.drop_fen is not None else None
            ),
            "printed_day_night_difference_fen_exact": (
                str(row.difference) if row.difference is not None else None
            ),
            "segment_anchor_rate_residual": residual,
            "source_clock": _clock(night),
            "local_argument_already_folded_explicitly_supplied": True,
            "midnight_solar_argument_or_fold_derived": False,
            "source_day_location_and_clock_relation_independently_verified": False,
            "used_in_native_birth_chart": False,
        }


def load_table(profile: str) -> SourceNightTable:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    if (
        data.get("schema") != "named_source_half_night_tables_v1"
        or data.get("day_cycle_fen") != "10000"
        or data.get("dawn_dusk_fen") != "250"
        or data.get("declination_rate_fen_per_du_divisor") != "100"
    ):
        raise ValueError("原表角分与日周分单位不符，不能自动缩放")
    if profile not in data["profiles"]:
        raise ValueError("须明确选择gujin37_siku或yuanshi55_digital，不混合版本")
    entry = data["profiles"][profile]
    rows = []
    for row in entry["rows"]:
        if any(
            v is not None and not isinstance(v, str) for v in (row[k] for k in FIELDS)
        ):
            raise TypeError("刊值须为原精度数值字符串或明确None，不接受隐式布尔/浮点")
        values = [F(row[k]) if row[k] is not None else None for k in FIELDS]
        assert values[0] is not None and values[3] is not None and values[4] is not None
        rows.append(
            NightRow(values[0], values[1], values[2], values[3], values[4], values[5])
        )
    return SourceNightTable(
        entry["profile_id"],
        entry["source_url"],
        entry["source_locator"],
        hashlib.sha256(raw).hexdigest(),
        tuple(rows),
    )


def local_solstice_sunrise(
    declination_du: F,
    *,
    solar_side: str,
    measured_solstice: str,
    measured_night_ke: F,
    observation_reference: str,
) -> dict[str, Any]:
    """卷37九服原式; requires an explicitly supplied local-solstice observation."""
    _fraction(declination_du, "原历内外度")
    _fraction(measured_night_ke, "当地至日夜刻")
    _side(solar_side)
    if not 0 <= declination_du <= F("23.9030") or not 0 <= measured_night_ke <= 100:
        raise ValueError("超出本原法日太阳内外度或百刻范围，不外推或截断")
    if measured_solstice not in ("winter", "summer"):
        raise ValueError("须明确当地观测属于冬至或夏至")
    if not isinstance(observation_reference, str) or not observation_reference.strip():
        raise ValueError("须提供当地至日观测记录的引用；引用本身不代表已认证")
    if (measured_solstice == "winter" and measured_night_ke < 50) or (
        measured_solstice == "summer" and measured_night_ke > 50
    ):
        raise ValueError("所给至日夜刻方向不合本原法的北方内外约定，不自动推广到南半球")
    amplitude = abs(measured_night_ke - 50)
    difference = declination_du * amplitude * 10 / 239
    night_ke = 50 + (difference if solar_side == "outside" else -difference)
    return {
        "model_id": "gujin37_local_observed_solstice_night_formula_v1",
        "source_url": "https://zh.wikisource.org/w/index.php?title=古今律厯考_(四庫全書本)/卷37&oldid=771685",
        "locator": "求九服所在漏刻",
        "solar_side": solar_side,
        "declination_du_exact": str(declination_du),
        "measured_solstice": measured_solstice,
        "measured_night_ke_exact": str(measured_night_ke),
        "observation_reference": observation_reference,
        "solstice_amplitude_ke_exact": str(amplitude),
        "printed_normalizer_du_exact": "239/10",
        "night_ke_exact": str(night_ke),
        "source_clock": _clock(night_ke * 50),
        "observation_independently_authenticated": False,
        "modern_latitude_or_birthplace_inferred": False,
        "used_in_native_birth_chart": False,
    }
