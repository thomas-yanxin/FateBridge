"""Separate literal contrasts from month/hour stem dependencies, without grading."""

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-contrast-dependencies-v1"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
PILLARS = ["year", "month", "day", "hour"]
DERIVED = {"month.stem", "hour.stem"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(path):
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Changed frozen document: " + path.name)
    return json.loads(path.read_text())


def parts(pillars):
    if set(pillars) != set(PILLARS):
        raise ValueError("All four source positions must remain present")
    result = {}
    for name in PILLARS:
        value = pillars[name]
        if value is None:
            result[name + ".stem"] = result[name + ".branch"] = None
        elif (
            not isinstance(value, str)
            or len(value) != 2
            or value[0] not in STEMS
            or value[1] not in BRANCHES
        ):
            raise ValueError("Unknown literal source symbol")
        else:
            result[name + ".stem"], result[name + ".branch"] = value
    return result


def profiles(values):
    return (
        ["ordinary", "li1947_late_zi"]
        if values["hour.branch"] == "子"
        else ["ordinary"]
    )


def stem_checks(values, reference, profile):
    checks = {}
    for field, first, second, table in [
        ("month.stem", "year.stem", "month.branch", "hko_table4_month"),
        ("hour.stem", "day.stem", "hour.branch", "hko_table5_hour"),
    ]:
        parent, branch, observed = values[first], values[second], values[field]
        if None in [parent, branch, observed]:
            checks[field] = {"expected": None, "observed": observed, "matches": None}
            continue
        if field == "hour.stem" and profile == "li1947_late_zi":
            if branch != "子":
                raise ValueError("Late-zi candidate cannot apply to a non-zi hour")
            parent = STEMS[(STEMS.index(parent) + 1) % 10]
        expected = reference[table][parent][branch]
        checks[field] = {
            "expected": expected,
            "observed": observed,
            "matches": observed == expected,
        }
    return checks


def compare(before, after, reference):
    left, right = parts(before), parts(after)
    unknown = [k for k in left if left[k] is None or right[k] is None]
    differences = [
        {"field": k, "before": left[k], "after": right[k]}
        for k in left
        if left[k] is not None and right[k] is not None and left[k] != right[k]
    ]
    nonderived = [r for r in differences if r["field"] not in DERIVED]
    derived = [r for r in differences if r["field"] in DERIVED]
    candidates = []
    for lp, rp in itertools.product(profiles(left), profiles(right)):
        lc, rc = stem_checks(left, reference, lp), stem_checks(right, reference, rp)
        candidates.append(
            {
                "before_profile": lp,
                "after_profile": rp,
                "before_checks": lc,
                "after_checks": rc,
                "all_observed_stems_match_tables": all(
                    c["matches"] is True for checks in [lc, rc] for c in checks.values()
                ),
                "changed_derived_field_checks": [
                    {
                        **row,
                        "before_matches": lc[row["field"]]["matches"],
                        "after_matches": rc[row["field"]]["matches"],
                    }
                    for row in derived
                ],
            }
        )
    return {
        "literal_differences": differences,
        "literal_glyph_change_count": None if unknown else len(differences),
        "non_derived_coordinate_differences": nonderived,
        "non_derived_coordinate_change_count": None if unknown else len(nonderived),
        "changed_derived_fields": derived,
        "unknown_coordinates_retained": unknown,
        "profile_candidates": candidates,
        "sixty_cycle_mismatches": {
            side: [
                name
                for name, value in values.items()
                if value is not None
                and value not in reference["hko_table2_sexagenary_cycle"]
            ]
            for side, values in [("before", before), ("after", after)]
        },
        "actual_zi_clock_inferred": False,
        "same_glyph_multiset": (
            None if unknown else sorted(left.values()) == sorted(right.values())
        ),
        "historical_calendar_realisability_certified": False,
        "single_variable_causal_experiment_certified": False,
        "source_wording_or_pillars_repaired": False,
    }


def assess(study, root):
    protocol = bound(study / "protocol-first.json")
    for name, key in [
        ("cases-first.json", "all558_cases_sha256"),
        ("claims-first.json", "all1380_claims_sha256"),
        ("selection-first.json", "selection_sha256"),
        ("warnings-first.json", "warnings_sha256"),
        ("source-origins-first.json", "source_origins_sha256"),
    ]:
        if sha(study / name) != protocol[key]:
            raise ValueError("Changed complete source inventory")
    reference = bound(study / "reference-first.json")
    if sha(study / "reference-first.json") != protocol["independent_reference_sha256"]:
        raise ValueError("Changed correspondence reference")
    review = bound(study / "pair-source-review-first.json")
    if review["parent_protocol_sha256"] != sha(study / "protocol-first.json") or review[
        "pair_link_plan_sha256"
    ] != sha(study / "pair-link-plan-first.json"):
        raise ValueError("Source pair review lost prospective binding")
    plan = bound(study / "pair-link-plan-first.json")
    if [(r["before_case_id"], r["after_case_id"]) for r in review["printed_pairs"]] != [
        (r["before_case_id"], r["after_case_id"]) for r in plan["printed_pairs"]
    ]:
        raise ValueError("Printed contrast pairs narrowed or reordered")
    for name, h in review["source_page_sha256"].items():
        if sha(root / name) != h:
            raise ValueError("Source page changed")
    pdf = root / "docs/validation/bazi-controller-root-load-v1/source-whole.pdf"
    if sha(pdf) != protocol["source_pdf_sha256"]:
        raise ValueError("Source edition changed")
    cases = json.loads((study / "cases-first.json").read_text())
    claims = json.loads((study / "claims-first.json").read_text())
    selection = json.loads((study / "selection-first.json").read_text())
    selected_claims = [
        c for c in claims.values() if any(x in c["anchor"] for x in ["換", "换"])
    ]
    selected_cases = [
        c
        for c in cases
        if any(
            re.search("compar|pair|counterfact|difference", k, re.I)
            for k in c.get("source_metadata", {})
        )
        or c.get("kind") == "source_counterfactual_relational_case"
    ]
    if (
        len(cases) != 558
        or len(claims) != 1380
        or selected_claims != selection["claims"]
        or selected_cases != selection["cases"]
    ):
        raise ValueError("Complete collection search changed")
    by_id = {c["case_id"]: c for c in cases}
    if len(by_id) != len(cases):
        raise ValueError("Duplicate source-case ID")
    results, pair_ids = [], set()
    for pair in review["printed_pairs"]:
        a, b = pair["before_case_id"], pair["after_case_id"]
        identity = frozenset([a, b])
        if (
            len(identity) != 2
            or identity in pair_ids
            or a not in by_id
            or b not in by_id
        ):
            raise ValueError("Absent, repeated or reflexive source pair")
        if pair["source_claim_ids"] != by_id[b]["claim_ids"]:
            raise ValueError("Pair lost linked source claims")
        pair_ids.add(identity)
        results.append(
            {
                **pair,
                "before_case": by_id[a],
                "after_case": by_id[b],
                "symbolic_contrast": compare(
                    by_id[a]["literal_pillars"], by_id[b]["literal_pillars"], reference
                ),
            }
        )
    relational = [
        c for c in cases if c.get("kind") == "source_counterfactual_relational_case"
    ]
    if [c["case_id"] for c in relational] != review["all14_relational_case_ids"] or any(
        any(c["literal_pillars"].values()) for c in relational
    ):
        raise ValueError("Unprinted source alternatives were filled or omitted")
    covered_cases = (
        {r["before_case_id"] for r in results}
        | {r["after_case_id"] for r in results}
        | {c["case_id"] for c in relational}
    )
    covered_claims = {
        claim_id for r in results for claim_id in r["source_claim_ids"]
    } | {claim_id for c in relational for claim_id in c["claim_ids"]}
    if (
        not {c["case_id"] for c in selected_cases} <= covered_cases
        or not {c["claim_id"] for c in selected_claims} <= covered_claims
    ):
        raise ValueError(
            "Selected source contrasts omitted from pair/relational review"
        )
    warnings = json.loads((study / "warnings-first.json").read_text())
    if len(warnings["original22"]) != 22 or len(warnings["input4"]) != 4:
        raise ValueError("Original unresolved questions narrowed")
    return {
        "protocol_sha256": sha(study / "protocol-first.json"),
        "pair_review_sha256": sha(study / "pair-source-review-first.json"),
        "runner_sha256": sha(Path(__file__)),
        "all558_case_records_retained": True,
        "all1380_claim_records_searched": True,
        "selected_claims": selected_claims,
        "selected_cases": selected_cases,
        "printed_pair_results": results,
        "all14_unprinted_relational_cases_retained": relational,
        "all_original_questions_retained": warnings,
        "source_ambiguities_closed": 0,
        "source_force_calculations": 0,
        "new_model_executions": 0,
        "original26_disagreement_gate_superseded": False,
        "independent_source_review_certified": False,
        "force_comparison_allowed": False,
        "causal_acceptance": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refuse to replace a source-contrast assessment")
    result = assess(args.study.resolve(), ROOT)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "printed_pairs": len(result["printed_pair_results"]),
                "unprinted_relational_cases": len(
                    result["all14_unprinted_relational_cases_retained"]
                ),
                "source_questions_closed": 0,
                "force_comparison_allowed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
