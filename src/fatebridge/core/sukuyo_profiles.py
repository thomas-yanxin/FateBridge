"""T1299 full-moon counting and an explicit T2465 short-month addendum.

The host calendar is chosen separately. The Hinoo profile applies
textual day-part assignments, not an invented civil noon or historical calendar.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from fatebridge.core.sukuyo_hinoo_critical import critical_calendar_reference
from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_calendar_profiles.json"
)
DEFAULT_PROFILE = "t1299_fullmoon27"
HINOO_PROFILE = "hinoo_t1299_host27"
PROFILES = (DEFAULT_PROFILE, HINOO_PROFILE)
DAY_PARTS = ("first_half", "second_half")
_ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def source_digest() -> str:
    return load_source(SOURCE).sha256


def fullmoon_calculation(month: int, day: int, order: Sequence[str]) -> dict[str, Any]:
    source = load_source(SOURCE)
    return _fullmoon_from_loaded(month, day, order, source.data, source.sha256)


def _fullmoon_from_loaded(
    month: int, day: int, order: Sequence[str], bundle: dict[str, Any], digest: str
) -> dict[str, Any]:
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("农历月必须为1..12的整数")
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("农历日必须为1..30的整数")
    if len(order) != 27 or len(set(order)) != 27 or "牛" in order:
        raise ValueError("望宿法必须使用不含牛的27宿顺序")
    rows = bundle["fullmoon_anchors"]
    if len(rows) != 12 or any(
        type(row.get("month")) is not int
        or not 1 <= row["month"] <= 12
        or not isinstance(row.get("fullmoon_mansion"), str)
        for row in rows
    ):
        raise ValueError("十二月望宿表必须完整、月份唯一且宿名有效")
    anchors = {
        row["month"]: row["fullmoon_mansion"].translate(_ALIASES) for row in rows
    }
    if set(anchors) != set(range(1, 13)) or any(
        name not in order for name in anchors.values()
    ):
        raise ValueError("十二月望宿表必须完整、月份唯一且宿名有效")
    anchor = anchors[month]
    anchor_index = order.index(anchor)
    # First method: day 15 is the anchor, earlier days count backwards.
    direct = order[(anchor_index + day - 15) % 27]
    # Second method is genuinely inclusive: the anchor itself is count one.
    # E.g. 2/17 -> 17+13=30 -> remainder 3 -> 角=1, 亢=2, 氐=3.
    inclusive_count = day + 13
    shortcut = order[(anchor_index + (inclusive_count - 1) % 27) % 27]
    if direct != shortcut:
        raise RuntimeError("原典两种望宿算法不一致，不能静默择一")
    return {
        "ruleset_id": bundle["id"],
        "lunar_month": month,
        "lunar_day": day,
        "fullmoon_day": 15,
        "fullmoon_mansion": anchor,
        "signed_day_offset": day - 15,
        "direct_mansion": direct,
        "shortcut_inclusive_count": inclusive_count,
        "shortcut_one_based_remainder": (inclusive_count - 1) % 27 + 1,
        "shortcut_mansion": shortcut,
        "methods_agree": direct == shortcut,
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": digest,
        "direct_locator": bundle["direct_count_locator"],
        "shortcut_locator": bundle["shortcut_locator"],
        "scope": "原典月日配当算法；十五日是表定望日，不以实际天文满月瞬间替换。",
    }


def select_profile(
    month: int,
    day: int,
    leap: bool,
    order: Sequence[str],
    *,
    profile: str,
    leap_policy: str,
    day_part: Optional[str],
    previous_lunar: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError("calendar_profile仅支持t1299_fullmoon27或hinoo_t1299_host27")
    if day_part is not None and day_part not in DAY_PARTS:
        raise ValueError("calendar_day_part仅支持first_half或second_half")
    if day_part is not None and profile != HINOO_PROFILE:
        raise ValueError("calendar_day_part只适用于明确选择的hinoo_t1299_host27档案")
    if leap_policy not in {"unresolved", "repeat_month"}:
        raise ValueError("闰月政策无效")
    previous_lunar = deepcopy(previous_lunar)
    source = load_source(SOURCE)
    bundle = source.data

    # Every branch uses one captured table and digest, including the omitted
    # day and repeat-month alternatives; never mix separately reloaded tables.
    def calculate(m: int, d: int) -> dict[str, Any]:
        return _fullmoon_from_loaded(m, d, order, bundle, source.sha256)

    host = calculate(month, day)
    base = host["direct_mansion"]
    assignment = None
    missing_part = False
    precedence_unresolved = False
    previous_context_unavailable = False
    choices = [base]
    selected = base
    if profile == HINOO_PROFILE and day == 1:
        if previous_lunar is None:
            missing_part = day_part != "second_half"
            previous_context_unavailable = missing_part
        else:
            omitted = (
                calculate(previous_lunar["lunar_month"], 30)
                if previous_lunar["lunar_day"] == 29
                else None
            )
            adjacent_first = omitted["direct_mansion"] if omitted else base
            first_choices = [adjacent_first]
            precedence = None
            if leap:
                # Repeat-month and short-month rules are not explicitly
                # ordered by the source. Repeating the true month's first
                # day may preserve an earlier short month's assignment,
                # even if the immediately preceding month has 30 days.
                before_regular = previous_lunar.get("before_regular_month")
                if before_regular is None:
                    previous_context_unavailable = day_part != "second_half"
                else:
                    repeated_omitted = (
                        calculate(before_regular["lunar_month"], 30)
                        if before_regular["lunar_day"] == 29
                        else None
                    )
                    repeated_first = (
                        repeated_omitted["direct_mansion"] if repeated_omitted else base
                    )
                    first_choices = list(
                        dict.fromkeys([adjacent_first, repeated_first])
                    )
                    precedence = {
                        "kind": "modern_reconstruction_variants_not_two_explicit_source_algorithms",
                        "adjacent_month_first_half": adjacent_first,
                        "repeat_true_month_first_half": repeated_first,
                        "second_half_both_variants": base,
                        "source_rule_priority_established": False,
                        "reconstruction_calculations": [
                            {
                                "id": "adjacent_month_short_day_assignment",
                                "previous_lunar": deepcopy(previous_lunar),
                                "first_half_calculation": deepcopy(omitted or host),
                                "second_half_calculation": deepcopy(host),
                            },
                            {
                                "id": "repeat_regular_month_first_day_assignment",
                                "previous_lunar": deepcopy(before_regular),
                                "first_half_calculation": deepcopy(
                                    repeated_omitted or host
                                ),
                                "second_half_calculation": deepcopy(host),
                            },
                        ],
                    }
            slots = [
                {
                    "day_part": "first_half",
                    "mansion": first_choices[0] if len(first_choices) == 1 else None,
                    "candidate_mansions": first_choices,
                    "origin": (
                        "adjacent_month_or_repeated_true_month_assignment"
                        if leap
                        else (
                            "preceding_month_omitted_day_30"
                            if omitted
                            else "current_month_regular_day_1"
                        )
                    ),
                },
                {
                    "day_part": "second_half",
                    "mansion": base,
                    "candidate_mansions": [base],
                    "origin": "current_month_regular_day_1",
                },
            ]
            choices = (
                list(dict.fromkeys([*first_choices, base]))
                if day_part is None
                else first_choices if day_part == "first_half" else [base]
            )
            missing_part = day_part is None and len(choices) > 1
            precedence_unresolved = day_part == "first_half" and len(first_choices) > 1
            if len(choices) == 1:
                selected = choices[0]
            assignment = (
                {
                    "previous_lunar": previous_lunar,
                    "omitted_day_calculation": omitted,
                    "slots": slots,
                    "selected_day_part": day_part,
                    "source_url": bundle["hinoo_addendum"]["source_url"],
                    "locator": bundle["hinoo_addendum"]["short_month_locator"],
                    "clock_mapping": "not_automatic_explicit_textual_half_required_when_candidates_differ",
                    "leap_short_month_precedence": precedence,
                }
                if omitted or leap
                else None
            )
    effective_leap_policy = "repeat_month" if profile == HINOO_PROFILE else leap_policy
    leap_unresolved = leap and effective_leap_policy == "unresolved"
    resolved = (
        not leap_unresolved
        and not missing_part
        and not precedence_unresolved
        and not previous_context_unavailable
    )
    reason = (
        "leap_month_policy_unresolved"
        if leap_unresolved
        else (
            "hinoo_previous_lunar_context_unavailable"
            if previous_context_unavailable
            else (
                "hinoo_leap_short_month_precedence_unresolved"
                if precedence_unresolved
                else (
                    "hinoo_short_month_day_part_unresolved"
                    if missing_part
                    else "computed_under_declared_profile"
                )
            )
        )
    )
    return {
        "source_bundle_sha256": source.sha256,
        "calendar_profile": profile,
        "mansion_method_id": (
            bundle["hinoo_addendum"]["id"] if profile == HINOO_PROFILE else bundle["id"]
        ),
        "host_calculation": host,
        "requested_leap_month_policy": leap_policy,
        "effective_leap_month_policy": effective_leap_policy,
        "calendar_day_part": day_part,
        "resolved": resolved,
        "resolution_reason": reason,
        "natal_su27": selected if resolved else None,
        "candidate_su27": choices[0] if not resolved and len(choices) == 1 else None,
        "candidate_su27s": choices if not resolved else [],
        "candidate_set_complete_under_declared_reconstructions": not previous_context_unavailable
        and not leap_unresolved,
        "short_month_assignment": assignment,
        "hinoo_source": (
            _hinoo_reference(bundle, calculate) if profile == HINOO_PROFILE else None
        ),
        "historical_calendar_reconstruction": False,
        "classical_full_profile_acceptance": False,
    }


def _hinoo_reference(
    bundle: dict[str, Any], calculate: Callable[[int, int], dict[str, Any]]
) -> dict[str, Any]:
    reference: dict[str, Any] = deepcopy(bundle["hinoo_addendum"])
    reference["critical_calendar_reference"] = critical_calendar_reference(
        reference, [calculate(12, day) for day in (1, 15, 30)]
    )
    return reference
