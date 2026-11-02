"""Named source 黄赤道率, literal local interpolation and mansion projection.

The printed NLC table and corrected digital text remain separate. Source
rates are never replaced by differences of neighbouring accumulations. The
short final interval and its different axis endpoints are not stretched to
the theoretical quadrant. No modern physical coordinate epoch is supplied.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import MANSIONS, SHOUSHI_EQUATORIAL_1281
from fatebridge.core.guolao_coordinates import NLC166_MANSIONS

DATA = Path(__file__).resolve().parents[1] / "data/guolao/huangchi-v1.json"


@dataclass(frozen=True)
class RateRow:
    first: Fraction
    second: Fraction
    first_rate: Fraction | None
    second_rate: Fraction | None

    def rates(self) -> tuple[Fraction, Fraction]:
        if not isinstance(self.first_rate, Fraction) or not isinstance(
            self.second_rate, Fraction
        ):
            raise TypeError("当前行未提供两项明确古度率，不能补造或派生")
        return self.first_rate, self.second_rate


@dataclass(frozen=True)
class HuangChiTable:
    profile_id: str
    source_url: str
    locator: str
    terminal_marker: str
    data_sha256: str
    rows: tuple[RateRow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(self.rows))
        if len(self.rows) != 93:
            raise ValueError("黄赤道率须保留初至表尾93个锚点，不补齐缺行")
        for i, row in enumerate(self.rows):
            if not isinstance(row.first, Fraction) or not isinstance(
                row.second, Fraction
            ):
                raise TypeError("原历积度和度率须以Fraction明确表示古度")
            if i < 92:
                first_rate, second_rate = row.rates()
                if first_rate <= 0 or second_rate <= 0:
                    raise ValueError("源表度率须为正；不以零或负率补算")
            if i and (
                row.first <= self.rows[i - 1].first
                or row.second <= self.rows[i - 1].second
            ):
                raise ValueError("源表积度须严格递增，不能排序来消除倒序")
        if self.rows[0].first != 0 or self.rows[0].second != 0:
            raise ValueError("原历本地积度起点须为初")
        if (
            self.rows[-1].first_rate is not None
            or self.rows[-1].second_rate is not None
        ):
            raise ValueError("表尾无后继度率，不能补造")

    def residuals(self) -> list[dict[str, Any]]:
        findings = []
        for i, (row, following) in enumerate(zip(self.rows, self.rows[1:])):
            first_rate, second_rate = row.rates()
            first = row.first + first_rate - following.first
            second = row.second + second_rate - following.second
            if first or second:
                findings.append(
                    {
                        "row_index": i,
                        "first_residual_du_exact": str(first),
                        "second_residual_du_exact": str(second),
                    }
                )
        return findings

    def audit(self) -> dict[str, Any]:
        quadrant = SHOUSHI_EQUATORIAL_1281.circle_du / 4
        return {
            "profile_id": self.profile_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "data_sha256": self.data_sha256,
            "rows": len(self.rows),
            "segments": len(self.rows) - 1,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "first_axis_roles": "至后黄道、分后赤道积度",
            "second_axis_roles": "至后赤道、分后黄道积度",
            "terminal_marker_text": self.terminal_marker,
            "terminal_first_axis_policy": "previous_first_anchor_plus_printed_first_rate_not_a_literal_transcription_of_the_last_marker",
            "terminal_first_axis_is_interpretation": True,
            "terminal_literal_marker_conflicts_with_rate_endpoint": self.terminal_marker
            == "九十二",
            "first_endpoint_du_exact": str(self.rows[-1].first),
            "second_endpoint_du_exact": str(self.rows[-1].second),
            "theoretical_quadrant_du_exact": str(quadrant),
            "first_axis_uncovered_tail_du_exact": str(quadrant - self.rows[-1].first),
            "second_axis_uncovered_tail_du_exact": str(quadrant - self.rows[-1].second),
            "anchor_rate_residuals": self.residuals(),
            "rates_replaced_by_anchor_differences": False,
            "endpoint_extrapolated": False,
            "full_theoretical_quadrant_covered": self.rows[-1].first >= quadrant
            and self.rows[-1].second >= quadrant,
            "printed_terminal_marker_used_as_numeric_endpoint": False,
            "modern_epoch_calibrated": False,
        }

    def convert(
        self, degree_du: Fraction, *, origin: str, direction: str
    ) -> dict[str, Any]:
        """Local accumulation from a named 至/分 point, never mansion degree."""
        if not isinstance(degree_du, Fraction):
            raise TypeError("须以Fraction提供原历本地积度，不接收现代黄经或宿内度")
        if origin not in {"solstice", "equinox"} or direction not in {
            "equatorial_to_ecliptic",
            "ecliptic_to_equatorial",
        }:
            raise ValueError("须明确至后/分后及黄赤道转换方向")
        use_second = (origin == "solstice") == (direction == "equatorial_to_ecliptic")
        source = tuple(row.second if use_second else row.first for row in self.rows)
        target = tuple(row.first if use_second else row.second for row in self.rows)
        if not 0 <= degree_du <= source[-1]:
            raise ValueError(
                "输入越过所选原表本地积度范围；不填满理论象限、不取模或外推"
            )
        index = min(bisect_right(source, degree_du) - 1, 91)
        row = self.rows[index]
        first_rate, second_rate = row.rates()
        numerator, denominator = (
            (first_rate, second_rate) if use_second else (second_rate, first_rate)
        )
        value = target[index] + (degree_du - source[index]) * numerator / denominator
        local = next((r for r in self.residuals() if r["row_index"] == index), None)
        return {
            "profile_id": self.profile_id,
            "origin": origin,
            "direction": direction,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "input_local_accumulation_du_exact": str(degree_du),
            "output_local_accumulation_du_exact": str(value),
            "row_index": index,
            "source_anchor_du_exact": str(source[index]),
            "target_anchor_du_exact": str(target[index]),
            "source_rate_du_exact": str(denominator),
            "target_rate_du_exact": str(numerator),
            "source_next_anchor_du_exact": str(source[index + 1]),
            "target_next_anchor_du_exact": str(target[index + 1]),
            "local_anchor_rate_residual": local,
            "table_anchor_rate_residuals": self.residuals(),
            "data_sha256": self.data_sha256,
            "status": "source_inconsistent_segment" if local else "source_arithmetic",
            "source_url": self.source_url,
            "locator": self.locator,
            "modern_coordinate": None,
            "used_in_native_birth_chart": False,
        }


def load_table(profile: str) -> HuangChiTable:
    raw = DATA.read_bytes()
    entries = json.loads(raw)["profiles"]
    if profile not in entries:
        raise ValueError("须明确选择nlc166或wikisource，不能自动拼合版本")
    entry = entries[profile]
    values = entry["rows"]
    rows = tuple(
        RateRow(
            Fraction(r["first_axis_du"]),
            Fraction(r["second_axis_du"]),
            Fraction(r["first_rate_du"]) if r["first_rate_du"] is not None else None,
            Fraction(r["second_rate_du"]) if r["second_rate_du"] is not None else None,
        )
        for r in values
    )
    return HuangChiTable(
        entry["profile_id"],
        entry["source_url"],
        entry["locator"],
        entry["terminal_marker_text"],
        hashlib.sha256(raw).hexdigest(),
        rows,
    )


def project_reference_mansions(
    *, profile: str, winter_mansion: str, winter_degree_du: Fraction
) -> dict[str, Any]:
    """Project all fixed measured RA boundaries with an explicit source anchor.

    This returns literal unrounded interpolation, plus a declared comparison
    using nearest 1/100 du of each resulting width. It does not alter rates or
    choose rounding to fit the printed ecliptic table.
    """
    eq = SHOUSHI_EQUATORIAL_1281
    if winter_mansion not in MANSIONS or not isinstance(winter_degree_du, Fraction):
        raise ValueError("须明确给定固定赤道宿表中的冬至宿名和Fraction古度")
    i = MANSIONS.index(winter_mansion)
    if not 0 <= winter_degree_du < eq.widths_du[i]:
        raise ValueError("冬至宿内度须首含尾不含，不能按现代黄经取模")
    table = load_table(profile)
    origin = sum(eq.widths_du[:i], Fraction()) + winter_degree_du
    quadrant = eq.circle_du / 4
    boundaries: list[dict[str, Any]] = []
    for index, mansion in enumerate(MANSIONS):
        relative = (sum(eq.widths_du[:index], Fraction()) - origin) % eq.circle_du
        q = int(relative // quadrant)
        try:
            trace = table.convert(
                relative - q * quadrant,
                origin="solstice" if q % 2 == 0 else "equinox",
                direction="equatorial_to_ecliptic",
            )
            value = q * quadrant + Fraction(trace["output_local_accumulation_du_exact"])
            error = None
        except ValueError as exc:
            trace, value, error = None, None, str(exc)
        boundaries.append(
            {
                "mansion": mansion,
                "quadrant_index": q,
                "equatorial_relative_du_exact": str(relative),
                "ecliptic_relative_du_exact": str(value) if value is not None else None,
                "trace": trace,
                "unavailable_reason": error,
            }
        )
    widths: list[dict[str, Any]] = []
    for index, boundary in enumerate(boundaries):
        a = boundary["ecliptic_relative_du_exact"]
        b = boundaries[(index + 1) % 28]["ecliptic_relative_du_exact"]
        width = (
            (Fraction(b) - Fraction(a)) % eq.circle_du
            if a is not None and b is not None
            else None
        )
        rounded = None
        if width is not None:
            scaled = width * 100 + Fraction(1, 2)
            rounded = Fraction(scaled.numerator // scaled.denominator, 100)
        printed = NLC166_MANSIONS.widths_du[index]
        widths.append(
            {
                "mansion": MANSIONS[index],
                "raw_width_du_exact": str(width) if width is not None else None,
                "nearest_centidu_width_exact": (
                    str(rounded) if rounded is not None else None
                ),
                "printed_nlc_width_du_exact": str(printed),
                "rounded_minus_printed_du_exact": (
                    str(rounded - printed) if rounded is not None else None
                ),
                "rounded_equals_printed": rounded == printed,
            }
        )
    return {
        "table_audit": table.audit(),
        "input_anchor": {
            "mansion": winter_mansion,
            "degree_du_exact": str(winter_degree_du),
            "coordinate_frame": eq.coordinate_frame,
            "reference_table_id": eq.source_id,
        },
        "quadrant_du_exact": str(quadrant),
        "rounding_comparison_policy": "raw_each_width_then_nearest_1_100_du_half_up_not_cumulative_rounding",
        "printed_ecliptic_comparison_table_id": NLC166_MANSIONS.source_id,
        "comparison_scope": "fixed_NLC_ecliptic_reference_not_a_redated_acceptance_target_for_arbitrary_anchors",
        "boundaries": boundaries,
        "widths": widths,
        "all_28_boundaries_returned": all(
            b["ecliptic_relative_du_exact"] is not None for b in boundaries
        ),
        "raw_width_sum_du_exact": (
            str(sum((Fraction(w["raw_width_du_exact"]) for w in widths), Fraction()))
            if all(w["raw_width_du_exact"] is not None for w in widths)
            else None
        ),
        "rounded_match_count": sum(w["rounded_equals_printed"] for w in widths),
        "printed_ecliptic_table_reproduced": all(
            w["rounded_equals_printed"] for w in widths
        ),
        "modern_epoch_calibrated": False,
        "life_degree_accepted": False,
        "used_in_native_birth_chart": False,
    }
