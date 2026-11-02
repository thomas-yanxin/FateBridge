"""Bind the selected Jingben relation ledger to its actual course inputs."""

from __future__ import annotations

from typing import Any

from .metaphysics.common import (
    SIX_CLASH_BRANCHES,
    branch_element_text,
    stem_element_text,
)
from .metaphysics.jinkou_relations import (
    CALENDAR_CONTEXTS,
    JUE_CONTEXTS,
    SI_BAI,
    SI_JUE,
    SOURCE_SHA256,
    SOURCE_URL,
    absolute_check,
    calendar_check,
    calendar_target,
    defeat_check,
    structural_relations,
)

RULE = "jinkou.jingben_relations"
SECTION = "卷上·四绝/四败/岁君建破/论岁神"
POSITIONS = ("人元", "贵神", "将神", "地分")


def compare(
    actual: Any, expected: Any, path: str = "", *, complete: bool = False
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or (
            complete and expected.keys() - actual.keys()
        ):
            raise ValueError("完整京本结构关系缺少原始依据或判定")
        for key in actual.keys() & expected.keys():
            compare(actual[key], expected[key], path + "." + key, complete=complete)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("京本结构关系须保留所选完整队列")
        if path.endswith(".checks") and expected:
            keys = (
                ("left_position", "right_position")
                if "left_position" in expected[0]
                else (
                    ("rule_id", "position")
                    if "rule_id" in expected[0]
                    else ("position",)
                )
            )
            if all(
                isinstance(r, dict) and all(isinstance(r.get(k), str) for k in keys)
                for r in actual
            ):
                observed = {tuple(r[k] for k in keys): r for r in actual}
                canonical = {tuple(r[k] for k in keys): r for r in expected}
                if len(observed) != len(actual) or observed.keys() != canonical.keys():
                    raise ValueError("京本结构关系的角色／规则不可重复或替换")
                for identity, row in observed.items():
                    compare(row, canonical[identity], path, complete=complete)
                return
        for a, e in zip(actual, expected, strict=True):
            compare(a, e, path, complete=complete)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("京本四绝、四败或岁日关系与同次原始依据不一致")


def same(value: dict[str, Any], key: str, expected: Any) -> None:
    if key in value:
        compare(value[key], expected)


def branch(value: dict[str, Any], key: str) -> str | None:
    v = value.get(key)
    if v is not None and (not isinstance(v, str) or v not in SIX_CLASH_BRANCHES):
        raise ValueError("京本结构关系须使用单个明确地支")
    return v if isinstance(v, str) else None


def unknown_is_not_a_verdict(value: dict[str, Any], anchors: tuple[str, ...]) -> None:
    if (
        any(k in value and value[k] is None for k in anchors)
        and value.get("matched") is not None
    ):
        raise ValueError("明确缺失的关系输入不能判为命中或不命中")


def validate_absolute_row(value: dict[str, Any]) -> None:
    left, right = value.get("left_position"), value.get("right_position")
    a, b = branch(value, "left_branch"), branch(value, "right_branch")
    if right == "命支":
        same(value, "left_position", "将神")
        same(value, "classification", "大绝")
        same(value, "original_pdf_page", 109)
        if b is None:
            same(value, "matched", None)
            same(value, "element", None)
        return
    contexts = [
        c
        for c in JUE_CONTEXTS
        if (left is None or c[0] == left) and (right is None or c[1] == right)
    ]
    if not contexts:
        raise ValueError("所选四绝不存在该角色配对")
    if len(contexts) == 1:
        same(value, "classification", contexts[0][2])
        same(value, "original_pdf_page", contexts[0][3])
    if a is not None and b is not None:
        phase = SI_JUE.get(frozenset((a, b)))
        same(value, "matched", phase is not None)
        same(value, "element", phase)
        if left is not None and right is not None:
            compare(value, absolute_check(left, right, a, b))
    elif (
        any(k in value and value[k] is None for k in ("left_branch", "right_branch"))
        and value.get("matched") is not None
    ):
        raise ValueError("明确缺失的四绝输入不能判为命中或不命中")


def validate_defeat_row(value: dict[str, Any]) -> None:
    unknown_is_not_a_verdict(value, ("element", "seat_branch"))
    position, phase = value.get("position"), value.get("element")
    if position is not None and position not in POSITIONS[:3]:
        raise ValueError("所选四败仅核对人元、贵神、将神临共同地分")
    if phase is not None and (not isinstance(phase, str) or phase not in SI_BAI):
        raise ValueError("四败须使用明确的五行")
    seat = branch(value, "seat_branch")
    branch(value, "bai_branch")
    same(value, "original_pdf_page", 110)
    if phase is not None:
        same(value, "bai_branch", SI_BAI[phase])
        if seat is not None:
            same(value, "matched", seat == SI_BAI[phase])
            if position is not None:
                compare(value, defeat_check(position, phase, seat))


def validate_calendar_row(value: dict[str, Any]) -> None:
    unknown_is_not_a_verdict(value, ("rule_id", "branch", "reference_branch"))
    rid, position = value.get("rule_id"), value.get("position")
    a, b = branch(value, "branch"), branch(value, "reference_branch")
    if rid is None:
        return
    context = next((c for c in CALENDAR_CONTEXTS if c[0] == rid), None)
    if context is None or (position is not None and position not in context[2]):
        raise ValueError("岁建仅神将、日建仅将神；不能替换适用位置")
    same(value, "name", context[1])
    same(value, "original_pdf_page", context[4])
    if a is not None and b is not None:
        same(value, "matched", a == calendar_target(rid, b))
        if position is not None:
            compare(value, calendar_check(rid, position, a, b))


def validate_queue(value: dict[str, Any], group: str) -> None:
    if value.get("checks") is None:
        return
    if group == "si_jue":
        expected = [
            dict(
                left_position=a, right_position=b, classification=c, original_pdf_page=p
            )
            for a, b, c, p in JUE_CONTEXTS
        ]
        check = validate_absolute_row
    elif group == "si_bai":
        expected = [dict(position=p, original_pdf_page=110) for p in POSITIONS[:3]]
        check = validate_defeat_row
    else:
        expected = [
            dict(rule_id=rid, name=name, position=p, original_pdf_page=page)
            for rid, name, positions, _, page in CALENDAR_CONTEXTS
            for p in positions
        ]
        check = validate_calendar_row
    compare(value["checks"], expected, "." + group + ".checks")
    for row in value["checks"]:
        check(row)


def bind(anchors: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if key in anchors:
        compare(value, anchors[key])
    anchors[key] = value


def relation_anchors(value: dict[str, Any]) -> dict[str, Any]:
    anchors: dict[str, Any] = {}
    calendar = value.get("calendar") or {}
    for key in ("year_branch", "day_branch"):
        bind(anchors, key, branch(calendar, key))
    for row in calendar.get("checks") or []:
        if row.get("position") is not None:
            bind(anchors, row["position"], branch(row, "branch"))
        rid = row.get("rule_id")
        if rid in {c[0] for c in CALENDAR_CONTEXTS}:
            bind(
                anchors,
                "year_branch" if rid.startswith("year") else "day_branch",
                branch(row, "reference_branch"),
            )
    for row in (value.get("si_jue") or {}).get("checks") or []:
        for role, fact in (
            ("left_position", "left_branch"),
            ("right_position", "right_branch"),
        ):
            if row.get(role) is not None:
                key = {"日支": "day_branch", "时支": "hour_branch"}.get(
                    row[role], row[role]
                )
                bind(anchors, key, branch(row, fact))
    for row in (value.get("si_bai") or {}).get("checks") or []:
        bind(anchors, "地分", branch(row, "seat_branch"))
    return anchors


def validate_relations(value: dict[str, Any]) -> None:
    for key, expected in dict(
        ruleset_id="jinkou_jingben_relations_v1",
        source_url=SOURCE_URL,
        source_sha256=SOURCE_SHA256,
        transcription_url="https://divinehere.com/classic/0905011.html",
        source_section=SECTION,
        complete_classical_conformance=False,
    ).items():
        same(value, key, expected)
    if "transcription_variants" in value:
        compare(
            value["transcription_variants"],
            [
                dict(
                    branches=["午", "亥"],
                    scan_element="火",
                    transcription_element="水",
                    original_pdf_page=109,
                ),
                dict(
                    branches=["子", "巳"],
                    scan_element="水",
                    transcription_element="火",
                    original_pdf_page=109,
                ),
            ],
        )
    for group in ("si_jue", "si_bai", "calendar"):
        if (
            group in value
            and value[group] is not None
            and not isinstance(value[group], dict)
        ):
            raise ValueError("京本结构关系的已给出分组须为对象")
        if isinstance(value.get(group), dict):
            validate_queue(value[group], group)
    relation_anchors(value)


def validate_relation_anchors(board: dict[str, Any], *, complete: bool = False) -> None:
    primary = board.get("relations")
    traces = [t for t in board.get("rule_trace") or [] if t.get("rule_id") == RULE]
    if len(traces) > 1 or (complete and len(traces) != 1):
        raise ValueError("京本结构关系须保留唯一同次规则轨迹")
    nodes = [primary] if isinstance(primary, dict) else []
    for trace in traces:
        same(trace, "source_url", SOURCE_URL)
        same(trace, "source_section", SECTION)
        if isinstance(trace.get("result"), dict):
            nodes.append(trace["result"])
        elif complete:
            raise ValueError("完整京本结构关系轨迹缺失计算结果")
    if complete and not isinstance(primary, dict):
        raise ValueError("完整金口诀须保留京本结构关系")
    anchors: dict[str, Any] = {}
    for node in nodes:
        validate_relations(node)
        for key, val in relation_anchors(node).items():
            bind(anchors, key, val)
    stars = board.get("branch_stars") or {}
    bind(anchors, "year_branch", stars.get("year_branch"))
    day = (board.get("calendar_policy") or {}).get("effective_day_ganzhi")
    if isinstance(day, str) and len(day) == 2:
        bind(anchors, "day_branch", day[1])
    for child in (board.get("qi_evidence") or {}, board.get("combinations") or {}):
        bind(anchors, "day_branch", child.get("day_branch"))
    overview = board.get("overview") or {}
    bind(
        anchors,
        "hour_branch",
        (overview.get("diurnal_evidence") or {}).get("hour_branch"),
    )
    bind(
        anchors,
        "hour_branch",
        (board.get("definition_evidence") or {}).get("hour_branch"),
    )
    rows = board.get("rows")
    canonical = []
    if (
        isinstance(rows, list)
        and len(rows) == 4
        and [r.get("label") for r in rows] == list(POSITIONS)
    ):
        for i, row in enumerate(rows):
            content = row.get("content")
            if content is None:
                break
            try:
                phase = (stem_element_text if i == 0 else branch_element_text)(content)
            except (KeyError, TypeError) as exc:
                raise ValueError("京本结构关系须使用本课人元干及三支") from exc
            canonical.append(dict(row, element=phase))
            if i:
                bind(anchors, POSITIONS[i], content)
        if len(canonical) == 4:
            for node in nodes:
                for c in (node.get("si_bai") or {}).get("checks") or []:
                    if c.get("position") in POSITIONS[:3]:
                        p = POSITIONS.index(c["position"])
                        same(c, "element", canonical[p]["element"])
    for node in nodes:
        if primary is not None:
            compare(node, primary)
    year = branch(anchors, "year_branch")
    day = branch(anchors, "day_branch")
    hour = branch(anchors, "hour_branch")
    if len(canonical) != 4 or year is None or day is None or hour is None:
        if complete:
            raise ValueError("完整京本结构关系缺少本课四位或年月日时依据")
        return
    natal_known = False
    natal = None
    source = None
    for node in nodes:
        n = (node.get("si_jue") or {}).get("natal")
        if isinstance(n, dict) and "right_branch" in n:
            if natal_known:
                compare(n["right_branch"], natal)
            natal_known = True
            natal = n["right_branch"]
            if "input_source" in n:
                if source is not None:
                    compare(n["input_source"], source)
                source = n["input_source"]
    if complete and not natal_known:
        raise ValueError("完整京本结构关系须保留可空本命支依据")
    expected = structural_relations(
        canonical,
        year_branch=year,
        day_branch=day,
        hour_branch=hour,
        natal_branch=natal,
        natal_branch_source=source,
    )
    if not natal_known:
        expected["si_jue"].pop("natal")
        expected["si_jue"].pop("unavailable")
    for node in nodes:
        compare(node, expected, complete=complete)


def require_complete_relations(board: dict[str, Any]) -> None:
    validate_relation_anchors(board, complete=True)
