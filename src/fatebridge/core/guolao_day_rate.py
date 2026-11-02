"""Literal Gujin45 day-rate lookup and a bounded integer-angle reconstruction.

This implements Gujin37's alternative interpolation, with an explicitly partial
collation of the angular table. Printed rate conflicts are data, not corrections
to be fitted away. The earlier continuous/floor method remains a separate model.
"""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_conjunctions import GUJIN_COMPONENTS, source_conjunction
from fatebridge.core.guolao_lunar_velocity import _table as _velocity_table

DATA = Path(__file__).resolve().parents[1] / "data/guolao/gujin45-day-rate-v1.json"
PROFILE = "gujin36_37_45_day_rate_integer_interpolation_research"
CALENDAR_PROFILE = "gujin36_37_45_day_rate_fixed_qice_civil_months_research"
METHODS = ("floor_table", "day_rate", "literal_table")
OUTPUT_SCHEMA = "gujin45-day-rate-source-values-v2"
ORIGIN_POLICY = "printed_empty_day_rate_at_index0_interpreted_as_lookup_zero_only"


def validate_method(method: str) -> None:
    if method not in METHODS:
        raise ValueError(
            "须明确选择floor_table、day_rate或literal_table具名方法，不按吻合程度自动换法"
        )


def _table() -> tuple[dict[str, Any], str]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    rows = data["rows"]
    if data["profile_id"] != PROFILE or len(rows) != 169:
        raise ValueError("日率具名表须保留全部169限")
    if [r["limit_index"] for r in rows] != list(range(169)):
        raise ValueError("原刊日率不能重排或去重")
    for i, row in enumerate(rows):
        if row.get("printed_empty_origin") is not (i == 0):
            raise ValueError("原刊日率空格须仅标在初限，不能删标或将数值格改作空格")
        if not re.fullmatch(r"\d+\.\d{4}", row["day_rate_days"]):
            raise ValueError("日率须为原刊四位小数，不自行延长精度")
        if not F() <= F(row["day_rate_days"]) <= F("13.7773"):
            raise ValueError("原刊日率须在转中范围内")
    anchors = data["collated_cumulative_anchors"]
    if [r["limit_index"] for r in anchors] != [82, 83, 84, 85, 86] or any(
        not re.fullmatch(r"\d+\.\d{8}", r["cumulative_ancient_du"]) for r in anchors
    ):
        raise ValueError("仅登记82至86限五个八位小数积度核读值")
    if (
        F(data["anomalistic_month_days"]),
        F(data["half_anomalistic_month_days"]),
        F(data["interpolation_divisor_days"]),
        F(rows[0]["day_rate_days"]),
        F(rows[-1]["day_rate_days"]),
    ) != (F("27.5546"), F("13.7773"), F(".082"), F(), F("13.7773")):
        raise ValueError("转终、转中、插值除数和日率端点须保留具名参数")
    if data["full_angular_table_independently_collated"]:
        raise ValueError("本方法只重建整数积度，不能冒称已全表校勘")
    return data, hashlib.sha256(raw).hexdigest()


def _integer_angle(index: int, data: dict[str, Any]) -> F:
    # Only these three cells replace the integer cubic; not a fitted smoothing.
    if index in (83, 84, 85):
        return F(
            next(
                r["cumulative_ancient_du"]
                for r in data["collated_cumulative_anchors"]
                if r["limit_index"] == index
            )
        )
    argument = min(index, 168 - index)
    return F(argument * (11110000 - argument * (28100 + 325 * argument)), 100000000)


