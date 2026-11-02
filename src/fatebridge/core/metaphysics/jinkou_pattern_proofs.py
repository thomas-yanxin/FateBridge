"""Every premise of the selected 58 predicates, including failed premises.

The any-of-all expressions are a calculation trace of the existing selected
definitions. They do not settle the six unresolved definitions or repair a
book's inconsistent example. No source-case values are looked up here.
"""

from __future__ import annotations

from typing import Any

from ...utils.data import EARTHLY_BRANCHES
from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES, SIX_CLASH_BRANCHES

ROLES = dict(zip("HGJD", ("人元", "贵神", "将神", "地分")))

# Each outer list is an alternative; every term within one alternative must
# hold. A leading ! requires the *computed fact* to be false, not absent.
EXPRESSIONS = {
    1: ["trine trine_controls:H"],
    2: ["trine control:G:H"],
    3: ["trine !control:G:H !control:D:H robbery_absent control:J:G"],
    4: ["three_wonders"],
    5: ["same_branches house"],
    6: ["same:H:G same:G:J same:J:D"],
    7: ["same:H:D"],
    8: ["same:H:G"],
    9: ["same:G:J"],
    10: ["same:J:D"],
    11: ["equal_branch:J:D"],
    12: ["equal_branch:G:J control:H:J control:G:D"],
    13: ["clash:J:D"],
    14: ["clash:G:J"],
    15: ["clash:G:J branch_set:G:J:卯酉"],
    16: ["branch:D:酉 phase:J:木"],
    17: ["branch:D:卯 phase:J:土"],
    18: ["branch:D:卯 phase:J:金"],
    19: ["branch:D:酉 phase:J:木 phase:G:金"],
    20: ["branch:D:卯 phase:J:土 phase:G:木"],
    21: ["branch:D:卯 phase:J:金 phase:G:火"],
    22: ["stem_combine:H:G"],
    23: ["combine:G:J !control:H:D !control:D:H"],
    24: ["combine:G:J control:H:D", "combine:G:J control:D:H"],
    25: ["same:H:J"],
    26: ["xun_kong:G xun_kong:J xun_kong:D"],
    27: ["combine:G:J xun_kong:D control:D:H"],
    28: ["si_da_kong:H", "si_da_kong:G", "si_da_kong:J", "si_da_kong:D"],
    29: ["generate:G:H generate:J:D"],
    30: ["control:G:H control:J:D"],
    31: ["generate:H:G generate:D:J"],
    32: ["control:H:G control:D:J"],
    33: ["step:G:J:1 step:J:D:1", "step:G:J:11 step:J:D:11"],
    34: ["generate:D:J generate:J:G generate:G:H"],
    35: ["control:D:J control:J:G control:G:H"],
    36: ["generate:H:G generate:G:J generate:J:D"],
    37: ["control:H:G control:G:J control:J:D"],
    38: ["same:H:G same:J:D control:H:J"],
    39: ["same:H:G same:J:D control:J:H"],
    40: ["control:G:H control:J:H control:D:H"],
    41: ["generate:H:G generate:J:G generate:D:G"],
    42: ["control:H:D control:G:D control:J:D"],
    43: ["generate:H:D generate:G:D generate:J:D"],
    44: ["control:H:G control:H:J control:H:D"],
    45: ["generate:H:G generate:H:J generate:H:D"],
    46: ["control:D:H control:D:G control:D:J"],
    47: ["generate:D:H generate:D:G generate:D:J"],
    48: ["control:G:H control:G:D control:J:H control:J:D"],
    49: ["generate:G:H generate:G:D generate:J:H generate:J:D"],
    50: ["control:H:G control:H:J control:D:G control:D:J"],
    51: ["generate:H:G generate:H:J generate:D:G generate:D:J"],
    54: ["control:G:D control:J:H control:H:G"],
    55: ["control:G:H control:D:H"],
    60: ["same:G:J control:D:H"],
    61: ["control:G:J"],
    62: ["control:H:D"],
    63: ["branch:D:戌 branch:G:辰"],
    64: ["branch:D:辰 branch:J:戌"],
}


def text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        raise ValueError("课钤条件缺少明确文字输入")
    return value


