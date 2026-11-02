"""Flag all recorded pillar relations without repairing source text or grading force."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-census-pillar-consistency-v1"
PILLARS = ("year", "month", "day", "hour")
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_pillar(value):
    if (
        isinstance(value, str)
        and len(value) == 2
        and value[0] in STEMS
        and value[1] in BRANCHES
    ):
        return value[0], value[1]
    return None


def assess_record(record, reference):
    case = record["case"]
    supplied = case["literal_pillars"]
    cycle = set(reference["hko_table2_sexagenary_cycle"])
    parts = {name: split_pillar(supplied[name]) for name in PILLARS}
    flags = []
    membership = {}
    for name in PILLARS:
        value = supplied[name]
        status = (
            "not_supplied"
            if value is None
            else (
                "unknown_symbols_or_shape"
                if parts[name] is None
                else "in_cycle" if value in cycle else "not_in_sixty_cycle"
            )
        )
        membership[name] = status
        if status not in {"not_supplied", "in_cycle"}:
            flags.append(f"{name}:{status}")

    month = {"status": "not_assessable_missing_or_unparsed_pillar"}
    if parts["year"] and parts["month"]:
        year_stem = parts["year"][0]
        month_stem, month_branch = parts["month"]
        expected = reference["li1947_pdf32_month"][year_stem][month_branch]
        month = {
            "status": "matches" if month_stem == expected else "mismatch",
            "year_stem": year_stem,
            "month_branch": month_branch,
            "actual_month_stem": month_stem,
            "expected_month_stem": expected,
            "rule": "Li1947_PDF32_yearstem_monthbranch_correspondence",
            "actual_calendar_year_and_term_boundary_identified": False,
        }
        if month["status"] == "mismatch":
            flags.append("year_month:mismatch")

    hour = {"status": "not_assessable_missing_or_unparsed_pillar"}
    if parts["day"] and parts["hour"]:
        day_stem = parts["day"][0]
        actual, branch = parts["hour"]
        ordinary = reference["li1947_pdf34_35_hour"][day_stem][branch]
        expected = {"same_display_day_hour_table": ordinary}
        if branch == "子":
            following = STEMS[(STEMS.index(day_stem) + 1) % len(STEMS)]
            expected["Li1947_late_zi_hour_with_same_displayed_day"] = reference[
                "li1947_pdf34_35_hour"
            ][following]["子"]
        matching = [name for name, value in expected.items() if value == actual]
        hour = {
            "status": (
                "matches_declared_profile"
                if matching
                else "mismatch_all_declared_profiles"
            ),
            "day_stem": day_stem,
            "hour_branch": branch,
            "actual_hour_stem": actual,
            "expected_by_profile": expected,
            "matching_profiles": matching,
            "actual_early_or_late_zi_clock_identified": False,
            "rule_scope": "symbolic_relation_only_not_birth_clock_or_historical_realisability",
        }
        if not matching:
            flags.append("day_hour:mismatch_all_declared_profiles")
    return {
        **record,
        "symbolic_assessment": {
            "pillar_membership": membership,
            "year_month": month,
            "day_hour": hour,
            "flags": flags,
            "complete_literal_four_pillars": all(
                supplied[n] is not None for n in PILLARS
            ),
            "source_kind_recorded": case.get("kind"),
            "source_repaired": False,
            "historical_birth_moment_identified": False,
            "force_grade_evaluated": False,
        },
    }


def run(study, output):
    if output.exists():
        raise FileExistsError("Refuse to overwrite an existing audit receipt")
    protocol_path = study / "protocol-first.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Protocol changed")
    protocol = json.loads(protocol_path.read_text())
    cases_path, reference_path = (
        study / "cases-first.json",
        study / "reference-first.json",
    )
    if digest(cases_path) != protocol["cases_sha256"]:
        raise ValueError("Frozen complete case inventory changed")
    if (
        digest(reference_path)
        != reference_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen correspondence reference changed")
    reference = json.loads(reference_path.read_text())
    if reference["all240_table_cell_differences"]:
        raise ValueError("Do not choose between disagreeing source tables silently")

    def guard_sources():
        for path, value in protocol["source_batches_sha256"].items():
            if digest(ROOT / path) != value:
                raise ValueError("Source batch changed")
        if (
            digest(
                ROOT / "docs/validation/bazi-controller-root-load-v1/source-whole.pdf"
            )
            != protocol["source_pdf_sha256"]
        ):
            raise ValueError("Source PDF changed")

    guard_sources()
    source = json.loads(cases_path.read_text())
    records = source["records"]
    if len(records) != protocol["registered_records"] or len(
        {r["case"]["case_id"] for r in records}
    ) != len(records):
        raise ValueError("Incomplete or duplicate-id case inventory")
    results = []
    flags = Counter()
    kinds = Counter()
    groups = defaultdict(list)
    for record in records:
        case = record["case"]
        encoded = json.dumps(
            case, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        if hashlib.sha256(encoded).hexdigest() != record["case_object_sha256"]:
            raise ValueError("A source-case object changed")
        result = assess_record(record, reference)
        results.append(result)
        flags.update(result["symbolic_assessment"]["flags"])
        kinds[case.get("kind", "field_not_recorded")] += 1
        groups[tuple(case["literal_pillars"][n] for n in PILLARS)].append(
            case["case_id"]
        )
    complete = sum(
        r["symbolic_assessment"]["complete_literal_four_pillars"] for r in results
    )
    if complete != protocol["complete_literal_four_pillars"]:
        raise ValueError("Original completeness denominator changed")
    flagged = [
        r["case"]["case_id"] for r in results if r["symbolic_assessment"]["flags"]
    ]
    guard_sources()
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    receipt = {
        "protocol_sha256": digest(protocol_path),
        "cases_sha256": digest(cases_path),
        "reference_sha256": digest(reference_path),
        "runner_sha256": digest(Path(__file__)),
        "collection_integrity_passed": True,
        "counts": {
            "records": len(results),
            "complete_literal_four_pillars": complete,
            "partial_records_retained": len(results) - complete,
            "flagged_records": len(flagged),
            "flags_by_relation": dict(flags),
            "source_kinds_retained": dict(kinds),
            "zi_profile_not_identified_records": sum(
                r["symbolic_assessment"]["day_hour"].get("hour_branch") == "子"
                for r in results
            ),
        },
        "flagged_ids": flagged,
        "records": results,
        "duplicate_literal_pillar_groups_retained": [
            {
                "literal_pillars": list(values),
                "case_ids": ids,
                "historical_identity_resolved": False,
            }
            for values, ids in groups.items()
            if len(ids) > 1
        ],
        "all_assessable_symbolic_relations_match": not flagged,
        "historical_realisability_accepted": False,
        "source_text_repaired": False,
        "original_source_gates_superseded": False,
        "new_source_case_force_calculations": 0,
        "new_model_executions": 0,
        "no_fatebridge_imports": True,
        "full_goal_complete": False,
        "overall_score": None,
    }
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"counts": receipt["counts"], "flagged_ids": flagged}, ensure_ascii=False
        )
    )
    return int(bool(flagged))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.study.resolve(), args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