def gujin45_day_rate(anomaly_days: F) -> dict[str, Any]:
    """Use literal adjacent bounds; conflicting reversed spans stay unresolved."""
    if not isinstance(anomaly_days, F):
        raise TypeError("入转须为Fraction原历日数")
    data, digest = _table()
    phase = anomaly_days % F(data["anomalistic_month_days"])
    half = F(data["half_anomalistic_month_days"])
    fast = phase <= half
    within = phase if fast else phase - half
    rates = [F(r["day_rate_days"]) for r in data["rows"]]
    candidates = [i for i in range(168) if rates[i] <= within < rates[i + 1]]
    reversed_spans = [
        i
        for i in range(168)
        if rates[i + 1] <= within <= rates[i] and rates[i + 1] <= rates[i]
    ]
    index = (
        168
        if within == rates[-1]
        else (candidates[0] if len(candidates) == 1 and not reversed_spans else None)
    )
    status = (
        "literal_rate_endpoint"
        if index == 168
        else (
            "origin_zero_interpretation_bracket"
            if index == 0
            else (
                "unique_literal_rate_bracket"
                if index is not None
                else "ambiguous_literal_rate_not_repaired"
            )
        )
    )
    row = data["rows"][index] if index is not None else None
    return {
        "profile_id": PROFILE,
        "day_rate_output_schema_version": OUTPUT_SCHEMA,
        "source_data_sha256": digest,
        "source_url": data["source_url"],
        "anomaly_phase_days_exact": str(phase),
        "phase": "疾" if fast else "遲",
        "within_half_days_exact": str(within),
        "whole_limit_index": index,
        "candidate_limit_indices": candidates,
        "conflicting_reversed_interval_indices": reversed_spans,
        "selected_printed_day_rate_days": (
            row["day_rate_days"] if row and not row["printed_empty_origin"] else None
        ),
        "selected_effective_day_rate_days": row["day_rate_days"] if row else None,
        "selected_day_rate_source_mark": (
            ("空" if row["printed_empty_origin"] else "numeric") if row else None
        ),
        "empty_day_rate_origin_interpreted_as_zero": index == 0,
        "day_rate_origin_policy": ORIGIN_POLICY,
        "next_printed_day_rate_days": (
            data["rows"][index + 1]["day_rate_days"]
            if index is not None and index < 168
            else None
        ),
        "source_locator": (
            {"djvu_page": row["djvu_page"], "half": row["half"], "limit_index": index}
            if row
            else None
        ),
        "status": status,
        "printed_rates_sorted_or_corrected": False,
        "used_in_native_birth_chart": False,
    }


def gujin_day_rate_lunar(anomaly_days: F) -> dict[str, Any]:
    lookup = gujin45_day_rate(anomaly_days)
    data, _ = _table()
    index = lookup["whole_limit_index"]
    angle = slope = fraction = None
    if index is not None:
        angle = _integer_angle(index, data)
        if index < 168:
            slope = _integer_angle(index + 1, data) - angle
            fraction = (
                F(lookup["within_half_days_exact"])
                - F(lookup["selected_effective_day_rate_days"])
            ) / F(data["interpolation_divisor_days"])
            angle += slope * fraction
    signed = -angle if angle is not None and lookup["phase"] == "疾" else angle
    return {
        **lookup,
        "signed_correction_ancient_du_exact": (
            str(signed) if signed is not None else None
        ),
        "unsigned_correction_ancient_du_exact": (
            str(angle) if angle is not None else None
        ),
        "integer_cumulative_ancient_du_exact": (
            str(_integer_angle(index, data)) if index is not None else None
        ),
        "next_minus_current_cumulative_ancient_du_exact": (
            str(slope) if slope is not None else None
        ),
        "interpolation_fraction_exact": str(fraction) if fraction is not None else None,
        "interpolation_fraction_exceeds_one": (
            fraction > 1 if fraction is not None else False
        ),
        "interpolation_divisor_days_exact": str(F(data["interpolation_divisor_days"])),
        "argument_within_printed_limits": index is not None,
        "cumulative_reconstruction": data["cumulative_reconstruction"],
        "full_angular_table_independently_collated": False,
        "literal_day_rate_conflicts_present": True,
        "interpolation_clipped_or_endpoint_smoothed": False,
    }


