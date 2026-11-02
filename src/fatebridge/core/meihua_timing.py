"""Exact nominal post-heaven count scales, without inventing a time unit."""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..utils.data import EARTHLY_BRANCHES
from .divination import BAGUA_BY_NUMBER


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/postheaven-timing-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_postheaven_timing_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or profile["accepted_casting_methods"]
        != ["observed_trigrams", "observed_categories"]
        or {
            r["activity"]: (r["numerator"], r["denominator"]) for r in profile["scales"]
        }
        != {"walking": (1, 2), "seated": (2, 1), "standing": (1, 1)}
        or len(profile["scales"]) != 3
    ):
        raise ValueError("Unknown selected post-heaven timing profile")
    return profile


def postheaven_timing_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def build_postheaven_count_reference(
    cast: dict[str, Any],
    *,
    observer_activity: str | None,
    activity_fact_path: str,
) -> dict[str, Any] | None:
    """Use the actual original total and declared observer, never line remainder."""
    if observer_activity is None:
        return None
    profile = _profile()
    scale = next(
        (r for r in profile["scales"] if r["activity"] == observer_activity), None
    )
    if scale is None:
        raise ValueError("No selected numeric scale for this observer activity")
    seed = cast["seed"]
    if seed.get("casting_method") not in profile["accepted_casting_methods"]:
        return None
    numbers = {name: number for number, name in BAGUA_BY_NUMBER.items()}
    upper = numbers[cast["base_hexagram"]["upper"]["name"]]
    lower = numbers[cast["base_hexagram"]["lower"]["name"]]
    branch = seed.get("hour_branch")
    if branch not in EARTHLY_BRANCHES:
        raise ValueError("Post-heaven timing requires the original hour branch")
    hour = EARTHLY_BRANCHES.index(branch) + 1
    total = upper + lower + hour
    expected = {
        "raw_upper_number": upper,
        "raw_lower_number": lower,
        "upper_number": upper,
        "lower_number": lower,
        "line_sum": total,
        "moving_line": total % 6 or 6,
    }
    if any(type(seed.get(k)) is not int or seed[k] != v for k, v in expected.items()):
        raise ValueError("Timing must bind this observed cast's unreduced total")
    if (
        seed["parameters"].get("hour_branch") != branch
        or seed["parameters"].get("method") != seed["casting_method"]
    ):
        raise ValueError("Timing method and hour must bind the actual parameters")
    nominal = Fraction(total) * Fraction(scale["numerator"], scale["denominator"])
    activity_label = {"walking": "行", "seated": "坐", "standing": "立"}[
        observer_activity
    ]
    summary = (
        f"端法计数另核：上卦数{upper}、下卦数{lower}加原时支{branch}数{hour}一次，"
        f"未除六总数为{total}；所报占者{activity_label}，按所选比例得名义数{nominal}。"
        "这不是动爻余数，也没有确定为天数或其他时长；分数保留精确比例，不取整。"
        "原文二花皆朝夕为变通句，未给通用两日期限；未定时间单位、起算点、实际应期或观测窗口。"
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": postheaven_timing_ruleset(),
        "casting_method": seed["casting_method"],
        "method_fact_path": "meihua.seed.casting_method",
        "method_classification_scope": profile["method_scope"],
        "observer_activity": observer_activity,
        "observer_activity_fact_path": activity_fact_path,
        "observer_declaration_status": "caller_reported_unverified",
        "operands": [
            {
                "role": "upper",
                "number": upper,
                "fact_path": "meihua.seed.raw_upper_number",
            },
            {
                "role": "lower",
                "number": lower,
                "fact_path": "meihua.seed.raw_lower_number",
            },
            {
                "role": "hour",
                "branch": branch,
                "number": hour,
                "fact_path": "meihua.seed.hour_branch",
                "number_basis": "original_1_to_12_branch_number",
            },
        ],
        "unreduced_total": total,
        "total_fact_path": "meihua.seed.line_sum",
        "hour_added_times": 1,
        "moving_line": seed["moving_line"],
        "moving_line_fact_path": "meihua.seed.moving_line",
        "moving_line_remainder_used_as_timing_total": False,
        "scale": deepcopy(scale),
        "nominal_scaled_count": {
            "numerator": nominal.numerator,
            "denominator": nominal.denominator,
            "exact_rational": str(nominal),
        },
        "rounding_applied": False,
        "contextual_exception": deepcopy(profile["exception"]),
        "contextual_exception_applied_automatically": False,
        "unresolved": deepcopy(profile["unresolved"]),
        "full_timing_synthesis": "not_computed",
        "time_unit": None,
        "duration": None,
        "start_instant": None,
        "event_time": None,
        "real_world_observation_window": None,
        "real_outcome": None,
        "independent_verified_observations": 0,
        "summary": summary,
    }


def apply_postheaven_count_reference(
    cast: dict[str, Any], interpretation: dict[str, Any]
) -> None:
    """Append only an eligible declared observer's source count; preserve all old text."""
    if interpretation["interpretation_topic"] == "weather":
        return
    motion = interpretation.get("motion_context")
    if motion is None:
        return
    observer = motion["observer"]
    declaration = observer["declaration"]
    if declaration is None:
        return
    result = build_postheaven_count_reference(
        cast,
        observer_activity=observer["activity"],
        activity_fact_path=declaration["fact_path"],
    )
    if result is None:
        return
    if cast.get("counting_variants") or interpretation.get("casting_readings"):
        raise ValueError("Selected observed methods must not borrow a count variant")
    motion["postheaven_count_reference"] = result
    motion["summary"] += result["summary"]
    interpretation["comprehensive_judgement"] += result["summary"]
