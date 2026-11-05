"""Keep all64 month readings and intra-edition failures visible."""

import argparse
import hashlib
import json
from pathlib import Path

from fatebridge.core.heluo import MONTH_GUA, _gua_tables, calculate, gua_lines
from fatebridge.core.heluo_months import MONTH_BRANCHES, month_affinity

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/heluo_month_profiles_v1"


def audit():
    front = json.loads((FIXTURES / "front-table-reference.json").read_bytes())
    intro = {
        r["gua"]: r
        for r in json.loads((FIXTURES / "intro-reference.json").read_bytes())[
            "assigned_months"
        ]
    }
    rows = []
    engine_failures = []
    pillars = dict(year="甲子", month="丁卯", day="庚申", hour="庚辰")
    chart = calculate(
        four_pillars=pillars,
        gender="男",
        hour_zhi="辰",
        birth_year=1924,
        month_zhi="卯",
    )
    for source in front["assigned_months"]:
        gua = source["gua"]
        pair = _gua_tables()[0][gua]
        for p in ("xian", "hou"):
            chart[p].update(name=gua, **pair, lines=gua_lines(pair["up"], pair["low"]))
        for method in ("intro_preferred_v1", "volume_one_table_v1"):
            expected = (
                source if method == "volume_one_table_v1" else intro.get(gua, source)
            )
            for number, branch in enumerate(MONTH_BRANCHES, 1):
                result = month_affinity(
                    chart, branch, MONTH_GUA, assignment_method=method
                )
                for p in result["phases"]:
                    if (
                        p["assigned_month_number"],
                        p["assigned_month_match"],
                        p["source_pdf_page"],
                    ) != (
                        expected["month"],
                        number == expected["month"],
                        expected["page"],
                    ):
                        engine_failures.append(
                            {
                                "gua": gua,
                                "method": method,
                                "month": number,
                                "phase": p["phase"],
                                "actual": p,
                            }
                        )
        other = intro.get(gua)
        rows.append(
            {
                "gua": gua,
                "table_month": source["month"],
                "table_pdf_page": source["page"],
                "intro_month": other["month"] if other else None,
                "intro_pdf_page": other["page"] if other else 177,
                "source_months_agree": (
                    other["month"] == source["month"] if other else None
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


def main():
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
