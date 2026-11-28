"""Compact structured Liuyao evidence, focus resolution, and timing candidates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic_core import PydanticCustomError

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    SOLAR_TERM_NAMES,
    get_bazi_month_boundaries,
)
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.liuyao.strength import (
    ADVANCES,
    COMBINES,
    CONTROLS,
    ELEMENTS,
    GENERATES,
    SOURCES,
    STAGES,
    branch_facts,
    clash,
    classify_day_clash,
    detect_three_harmony,
    element_relation,
    month_strength,
    xunkong,
)
from fatebridge.utils.civil_clock import LOCAL_INTERVAL_METHOD_ID as METHOD_ID
from fatebridge.utils.civil_clock import local_interval_preimages
from fatebridge.utils.civil_time import NominalClockLabel, UTCCalendar, ZonedCalendar
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.timezones import is_unspecified_local_time

KINSHIPS = ("父母", "兄弟", "子孙", "妻财", "官鬼")
FOCUS_KINDS = ("visible", "changed", "hidden", "month", "day")


def month_model_comparison(
    moment: datetime,
    *,
    month_branch: str,
    boundary_models: tuple[str, str],
) -> dict[str, object] | None:
    """Report alternate path metadata only when analytic solar model is active."""
    if MODEL_ID not in boundary_models:
        return None
    return {
        "status": "not_compared_incomplete_native_probes",
        "calculation_month_branch": month_branch,
        "comparison_utc": moment.astimezone(timezone.utc).isoformat(),
        "compared_month_boundaries": 0,
        "missing_native_probes": [
            f"{year}:{name}"
            for year in range(moment.year - 1, moment.year + 2)
            for name in SOLAR_TERM_NAMES
            if name in BAZI_MONTH_START_TERMS
        ],
        "coverage_complete": False,
        "selected_models": sorted(set(boundary_models)),
        "native_models": [],
        "active_boundary_differences": [],
    }


def _kinship(palace: str, element: str) -> str:
    return {
        "比和": "兄弟",
        "生爻": "子孙",
        "克爻": "妻财",
        "爻生": "父母",
        "爻克": "官鬼",
    }[element_relation(palace, element)]


def role_against_focus(element: str, focus: str) -> str:
    """Return 用神/元神/忌神/仇神/同类/用神所生 role of element against focus element."""
    if element == focus:
        return "同类"
    if GENERATES[element] == focus:
        return "元神"
    if CONTROLS[element] == focus:
        return "忌神"
    yuan = next(e for e in GENERATES if GENERATES[e] == focus)
    ji = next(e for e in CONTROLS if CONTROLS[e] == focus)
    if CONTROLS[element] == yuan and GENERATES[element] == ji:
        return "仇神"
    return "用神所生"


def resolve_focus(
    *,
    focus_line: int | None,
    focus_kinship: str | None,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    palace: str,
    month: str,
    day: str,
    focus_kind: str | None = None,
) -> dict[str, Any]:
    """Resolve explicit focus line/kinship/kind without keyword guessing."""
    if focus_line is not None and (
        type(focus_line) is not int or not 1 <= focus_line <= 6
    ):
        raise ParameterError(
            "focus_line 必须是1至6的整数",
            [
                {
                    "path": "focus_line",
                    "code": "invalid_focus_line",
                    "constraints": {"ge": 1, "le": 6},
                }
            ],
        )
    if focus_kind is not None and focus_kind not in FOCUS_KINDS:
        raise ParameterError(
            "focus_kind 必须为visible、changed、hidden、month或day",
            [
                {
                    "path": "focus_kind",
                    "code": "invalid_focus_kind",
                    "constraints": {"allowed": list(FOCUS_KINDS)},
                }
            ],
        )
    if focus_kinship is not None and focus_kinship not in KINSHIPS:
        raise ParameterError(
            "focus_kinship 必须为父母、兄弟、子孙、妻财或官鬼",
            [
                {
                    "path": "focus_kinship",
                    "code": "invalid_focus_kinship",
                    "constraints": {"allowed": list(KINSHIPS)},
                }
            ],
        )
    if focus_kind in ("day", "month") and focus_line is not None:
        raise ParameterError(
            "日月取用不能同时指定爻位",
            [{"path": "focus_line", "code": "conflicting_focus_line"}],
        )
    if (
        focus_line is None
        and focus_kinship is None
        and focus_kind not in ("day", "month")
    ):
        if focus_kind is not None:
            raise ParameterError(
                "指定爻类取用还须提供focus_line或focus_kinship",
                [
                    {
                        "path": "focus_kind",
                        "code": "missing_focus_target",
                        "constraints": {
                            "required_with": ["focus_line", "focus_kinship"]
                        },
                    }
                ],
            )
        return {
            "status": "not_requested",
            "selected": None,
            "candidates": [],
            "roles": [],
        }

    def candidate(
        location: str,
        branch: str,
        position: int | None = None,
        moving: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "location": location,
            "position": position,
            "branch": branch,
            "element": ELEMENTS[branch],
            "liuqin": _kinship(palace, ELEMENTS[branch]),
            **({"moving": moving} if moving is not None else {}),
        }

    visible = [
        candidate("visible", r["branch"], r["position"], r["change"]) for r in lines
    ]
    changed = [
        candidate("changed", r["changed_branch"], r["position"], True)
        for r in lines
        if r["change"]
    ]
    day_month = [candidate("month", month), candidate("day", day)]
    concealed = [candidate("hidden", r["branch"], r["position"]) for r in hidden]
    pool = {
        "visible": visible,
        "changed": changed,
        "month": day_month[:1],
        "day": day_month[1:],
        "hidden": concealed,
    }
    selected = None
    if focus_line is not None:
        location = focus_kind or "visible"
        matching = [r for r in pool[location] if r["position"] == focus_line]
        if len(matching) != 1:
            available_positions = sorted(
                r["position"] for r in pool[location] if r.get("position") is not None
            )
            raise ParameterError(
                "所选爻位不存在该类用爻；静爻不能作为变爻，未列伏神不能凭空取用",
                [
                    {
                        "path": "focus_line",
                        "code": "focus_line_not_available",
                        "constraints": {"available": available_positions},
                    }
                ],
            )
        selected = matching[0]
        status = (
            "explicit_line" if location == "visible" else f"explicit_{location}_line"
        )
    elif focus_kind in ("day", "month"):
        selected = pool[focus_kind][0]
        status = f"explicit_{focus_kind}"
    else:
        status = "unresolved"
    if selected is not None:
        if focus_kinship is not None and selected["liuqin"] != focus_kinship:
            raise ParameterError(
                "所选用爻的六亲与focus_kinship不一致",
                [
                    {
                        "path": "focus_kinship",
                        "code": "focus_kinship_mismatch",
                        "constraints": {"expected": selected["liuqin"]},
                    }
                ],
            )
        focus_kinship = selected["liuqin"]
    matching_visible = [r for r in visible if r["liuqin"] == focus_kinship]
    matching_changed = [r for r in changed if r["liuqin"] == focus_kinship]
    if focus_kind is not None:
        candidates = [r for r in pool[focus_kind] if r["liuqin"] == focus_kinship]
        if selected is None and len(candidates) == 1:
            selected, status = candidates[0], f"unique_{focus_kind}_candidate"
        elif selected is None:
            status = (
                f"multiple_{focus_kind}_candidates"
                if candidates
                else f"no_{focus_kind}_candidate"
            )
    elif matching_visible:
        candidates = [*matching_visible, *matching_changed]
        if selected is None and len(candidates) == 1:
            selected, status = matching_visible[0], "unique_visible_candidate"
        elif selected is None:
            status = (
                "multiple_visible_and_changed_candidates"
                if matching_changed
                else "multiple_visible_candidates"
            )
    else:
        alternatives = [r for r in day_month if r["liuqin"] == focus_kinship]
        candidates = [*matching_changed, *alternatives]
        if matching_changed:
            status = "changed_candidates_before_hidden"
        elif alternatives:
            status = "day_month_candidates_before_hidden"
        else:
            candidates = [r for r in concealed if r["liuqin"] == focus_kinship]
            status = "hidden_candidates" if candidates else "no_candidate"
    focus_element = (
        selected["element"]
        if selected
        else (candidates[0]["element"] if candidates else None)
    )
    return {
        "status": status,
        "requested_kinship": focus_kinship,
        "requested_kind": focus_kind,
        "selected": selected,
        "candidates": candidates,
        "roles": (
            [
                {
                    "location": "visible",
                    "position": row["position"],
                    "branch": row["branch"],
                    "role": (
                        "用神"
                        if selected
                        and selected["location"] == "visible"
                        and row["position"] == selected["position"]
                        else role_against_focus(row["element"], focus_element)
                    ),
                }
                for row in lines
            ]
            if focus_element
            else []
        ),
    }


def timing_candidates(
    *,
    moment: datetime,
    timezone_name: str,
    days: int,
    selected: dict[str, Any] | None,
    month: str,
    original_ganzhi: str,
    line: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute day-level sexagenary windows when timing_days > 0."""
    if type(days) is not int or not 0 <= days <= 60:
        raise ValueError("timing_days 必须是0至60的整数")
    if not days:
        return {
            "status": "not_requested",
            "windows": [],
            "granularity": "sexagenary_day",
        }
    if selected and selected["location"] not in ("visible", "changed"):
        return {
            "status": "nonvisible_focus_requires_separate_timing_rules",
            "windows": [],
            "granularity": "sexagenary_day",
        }
    if selected is None or line is None:
        return {
            "status": "requires_unambiguous_visible_focus",
            "windows": [],
            "granularity": "sexagenary_day",
        }
    zone = moment.tzinfo
    if zone is None or moment.utcoffset() is None:
        raise ValueError("日级条件窗口需要带时区的起卦时刻")
    cast_utc = ZonedCalendar.from_datetime(moment).utc
    _, next_month, _, _ = get_bazi_month_boundaries(moment, timezone_name)
    next_month_day = next_month.point.day
    branch = selected["branch"]
    original_void = branch in xunkong(original_ganzhi)
    effective_ordinal = moment.toordinal() + (moment.hour >= 23)
    windows: list[tuple[UTCCalendar, dict[str, Any]]] = []
    left_original_xun = False
    for index in range(days):
        ordinal = effective_ordinal + index
        wall_start = NominalClockLabel(ordinal - 1, 23 * 3_600_000_000)
        wall_end = NominalClockLabel(ordinal, 23 * 3_600_000_000)
        try:
            intervals = local_interval_preimages(wall_start, wall_end, zone)
        except PydanticCustomError as error:
            if error.type != "unresolved_timezone_offset":
                raise
            intervals = []
        pillar = "".join(
            BaZiCalendar.calculate_day_pillar(
                *wall_end.date_parts, apply_late_zi_rollover=False
            )
        )
        day = pillar[1]
        matches = []
        if selected["location"] == "changed" and day == branch:
            matches.append("变爻逢值")
        elif selected["location"] == "visible" and day == branch:
            matches.append("动逢值" if line["change"] else "静逢值")
        if (
            selected["location"] == "visible"
            and line["change"]
            and day == COMBINES[branch]
        ):
            matches.append("动逢合")
        if (
            selected["location"] == "visible"
            and not line["change"]
            and day == clash(branch)
        ):
            matches.append("静逢冲")
        if original_void and day in (branch, clash(branch)):
            matches.append("旬空填实" if day == branch else "旬空逢冲")
        if original_void and not left_original_xun and pillar[0] == "甲" and index > 0:
            matches.append("离开起卦日所在旬")
            left_original_xun = True
        if clash(month) == branch and day == COMBINES[branch]:
            matches.append("原局月破逢合")
        if not matches:
            continue
        for low, high in intervals:
            clipped = max(low, cast_utc)
            if clipped >= high:
                continue
            start = ZonedCalendar(clipped, zone)
            end = ZonedCalendar(high, zone)
            end_is_unspecified = is_unspecified_local_time(end.rule_sample())
            last_member = high.shifted(timedelta(microseconds=-1))
            windows.append(
                (
                    clipped,
                    {
                        "effective_date": wall_end.date_isoformat(),
                        "day_ganzhi": pillar,
                        "start_at": start.isoformat(),
                        "end_at": (high if end_is_unspecified else end).isoformat(),
                        "matched_rules": list(matches),
                        "requires_month_reassessment": last_member.julian_day_exact()
                        >= next_month_day,
                    },
                )
            )
    windows.sort(key=lambda item: item[0])
    return {
        "status": "condition_windows_only",
        "granularity": "sexagenary_day",
        "requested_days": days,
        "windows": [window for _, window in windows],
        "source_url": SOURCES["relations"],
    }


