"""Compare all 64 Heluo month readings with the selected source profiles."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import TypedDict

from pydantic import JsonValue

from fatebridge.core.heluo.heluo import MONTH_GUA, calculate
from fatebridge.core.heluo.heluo_hexagrams import _gua_tables, gua_lines
from fatebridge.core.heluo.heluo_months import (
    MONTH_BRANCHES,
    MonthAssignmentMethod,
    month_affinity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/heluo_month_profiles_v1"


class MonthSourceComparison(TypedDict):
    gua: str
    table_month: int
    table_pdf_page: int
    intro_month: int | None
    intro_pdf_page: int
    source_months_agree: bool | None


class MonthProfileFailure(TypedDict):
    gua: str
    method: str
    month: int
    phase: str
    actual: dict[str, JsonValue]


class MonthProfileAudit(TypedDict):
    schema_version: str
    references_sha256: dict[str, str]
    all64_source_rows: list[MonthSourceComparison]
    source_consistency_failures: list[MonthSourceComparison]
    source_consistency_passed: bool
    engine_profile_failures: list[MonthProfileFailure]
    engine_profile_checks: int
    engine_profile_checks_passed: bool
    independent_second_reviews: int
    calendar_reference_instants_added: int
    original_birth_examples_added: int
    real_model_runs_added: int
    prediction_evidence: str
    three_dimensions_full_score: bool
    four_dimensions_full_score: bool
    authority_system: bool
    scope: str


def audit() -> MonthProfileAudit:
    """Record source conflicts separately from failed engine reproduction checks."""
    front = json.loads((FIXTURES / "front-table-reference.json").read_bytes())
    intro = {
        r["gua"]: r
        for r in json.loads((FIXTURES / "intro-reference.json").read_bytes())[
            "assigned_months"
        ]
    }
    rows: list[MonthSourceComparison] = []
    engine_failures: list[MonthProfileFailure] = []
    pillars = dict(year="甲子", month="丁卯", day="庚申", hour="庚辰")
    chart = calculate(
        four_pillars=pillars,
        gender="男",
        hour_zhi="辰",
        birth_year=1924,
        month_zhi="卯",
    )
    methods: tuple[MonthAssignmentMethod, ...] = (
        "intro_preferred_v1",
        "volume_one_table_v1",
    )
    for source in front["assigned_months"]:
        hexagram_name = source["gua"]
        trigrams = _gua_tables()[0][hexagram_name]
        for phase_name in ("xian", "hou"):
            chart[phase_name].update(
                name=hexagram_name,
                **trigrams,
                lines=gua_lines(trigrams["up"], trigrams["low"]),
            )
        for method in methods:
            expected = (
                source
                if method == "volume_one_table_v1"
                else intro.get(hexagram_name, source)
            )
            for month_number, month_branch in enumerate(MONTH_BRANCHES, 1):
                result = month_affinity(
                    chart, month_branch, MONTH_GUA, assignment_method=method
                )
                for phase in result["phases"]:
                    if (
                        phase["assigned_month_number"],
                        phase["assigned_month_match"],
                        phase["source_pdf_page"],
                    ) != (
                        expected["month"],
                        month_number == expected["month"],
                        expected["page"],
                    ):
                        engine_failures.append(
                            {
                                "gua": hexagram_name,
                                "method": method,
                                "month": month_number,
                                "phase": phase["phase"],
                                "actual": phase,
                            }
                        )
                    else:
                        pass
        intro_reading = intro.get(hexagram_name)
        rows.append(
            {
                "gua": hexagram_name,
                "table_month": source["month"],
                "table_pdf_page": source["page"],
                "intro_month": intro_reading["month"] if intro_reading else None,
                "intro_pdf_page": intro_reading["page"] if intro_reading else 177,
                "source_months_agree": (
                    intro_reading["month"] == source["month"] if intro_reading else None
                ),
            }
        )
    failures = [r for r in rows if r["source_months_agree"] is False]
    return {
        "schema_version": "heluo_month_source_profiles_v1",
        "references_sha256": {
            n: hashlib.sha256((FIXTURES / n).read_bytes()).hexdigest()
            for n in [
                "front-table-reference.json",
                "intro-reference.json",
                "research-protocol.json",
                "shi-hypothesis-results.json",
            ]
        },
        "all64_source_rows": rows,
        "source_consistency_failures": failures,
        "source_consistency_passed": not failures
        and all(r["source_months_agree"] is True for r in rows),
        "engine_profile_failures": engine_failures,
        "engine_profile_checks": 64 * 2 * 12 * 2,
        "engine_profile_checks_passed": not engine_failures,
        "independent_second_reviews": 0,
        "calendar_reference_instants_added": 0,
        "original_birth_examples_added": 0,
        "real_model_runs_added": 0,
        "prediction_evidence": "not_assessed",
        "three_dimensions_full_score": False,
        "four_dimensions_full_score": False,
        "authority_system": False,
        "scope": "All source disagreements retained. Profile reproduction checks are deterministic engineering checks, not independent double collation, whole-book conformity, complete deTime, calendar accuracy, semantic model evaluation or prediction evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-source-consistency", action="store_true")
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Engineering profile failures: {len(result['engine_profile_failures'])}; unresolved source month conflicts: {len(result['source_consistency_failures'])}"
    )
    return int(
        not result["engine_profile_checks_passed"]
        or (args.require_source_consistency and not result["source_consistency_passed"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
