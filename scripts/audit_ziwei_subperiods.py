"""Audit selected textual groups and conditional ordinals without an outcome oracle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.ziwei_subperiods import decade_half
from scripts.ziwei_conditional_inputs import synthetic_birth_clock

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def audit_subperiods(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "naj_ming_subperiods_v1"
    for name, digest in json.loads((folder / "checksums.json").read_text()).items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Ming subperiod source checksum mismatch: " + name)
    source = json.loads((folder / "collation.json").read_text())
    extension = json.loads((folder / "coverage_extension.json").read_text())
    if (
        extension["original_collation_sha256"]
        != hashlib.sha256((folder / "collation.json").read_bytes()).hexdigest()
        or not extension["declared_after_implementation"]
        or extension["month_bureau_pairs"] != [[11, 2], [3, 3], [7, 4], [5, 5]]
    ):
        raise ValueError("Ming subperiod postimplementation coverage policy mismatch")
    for name, digest in source["external_sources"].items():
        if hashlib.sha256((fixtures / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Ming group definition source checksum mismatch: " + name)
    compiled = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-subperiods.json"
        ).read_text()
    )
    differences: list[dict[str, Any]] = []
    if compiled != {k: source[k] for k in compiled}:
        differences.append(dict(case="compiled_source_copy"))
    for vector in source["conditional_boundary_vectors"]:
        first, age = vector["first_age"], vector["given_age"]
        lo = first + (10 if age == first + 10 else 0)
        r = decade_half(
            [dict(ganzhi="甲子", daxian=f"{lo}~{lo + 9}")],
            dict(status="not_started" if age < first else "computed", branch="子"),
            age,
        )
        if (r["half"], r["year_ordinal_in_decade"]) != (
            vector["half"],
            vector["ordinal"],
        ):
            differences.append(dict(case="frozen_boundary", vector=vector))
    expected_groups = {
        name: row for row in source["group_rows"] for name in row["stars"]
    }
    charts = joins = 0
    original_charts = 0
    bureau_numbers: set[int] = set()
    policy = source["coverage_policy"]
    inputs = [(year, policy["month"], None) for year in policy["years"]]
    inputs += [
        (extension["year"], month, bureau)
        for month, bureau in extension["month_bureau_pairs"]
    ]
    for year, month, expected_bureau in inputs:
        for profile in policy["profiles"]:
            for gender in policy["genders"]:
                c = build_ziwei_chart(
                    _seed(year, month, policy["day"], policy["hour_branch"]),
                    gender,
                    rule_profile=profile,
                )
                first = c["wuxing_ju"]["number"]
                if expected_bureau is not None and first != expected_bureau:
                    differences.append(
                        dict(case="coverage_bureau", month=month, actual=first)
                    )
                bureau_numbers.add(first)
                for age in range(1, first + 120):
                    h = build_ziwei_horoscope(
                        # These clocks supply only the conditional ordinal;
                        # the natal rule chart remains the literal source input.
                        birth_seed=synthetic_birth_clock(1901),
                        chart=c,
                        gender=gender,
                        target_seed=_seed(1901 + age - 1),
                    )
                    evidence = h["ming_limit_subperiods"]
                    r = evidence["daxian"]
                    ok = r["nominal_age"] == age
                    if age < first:
                        ok = ok and r["status"] == "not_started" and r["half"] is None
                    else:
                        p = next(
                            p
                            for p in c["palaces"]
                            if p["ganzhi"][1] == h["scopes"][0]["branch"]
                        )
                        start, end = (int(v) for v in p["daxian"].split("~"))
                        ordinal = list(range(start, end + 1)).index(age) + 1
                        half = (
                            "upper_five_years"
                            if ordinal in [1, 2, 3, 4, 5]
                            else "lower_five_years"
                        )
                        ok = ok and (
                            r["selected_decade_age_range"] == [start, end]
                            and r["year_ordinal_in_decade"] == ordinal
                            and r["half"] == half
                            and r["selected_half_age_range"]
                            == (
                                [start, start + 4] if ordinal <= 5 else [start + 5, end]
                            )
                            and r["textual_group"]
                            == ("north" if ordinal <= 5 else "south")
                        )
                    records = evidence["natal_star_groups"]
                    ok = ok and len(records) == len(expected_groups)
                    for record in records:
                        expected = expected_groups[record["star"]]
                        group = expected["group"]
                        ok = ok and (
                            record["textual_group"] == group
                            and record["source_quote"] == expected["quote"]
                            and record["source_frame"] == expected["frame"]
                            and record["textual_daxian_half"]
                            == {
                                "north": "upper_five_years",
                                "south": "lower_five_years",
                                "both": None,
                            }[group]
                            and record["selected_as_relevant_star"] is None
                            and len(record["actual_occurrences"]) == 1
                        )
                        for occurrence in record["actual_occurrences"]:
                            actual: Any = {"ziwei_horoscope": h}
                            for part in occurrence["calculation_path"].split("."):
                                actual = (
                                    actual[int(part)]
                                    if isinstance(actual, list)
                                    else actual[part]
                                )
                            ok = ok and (
                                actual["name"] == record["star"]
                                and actual["mutagen"] == occurrence["natal_mutagen"]
                            )
                            joins += 1
                    ok = ok and (
                        evidence["xiaoxian"]["half"] is None
                        and evidence["xiaoxian"]["half_start"] is None
                        and evidence["xiaoxian"]["half_end"] is None
                        and evidence["full_traditional_judgment"] is None
                        and not evidence["source_outcome_claim_adopted"]
                        and not evidence["relevant_star_geometry_defined"]
                        and not evidence["actual_assignments_modified"]
                        and not r["calendar_boundaries_classically_verified"]
                    )
                    if not ok:
                        differences.append(
                            dict(
                                case="conditional_chart",
                                year=year,
                                profile=profile,
                                gender=gender,
                                age=age,
                            )
                        )
                    charts += 1
                    original_charts += expected_bureau is None
    return dict(
        method_id=source["id"],
        source_frame=35,
        source_clauses=2,
        adjacent_context_clauses_retained_not_evaluated=1,
        source_transcription_method=source["transcription_method"],
        independent_human_reviewers=0,
        independent_model_reviewers=0,
        textual_group_definitions=len(source["group_rows"]),
        textual_star_entities=len(expected_groups),
        dual_group_star_entities=sum(
            r["group"] == "both" for r in expected_groups.values()
        ),
        frozen_conditional_boundary_vectors=len(source["conditional_boundary_vectors"]),
        whole_chart_conditional_age_cases=charts,
        original_preimplementation_policy_chart_cases=original_charts,
        postimplementation_coverage_chart_cases=charts - original_charts,
        postimplementation_coverage_declared=True,
        observed_bureau_numbers=sorted(bureau_numbers),
        actual_star_joins_checked=joins,
        independent_calendar_or_placement_oracle=False,
        synthetic_ordinal_clock_anchor_year=1901,
        xiaoxian_calendar_half_years_selected=0,
        full_traditional_judgments_evaluated=0,
        live_model_blind_evaluation="not_run",
        whole_book_acceptance_passed=False,
        differences=differences,
        limits=source["limits"],
    )