def gujin_day_rate_conjunction(zhongji_days: F, lunation_index: int) -> dict[str, Any]:
    """Keep Gujin37's early anomaly epoch; only select the named new lunar step."""
    old = source_conjunction(zhongji_days, lunation_index, profile_id=GUJIN_COMPONENTS)
    lunar = gujin_day_rate_lunar(F(old["lunar"]["anomaly_phase_days_exact"]))
    table, velocity_digest = _velocity_table()
    index = lunar["whole_limit_index"]
    key = (
        "fast_ancient_du_per_limit"
        if lunar["phase"] == "疾"
        else "slow_ancient_du_per_limit"
    )
    row = table["rows"][index] if index is not None else None
    value = row[key] if row else None
    velocity = {
        "profile_id": PROFILE,
        "source_data_sha256": velocity_digest,
        "anomaly_phase_days_exact": lunar["anomaly_phase_days_exact"],
        "whole_limit_index": index,
        "printed_velocity_ancient_du_per_limit": value,
        "velocity_ancient_du_per_limit_exact": (
            str(F(value)) if value is not None else None
        ),
        "source_locator": (
            {
                "djvu_page": row["djvu_page"],
                "half": row["half"],
                "limit_index": index,
                "column": key,
            }
            if row
            else None
        ),
        "status": (
            "printed_cell"
            if value is not None
            else (
                "printed_empty_endpoint_no_value"
                if index == 168
                else "ambiguous_literal_rate_not_repaired"
            )
        ),
        "reflected_or_periodically_filled": False,
    }
    correction = None
    if value is not None and lunar["signed_correction_ancient_du_exact"] is not None:
        correction = (
            F(".082")
            * (
                F(old["solar"]["signed_correction_ancient_du_exact"])
                + F(lunar["signed_correction_ancient_du_exact"])
            )
            / F(value)
        )
    offset = F(old["mean_conjunction_offset_from_winter_days_exact"])
    mean_total = zhongji_days + F("55.06") + offset
    total = mean_total + correction if correction is not None else None
    cycle = total % 60 if total is not None else None
    day = cycle // 1 if cycle is not None else None
    return {
        "model_id": "gujin_named_day_rate_conjunction_v1",
        "profile_id": PROFILE,
        "zhongji_days_exact": str(zhongji_days),
        "lunation_index": lunation_index,
        "angular_components": {
            "profile_id": PROFILE,
            "solar": old["solar"],
            "lunar": lunar,
            "legacy_continuous_lunar_diagnostic": old["lunar"],
            "early_gujin37_epoch_retained": True,
        },
        "lunar_velocity": velocity,
        "time_correction_days_exact": (
            str(correction) if correction is not None else None
        ),
        "research_conjunction_offset_from_winter_days_exact": (
            str(offset + correction) if correction is not None else None
        ),
        "research_conjunction_day_cycle_exact": (
            str(cycle) if cycle is not None else None
        ),
        "research_conjunction_sexagenary_day": (
            STEMS[day % 10] + BRANCHES[day % 12] if day is not None else None
        ),
        "midnight_displacement_from_mean_days": (
            total // 1 - mean_total // 1 if total is not None else None
        ),
        "status": (
            "integer_reconstruction_with_literal_day_rate_research"
            if correction is not None
            else "missing_or_ambiguous_source_value_not_filled"
        ),
        "lunar_date": None,
        "complete_source_calendar_accepted": False,
        "intercalation_reconstructed": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }


def audit_day_rate_table() -> dict[str, Any]:
    """Expose conflicts and every boundary jump; no continuity is manufactured."""
    data, digest = _table()
    rates = [F(r["day_rate_days"]) for r in data["rows"]]
    conflicts: list[dict[str, Any]] = []
    jumps: list[dict[str, Any]] = []
    for i, rate in enumerate(rates):
        diagnostic = (i * F(".082008") * 10000 // 1) / F(10000)
        if not data["rows"][i]["printed_empty_origin"] and rate != diagnostic:
            conflicts.append(
                {
                    "limit_index": i,
                    "printed_day_rate_days": data["rows"][i]["day_rate_days"],
                    "equal_step_truncation_diagnostic_days_exact": str(diagnostic),
                    "diagnostic_used_to_replace_source": False,
                }
            )
        if 0 < i < 168:
            before = _integer_angle(i - 1, data)
            slope = _integer_angle(i, data) - before
            left = before + slope * (rate - rates[i - 1]) / F(".082")
            jumps.append(
                {
                    "boundary_index": i,
                    "right_minus_left_unsigned_ancient_du_exact": str(
                        _integer_angle(i, data) - left
                    ),
                    "preceding_day_rate_interval_increasing": rates[i - 1] < rate,
                }
            )
    return {
        "model_id": "gujin_literal_day_rate_table_audit_v2",
        "profile_id": PROFILE,
        "day_rate_output_schema_version": OUTPUT_SCHEMA,
        "source_data_sha256": digest,
        "rate_position_count": len(rates),
        "printed_numeric_rate_count": sum(
            not row["printed_empty_origin"] for row in data["rows"]
        ),
        "printed_empty_rate_indices": [
            row["limit_index"] for row in data["rows"] if row["printed_empty_origin"]
        ],
        "effective_lookup_rate_count": len(rates),
        "day_rate_origin_policy": ORIGIN_POLICY,
        "equal_step_diagnostic_numeric_compared_count": sum(
            not row["printed_empty_origin"] for row in data["rows"]
        ),
        "equal_step_diagnostic_increment_days": "0.082008",
        "equal_step_increment_is_diagnostic_not_adjudicated_source": True,
        "equal_step_diagnostic_conflicts": conflicts,
        "nonincreasing_interval_indices": [
            i for i in range(168) if rates[i + 1] <= rates[i]
        ],
        "boundary_jumps": jumps,
        "nonzero_boundary_jumps": sum(
            F(j["right_minus_left_unsigned_ancient_du_exact"]) != 0 for j in jumps
        ),
        "collated_cumulative_anchors": data["collated_cumulative_anchors"],
        "full_angular_table_independently_collated": False,
        "complete_source_calendar_accepted": False,
        "real_world_prediction_validated": False,
    }
