"""Frozen printed definitions and calculation joins, not an interpretation blind test."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def audit_ming_properties(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "naj_ming_symbolism_v1"
    manifest = json.loads((folder / "checksums.json").read_text())
    for item in manifest["files"]:
        if (
            hashlib.sha256((folder / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("Ming symbolism source checksum mismatch: " + item["path"])
    source = json.loads((folder / "collation.json").read_text())
    expected = {k: v for k, v in source.items() if k != "images"}
    expected["source_frames"] = [82, 83, 84]
    production = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-symbolism.json"
        ).read_text()
    )
    mismatches: list[dict[str, Any]] = []
    if production != expected:
        mismatches.append(dict(case="production_source_data"))
    entities = {
        (e["kind"], e["name"]): clause["id"]
        for clause in source["clauses"]
        for e in clause["entities"]
    }
    for row in source["clauses"]:
        literal = re.search(r"(?:屬|為)([水木金土火]+)", row["quote"])
        if literal:
            elements = list(literal[1])
        elif row["quote"][-1] in "水木金土火":
            elements = [row["quote"][-1]]
        else:
            elements = []
        if elements != row["elements"]:
            mismatches.append(dict(case="literal_elements/" + row["id"]))
    joins = 0
    cases = 0
    for year in range(1984, 2044):
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            for gender in ("男", "女", "未知"):
                chart = build_ziwei_chart(_seed(year), gender, rule_profile=profile)
                evidence = chart["ming_textual_properties"]
                wanted = []
                for i, palace in enumerate(chart["palaces"]):
                    for j, star in enumerate(palace["stars_detail"]):
                        for kind, name in (
                            ("natal_star", star["name"]),
                            ("natal_transformation", star["mutagen"]),
                        ):
                            if (kind, name) not in entities:
                                continue
                            wanted.append(
                                dict(
                                    kind=kind,
                                    name=name,
                                    definition_id=entities[(kind, name)],
                                    star=star["name"],
                                    natal_palace_name=palace["name"],
                                    natal_branch=palace["ganzhi"][1],
                                    natal_mutagen=star["mutagen"],
                                    calculation_path=f"ziwei_birth.palaces.{i}.stars_detail.{j}",
                                )
                            )
                    cycle = palace["boshi12"]
                    if cycle is not None:
                        wanted.append(
                            dict(
                                kind="boshi_cycle_label",
                                name=cycle,
                                definition_id=entities[("boshi_cycle_label", cycle)],
                                natal_palace_name=palace["name"],
                                natal_branch=palace["ganzhi"][1],
                                calculation_path=f"ziwei_birth.palaces.{i}.boshi12",
                            )
                        )
                checks = {
                    "definitions": evidence["definitions"]
                    == {r["id"]: r for r in source["clauses"]},
                    "occurrences": evidence["occurrences"] == wanted,
                    "natal_source_stars_located": evidence[
                        "unlocated_natal_source_stars"
                    ]
                    == [],
                    "unknown_cycle_slots": len(evidence["unresolved_boshi_labels"])
                    == (10 if gender == "未知" else 0),
                    "source_identity": [
                        evidence[k]
                        for k in (
                            "method_id",
                            "version",
                            "source",
                            "printed_volume",
                            "source_section",
                        )
                    ]
                    == [
                        source[k]
                        for k in (
                            "id",
                            "version",
                            "source_url",
                            "printed_volume",
                            "section",
                        )
                    ],
                    "printed_count_not_rewritten": evidence["positive_star_count_note"]
                    == source["positive_star_count_note"],
                    "source_taxonomy_not_applied": evidence[
                        "source_taxonomy_applied_to_modern_classification"
                    ]
                    is False,
                    "unassigned_labels_preserved": evidence["unassigned_source_labels"]
                    == sorted(
                        name
                        for kind, name in entities
                        if kind == "unassigned_source_label"
                    ),
                    "reader_count": evidence["manual_reader_count"] == 1,
                    "relation_phrases_not_silently_applied": evidence[
                        "unresolved_relational_definitions"
                    ]
                    == source["unresolved_relational_definitions"],
                    "no_new_sihua": evidence["symbolic_verbs_create_sihua_assignments"]
                    is False,
                    "no_false_full_claim": evidence["whole_book_acceptance_passed"]
                    is False
                    and evidence["full_section_transcription_certified"] is False,
                }
                c = evidence["conditional_readings"]
                lian = next(
                    p
                    for p in chart["palaces"]
                    if any(s["name"] == "廉贞" for s in p["stars_detail"])
                )
                expected_terms = []
                if lian["name"] == "官禄宫":
                    expected_terms.append("官祿主")
                if lian["ganzhi"][1] in {
                    chart["ming_gong"]["branch"],
                    chart["shen_gong"]["branch"],
                }:
                    expected_terms.append("次桃花")
                checks["lianzhen_premises"] = (
                    c["lianzhen"]["applicable_terms_given_selected_reading"]
                    == expected_terms
                )
                checks["lianzhen_factual_flags"] = [
                    c["lianzhen"][k]
                    for k in ("at_career_palace", "at_ming_branch", "at_shen_branch")
                ] == [
                    lian["name"] == "官禄宫",
                    lian["ganzhi"][1] == chart["ming_gong"]["branch"],
                    lian["ganzhi"][1] == chart["shen_gong"]["branch"],
                ]
                checks["encounter_not_invented"] = (
                    c["qisha"]["condition_match"] is None
                    and c["qisha"]["source_encounter_geometry_defined"] is False
                )
                if not all(checks.values()):
                    mismatches.append(
                        dict(year=year, profile=profile, gender=gender, checks=checks)
                    )
                joins += len(wanted)
                cases += 1
    return dict(
        method_id=source["id"],
        source_clauses=len(source["clauses"]),
        source_entities=len(entities),
        natal_star_definitions=sum(k == "natal_star" for k, n in entities),
        transformation_definitions=sum(
            k == "natal_transformation" for k, n in entities
        ),
        cycle_definitions=sum(k == "boshi_cycle_label" for k, n in entities),
        unassigned_source_labels=sorted(
            n for k, n in entities if k == "unassigned_source_label"
        ),
        conditional_chart_inputs=cases,
        calculation_joins_checked=joins,
        mismatches=mismatches,
        positive_star_count_note=source["positive_star_count_note"],
        unresolved_quote_tails={
            r["id"]: r["unresolved_tail_candidates"]
            for r in source["clauses"]
            if "unresolved_tail_candidates" in r
        },
        manual_reader_count=1,
        independent_placement_or_calendar_oracle=False,
        live_model_blind_evaluation="not_run",
        full_section_transcription_certified=False,
        whole_book_acceptance_passed=False,
        scope="Printed definitions and source-conditioned joins only; derived checks are not additional independent source cases",
    )