def texts(values: dict[str, Any], key: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("课钤条件缺少明确符号队列")
    return value


def evaluate_fact(
    operation: str, operands: dict[str, Any]
) -> tuple[bool | None, list[str]]:
    """Recompute a complete atomic statement, independently of its verdict."""
    from fatebridge.core.metaphysics.jinkou_pattern_tables import (
        BRANCH_COMBINES,
        HOUSE_BRANCH,
        STEM_COMBINES,
        TRINES,
    )

    if operation in {"control", "generate", "same"}:
        a, b = text(operands, "source_element"), text(operands, "target_element")
        target = (
            ELEMENT_CONTROLS[a]
            if operation == "control"
            else ELEMENT_GENERATES[a] if operation == "generate" else a
        )
        return b == target, [target]
    if operation in {"equal_branch", "clash", "combine", "stem_combine"}:
        a = text(operands, "source_symbol")
        right_symbol = operands.get("target_symbol")
        if right_symbol is not None and not isinstance(right_symbol, str):
            raise ValueError("课钤条件的目标符号无效")
        target = (
            SIX_CLASH_BRANCHES[a]
            if operation == "clash"
            else (
                BRANCH_COMBINES[a]
                if operation == "combine"
                else STEM_COMBINES[a] if operation == "stem_combine" else a
            )
        )
        return (None if right_symbol is None else right_symbol == target), [target]
    if operation in {"trine", "trine_controls"}:
        branches = texts(operands, "branches")
        if len(branches) != 3:
            raise ValueError("三合条件需要三位本支")
        phase = TRINES.get(frozenset(branches))
        if operation == "trine":
            return phase is not None, ["寅午戌", "申子辰", "亥卯未", "巳酉丑"]
        target = text(operands, "target_element")
        return bool(phase and ELEMENT_CONTROLS[phase] == target), (
            [ELEMENT_CONTROLS[phase]] if phase else []
        )
    if operation == "three_wonders":
        stems = operands.get("stems")
        if (
            not isinstance(stems, list)
            or len(stems) != 3
            or any(s is not None and not isinstance(s, str) for s in stems)
        ):
            raise ValueError("三奇条件需要人元、神遁干、将遁干三位")
        groups = ["甲戊庚", "乙丙丁", "壬癸辛"]
        return (
            None if None in stems else set(stems) in [set(v) for v in groups]
        ), groups
    if operation == "same_branches":
        branches = texts(operands, "branches")
        if len(branches) != 3:
            raise ValueError("本家同支条件需要三位本支")
        return len(set(branches)) == 1, [branches[0]]
    if operation == "house":
        house_branches = list(HOUSE_BRANCH[text(operands, "stem")])
        return text(operands, "branch") in house_branches, house_branches
    if operation == "robbery_absent":
        day = text(operands, "day_ganzhi")
        target = next(
            value
            for group, value in (
                ("申子辰", "巳"),
                ("亥卯未", "申"),
                ("寅午戌", "亥"),
                ("巳酉丑", "寅"),
            )
            if day[1] in group
        )
        return target not in texts(operands, "branches"), [target]
    if operation == "step":
        a, z = text(operands, "source_symbol"), text(operands, "target_symbol")
        step = operands.get("step")
        if type(step) is not int or step not in (1, 11):
            raise ValueError("连茹条件只核逐支顺接或逆接")
        delta = (EARTHLY_BRANCHES.index(z) - EARTHLY_BRANCHES.index(a)) % 12
        return delta == step, [
            EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(a) + step) % 12]
        ]
    if operation == "branch_set":
        return set(texts(operands, "branches")) == set(
            text(operands, "required")
        ), list(text(operands, "required"))
    if operation in {"branch", "phase"}:
        return text(operands, "actual") == text(operands, "required"), [
            text(operands, "required")
        ]
    if operation in {"xun_kong", "si_da_kong"}:
        value = operands.get("flag")
        if value is not None and type(value) is not bool:
            raise ValueError("空亡条件须保留已算布尔旗标")
        return value, ["true"]
    raise ValueError("未知课钤条件运算")


def evaluate_groups(
    groups: list[list[dict[str, Any]]], facts: dict[str, bool | None]
) -> bool | None:
    """False dominates unknown in AND; true dominates unknown in OR."""
    if not groups or any(not group for group in groups):
        raise ValueError("课钤条件表达式不可为空")
    alternatives: list[bool | None] = []
    for group in groups:
        terms: list[bool | None] = []
        for term in group:
            value = facts[term["fact_id"]]
            terms.append(None if value is None else value is term["expected"])
        alternatives.append(
            False if False in terms else None if None in terms else True
        )
    return True if True in alternatives else None if None in alternatives else False


