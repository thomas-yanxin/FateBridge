"""Edition-specific definitions joined to actual natal objects and cycle labels."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-symbolism.json")
            .read_text(encoding="utf-8")
        ),
    )


def contextual_readings(
    palaces: list[dict[str, Any]], *, ming_branch: str, shen_branch: str
) -> dict[str, Any]:
    """Keep explicit premises, a declared 身命 reading, and undefined 遇 separate."""
    objects = {
        s["name"]: (p, s, f"ziwei_birth.palaces.{i}.stars_detail.{j}")
        for i, p in enumerate(palaces)
        for j, s in enumerate(p["stars_detail"])
    }
    lian, _, lian_path = objects["廉贞"]
    qisha, qi, qi_path = objects["七杀"]
    emperor, _, emperor_path = objects["紫微"]
    at_career = lian["name"] == "官禄宫"
    at_ming = lian["ganzhi"][1] == ming_branch
    at_shen = lian["ganzhi"][1] == shen_branch
    terms = (["官祿主"] if at_career else []) + (
        ["次桃花"] if at_ming or at_shen else []
    )
    branches = "子丑寅卯辰巳午未申酉戌亥"
    distance = (
        branches.index(qisha["ganzhi"][1]) - branches.index(emperor["ganzhi"][1])
    ) % 12
    clauses = {r["id"]: r for r in _source()["clauses"]}
    return {
        "lianzhen": {
            "definition_id": "lianzhen",
            "frame": 82,
            "quote": clauses["lianzhen"]["quote"],
            "calculation_path": lian_path,
            "natal_palace_name": lian["name"],
            "natal_branch": lian["ganzhi"][1],
            "at_career_palace": at_career,
            "at_ming_branch": at_ming,
            "at_shen_branch": at_shen,
            "selected_mingshen_reading": "either_ming_or_shen_not_exclusive_of_career",
            "mingshen_reading_independently_adjudicated": False,
            "applicable_terms_given_selected_reading": terms,
            "terms_are_new_palace_names": False,
        },
        "qisha": {
            "definition_id": "qisha",
            "frame": 83,
            "quote": clauses["qisha"]["quote"],
            "qisha_calculation_path": qi_path,
            "ziwei_calculation_path": emperor_path,
            "separation_steps": distance,
            "same_palace": distance == 0,
            "opposite_palace": distance == 6,
            "trine": distance in (4, 8),
            "source_encounter_geometry_defined": False,
            "condition_match": None,
            "unresolved_reason": "This passage does not define the geometry of 遇帝; observed geometry cannot select it silently",
            "actual_qisha_mutagen": qi["mutagen"],
            "symbolic_quan_is_new_sihua_assignment": False,
        },
    }


def ming_property_evidence(
    palaces: list[dict[str, Any]], *, ming_branch: str, shen_branch: str
) -> dict[str, Any]:
    source = _source()
    lookup = {
        (entity["kind"], entity["name"]): clause["id"]
        for clause in source["clauses"]
        for entity in clause["entities"]
    }
    occurrences = []
    located: set[tuple[str, str]] = set()
    for i, palace in enumerate(palaces):
        for j, star in enumerate(palace["stars_detail"]):
            for kind, name in (
                ("natal_star", star["name"]),
                ("natal_transformation", star["mutagen"]),
            ):
                if (kind, name) not in lookup:
                    continue
                located.add((kind, name))
                occurrences.append(
                    dict(
                        kind=kind,
                        name=name,
                        definition_id=lookup[(kind, name)],
                        star=star["name"],
                        natal_palace_name=palace["name"],
                        natal_branch=palace["ganzhi"][1],
                        natal_mutagen=star["mutagen"],
                        calculation_path=f"ziwei_birth.palaces.{i}.stars_detail.{j}",
                    )
                )
        cycle = palace["boshi12"]
        if cycle is not None:
            key = ("boshi_cycle_label", cycle)
            located.add(key)
            occurrences.append(
                dict(
                    kind=key[0],
                    name=cycle,
                    definition_id=lookup[key],
                    natal_palace_name=palace["name"],
                    natal_branch=palace["ganzhi"][1],
                    calculation_path=f"ziwei_birth.palaces.{i}.boshi12",
                )
            )
    return {
        "method_id": source["id"],
        "version": source["version"],
        "source": source["source_url"],
        "source_title": source["title"],
        "printed_volume": source["printed_volume"],
        "source_section": source["section"],
        "manual_reader_count": source["manual_reader_count"],
        "scope": "edition_specific_definitions_joined_to_natal_facts_not_event_predictions",
        "definitions": {r["id"]: deepcopy(r) for r in source["clauses"]},
        "occurrences": occurrences,
        "unlocated_natal_source_stars": sorted(
            name
            for kind, name in lookup
            if kind == "natal_star" and (kind, name) not in located
        ),
        "unresolved_boshi_labels": sorted(
            name
            for kind, name in lookup
            if kind == "boshi_cycle_label" and (kind, name) not in located
        ),
        "unassigned_source_labels": sorted(
            name for kind, name in lookup if kind == "unassigned_source_label"
        ),
        "conditional_readings": contextual_readings(
            palaces, ming_branch=ming_branch, shen_branch=shen_branch
        ),
        "unresolved_relational_definitions": deepcopy(
            source["unresolved_relational_definitions"]
        ),
        "name_mapping": {
            "古天空": "本系统地空，不是软件年支天空",
            "博士飛廉": "博士循环飞廉，不是年支星蜚廉",
            "官符": "未把本段官符属性自动补给其他层的官府",
        },
        "positive_star_count_note": deepcopy(source["positive_star_count_note"]),
        "source_elements_replace_bureau_or_star_brightness": False,
        "source_taxonomy_applied_to_modern_classification": False,
        "symbolic_verbs_create_sihua_assignments": False,
        "actual_assignments_modified": False,
        "full_section_transcription_certified": False,
        "whole_book_acceptance_passed": False,
    }
