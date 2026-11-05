"""Reject invented pre-decade palaces/transformations under the selected age rule."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import (
    _palace_for_nominal_age,
    build_ziwei_chart,
    build_ziwei_horoscope,
)
from scripts.ziwei_conditional_inputs import synthetic_birth_clock

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

FIXTURES = Path(__file__).resolve().parents[1] / "tests/data/ziwei_independent"


def audit_activation(fixtures: Path = FIXTURES) -> dict[str, Any]:
    source = json.loads((fixtures / "pre_decade_policy_manifest.json").read_text())
    software = source["software_reference"]
    reference_path = fixtures / software["path"]
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != software["sha256"]:
        raise ValueError("Decade activation software reference checksum mismatch")
    reference = json.loads(reference_path.read_text())
    for label, row in software["pre_decade_rows_asserted_as_differences"].items():
        if reference[label]["scopes"]["大限"] != row:
            raise ValueError("Declared pre-decade software difference changed")
    for rel, digest in source["source_manifest_sha256"].items():
        p = fixtures / rel
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Decade activation source manifest mismatch: {rel}")
        for row in json.loads(p.read_text())["files"]:
            if (
                hashlib.sha256((p.parent / row["path"]).read_bytes()).hexdigest()
                != row["sha256"]
            ):
                raise ValueError(f"Decade activation source checksum mismatch: {rel}")
    mismatches: list[dict[str, Any]] = []
    before = started = chart_inputs = 0
    bureaus = set()
    for row in source["literal_conditional_inputs"]:
        first = row["given_bureau_number"]
        bureaus.add(first)
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            for gender in ("男", "女"):
                chart = build_ziwei_chart(
                    _seed(
                        row["lunar_year"], row["lunar_month"], hour=row["hour_branch"]
                    ),
                    gender,
                    rule_profile=profile,
                )
                chart_inputs += 1
                if chart["wuxing_ju"]["number"] != first:
                    mismatches.append(dict(case="conditional_bureau_premise"))
                formal_first = "命宫"
                if profile == "quanshu_v2_excerpt":
                    formal_first = "父母宫" if gender == "男" else "兄弟宫"
                for age in range(1, first + 2):
                    h = build_ziwei_horoscope(
                        birth_seed=synthetic_birth_clock(
                            int((chart)["lunar_date"]["year"])
                        ),
                        chart=chart,
                        gender=gender,
                        target_seed=_seed(row["lunar_year"] + age - 1),
                    )
                    d = h["scopes"][0]
                    checks = {
                        "age": h["nominal_age"] == age,
                        "first_age": d["first_age"] == first,
                        "not_a_childhood_substitute": "is_childhood_limit" not in d,
                        "other_scope_slots": [s["scope"] for s in h["scopes"][1:]]
                        == source["other_scopes"],
                    }
                    for s in h["scopes"][1:]:
                        checks[f"{s['scope']}_available"] = (
                            s["branch"] is not None
                            and len(s["mutagen"]) == len(s["mutagen_natal_links"]) == 4
                            and len(s["palace_map"]) == 12
                        )
                    if age < first:
                        before += 1
                        checks["not_started"] = d["status"] == "not_started"
                        checks.update(
                            {
                                f"null_{key}": d[key] is None
                                for key in source["null_formal_scope_fields"]
                            }
                        )
                        checks.update(
                            {
                                f"empty_{key}": d[key] == []
                                for key in source["empty_formal_scope_lists"]
                            }
                        )
                        try:
                            _palace_for_nominal_age(chart["palaces"], age)
                        except ValueError:
                            checks["formal_lookup_rejects_substitution"] = True
                        else:
                            checks["formal_lookup_rejects_substitution"] = False
                    else:
                        started += 1
                        checks["computed"] = d["status"] == "computed"
                        checks["first_palace"] = d["natal_palace_name"] == formal_first
                        checks["formal_facts"] = (
                            len(d["mutagen"]) == len(d["mutagen_natal_links"]) == 4
                            and len(d["palace_map"]) == 12
                        )
                    failed = [k for k, passed in checks.items() if not passed]
                    if failed:
                        mismatches.append(
                            dict(
                                bureau=first,
                                profile=profile,
                                gender=gender,
                                age=age,
                                failed=failed,
                            )
                        )
    return {
        "method_id": source["id"],
        "conditional_chart_inputs": chart_inputs,
        "conditional_age_cases_checked": before + started,
        "pre_decade_cases": before,
        "started_decade_cases": started,
        "given_bureaus": sorted(bureaus),
        "declared_software_reference_differences": software[
            "pre_decade_rows_asserted_as_differences"
        ],
        "original_software_reference_sha256": software["sha256"],
        "mismatches": mismatches,
        "new_independent_sources": 0,
        "independent_calendar_or_placement_oracle": False,
        "historical_age_boundary_certified": False,
        "historical_unique_policy_certified": False,
        "live_model_blind_evaluation": "not_run",
        "whole_book_acceptance_passed": False,
        "scope": "Engineering availability policy under selected age/bureau premises; no invented formal pre-decade calculation",
    }
