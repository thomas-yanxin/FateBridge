"""Apply the same-edition earth/Si exception without self-proving its root."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_condition
from .liuyao_relations import ELEMENTS, element_relation
from .liuyao_stages import query_stage

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-cessation-v17.json")
    .read_text(encoding="utf-8")
)
ROOT = "liuyao_evidence.conditional_analysis.cessation_conditions"


def _qualified_actor(actor: dict[str, Any], element: str) -> bool:
    return actor.get("benefit_now") is True or (
        element_relation(ELEMENTS[actor["branch"]], element) == "比和"
        and actor.get("source_grounded") is True
        and not actor.get("held")
        and not actor.get("activity_pending")
    )


def _independent_sources(
    excluded_position: int,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    assessment: dict[str, Any],
) -> dict[int, list[dict[str, Any]]]:
    """Trace qualified support to anchors without the queried line or Si loop.

    Reusing a final `source_grounded` bit alone would permit a multi-step
    generation cycle whose sole anchor was the queried earth's own changed Si.
    This is a dependency proof over existing qualifications, not new strength.
    """
    proofs: dict[int, list[dict[str, Any]]] = {}
    for row, assessed in zip(lines, assessment["lines"]):
        p, element = row["position"], row["element"]
        if p == excluded_position or assessed["strength"]["oppositions"]:
            continue
        anchors = []
        for i, actor in enumerate(assessed["strength"]["supports"]):
            location, branch = actor["location"], actor["branch"]
            if element == "土" and location in ("day", "changed") and branch == "巳":
                continue
            if (
                location in ("month", "day")
                and element_relation(ELEMENTS[branch], element) in ("生爻", "比和")
            ) or (
                location == "changed" and actor.get("back_generation_condition") is True
            ):
                anchors.append(
                    {
                        "position": p,
                        "anchor": deepcopy(actor),
                        "support_fact_path": f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p-1}.strength.supports.{i}",
                    }
                )
        if anchors:
            proofs[p] = anchors
    changed = True
    while changed:
        changed = False
        for row, assessed in zip(lines, assessment["lines"]):
            p = row["position"]
            if p == excluded_position or p in proofs:
                continue
            for i, actor in enumerate(assessed["strength"]["supports"]):
                source = actor.get("position")
                if (
                    actor["location"] == "visible"
                    and source in proofs
                    and activity_condition(lines[source - 1], conditions[source - 1])
                    is True
                    and _qualified_actor(actor, row["element"])
                ):
                    proofs[p] = [
                        *deepcopy(proofs[source]),
                        {
                            "position": p,
                            "source_position": source,
                            "qualification": deepcopy(actor),
                            "support_fact_path": f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p-1}.strength.supports.{i}",
                        },
                    ]
                    changed = True
                    break
    return proofs


def build_cessation_conditions(
    *,
    lines: list[dict[str, Any]],
    assessment: dict[str, Any],
    conditions: list[dict[str, Any]],
    stages: dict[str, dict[str, str]],
    day_ganzhi: str,
    focus: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for row, assessed in zip(lines, assessment["lines"]):
        p, element = row["position"], row["element"]
        path = f"{ROOT}.lines.{p-1}"
        strength = assessed["strength"]
        proofs = _independent_sources(p, lines, conditions, assessment)
        independent, excluded = [], []
        for i, actor in enumerate(strength["supports"]):
            location = actor["location"]
            branch = actor["branch"]
            source = deepcopy(actor)
            source["support_fact_path"] = (
                f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p-1}.strength.supports.{i}"
            )
            if location in ("day", "changed") and branch == "巳":
                excluded.append(
                    {**source, "exclusion": "queried_si_cannot_self_certify"}
                )
            elif location in ("month", "day") and element_relation(
                ELEMENTS[branch], element
            ) in ("生爻", "比和"):
                independent.append(source)
            elif (
                location == "changed" and actor.get("back_generation_condition") is True
            ):
                independent.append(source)
            elif location == "visible" and (
                actor["position"] in proofs
                and activity_condition(
                    lines[actor["position"] - 1], conditions[actor["position"] - 1]
                )
                is True
                and _qualified_actor(actor, element)
            ):
                independent.append(
                    {
                        **source,
                        "independence_proof": deepcopy(proofs[actor["position"]]),
                    }
                )
            else:
                excluded.append(
                    {
                        **source,
                        "exclusion": "outside_verified_independent_support_scope",
                    }
                )
        oppositions = deepcopy(strength["oppositions"])

        def query(location: str, branch: str | None) -> dict[str, Any]:
            position_match = (
                query_stage(stages, element, branch, ["绝"])["condition_match"]
                if branch is not None
                else False
            )
            if branch is None:
                match, status = False, "no_actual_transformation"
            elif position_match is False:
                match, status = False, "no_listed_cessation_position"
            elif position_match is None:
                match, status = None, "phase_mapping_incomplete"
            elif element != "土":
                match, status = True, "position_predicate_retains_role_prerequisites"
            elif independent and not oppositions:
                match, status = False, "earth_supported_si_generation_not_cessation"
            elif independent:
                match, status = None, "earth_support_and_opposition_require_review"
            else:
                # A finite inventory without support cannot establish total
                # rootlessness. In particular the queried Si is no such proof.
                match, status = None, "earth_total_qi_not_adjudicated"
            return dict(
                location=location,
                branch=branch,
                position_match=position_match,
                condition_match=match,
                status=status,
                actual_cessation_adjudicated=False,
                source_path=f"{path}.{location}",
                source_url=PROFILE["source"]["url"] + "#page=98",
            )

        rows.append(
            dict(
                position=p,
                branch=row["branch"],
                element=element,
                day=query("day", day_ganzhi[1]),
                changed=query(
                    "changed", row["changed_branch"] if row["change"] else None
                ),
                independent_supports=independent,
                excluded_self_or_unqualified_supports=excluded,
                pending_supports=deepcopy(strength["pending_supports"]),
                oppositions=oppositions,
                independent_support_present=bool(independent),
                total_rootlessness_established=False,
                strength_source_path=f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p-1}.strength",
                source_path=path,
            )
        )
    selected = focus["selected"]
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=98",
        source_sha256=PROFILE["source"]["sha256"],
        clauses=deepcopy(PROFILE["clauses"]),
        lines=rows,
        focus=(
            deepcopy(rows[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        scope="土逢巳绝位另核独立生扶与反制；巳本身不循环证明已生土。其余五行保留原位谓词及角色层的强弱前提；未裁定全局真绝或化散，不据此断现实成败。",
    )
