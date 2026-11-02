"""Evaluate partial phase mappings without inventing uncollated positions."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_relations import BRANCHES, ELEMENTS, element_relation

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-stages-v15.json")
    .read_text(encoding="utf-8")
)
PHASES = ("长生", "帝旺", "墓", "绝")
STAGES: dict[str, dict[str, str]] = deepcopy(PROFILE["known_stages"])


def query_stage(
    stages: dict[str, dict[str, str]], element: str, branch: str, expected: list[str]
) -> dict[str, Any]:
    if (
        element not in stages
        or branch not in BRANCHES
        or any(s not in PHASES for s in expected)
    ):
        raise ValueError("阶段查询只接受已发布五行、地支及生旺墓绝")
    table = stages[element]
    known = table.get(branch)
    missing = [p for p in PHASES if p not in table.values()]
    missing_expected = [p for p in expected if p in missing]
    match = (
        known in expected if known is not None else None if missing_expected else False
    )
    return dict(
        element=element,
        branch=branch,
        expected_stages=list(expected),
        known_stage=known,
        condition_match=match,
        query_complete=match is not None,
        table_complete=not missing,
        missing_stages=missing,
        missing_expected_stages=missing_expected,
        status=(
            "known_phase_matches"
            if match is True
            else (
                "known_phase_excludes"
                if match is False
                else "requested_phase_mapping_incomplete"
            )
        ),
    )


def stage_knowledge() -> dict[str, Any]:
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=97",
        source_sha256=PROFILE["source"]["sha256"],
        known_stages=deepcopy(STAGES),
        missing_stages={
            e: [p for p in PHASES if p not in table.values()]
            for e, table in STAGES.items()
        },
        clauses=deepcopy(PROFILE["clauses"]),
        interpretation=deepcopy(PROFILE["interpretation"]),
        raw_table_unchanged=True,
        table_complete=all(
            all(p in table.values() for p in PHASES) for table in STAGES.values()
        ),
        adjudication="phase_positions_not_efficacy",
        scope=PROFILE["scope"],
    )


def attach_hidden_stage_conditions(
    *,
    hidden: list[dict[str, Any]],
    stages: dict[str, dict[str, str]],
    month: str,
    day_ganzhi: str,
) -> None:
    for i, h in enumerate(hidden):
        root = f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.stage_conditions"

        def group(
            name: str, element: str, positions: list[tuple[str, str]]
        ) -> dict[str, Any]:
            queries = [
                {
                    **query_stage(stages, element, branch, ["墓", "绝"]),
                    "location": location,
                    "source_path": f"{root}.{name}.queries.{j}",
                }
                for j, (location, branch) in enumerate(positions)
            ]
            values = [q["condition_match"] for q in queries]
            match = True if True in values else None if None in values else False
            return dict(
                element=element,
                condition_match=match,
                all_queries_resolved=all(v is not None for v in values),
                predicate_determined=match is not None,
                queries=queries,
                source_path=f"{root}.{name}",
                status=(
                    "position_relation_matched"
                    if match is True
                    else (
                        "position_relation_not_matched"
                        if match is False
                        else "position_relation_requires_collation"
                    )
                ),
            )

        target = group(
            "hidden_tomb_cessation",
            ELEMENTS[h["branch"]],
            [("month", month), ("day", day_ganzhi[1]), ("flying", h["flying_branch"])],
        )
        flying = group(
            "flying_tomb_cessation",
            ELEMENTS[h["flying_branch"]],
            [("month", month), ("day", day_ganzhi[1])],
        )
        pressure = (
            element_relation(ELEMENTS[h["flying_branch"]], ELEMENTS[h["branch"]])
            == "克爻"
        )
        relevant_unknown = target["condition_match"] is None or (
            pressure and flying["condition_match"] is None
        )
        h["stage_conditions"] = dict(
            ruleset_id=PROFILE["ruleset_id"],
            ruleset_version=PROFILE["ruleset_version"],
            source_url=PROFILE["source"]["url"] + "#page=101",
            source_sha256=PROFILE["source"]["sha256"],
            source_path=root,
            hidden_tomb_cessation=target,
            flying_tomb_cessation=flying,
            flying_controls_hidden=pressure,
            has_relevant_unknown=relevant_unknown,
            ignored_unknown_groups=(
                ["flying_tomb_cessation"]
                if not pressure and flying["condition_match"] is None
                else []
            ),
            adjudication="phase_positions_not_actual_entry_or_emergence",
            scope="已知位置与缺表分开；一个已核墓绝位置不被其他未知位置抹掉。飞神不能克伏时，其墓绝缺项仅作附加支持诊断，不删除独立已核的伏神生扶。涉及克伏的缺项仍待审；不据位置判真墓真绝。",
        )
        raw = next(
            c
            for c in h["obstructing_conditions"]
            if c["rule_id"] == "hidden_tomb_cessation"
        )
        raw.update(
            qualified_matched=target["condition_match"],
            qualification_status=target["status"],
            qualification_source_path=target["source_path"],
        )
