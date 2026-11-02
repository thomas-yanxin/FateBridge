"""Explicit Ming table application; expected cells come from frozen scan readings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_rules
from fatebridge.services.metaphysics import (
    _build_person_seed,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/ziwei_independent"
ABBREVIATIONS = dict(
    zip(
        "廉破武陽機梁紫月同昌貞巨貪弼曲日相府陰",
        [
            "廉贞",
            "破军",
            "武曲",
            "太阳",
            "天机",
            "天梁",
            "紫微",
            "太阴",
            "天同",
            "文昌",
            "廉贞",
            "巨门",
            "贪狼",
            "右弼",
            "文曲",
            "太阳",
            "天相",
            "天府",
            "太阴",
        ],
    )
)


def frozen_table(
    fixtures: Path = FIXTURES,
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    vectors = json.loads((fixtures / "sihua_selection_vectors.json").read_text())
    folder = fixtures / "naj_ming_anxing_v1"
    manifest = folder / "checksums.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        != vectors["source_manifest_sha256"]
    ):
        raise ValueError("Ming selection source manifest checksum mismatch")
    for row in json.loads(manifest.read_text())["files"]:
        if (
            hashlib.sha256((folder / row["path"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("Ming selection source checksum mismatch")
    source = json.loads((folder / "collation.json").read_text())["sihua"]
    table = {
        row["stem"]: dict(
            zip(source["order"], [ABBREVIATIONS[c] for c in row["star_abbreviations"]])
        )
        for row in source["rows"]
    }
    return vectors, table


def audit_sihua_selection(fixtures: Path = FIXTURES) -> dict[str, Any]:
    vectors, expected = frozen_table(fixtures)
    failures: list[dict[str, Any]] = []
    natal_cases = natal_joins = table_cells = dynamic_joins = 0
    profiles = ("iztro_2_5_8", "quanshu_v2_excerpt")
    for profile in profiles:
        catalogue = build_ziwei_rules(rule_profile=profile, sihua_source="naj_ming_v1")[
            "rule_catalogue"
        ]
        if catalogue["sihua_by_year_stem"] != expected:
            failures.append(dict(case="selected_table", profile=profile))
        table_cells += 40
        for year in range(1984, 1994):
            for gender in ("男", "女", "未知"):
                old = build_ziwei_chart(_seed(year), gender, rule_profile=profile)
                new = build_ziwei_chart(
                    _seed(year),
                    gender,
                    rule_profile=profile,
                    sihua_source="naj_ming_v1",
                )
                actual = [
                    (s["mutagen"], s["name"])
                    for p in new["palaces"]
                    for s in p["stars_detail"]
                    if s["mutagen"] is not None
                ]
                checks = {
                    "four_markers": len(actual) == 4
                    and dict(actual) == expected[new["year_stem"]],
                    "sihua": dict(new["sihua"]) == expected[new["year_stem"]],
                    "actual_selection": new["sihua_source_comparison"][
                        "compared_assignments_applied"
                    ]
                    is True,
                    "source_agreement": new["sihua_source_comparison"][
                        "source_agrees_on_this_stem"
                    ]
                    is True,
                    "version_identity": new["ruleset"]["version"]
                    == old["ruleset"]["version"] + "+sihua.naj-ming-v1",
                }
                for key in [
                    "wuxing_ju",
                    "ming_gong",
                    "shen_gong",
                    "lunar_date",
                    "hour_branch",
                    "calendar_rules",
                    "calendar_cycles",
                    "cycle_source_comparison",
                    "void_systems",
                    "daxian_direction",
                    "auxiliary_placement_sources",
                ]:
                    checks[key] = new[key] == old[key]

                def geometry(c: dict[str, Any]) -> list[tuple[str, str, str | None]]:
                    return sorted(
                        (s["name"], p["ganzhi"], s["brightness"])
                        for p in c["palaces"]
                        for s in p["stars_detail"]
                    )

                checks["star_geometry_brightness"] = geometry(new) == geometry(old)
                bad = [k for k, v in checks.items() if not v]
                if bad:
                    failures.append(
                        dict(
                            case="natal",
                            profile=profile,
                            year=year,
                            gender=gender,
                            failed=bad,
                        )
                    )
                natal_cases += 1
                natal_joins += len(actual)
    person = create_person_info(**vectors["birth"])
    charts = {
        p: build_ziwei_chart(
            _build_person_seed(person),
            person.gender or "未知",
            rule_profile=p,
            sihua_source="naj_ming_v1",
        )
        for p in profiles
    }
    coverage = set()
    for row in vectors["selected"]:
        profile = row["profile"]
        result = calculate_ziwei_horoscope(
            person, rule_profile=profile, sihua_source="naj_ming_v1", **row["target"]
        )
        h = result.get("ziwei_horoscope")
        if h is None:
            failures.append(dict(case="service_error", input=row, error=result))
            continue
        actual_stems = {s["scope"]: s["stem"] for s in h["scopes"]}
        if actual_stems != row["computed_stems"]:
            failures.append(dict(case="coverage_stems_changed", input=row))
        for scope in h["scopes"]:
            stem = scope["stem"]
            if stem in ("庚", "壬"):
                coverage.add((profile, scope["scope"], stem))
            wanted = expected[stem]
            if scope["mutagen"] != wanted:
                failures.append(
                    dict(
                        case="dynamic_table",
                        profile=profile,
                        scope=scope["scope"],
                        stem=stem,
                    )
                )
            objects = {
                s["name"]: (p, s)
                for p in charts[profile]["palaces"]
                for s in p["stars_detail"]
            }
            for link in scope["mutagen_natal_links"]:
                palace, star = objects[wanted[link["transformation"]]]
                if not all(
                    [
                        link["star"] == star["name"],
                        link["natal_branch"] == palace["ganzhi"][1],
                        link["natal_palace_name"] == palace["name"],
                        link["natal_mutagen"] == star["mutagen"],
                    ]
                ):
                    failures.append(
                        dict(
                            case="dynamic_natal_join",
                            input=row,
                            scope=scope["scope"],
                            transformation=link["transformation"],
                        )
                    )
                dynamic_joins += 1
        if (
            h["sihua_source_comparison"]["dynamic_reuse_classically_verified"]
            is not False
        ):
            failures.append(dict(case="unearned_dynamic_certification"))
    if len(coverage) != 24:
        failures.append(dict(case="coverage_incomplete", count=len(coverage)))
    return {
        "method_id": "explicit_ming_sihua_selection_v1",
        "independent_literal_source_cells": 40,
        "table_cells_checked_across_profiles": table_cells,
        "conditional_natal_cases": natal_cases,
        "natal_assignment_joins_checked": natal_joins,
        "software_coverage_candidates": vectors["candidate_cases_scanned"],
        "selected_coverage_inputs": len(vectors["selected"]),
        "scope_profile_geng_ren_coverage": len(coverage),
        "dynamic_natal_joins_checked": dynamic_joins,
        "differences": failures,
        "new_independent_sources": 0,
        "manual_source_readers": 1,
        "independent_calendar_or_star_placement_oracle": False,
        "dynamic_reuse_classically_verified": False,
        "whole_book_conformance_claimed": False,
        "live_model_blind_evaluation": "not_run",
        "scope": "Explicit natal table application and software reuse; source cells are reused, not multiplied into independent cases",
    }