def build_liuyao_evidence(
    *,
    day_ganzhi: str,
    month_branch: str,
    current_code: str,
    changed_code: str,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    palace_element: str,
    moment: datetime,
    timezone_name: str,
    shensha: dict[str, dict[str, Any]] | None = None,
    line_shensha: dict[int, list[str]] | None = None,
    moving_focus_guidance: dict[str, Any] | None = None,
    focus_line: int | None = None,
    focus_kinship: str | None = None,
    focus_kind: str | None = None,
    timing_days: int = 0,
) -> dict[str, Any]:
    """Build compact, deterministic Liuyao structural evidence (<25 KB audit)."""
    void = xunkong(day_ganzhi)
    day = day_ganzhi[1]
    moving_elements = {ELEMENTS[line["branch"]] for line in lines if line.get("change")}
    rows: list[dict[str, Any]] = []
    dark_moving_positions: set[int] = set()
    for line in lines:
        pos = line["position"]
        branch = line["branch"]
        elem = ELEMENTS[branch]
        facts = branch_facts(branch, month_branch, day, void)
        monthly = month_strength(branch, month_branch)
        has_moving_support = any(
            GENERATES[src] == elem or src == elem for src in moving_elements
        )
        clash_flags = classify_day_clash(
            branch=branch,
            is_moving=bool(line["change"]),
            month=month_branch,
            day=day,
            facts=facts,
            monthly=monthly,
            has_moving_support=has_moving_support,
        )
        if clash_flags["is_dark_moving"]:
            dark_moving_positions.add(pos)
        row: dict[str, Any] = {
            "position": pos,
            "branch": branch,
            "month_strength": monthly["category"],
            "day_growth_stage": STAGES[elem].get(day),
            "shensha": (line_shensha or {}).get(pos, []),
            **facts,
            **clash_flags,
        }
        if line["change"]:
            old, new = branch, line["changed_branch"]
            relation = element_relation(ELEMENTS[new], ELEMENTS[old])
            row["transformation"] = {
                "branch": new,
                "back_relation": {"生爻": "回头生", "克爻": "回头克"}.get(
                    relation, relation
                ),
                "advance": ADVANCES.get(old) == new,
                "retreat": ADVANCES.get(new) == old,
                **branch_facts(new, month_branch, day, void),
            }
        rows.append(row)

    for candidate in hidden:
        candidate["calendar_relations"] = branch_facts(
            candidate["branch"], month_branch, day, void
        )
        candidate["flying_to_hidden_relation"] = element_relation(
            ELEMENTS[candidate["flying_branch"]], ELEMENTS[candidate["branch"]]
        )

    focus = resolve_focus(
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        lines=lines,
        hidden=hidden,
        palace=palace_element,
        month=month_branch,
        day=day,
    )
    three_harmony = detect_three_harmony(
        lines=lines,
        dark_moving_positions=dark_moving_positions,
        month=month_branch,
        day=day,
    )
    result: dict[str, Any] = {
        "ruleset_id": "zengshan_structural_v2",
        "ruleset_version": "2.0.0",
        "lines": rows,
        "hidden_spirits": hidden,
        "hidden_policy": "仅按本卦缺失六亲取本宫纯卦同位伏神；变爻是否现该六亲另行标注，不掩盖本卦伏神。",
        "shensha": shensha or {},
        "three_harmony": three_harmony,
        "moving_focus_guidance": moving_focus_guidance or {},
        "focus": focus,
    }
    if timing_days:
        selected = focus.get("selected")
        selected_line = (
            lines[selected["position"] - 1]
            if selected and selected.get("position")
            else None
        )
        result["timing_candidates"] = timing_candidates(
            moment=moment,
            timezone_name=timezone_name,
            days=timing_days,
            selected=selected,
            month=month_branch,
            original_ganzhi=day_ganzhi,
            line=selected_line,
        )
    return result
