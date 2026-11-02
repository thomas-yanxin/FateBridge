"""Year and lunar-month-start stems, distinct from day/hour and solar months.

The selected text does not settle a universal year boundary or substitution
for Jia. Preserve those unknowns instead of choosing a favorable match.
Month starts use the declared modern lunar calendar on the local civil date,
not an astronomical conjunction instant or an apparent-solar date label.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
    get_day_ganzhi,
    get_lunar_context,
    localize_datetime,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed, sexagenary_text


def resolve_calendar_stems(seed: MetaphysicsSeed) -> dict[str, Any]:
    civil = localize_datetime(seed.input_datetime, seed.timezone)
    policy = {
        "date_clock": "local_civil_date",
        "month_anchor": "selected_lunar_table_month_first_civil_date_00_00",
        "lunar_calendar_scope": f"{LUNAR_SUPPORTED_SOLAR_START.isoformat()}_to_{LUNAR_SUPPORTED_SOLAR_END.isoformat()}_tables_not_universal_historical_calendar_reconstruction",
        "year_boundary": "compare_lichun_and_lunar_new_year_do_not_select_when_different",
        "jia_substitution": "unresolved_no_automatic_selection",
        "astronomical_new_moon_calculated": False,
        "solar_month_stem_used_as_lunar_month_start": False,
    }
    missing: dict[str, Any] = {
        "status": "calendar_anchor_unavailable",
        "effective_stem": None,
        "candidates": [],
        "note": "完整民用历法资料未提供或超出离线农历范围，不猜年界或月朔干。",
    }
    contexts: dict[str, Any] = {
        "year": dict(missing),
        "lunar_month_start": dict(missing),
        "calendar_anchor_policy": policy,
        "civil_datetime": civil.isoformat(),
    }
    # Raw geometry audits deliberately omit a real date/calendar. Do not turn
    # their placeholder seed date into an asserted historical year/month.
    if "lunar_calendar_support" not in seed.calendar_context:
        return contexts
    lunar = get_lunar_context(civil, timezone_name=seed.timezone)
    if lunar is None:
        return contexts
    solar_year = seed.pillars.get("year")
    lunar_year = cast(int, lunar["year"])
    lunar_ganzhi = sexagenary_text((lunar_year - 4) % 60)
    candidates: list[dict[str, Any]] = [
        {
            "policy": "lunar_new_year",
            "ganzhi": lunar_ganzhi,
            "literal_stem": lunar_ganzhi[0],
            "calendar_year": lunar_year,
        }
    ]
    if solar_year is not None:
        ganzhi = "".join(solar_year)
        candidates.insert(
            0, {"policy": "lichun", "ganzhi": ganzhi, "literal_stem": ganzhi[0]}
        )
    agreed = len(candidates) == 2 and len({c["ganzhi"] for c in candidates}) == 1
    contexts["year"] = {
        "status": (
            "literal_stem_resolved"
            if agreed and lunar_ganzhi[0] != "甲"
            else ("unresolved_jia_identity" if agreed else "unresolved_year_boundary")
        ),
        "ganzhi": lunar_ganzhi if agreed else None,
        "literal_stem": lunar_ganzhi[0] if agreed else None,
        "effective_stem": (
            lunar_ganzhi[0] if agreed and lunar_ganzhi[0] != "甲" else None
        ),
        "resolution_policy": (
            "agreed_across_lichun_and_lunar_new_year" if agreed else None
        ),
        "boundary_candidates": candidates,
        "year_boundary_automatically_selected": False,
        "candidates": [],
        "note": "仅当立春与农历年候选一致且非甲时直取岁干；年界不同或甲的身份待核，不据未输出岁格判定不存在。",
    }
    start = civil.date() - timedelta(days=cast(int, lunar["day"]) - 1)
    start_lunar = get_lunar_context(
        datetime.combine(start, datetime.min.time()), timezone_name=seed.timezone
    )
    keys = ("year", "month", "is_leap_month")
    if (
        start_lunar is None
        or start_lunar["day"] != 1
        or any(start_lunar[k] != lunar[k] for k in keys)
    ):
        contexts["lunar_month_start"][
            "note"
        ] = "回推月初不能核成同一农历月初一；不回退为八字月干。"
        return contexts
    start_ganzhi = get_day_ganzhi(start.year, start.month, start.day)
    stem = start_ganzhi[0]
    contexts["lunar_month_start"] = {
        "status": (
            "literal_stem_resolved" if stem != "甲" else "unresolved_jia_identity"
        ),
        "ganzhi": start_ganzhi,
        "literal_stem": stem,
        "effective_stem": stem if stem != "甲" else None,
        "resolution_policy": "literal_first_civil_day_stem" if stem != "甲" else None,
        "anchor_date": start.isoformat(),
        "calendar_year": lunar_year,
        "lunar_month": cast(int, lunar["month"]),
        "is_leap_month": bool(lunar["is_leap_month"]),
        "civil_lunar_day": cast(int, lunar["day"]),
        "candidates": [],
        "note": "取实际农历月初一的日干，不取八字月柱天干；闰月按该闰月自己的初一。此为现代民用历表口径，未复原古历或合朔时刻。",
    }
    return contexts


def match_calendar_stems(
    board: dict[str, Any],
    contexts: dict[str, Any],
    *,
    leader: dict[str, str],
    source: str,
) -> list[dict[str, Any]]:
    """Match literal stems on the actual sky/earth layers, including hosting."""
    from fatebridge.core.metaphysics.qimen_calendar_tables import (
        QIMEN_FUHEAD_HEAVEN_STEM,
    )

    outer = [(i, p) for i, p in enumerate(board["palaces"]) if p["trigram"] != "中"]

    def matching(stem: str) -> list[str]:
        return [
            p["name"]
            for _, p in outer
            if "庚" in p["heaven_stems"] and stem in p["earth_stems"]
        ]

    result = []
    for role, rule_id, name in [
        ("year", "year_stem_block", "岁格"),
        ("lunar_month_start", "lunar_month_start_block", "月朔格"),
    ]:
        context = contexts[role]
        if context["status"] == "unresolved_jia_identity":
            context["candidates"] = [
                {
                    "policy": f"{role}_jia_own_six_instrument",
                    "xun_head": context["ganzhi"],
                    "effective_stem": QIMEN_FUHEAD_HEAVEN_STEM[context["ganzhi"]],
                },
                {
                    "policy": "current_hour_xun_six_instrument",
                    "xun_head": leader["xun_head"],
                    "effective_stem": leader["zhifu_heaven_stem"],
                },
            ]
            for candidate in context["candidates"]:
                candidate.update(
                    {
                        "candidate_matches": matching(candidate["effective_stem"]),
                        "adopted": False,
                    }
                )
        for candidate in context.get("boundary_candidates", []):
            stem = candidate["literal_stem"]
            candidate["candidate_matches"] = matching(stem) if stem != "甲" else None
            candidate["jia_identity_resolved"] = stem != "甲"
            candidate["adopted"] = False
        if context["status"] != "literal_stem_resolved":
            continue
        stem = context["effective_stem"]
        context["evaluations"] = matching(stem)
        for index, palace in outer:
            if palace["name"] not in context["evaluations"]:
                continue
            result.append(
                {
                    "rule_id": rule_id,
                    "name": name,
                    "palace": palace["name"],
                    "facts": {
                        "heaven_stem": "庚",
                        "earth_stem": stem,
                        "anchor_ganzhi": context["ganzhi"],
                        "anchor_date": context.get("anchor_date"),
                    },
                    "source": source,
                    "section": f"卷二·小隔并岁隔月隔日隔时隔·{name}",
                    "source_scan_pages": [29],
                    "evidence_paths": [
                        f"qimen.palaces.{index}",
                        f"qimen.stem_context.{role}",
                    ],
                    "layer": "traditional_rule_match",
                    "traditional_meaning": "原文以庚加岁干或月朔干描述传统阻隔；不据此断现实成败、损失、家人状况或人身后果。",
                    "qualification": {
                        "condition": (
                            "按已明确身份的实际非甲岁干核对庚加岁干"
                            if role == "year"
                            else "按已明确身份的农历本月初一非甲日干核对庚加月朔干"
                        ),
                        "condition_observed": True,
                        "blocking_rule_names": [],
                        "same_palace_conflicts": [],
                        "source_disagreements": list(
                            board.get("source_disagreements", [])
                        ),
                        "stem_identity": dict(context),
                        "stem_role": role,
                        "shared_evidence_group": f"heaven:庚|earth:{stem}|palace:{palace['trigram']}",
                        "independent_outcome_evidence": False,
                        "overall_judgment": "requires_whole_board",
                        "outcome_inference_allowed": False,
                    },
                }
            )
    return result
