"""Printed conditional premises joined to actual natal geometry, without verdicts."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

from fatebridge.utils.data import EARTHLY_BRANCHES


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-conditions.json")
            .read_text(encoding="utf-8")
        ),
    )


def structural_condition_evidence(
    palaces: list[dict[str, Any]], *, ming_branch: str, year_stem: str
) -> dict[str, Any]:
    """A matched necessary premise cannot discharge omitted qualitative conditions.

    Keep unknowns as None when input objects are absent or duplicated. A
    projected or malformed chart must not turn missing stars into a negative.
    """
    source = _source()
    positions: dict[str, list[dict[str, Any]]] = {}
    for i, palace in enumerate(palaces):
        for j, star in enumerate(palace["stars_detail"]):
            positions.setdefault(star["name"], []).append(
                dict(
                    star=star["name"],
                    natal_palace_name=palace["name"],
                    natal_branch=palace["ganzhi"][1],
                    natal_mutagen=star["mutagen"],
                    calculation_path=f"ziwei_birth.palaces.{i}.stars_detail.{j}",
                )
            )
    center = EARTHLY_BRANCHES.index(ming_branch)
    neighbors = [
        EARTHLY_BRANCHES[(center - 1) % 12],
        EARTHLY_BRANCHES[(center + 1) % 12],
    ]
    records = []
    for clause in source["clauses"]:
        occurrences = {
            name: deepcopy(positions.get(name, [])) for name in clause["stars"]
        }
        complete = all(len(rows) == 1 for rows in occurrences.values())
        geometry: bool | None = None
        if complete:
            branches = [rows[0]["natal_branch"] for rows in occurrences.values()]
            if clause["geometry"] == "flank_ming":
                geometry = len(branches) == 2 and set(branches) == set(neighbors)
            elif clause["geometry"] == "same_palace":
                geometry = len(set(branches)) == 1
            elif clause["geometry"] == "same_ming_palace":
                geometry = all(branch == ming_branch for branch in branches)
            else:
                raise ValueError(
                    "Unknown compiled Ming geometry: " + clause["geometry"]
                )
        branch_match = not clause["branches"] or ming_branch in clause["branches"]
        stem_match = not clause["year_stems"] or year_stem in clause["year_stems"]
        # Known false premises remain false even if another premise is unknown.
        premises: bool | None = (
            False
            if geometry is False or not branch_match or not stem_match
            else True if geometry is True else None
        )
        example = clause["literal_example"]
        example_match: bool | None = None
        if example is not None and complete:
            example_match = ming_branch == example["ming"] and all(
                occurrences[name][0]["natal_branch"] == branch
                for name, branch in example["positions"].items()
            )
        records.append(
            dict(
                id=clause["id"],
                source_frame=clause["frame"],
                source_quote=clause["quote"],
                source_annotation=clause["annotation"],
                annotation_revision=deepcopy(clause.get("annotation_revision")),
                geometry_rule=clause["geometry"],
                actual_occurrences=occurrences,
                geometry_match=geometry,
                ming_branch_requirement_met=branch_match,
                year_stem_requirement_met=stem_match,
                evaluated_necessary_premises_match=premises,
                source_literal_example_matches=example_match,
                literal_example=deepcopy(example),
                source_qualifications_not_evaluated=list(
                    clause["unresolved_conditions"]
                ),
                full_traditional_judgment=None,
                source_outcome_claim_adopted=False,
                missing_or_duplicated_stars=[
                    name for name, rows in occurrences.items() if len(rows) != 1
                ],
            )
        )
    return dict(
        method_id=source["id"],
        version=source["version"],
        source=source["source_url"],
        source_title=source["title"],
        source_section=source["source_section"],
        source_section_is_editorial_label=True,
        source_status="independent_rereading_partial_clause_collation",
        manual_reader_count=source["manual_reader_count"],
        source_revision=deepcopy(source["source_revision"]),
        ming_branch=ming_branch,
        year_stem=year_stem,
        adjacent_branches=neighbors,
        flanking_reading=source["flanking_reading"],
        index=[
            {
                k: r[k]
                for k in (
                    "id",
                    "source_frame",
                    "source_quote",
                    "geometry_match",
                    "evaluated_necessary_premises_match",
                    "source_literal_example_matches",
                    "source_qualifications_not_evaluated",
                    "full_traditional_judgment",
                    "source_outcome_claim_adopted",
                )
            }
            for r in records
        ],
        records=records,
        scope=source["scope"],
        actual_assignments_modified=False,
        whole_book_acceptance_passed=False,
        real_world_efficacy="not_tested",
    )