def condition_evidence(
    rows: list[dict[str, Any]], *, day_ganzhi: str
) -> tuple[
    list[dict[str, Any]], dict[int, list[list[dict[str, Any]]]], dict[int, bool | None]
]:
    by_role = dict(zip("HGJD", rows, strict=True))
    facts: dict[str, dict[str, Any]] = {}

    def fact(identity: str) -> None:
        if identity in facts:
            return
        op, *parts = identity.split(":")
        operands: dict[str, Any]
        if op in {
            "control",
            "generate",
            "same",
            "equal_branch",
            "clash",
            "combine",
            "stem_combine",
            "step",
        }:
            a, z = parts[:2]
            left, right = by_role[a], by_role[z]
            operands = dict(
                source_position=ROLES[a],
                target_position=ROLES[z],
                source_symbol=left["content"],
                target_symbol=right["content"],
            )
            if op in {"control", "generate", "same"}:
                operands.update(
                    source_element=left["element"], target_element=right["element"]
                )
            elif op == "stem_combine":
                operands["target_symbol"] = right["dun_stem"]
                operands["target_field"] = "dun_stem"
            elif op == "step":
                operands["step"] = int(parts[2])
            label = {
                "control": "克",
                "generate": "生",
                "same": "五行比和",
                "equal_branch": "本支相同",
                "clash": "本支相冲",
                "combine": "本支六合",
                "stem_combine": "人元与当日神遁干五合",
                "step": "地支逐位相接",
            }[op]
            description = ROLES[a] + "／" + ROLES[z] + "：" + label
        elif op in {"trine", "trine_controls", "same_branches", "robbery_absent"}:
            operands = dict(branches=[by_role[v]["content"] for v in "GJD"])
            description = {
                "trine": "贵神、将神、地分三合齐支",
                "trine_controls": "三合名义局五行克人元",
                "same_branches": "贵神、将神、地分三支相同",
                "robbery_absent": "占日日支劫煞未入贵神、将神、地分三支",
            }[op]
            if op == "trine_controls":
                operands["target_element"] = rows[0]["element"]
                operands["target_position"] = "人元"
            if op == "robbery_absent":
                operands["day_ganzhi"] = day_ganzhi
        elif op == "three_wonders":
            operands = dict(
                stems=[rows[0]["content"], rows[1]["dun_stem"], rows[2]["dun_stem"]],
                day_ganzhi=day_ganzhi,
            )
            description = "人元、当日神遁干、当日将遁干三奇齐全"
        elif op == "house":
            operands = dict(stem=rows[0]["content"], branch=rows[3]["content"])
            description = "地分属于人元本家支；三支相同另核"
        elif op == "branch_set":
            a, z, required = parts
            operands = dict(
                branches=[by_role[a]["content"], by_role[z]["content"]],
                required=required,
            )
            description = ROLES[a] + "／" + ROLES[z] + "两支恰为" + required
        elif op in {"branch", "phase"}:
            role, required = parts
            field = "content" if op == "branch" else "element"
            operands = dict(
                position=ROLES[role], actual=by_role[role][field], required=required
            )
            description = (
                ROLES[role] + ("本支为" if op == "branch" else "五行为") + required
            )
        elif op in {"xun_kong", "si_da_kong"}:
            role = parts[0]
            row = by_role[role]
            operands = dict(
                position=ROLES[role],
                symbol=row["content"],
                element=row["element"],
                day_ganzhi=day_ganzhi,
                flag=row[op],
            )
            description = ROLES[role] + (
                "本支旬空已算旗标" if op == "xun_kong" else "本五行四大空亡已算旗标"
            )
        else:
            raise RuntimeError("未登记的课钤条件")
        matched, reference = evaluate_fact(op, operands)
        facts[identity] = dict(
            id=identity,
            operation=op,
            description=description,
            operands=operands,
            reference=reference,
            matched=matched,
        )

    groups: dict[int, list[list[dict[str, Any]]]] = {}
    for index, alternatives in EXPRESSIONS.items():
        groups[index] = []
        for alternative in alternatives:
            terms = []
            for term in alternative.split():
                expected = not term.startswith("!")
                identity = term.lstrip("!")
                fact(identity)  # Always record every premise, even after a failure.
                terms.append(dict(fact_id=identity, expected=expected))
            groups[index].append(terms)
    outcomes = {identity: f["matched"] for identity, f in facts.items()}
    values = {
        index: evaluate_groups(alternatives, outcomes)
        for index, alternatives in groups.items()
    }
    return list(facts.values()), groups, values
