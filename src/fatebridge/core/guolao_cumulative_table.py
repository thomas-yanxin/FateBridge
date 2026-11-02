"""Gujin45's separately transcribed cumulative angle and signed increment.

Literal printed conflicts are preserved. Only the empty cumulative origin is
explicitly interpreted as zero; the empty endpoint and velocity are not filled.
This is single-collator source research, not whole-calendar adjudication.
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
from fatebridge.core.guolao_day_rate import (
    ORIGIN_POLICY,
    OUTPUT_SCHEMA,
    gujin45_day_rate,
)
from fatebridge.core.guolao_lunar_velocity import _table as _velocity_table

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/gujin45-cumulative-table-v1.json"
)
PROFILE = "gujin36_37_45_literal_cumulative_day_rate_research"
CALENDAR_PROFILE = "gujin36_37_45_literal_cumulative_fixed_qice_civil_months_research"


def _table() -> tuple[dict[str, Any], str]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    rows = data["rows"]
    if (
        data["profile_id"] != PROFILE
        or len(rows) != 169
        or [r["limit_index"] for r in rows] != list(range(169))
    ):
        raise ValueError("具名积度与损益表须保留169限原序")
    for i, row in enumerate(rows):
        for key, empty in [
            ("cumulative_ancient_du", i in (0, 168)),
            ("signed_increment_ancient_du", i == 168),
        ]:
            value = row[key]
            if empty:
                if value is not None:
                    raise ValueError("原刊累计起点及末限空格不能改作刊载数字")
            elif not isinstance(value, str) or not re.fullmatch(r"-?\d+\.\d{8}", value):
                raise ValueError("积度与损益须保留规范化八位十进制古度，不补造精度")
        if row["cumulative_mark"] != ("空" if i in (0, 168) else "numeric"):
            raise ValueError("积度空格须保留所见标记")
        expected = "空" if i == 168 else "益" if i < 84 else "損"
        if row["increment_label"] != expected:
            raise ValueError("损益原字及限序不符")
        if i < 168 and (F(row["signed_increment_ancient_du"]) > 0) != (i < 84):
            raise ValueError("有符号损益须与原刊损益字对应")
    if (
        F(data["interpolation_divisor_days"]) != F(".082")
        or data["origin_policy"]
        != "empty_cumulative_at_index0_interpreted_as_origin_zero_only"
        or not data["full_single_collator_field_transcription"]
        or data["independent_second_collator"]
    ):
        raise ValueError(
            "本方法只登记单人全字段转录及明示起点政策，不更改除数或升级校勘等级"
        )
    return data, hashlib.sha256(raw).hexdigest()


def gujin_literal_lunar(anomaly_days: F) -> dict[str, Any]:
    """Interpolate the printed cumulative cell with its own printed increment."""
    return _literal_lunar_from_lookup(gujin45_day_rate(anomaly_days))


def _literal_lunar_from_lookup(lookup: dict[str, Any]) -> dict[str, Any]:
    """Shared arithmetic; callers must preserve the lookup's selection policy."""
    data, digest = _table()
    if lookup["source_data_sha256"] != data["day_rate_data_sha256"]:
        raise ValueError("日率资料指纹不符，不能跨见证混用取限")
    index = lookup["whole_limit_index"]
    row = data["rows"][index] if index is not None else None
    origin = index == 0
    cumulative = row["cumulative_ancient_du"] if row else None
    increment = row["signed_increment_ancient_du"] if row else None
    angle = fraction = None
    if index is not None and index < 168:
        if increment is None or (cumulative is None and not origin):
            raise ValueError("缺少原刊积度或损益，不从相邻格或公式代填")
        base = F(cumulative) if cumulative is not None else F()
        fraction = (
            F(lookup["within_half_days_exact"])
            - F(lookup["selected_effective_day_rate_days"])
        ) / F(data["interpolation_divisor_days"])
        angle = base + F(increment) * fraction
    signed = -angle if angle is not None and lookup["phase"] == "疾" else angle
    return {
        **lookup,
        "model_id": data["model_id"],
        "profile_id": PROFILE,
        "source_data_sha256": digest,
        "day_rate_source_data_sha256": lookup["source_data_sha256"],
        "source_selected_cumulative_ancient_du": cumulative,
        "source_selected_signed_increment_ancient_du": increment,
        "source_selected_increment_label": row["increment_label"] if row else None,
        "empty_cumulative_origin_interpreted_as_zero": origin,
        "empty_cumulative_endpoint_filled": False,
        "signed_correction_ancient_du_exact": (
            str(signed) if signed is not None else None
        ),
        "unsigned_correction_ancient_du_exact": (
            str(angle) if angle is not None else None
        ),
        "interpolation_fraction_exact": str(fraction) if fraction is not None else None,
        "interpolation_fraction_exceeds_one": (
            fraction > 1 if fraction is not None else False
        ),
        "interpolation_divisor_days_exact": str(F(data["interpolation_divisor_days"])),
        "argument_within_printed_limits": index is not None,
        "full_angular_table_single_collator_transcribed": True,
        "independent_second_collator": False,
        "integer_formula_or_reflection_used_to_supply_cumulative": False,
        "adjacent_cumulative_difference_used_to_supply_increment": False,
        "interpolation_clipped_or_endpoint_smoothed": False,
        "status": (
            "literal_cumulative_and_increment_research"
            if angle is not None
            else (
                "literal_empty_endpoint_not_filled"
                if index == 168
                else lookup["status"]
            )
        ),
    }


