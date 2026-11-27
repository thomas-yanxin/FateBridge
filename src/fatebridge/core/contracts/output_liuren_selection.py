"""Bind nine-method evidence to the returned day and complete rotating sky.

This reuses the domain derivation. It proves output consistency, not an
independent classical oracle or astronomical accuracy.
"""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.liureng.board import derive_selection

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SELECTION_TRACES = frozenset(
    {
        "liuren.direct_or_remote_candidates",
        "liuren.polarity",
        "liuren.harm_paths",
        "liuren.harm_depth",
        "liuren.harm_tie",
        "liuren.named_subtypes",
        "liuren.transmissions.result",
    }
)


def compare(actual: Any, expected: Any) -> None:
    """Check present facts without manufacturing projected-out keys."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        if actual.keys() - expected.keys():
            raise ValueError("九宗门证据含本次推导中不存在的字段")
        for key in actual.keys() & expected.keys():
            compare(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("九宗门证据队列与同次计算不一致")
        for a, e in zip(actual, expected):
            compare(a, e)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("九宗门选课、三传、细名或推导轨迹与日干支天地盘不一致")


def expected_selection(
    board: dict[str, Any], day: str | None = None
) -> dict[str, Any] | None:
    days = [day] if day is not None else []
    for name, key in (
        ("calendar_policy", "effective_day_ganzhi"),
        ("auxiliary_stars", "day_ganzhi"),
        ("transmission_relations", "day_ganzhi"),
        ("emptiness_evidence", "day_ganzhi"),
    ):
        value = board.get(name)
        if isinstance(value, dict) and value.get(key) is not None:
            days.append(value[key])
    if not days:
        return None
    if (
        any(not isinstance(d, str) or d not in SEXAGENARY_INDEX for d in days)
        or len(set(days)) != 1
    ):
        raise ValueError("九宗门计算日干支依据不一致")
    rows = board.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        return None
    if any(not isinstance(r, dict) for r in rows):
        raise ValueError("九宗门天地盘行必须是对象")
    if any(r.get("earth_branch") is None or r.get("sky_branch") is None for r in rows):
        return None
    if any(
        not isinstance(r[k], str) for r in rows for k in ("earth_branch", "sky_branch")
    ):
        raise ValueError("九宗门天地盘须使用十二地支")
    sky = {r["earth_branch"]: r["sky_branch"] for r in rows}
    if set(sky) != set(BRANCHES) or set(sky.values()) != set(BRANCHES):
        raise ValueError("九宗门需要完整且无重复的天地盘")
    offsets = {(BRANCHES.index(v) - BRANCHES.index(k)) % 12 for k, v in sky.items()}
    if len(offsets) != 1:
        raise ValueError("九宗门天地盘须为同一次顺布旋转盘")

    raw_meta = board.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    shehai = meta.get("shehai_method", "depth_first")
    if shehai not in ("depth_first", "meng_zhong_first"):
        shehai = "depth_first"
    shehai_method: Literal["depth_first", "meng_zhong_first"] = (
        "meng_zhong_first" if shehai == "meng_zhong_first" else "depth_first"
    )
    return derive_selection(
        days[0],
        sky,
        shehai_method=shehai_method,
        harm_include_terminal=bool(meta.get("harm_include_terminal", False)),
    )


def trace_expectations(selection: dict[str, Any]) -> list[dict[str, Any]]:
    classification = selection["classification"]
    traces: list[dict[str, Any]] = selection["rule_trace"]
    return traces + [
        dict(
            rule_id="liuren.named_subtypes",
            source_section=classification["source_section"],
            result=classification,
        ),
        dict(
            rule_id="liuren.transmissions.result",
            source_section="九宗门",
            result=dict(
                style=selection["board_style"],
                detail=selection["board_style_detail"],
                branches=selection["branches"],
                source_lesson=selection["selected_lesson_index"],
            ),
        ),
    ]


def validate_selection(
    board: dict[str, Any], day: str | None = None, *, complete: bool = False
) -> None:
    selection = expected_selection(board, day)
    if selection is None:
        if complete:
            raise ValueError("完整九宗门输出缺少日干支或天地盘依据")
        return
    for key in ("four_lessons", "board_style", "board_style_detail", "classification"):
        if complete:
            if key not in board:
                raise ValueError("完整九宗门输出缺少取传字段")
            require_shape(board[key], selection[key])
        if key in board:
            compare(board[key], selection[key])
    meta = board.get("meta")
    keys = ("selected_lesson_index", "selected_lesson_relation")
    wanted_meta = {key: selection[key] for key in keys}
    if complete:
        require_shape(meta, wanted_meta)
    if isinstance(meta, dict):
        compare({key: meta[key] for key in keys if key in meta}, wanted_meta)
    transmissions = board.get("three_transmissions")
    labels = ("initial", "middle", "final")
    wanted_transmissions = {
        "method": selection["transmission_method"],
        **{
            label: {"branch": branch}
            for label, branch in zip(labels, selection["branches"])
        },
    }
    if complete:
        require_shape(transmissions, wanted_transmissions)
    if isinstance(transmissions, dict):
        present = {k: transmissions[k] for k in ("method",) if k in transmissions}
        for label in labels:
            if label in transmissions:
                row = transmissions[label]
                present[label] = (
                    {"branch": row["branch"]}
                    if isinstance(row, dict) and "branch" in row
                    else ({} if isinstance(row, dict) else row)
                )
        compare(present, wanted_transmissions)
    actual = [
        t for t in board.get("rule_trace") or [] if t.get("rule_id") in SELECTION_TRACES
    ]
    ids = [t["rule_id"] for t in actual]
    if len(ids) != len(set(ids)):
        raise ValueError("九宗门轨迹重复或不属于本次取传分支")


def require_shape(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) - set(actual):
            raise ValueError("完整九宗门输出缺少选课计算依据")
        for key, value in expected.items():
            require_shape(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整九宗门输出缺少完整队列")
        for a, e in zip(actual, expected):
            require_shape(a, e)
