"""Qianyuan's three source days per year, separate from LuWei's chart rows.

This accepts explicitly labelled source elapsed days. It does not replace
days by angular degrees, locate a modern solar entry, resolve a birth age
calendar, or assign a Guolao natal life degree.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_nijl_grid import compare_intro_examples

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/qianyuan-initial-limit-v1.json"
)
DATA_SHA256 = "795003e9579164917fabb8c74484b02e69abbc8e1bcf5c2759ddf2e739f38e1a"
BASIS = "qianyuan_solar_palace_elapsed_source_days"
METHOD = "qianyuan_three_source_days_per_year_initial_limit_v1"


@dataclass(frozen=True)
class QianyuanSourceDays:
    value: Fraction
    quantity_basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Fraction):
            raise TypeError("原书日数须明确用Fraction，不接收浮点、初标或猜定时刻")
        if self.quantity_basis != BASIS:
            raise ValueError(
                "须明确为乾元太阳过宫原书日数，不把角度、尺格或UTC日重贴单位"
            )
        if not 0 <= self.value <= 30:
            raise ValueError("此原书比例只接收0至30原书日，不截断、取模或扩展到下一宫")


def _source() -> dict[str, Any]:
    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise ValueError("乾元童限资料指纹变化，不能悄悄改比例、来源或删原例")
    source: dict[str, Any] = json.loads(raw)
    if (
        source["method_id"] != METHOD
        or source["quantity_basis"] != BASIS
        or [case["id"] for case in source["cases"]]
        != ["two_days_six_source_hours", "thirty_days_less_nine_source_hours"]
    ):
        raise ValueError("须保持具名乾元方法及时间量纲，不能改名套用陆位图法")
    return source


def initial_limit(point: QianyuanSourceDays) -> dict[str, Any]:
    """Exact source-duration arithmetic; no civil date or modern birth mapping."""
    if not isinstance(point, QianyuanSourceDays):
        raise TypeError("须提供具名QianyuanSourceDays，不接收无单位Fraction或天文角度")
    point.__post_init__()
    source = _source()
    additional = point.value / Fraction(source["source_days_per_source_year"])
    total = Fraction(source["base_source_years"]) + additional
    whole = total.numerator // total.denominator
    months = (total - whole) * Fraction(source["source_months_per_year"])
    return dict(
        method_id=METHOD,
        source_id=source["id"],
        source_data_sha256=DATA_SHA256,
        source_pdf_sha256=source["original_sha256"],
        source_locator=source["locator"],
        author=source["author_as_title_page"],
        quantity_basis=BASIS,
        elapsed_source_days_exact=str(point.value),
        additional_source_years_exact=str(additional),
        total_source_years_exact=str(total),
        whole_source_years=whole,
        remaining_source_months_exact=str(months),
        domain_endpoint_policy="closed_0_30_for_ratio_arithmetic_only",
        source_exact_entry_boundary_policy_accepted=False,
        fractional_months_rounded=False,
        source_days_replaced_with_angular_degrees=False,
        source_years_are_modern_age_or_calendar_years=False,
        modern_birth_age_years=None,
        modern_calendar_date=None,
        birth_datetime=None,
        solar_entry_modern_epoch_calibrated=False,
        luwei_circular_rows_resolved=False,
        luwei_two_numeric_counterexamples_overridden=False,
        used_in_native_birth_chart=False,
        full_original_acceptance=False,
        predictive_effectiveness_verified=False,
    )


def audit_original_examples() -> dict[str, Any]:
    """Keep both printed recipes; their calendar examples remain literal text."""
    source = _source()
    cases = []
    for held in source["cases"]:
        result = initial_limit(
            QianyuanSourceDays(Fraction(held["elapsed_source_days"]), BASIS)
        )
        cases.append(
            dict(
                original=held,
                calculation=result,
                printed_duration_match=(
                    result["whole_source_years"] == held["printed_years"]
                    and Fraction(result["remaining_source_months_exact"])
                    == held["printed_months"]
                ),
                source_hour_policy="twelve_source_hours_per_day_explicit_for_example_components",
                printed_calendar_example_converted_to_modern_date=False,
                real_birth_datetime_known=False,
            )
        )
    legacy = compare_intro_examples()
    return dict(
        method_id=METHOD,
        source_data_sha256=DATA_SHA256,
        source=dict(
            title=source["title"],
            author=source["author_as_title_page"],
            pdf_sha256=source["original_sha256"],
            url=source["source_url"],
            locator=source["locator"],
            rule_text=source["rule_text"],
        ),
        cases=cases,
        example_count=len(cases),
        existing_luwei_original_comparison=legacy,
        original_luwei_numeric_counterexample_count=sum(
            row["target_numeric_label_match"] is False for row in legacy["cases"]
        ),
        luwei_circular_rows_resolved=False,
        exact_source_duration_arithmetic_only=True,
        modern_solar_entry_or_calendar_mapping_accepted=False,
        full_original_acceptance=False,
        real_world_prediction_cases=0,
        used_in_native_birth_chart=False,
    )