def gujin_literal_conjunction(zhongji_days: F, lunation_index: int) -> dict[str, Any]:
    old = source_conjunction(zhongji_days, lunation_index, profile_id=GUJIN_COMPONENTS)
    lunar = gujin_literal_lunar(F(old["lunar"]["anomaly_phase_days_exact"]))
    return _literal_conjunction_from_components(
        zhongji_days, lunation_index, old, lunar
    )


def _literal_conjunction_from_components(
    zhongji_days: F, lunation_index: int, old: dict[str, Any], lunar: dict[str, Any]
) -> dict[str, Any]:
    """Use the same selected printed limit for angle and velocity."""
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
        "model_id": "gujin_named_literal_cumulative_conjunction_v1",
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
            "literal_cumulative_and_increment_research"
            if correction is not None
            else "missing_or_ambiguous_source_value_not_filled"
        ),
        "lunar_date": None,
        "complete_source_calendar_accepted": False,
        "intercalation_reconstructed": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }


def audit_gujin45_cumulative_table() -> dict[str, Any]:
    """Compare independent columns; never derive a replacement from agreement."""
    from fatebridge.core.guolao_day_rate import DATA as RATE_DATA
    from fatebridge.core.guolao_day_rate import _integer_angle
    from fatebridge.core.guolao_day_rate import _table as old_table

    data, digest = _table()
    previous, _ = old_table()
    rate_bytes = RATE_DATA.read_bytes()
    if hashlib.sha256(rate_bytes).hexdigest() != data["day_rate_data_sha256"]:
        raise ValueError("日率资料指纹不符，不能跨见证审计")
    rates = json.loads(rate_bytes)
    rows = data["rows"]
    cumulative_disagreements = []
    increment_disagreements = []
    jumps: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        value = row["cumulative_ancient_du"]
        if value is not None and F(value) != _integer_angle(i, previous):
            cumulative_disagreements.append(
                {
                    "limit_index": i,
                    "printed": value,
                    "previous_integer_formula_exact": str(_integer_angle(i, previous)),
                }
            )
        if (
            i < 168
            and value is not None
            and rows[i + 1]["cumulative_ancient_du"] is not None
        ):
            adjacent = F(rows[i + 1]["cumulative_ancient_du"]) - F(value)
            difference = F(row["signed_increment_ancient_du"]) - adjacent
            if difference:
                increment_disagreements.append(
                    {
                        "limit_index": i,
                        "printed_signed_increment_ancient_du": row[
                            "signed_increment_ancient_du"
                        ],
                        "next_minus_current_printed_cumulative_exact": str(adjacent),
                        "printed_minus_adjacent_exact": str(difference),
                        "printed_increment_replaced": False,
                    }
                )
        if 0 < i < 168:
            left = F() if i == 1 else F(rows[i - 1]["cumulative_ancient_du"])
            duration = F(rates["rows"][i]["day_rate_days"]) - F(
                rates["rows"][i - 1]["day_rate_days"]
            )
            left += F(rows[i - 1]["signed_increment_ancient_du"]) * duration / F(".082")
            jumps.append(
                {
                    "boundary_index": i,
                    "right_minus_left_unsigned_ancient_du_exact": str(F(value) - left),
                    "preceding_day_rate_interval_increasing": duration > 0,
                }
            )
    return {
        "model_id": "gujin_literal_cumulative_increment_audit_v1",
        "profile_id": PROFILE,
        "day_rate_output_schema_version": OUTPUT_SCHEMA,
        "day_rate_origin_policy": ORIGIN_POLICY,
        "empty_day_rate_origin_interpreted_as_zero_at_boundary1": True,
        "source_data_sha256": digest,
        "numeric_cumulative_cells": sum(
            r["cumulative_ancient_du"] is not None for r in rows
        ),
        "numeric_signed_increment_cells": sum(
            r["signed_increment_ancient_du"] is not None for r in rows
        ),
        "empty_cumulative_indices": [
            r["limit_index"] for r in rows if r["cumulative_ancient_du"] is None
        ],
        "empty_increment_indices": [
            r["limit_index"] for r in rows if r["signed_increment_ancient_du"] is None
        ],
        "cumulative_vs_previous_integer_model_disagreements": cumulative_disagreements,
        "printed_increment_vs_adjacent_cumulative_disagreements": increment_disagreements,
        "boundary_jumps": jumps,
        "nonzero_boundary_jumps": sum(
            F(j["right_minus_left_unsigned_ancient_du_exact"]) != 0 for j in jumps
        ),
        "last_interval_uses_printed_increment_without_filling_empty_endpoint": True,
        "independent_second_collator": False,
        "complete_source_calendar_accepted": False,
        "real_world_prediction_validated": False,
    }
