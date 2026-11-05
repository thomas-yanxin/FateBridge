"""Keep an entire authored case cohort separate from calendar and empirical proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_tanyuan_cases_v1"
PIN = "f1f4c9c6c42aee61c89911fffbbe8fa4c4ca1fc26c02eac824059e7d5492e4c0"
PROFILE: Literal["tanyuan_xieji_v1"] = "tanyuan_xieji_v1"
LABELS = ("initial", "middle", "final")
ALIAS_CORPUS = ROOT / "tests/fixtures/liuren_tanyuan_case_alias_v1"
ALIAS_PIN = "2e96b4c60b2189907d85ad012771f5028767ef70e2de091e22891ed1fc1754ff"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen authored-case identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Frozen authored-case inventory changed")
    if any(sha(folder / n) != h for n, h in files.items()):
        raise ValueError("Frozen authored-case content changed")
    data = {
        key: json.loads((folder / f"{key}.json").read_text())
        for key in ("readings", "calendar-sources", "reference", "protocol")
    }
    reading, sources = data["readings"], data["calendar-sources"]
    for path, digest in (
        (reading["source_path"], reading["source_sha256"]),
        (sources["naoj_jdn_path"], sources["naoj_sha256"]),
        (sources["reference_path"], sources["reference_sha256"]),
    ):
        if sha(ROOT / path) != digest:
            raise ValueError("Primary transitive source changed: " + path)
    for source in sources["hko"]:
        if sha(folder / Path(source["path"]).name) != source["sha256"]:
            raise ValueError("Original HKO table changed")
    from tests.ren_source_arithmetic import tanyuan_cases

    if tanyuan_cases(folder) != json.loads((folder / "reference.json").read_text()):
        raise ValueError("Independent source arithmetic differs")
    if [r["id"] for r in reading["cases"]] != [f"C{i:02}" for i in range(1, 9)]:
        raise ValueError("Whole authored cohort changed")
    return data


def alias_reference(folder: Path = ALIAS_CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != ALIAS_PIN:
        raise ValueError("Frozen alias review identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Frozen alias review inventory changed")
    if any(sha(folder / n) != h for n, h in files.items()):
        raise ValueError("Frozen alias review content changed")
    review: dict[str, Any] = json.loads((folder / "review.json").read_text())
    if review["aliases"] != {"天乙": "贵人"} or review["original_cases_pin"] != PIN:
        raise ValueError("Alias scope or original identity changed")
    if sha(ROOT / review["source_path"]) != review["source_sha256"]:
        raise ValueError("Alias primary source changed")
    return review


def canonical_gods(facts: dict[str, Any]) -> dict[str, Any]:
    """A single pinned deity alias; preserve every non-god field verbatim."""
    return {
        key: (
            [{"天乙": "贵人"}.get(item, item) for item in value]
            if key in ("transmission_gods", "lesson_gods")
            else value
        )
        for key, value in facts.items()
    }


def expected_facts(case: dict[str, Any]) -> dict[str, Any]:
    return dict(
        transmission_branches=case["printed_transmission_branches"],
        transmission_gods=case["printed_transmission_gods"],
        lessons_upper_lower=case["printed_lessons_upper_lower"],
        lesson_gods=case["printed_lesson_gods"],
    )


def board_facts(board: dict[str, Any], day: str) -> dict[str, Any]:
    gods = {r["sky_branch"]: r["god"] for r in board["twelve_board"]}
    return dict(
        transmission_branches=[
            board["three_transmissions"][k]["branch"] for k in LABELS
        ],
        transmission_gods=[board["three_transmissions"][k]["god"] for k in LABELS],
        lessons_upper_lower=[
            r["upper_branch"] + (day[0] if i == 0 else r["lower_branch"])
            for i, r in enumerate(board["four_lessons"])
        ],
        lesson_gods=[gods[r["upper_branch"]] for r in board["four_lessons"]],
    )


def title_names(board: dict[str, Any]) -> list[str]:
    names = {board["board_style"], board["board_style_detail"]}
    names.update(r["name"].removesuffix("课") for r in board["patterns"])
    for section in (
        board["day_placement_patterns"],
        board["transmission_relations"]["course_conditions"],
        board["transmission_relations"]["named_structures"],
    ):
        names.update(
            r["name"]
            for r in section.get("evaluations", [])
            if r.get("matched") is True
        )
    return sorted(names)


def calendar_comparison(
    seed: Any, board: dict[str, Any], ref: dict[str, Any], sample: dict[str, Any]
) -> dict[str, bool]:
    lunar = seed.calendar_context["lunar_calendar"]
    return dict(
        lunar=[lunar["year"], lunar["month"], lunar["day"], lunar["is_leap_month"]]
        == ref["lunar_date"],
        day="".join(seed.pillars["day"]) == sample["day_ganzhi"],
        hour="".join(seed.pillars["hour"]) == sample["hour_ganzhi"],
        month_branch=seed.pillars["month"][1] in ref["month_branch_candidates"],
        month_general=board["month_general"]["branch"]
        in ref["month_general_candidates"],
    )


def audit() -> dict[str, Any]:
    data = reference()  # Verify every original before importing the producer.
    alias_review = alias_reference()
    from fatebridge.core.almanac import get_solar_term_environment_key
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    cases, errors, calendar_rows = [], [], []
    for case, ref in zip(
        data["readings"]["cases"], data["reference"]["cases"], strict=True
    ):
        if case["id"] != ref["id"]:
            raise ValueError("Case/reference input binding differs")
        solar = date.fromisoformat(ref["solar_date"])
        row: dict[str, Any] = dict(
            id=case["id"],
            source=case,
            reference=ref,
            first_minute_symbolic=None,
            calendar_failures=[],
            printed_day_mismatch_minutes=[],
            title_missing_minutes=[],
        )
        for sample in ref["samples"]:
            minute = sample["minute_of_day"]
            try:
                seed = _build_analysis_seed(
                    analysis_year=solar.year,
                    analysis_month=solar.month,
                    analysis_day=solar.day,
                    analysis_hour=minute // 60,
                    analysis_minute=minute % 60,
                    analysis_timezone="+08:00",
                    use_true_solar_time=False,
                )
                seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
                    seed
                )
                board = build_liureng_board(seed, guiren_profile=PROFILE)
                day = "".join(seed.pillars["day"])
                facts = board_facts(board, day)
                comparisons = calendar_comparison(seed, board, ref, sample)
                names = title_names(board)
                entry = dict(
                    id=case["id"],
                    minute_of_day=minute,
                    calendar_checks=comparisons,
                    calendar_passed=all(comparisons.values())
                    and not ref["term_day_underdetermined"],
                    printed_day_agrees=day == case["printed_day_ganzhi"],
                    expected_printed=expected_facts(case),
                    actual=facts,
                    printed_facts_agree=facts == expected_facts(case),
                    printed_title=case["printed_title"],
                    emitted_titles=names,
                    printed_title_recognized=case["printed_title"] in names,
                    current_term=board["meta"]["current_term"],
                )
                entry["canonical_facts_agree"] = canonical_gods(
                    facts
                ) == canonical_gods(expected_facts(case))
                calendar_rows.append(entry)
                if not entry["calendar_passed"]:
                    row["calendar_failures"].append(entry)
                if not entry["printed_day_agrees"]:
                    row["printed_day_mismatch_minutes"].append(minute)
                if not entry["printed_title_recognized"]:
                    row["title_missing_minutes"].append(minute)
                if row["first_minute_symbolic"] is None:
                    # Separate controlled reconstruction: use the printed general,
                    # never count this override as a calendar validation pass.
                    symbolic = build_liureng_board(
                        seed,
                        month_general_override=case["printed_month_general"],
                        guiren_profile=PROFILE,
                    )
                    common = build_liureng_board(
                        seed,
                        month_general_override=case["printed_month_general"],
                        guiren_profile="liuren_common_v1",
                    )
                    symbolic_row: dict[str, Any] = dict(
                        placeholder_minute=minute,
                        historical_instant_known=False,
                        facts=board_facts(symbolic, day),
                        agrees=board_facts(symbolic, day) == expected_facts(case),
                        default_profile_facts=board_facts(common, day),
                        default_profile_agrees=board_facts(common, day)
                        == expected_facts(case),
                        titles=title_names(symbolic),
                        title_recognized=case["printed_title"] in title_names(symbolic),
                        day_placements=symbolic["day_placement_patterns"],
                        calendar_override_used=True,
                        calendar_credit=False,
                    )
                    symbolic_row["canonical_agrees"] = canonical_gods(
                        board_facts(symbolic, day)
                    ) == canonical_gods(expected_facts(case))
                    symbolic_row["default_profile_canonical_agrees"] = canonical_gods(
                        board_facts(common, day)
                    ) == canonical_gods(expected_facts(case))
                    symbolic_row["actual_calendar_policy"] = seed.calendar_context[
                        "ren_calendar_policy"
                    ]
                    row["first_minute_symbolic"] = symbolic_row
            except Exception as error:
                errors.append(
                    dict(
                        id=case["id"],
                        minute_of_day=minute,
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
        cases.append(row)
    after = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    reference()
    alias_reference()
    result = dict(
        source_pin=PIN,
        source_sha256=data["readings"]["source_sha256"],
        source_protocol=data["protocol"],
        implementation_sha256=before,
        implementation_unchanged=before == after,
        runtime_environment={
            str(y): str(get_solar_term_environment_key(year=y))
            for y in (1909, 1910, 1911)
        },
        authored_cases=8,
        minute_grid_rows=len(calendar_rows),
        calendar_passed_rows=sum(r["calendar_passed"] for r in calendar_rows),
        calendar_failures=[r for r in calendar_rows if not r["calendar_passed"]],
        cases=cases,
        minute_grid=calendar_rows,
        execution_errors=errors,
        all_authored_boards_agree=all(
            c["first_minute_symbolic"] is not None
            and c["first_minute_symbolic"]["agrees"]
            for c in cases
        ),
        printed_facts_agree_rows=sum(r["printed_facts_agree"] for r in calendar_rows),
        title_recognized_rows=sum(r["printed_title_recognized"] for r in calendar_rows),
        historical_clock_certified=False,
        continuous_interval_proof=False,
        independent_blinded_reader=False,
        free_text_fidelity="not_reassessed",
        new_llm_processes=0,
        new_empirical_events=0,
        real_world_prediction="deferred_by_user",
        original_gates_reclassified=False,
        full_classical_conformance=False,
        goal_complete=False,
    )
    result.update(
        alias_review_pin=ALIAS_PIN,
        alias_review=alias_review,
        all_canonical_authored_boards_agree=all(
            c["first_minute_symbolic"] is not None
            and c["first_minute_symbolic"]["canonical_agrees"]
            for c in cases
        ),
        canonical_facts_agree_rows=sum(
            r["canonical_facts_agree"] for r in calendar_rows
        ),
        original_literal_comparison_retained=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "authored_cases",
                    "minute_grid_rows",
                    "calendar_passed_rows",
                    "all_authored_boards_agree",
                    "printed_facts_agree_rows",
                    "title_recognized_rows",
                    "execution_errors",
                    "goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return (
        1 if result["execution_errors"] or not result["implementation_unchanged"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
