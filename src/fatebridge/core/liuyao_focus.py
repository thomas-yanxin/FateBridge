"""Explicit Liu Yao focus locations, without replacing the original casting."""

from typing import Any

from .liuyao_relations import CONTROLS, ELEMENTS, GENERATES, element_relation

KINSHIPS = ("父母", "兄弟", "子孙", "妻财", "官鬼")
FOCUS_KINDS = ("visible", "changed", "hidden", "month", "day")


def kinship(palace: str, element: str) -> str:
    return {
        "比和": "兄弟",
        "生爻": "子孙",
        "克爻": "妻财",
        "爻生": "父母",
        "爻克": "官鬼",
    }[element_relation(palace, element)]


def role_against_focus(element: str, focus: str) -> str:
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
    if focus_line is not None and (
        type(focus_line) is not int or not 1 <= focus_line <= 6
    ):
        raise ValueError("focus_line 必须是1至6的整数")
    if focus_kind is not None and focus_kind not in FOCUS_KINDS:
        raise ValueError("focus_kind 必须为visible、changed、hidden、month或day")
    if focus_kinship is not None and focus_kinship not in KINSHIPS:
        raise ValueError("focus_kinship 必须为父母、兄弟、子孙、妻财或官鬼")
    if focus_kind in ("day", "month") and focus_line is not None:
        raise ValueError("日月取用不能同时指定爻位")
    if (
        focus_line is None
        and focus_kinship is None
        and focus_kind not in ("day", "month")
    ):
        if focus_kind is not None:
            raise ValueError("指定爻类取用还须提供focus_line或focus_kinship")
        return {
            "status": "not_requested",
            "selected": None,
            "candidates": [],
            "roles": [],
            "scope": "未根据问题关键词自动选用神",
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
            "liuqin": kinship(palace, ELEMENTS[branch]),
            **({"moving": moving} if moving is not None else {}),
        }

    visible = [
        candidate("visible", r["branch"], r["position"], r["change"]) for r in lines
    ]
    # Static positions in the changed hexagram are not actual 变爻.
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
            raise ValueError(
                "所选爻位不存在该类用爻；静爻不能作为变爻，未列伏神不能凭空取用"
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
            raise ValueError("所选用爻的六亲与focus_kinship不一致")
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
        "scope": "取用位置是调用方明确给定的分析前提；本爻与实际变爻均须检查，多现不自动择优，明示日月候选，本变不现才寻伏神。元忌仇为原卦诸爻相对用神的五行角色，不表示已生效。变爻或伏神不能冒充同位原爻。",
    }
