"""Frozen all-year reference and Shoushi winter error attribution audit."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_calendar_date_bridge import (
    CALENDARS,
    calendar_label_noon_jdn,
)
from fatebridge.core.guolao_modern_time import (
    CLOCK_POLICY,
    historical_clock_components,
    solar_crossing_tt,
)
from fatebridge.core.guolao_winter_error_budget import (
    CLOCK_HYPOTHESES,
    PROFILE,
    shoushi_winter_error_budget,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/winter-error-budget-v1.json"
REFERENCE_SHA256 = "567633e1694be7d1f234cd15a3658829f6a91b322e3d3e7986e43954b5725046"


def load_reference() -> tuple[dict[str, Any], str]:
    """Reject omitted years, changed plans and broken reference sign brackets."""
    blob = DATA.read_bytes()
    if hashlib.sha256(blob).hexdigest() != REFERENCE_SHA256:
        raise ValueError("固定参考文件哈希改变，须保留旧版并重新核验")
    source = json.loads(blob)
    plan = source["plan"]
    cases = source["cases"]
    if (
        source["schema"] != PROFILE
        or len(cases) != 400
        or len(plan["cohort"]) != 400
        or plan["reference_bisection_rounds"] != 17
        or plan["reference_bracket_width_seconds_exact"] != "675/1024"
        or plan["source_base_year_exact"] != "146097/400"
        or plan["source_epoch_label_serial_exact"] != "109446303/50"
        or plan["clock_policy"] != CLOCK_POLICY
        or plan["clock_hypotheses"] != list(CLOCK_HYPOTHESES)
        or plan["reference_model"] != "DE441"
        or plan["fit_epoch_year_rate_site_deltaT_or_frame"] is not False
        or plan["drop_or_replace_failed_cases"] is not False
        or source["source_epoch_calibrated"] is not False
        or source["used_in_native_birth_chart"] is not False
    ):
        raise ValueError("固定400年参考计划或政策改变，不能删年、调参或改精度迎合结果")
    for n, (case, selected) in enumerate(zip(cases, plan["cohort"])):
        year = 1280 + n
        if case["case"] != selected or selected != {
            "elapsed_years": n,
            "source_year": 1281 + n,
            "winter_year": year,
            "id": f"winter{year}",
            "gregorian_month": 12,
            "start_day": 19,
            "window_days": 5,
            "target_deg": 270,
            "historical_or_extrapolation": (
                "up_to_1644" if year <= 1644 else "post1644_explicit_extrapolation"
            ),
        }:
            raise ValueError("参考年份缺失、重排或扩大窗口")
        low, high = map(F, (case["lower_tt_jd_exact"], case["upper_tt_jd_exact"]))
        start = F(calendar_label_noon_jdn(year, 12, 19, calendar=CALENDARS[0])) - F(
            1, 2
        )
        if not (
            start <= low < high <= start + 5
            and (high - low) * 86400 == F(675, 1024)
            and 269
            < F(case["lower_longitude"])
            < 270
            <= F(case["upper_longitude"])
            < 271
            and F(case["clock"]["tt_jd_requested_exact"]) == (low + high) / 2
            and 0 <= F(case["clock"]["L_Ap_SOL_Time"]) < 24
        ):
            raise ValueError("独立参考夹逼、端点黄经或地方钟行不符")
    for name, wanted in plan["source_component_data_hashes"].items():
        if hashlib.sha256((DATA.parent / name).read_bytes()).hexdigest() != wanted:
            raise ValueError("原算链底本数据发生漂移，须重新核验")
    return source, hashlib.sha256(blob).hexdigest()


def _clock(case: dict[str, Any]) -> dict[str, Any]:
    return historical_clock_components(
        (F(case["lower_tt_jd_exact"]) + F(case["upper_tt_jd_exact"])) / 2,
        F(case["clock"]["TDB-UT"]),
        F(case["clock"]["L_Ap_SOL_Time"]),
        F("116.4"),
        year=case["case"]["winter_year"],
        timescale_difference_policy=CLOCK_POLICY,
    )


def _summary(rows: list[dict[str, Any]], hypothesis: str) -> dict[str, Any]:
    selected = [
        (
            r["case"]["winter_year"],
            F(r["budgets"][hypothesis]["source_minus_reference_nominal_minutes_exact"]),
        )
        for r in rows
    ]
    minimum = min(selected, key=lambda v: v[1])
    maximum = max(selected, key=lambda v: v[1])
    worst = max(selected, key=lambda v: abs(v[1]))
    return {
        "case_count": len(selected),
        "minimum_signed_nominal_minutes": {
            "winter_year": minimum[0],
            "exact": str(minimum[1]),
        },
        "maximum_signed_nominal_minutes": {
            "winter_year": maximum[0],
            "exact": str(maximum[1]),
        },
        "largest_absolute_nominal_minutes": {
            "winter_year": worst[0],
            "signed_exact": str(worst[1]),
        },
        "mean_absolute_nominal_minutes_exact": str(
            sum((abs(v[1]) for v in selected), F()) / len(selected)
        ),
        "algebraic_closure_nonzero_count": sum(
            F(r["budgets"][hypothesis]["algebraic_closure_error_nominal_days_exact"])
            != 0
            for r in rows
        ),
        "calendar_accuracy_pass_threshold_defined": False,
    }


def audit_winter_error_budget(*, include_native: bool = True) -> dict[str, Any]:
    """Compare every planned year; retain both clocks and all signed terms."""
    if type(include_native) is not bool:
        raise TypeError("include_native须为明确布尔值")
    source, fingerprint = load_reference()
    epoch_clock = _clock(source["cases"][0])
    epoch_tt = F(epoch_clock["tt_jd_exact"])
    clocks = {
        "local_mean_solar": "mean_local_calendar_label_serial_exact",
        "local_apparent_solar": "apparent_local_calendar_label_serial_exact",
    }
    rows = []
    for case in source["cases"]:
        clock = _clock(case)
        n = case["case"]["elapsed_years"]
        year = case["case"]["winter_year"]
        budgets = {
            h: shoushi_winter_error_budget(
                n,
                reference_tt_jd=F(clock["tt_jd_exact"]),
                reference_epoch_tt_jd=epoch_tt,
                reference_local_label_serial=F(clock[k]),
                reference_epoch_local_label_serial=F(epoch_clock[k]),
                clock_hypothesis=h,
            )
            for h, k in clocks.items()
        }
        native = None
        if include_native:
            start = F(calendar_label_noon_jdn(year, 12, 19, calendar=CALENDARS[0])) - F(
                1, 2
            )
            native = solar_crossing_tt(270, float(start), float(start + 5))
            value = F(native["selected_jd_tt_exact"])
            low = F(case["lower_tt_jd_exact"])
            high = F(case["upper_tt_jd_exact"])
            signed = (
                value - low if value < low else value - high if value > high else F()
            )
            native["signed_outside_reference_bracket_seconds_exact"] = str(
                signed * 86400
            )
        rows.append(
            {
                "case": case["case"],
                "independent_reference_bracket": {
                    k: case[k]
                    for k in (
                        "lower_tt_jd_exact",
                        "upper_tt_jd_exact",
                        "lower_longitude",
                        "upper_longitude",
                    )
                },
                "clock_components": clock,
                "budgets": budgets,
                "native_moshier_TT": native,
            }
        )
    return {
        "profile_id": PROFILE,
        "reference_data_sha256": fingerprint,
        "complete_planned_cohort": True,
        "case_count": len(rows),
        "historical_through1644_count": 365,
        "post1644_extrapolation_count": 35,
        "summaries": {h: _summary(rows, h) for h in CLOCK_HYPOTHESES},
        "by_century": {
            str(i): {
                h: _summary(rows[i * 100 : (i + 1) * 100], h) for h in CLOCK_HYPOTHESES
            }
            for i in range(4)
        },
        "source_epoch_or_rate_fitted": False,
        "clock_hypothesis_selected_by_smallest_error": False,
        "native_full_five_day_window_used": include_native,
        "native_birth_chart_changed": False,
        "historical_observations_independent_of_old_calendar": False,
        "source_midnight_calibrated": False,
        "real_world_predictive_efficacy_established": False,
        "rows": rows,
    }
