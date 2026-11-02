"""Audit Jingben year-fate ordinals and separate courses against pinned text."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "jinkou_year_fate_v1": "79d4d5b992c231d87e552b2bab813a3d737a85f34764496d17d9a22f929a2cd0",
    "jinkou_year_course_v1": "c0737ac73c7cf8f3f5b0259ffc2db063c5ff2c99bc9a7b7f3968239921a6040f",
    "jinkou_year_course_errata_v1": "a2b3f06c7ca8c9d021a16477e47acb0f5a6312410d23937f2e40fc38dd5fd166",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def references() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    out = []
    for name, digest in PINS.items():
        folder = ROOT / "tests/fixtures" / name
        if sha(folder / "freeze.json") != digest:
            raise ValueError("Frozen year-fate manifest changed")
        inventory = json.loads((folder / "freeze.json").read_text())["files"]
        if {p.name for p in folder.iterdir()} != set(inventory) | {"freeze.json"}:
            raise ValueError("Frozen year-fate inventory changed")
        if any(sha(folder / n) != h for n, h in inventory.items()):
            raise ValueError("Frozen year-fate source changed")
        out.append(json.loads((folder / "reference.json").read_text()))
    return out[0], out[1], out[2]


def course_cases() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _, raw, correction = references()
    cases = copy.deepcopy(raw["cases"])
    for change in correction["corrections"]:
        assert cases[change["case_index"]][change["field"]] == change["old"]
        cases[change["case_index"]][change["field"]] = change["new"]
    return raw, cases


def audit(baseline: Path | None = None) -> dict[str, Any]:
    source, raw, _ = references()
    names = [
        "src/fatebridge/core/metaphysics/jinkou_year_fate.py",
        "src/fatebridge/core/metaphysics/jinkou.py",
        "src/fatebridge/core/metaphysics/ren_evidence.py",
        "src/fatebridge/services/metaphysics.py",
        "src/fatebridge/core/output_chinese.py",
        "src/fatebridge/core/requests/metaphysics.py",
        "scripts/audit_jinkou_year_fate.py",
    ]
    names.extend(
        [
            "src/fatebridge/core/metaphysics/jinkou_relations.py",
            "src/fatebridge/core/output_jinkou_natal.py",
            "src/fatebridge/core/output_ren_anchors.py",
            "src/fatebridge/data/agent_examples.json",
            "scripts/audit_ren_golden_evidence.py",
        ]
    )
    before = {n: sha(ROOT / n) for n in names}
    from fatebridge.application.execution import validate_output
    from fatebridge.core.metaphysics.jinkou_stems import wuzidun_stem
    from fatebridge.core.metaphysics.jinkou_year_fate import ordinal_year_fate
    from fatebridge.services.metaphysics import calculate_jinkou_analysis
    from fatebridge.services.tool_catalog import CATALOG

    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    printed = []
    for row in source["source_ordinal_examples"]:
        actual = ordinal_year_fate(
            birth_year_ganzhi=row["birth_year_ganzhi"],
            age=row["age"],
            gender=row["gender"],
        )
        printed.append(
            dict(
                **row,
                actual=actual["ganzhi"],
                matched=actual["ganzhi"] == row["expected_ganzhi"],
            )
        )
    starts = []
    matrix = []
    for group in source["start_table"]:
        members = cycle[
            cycle.index(group["birth_xun"]) : cycle.index(group["birth_xun"]) + 10
        ]
        for sex, key in [("男", "male"), ("女", "female")]:
            start = group[key]
            start_result = ordinal_year_fate(
                birth_year_ganzhi=group["birth_xun"], age=1, gender=sex
            )
            tenth = ordinal_year_fate(
                birth_year_ganzhi=group["birth_xun"], age=10, gender=sex
            )
            starts.append(
                dict(
                    xun=group["birth_xun"],
                    gender=sex,
                    expected=start,
                    actual=start_result["ganzhi"],
                    tenth_branch=tenth["branch"],
                    matched=start_result["ganzhi"] == start
                    and tenth["branch"] == group["tenth_branch"],
                )
            )
            ordered = (
                cycle[cycle.index(start) :] + cycle[: cycle.index(start)]
                if sex == "男"
                else [start]
                + list(reversed(cycle[: cycle.index(start)]))
                + list(reversed(cycle[cycle.index(start) + 1 :]))
            )
            for born in members:
                for age in range(1, 151):
                    actual = ordinal_year_fate(
                        birth_year_ganzhi=born, age=age, gender=sex
                    )
                    expected = ordered[(age - 1) % 60]
                    assert actual["ganzhi"] == expected, (
                        born,
                        sex,
                        age,
                        actual["ganzhi"],
                        expected,
                    )
                    matrix.append([born, sex, age, actual["ganzhi"]])
    parity = []
    combinations = {
        frozenset(pair) for pair in ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"]
    }
    stems = "甲乙丙丁戊己庚辛壬癸"
    for annual in cycle:
        for day_stem in stems:
            human = wuzidun_stem(day_stem, annual[1])
            same_parity = stems.index(annual[0]) % 2 == stems.index(human) % 2
            combined = frozenset([annual[0], human]) in combinations
            assert same_parity and not combined
            parity.append([annual, day_stem, human, same_parity, combined])
    descriptor, corrected = course_cases()
    spec = next(s for s in CATALOG if s.key == "jinkou")
    courses = []
    for original, case in zip(raw["cases"], corrected):
        result = calculate_jinkou_analysis(
            **descriptor["calendar"],
            gender=case["gender"],
            is_diurnal=case["is_diurnal"],
        )
        validate_output(spec, result)
        annual = result["jinkou"]["year_fate"]
        board = annual["course"]
        actual = dict(
            year_ganzhi=annual["ganzhi"],
            ground=board["overview"]["di_fen"],
            positions=[r["content"] for r in board["rows"]],
            god=board["overview"]["guishen"]["name"],
            polarity_use=board["overview"]["use_position"],
        )
        facts = ("year_ganzhi", "ground", "positions", "god", "polarity_use")
        assert all(actual[k] == case[k] for k in facts), actual
        assert (
            result["jinkou"]["overview"]["di_fen"] == descriptor["calendar"]["di_fen"]
        )
        courses.append(
            dict(
                inputs=dict(gender=case["gender"], is_diurnal=case["is_diurnal"]),
                expected={k: case[k] for k in facts},
                actual=actual,
                matched=True,
                original_annotation_matched=all(
                    actual[k] == original[k] for k in facts
                ),
            )
        )
    legacy = None
    if baseline is not None:
        from fatebridge.core.metaphysics.jinkou import build_jinkou_board
        from scripts.audit_ren_classical import make_seed

        with gzip.open(baseline, "rt", encoding="utf-8") as f:
            old = json.load(f)
        assert len(old) == 720
        for row in old:
            current = build_jinkou_board(
                make_seed(dict(day=row["day"], hour="巳", month="辰")),
                {"month_general": {"branch": "戌"}},
                di_fen=row["ground"],
            )
            expected_ruleset = copy.deepcopy(row["board"]["ruleset"])
            assert expected_ruleset["version"] == "1.10.0"
            expected_ruleset["version"] = "1.11.0"
            expected_ruleset["source_title"] += "与六甲旬行年另课"
            expected_ruleset["conventions"][
                "year_fate"
            ] = "京本按明确出生年干支所属六甲旬取男女起点，男顺女逆；只用指定一岁起算岁序，另课采用行年支作地分的所选释读，不表示已观测来人方位；不借用大六壬通用行年起点。"
            expected_ruleset["conventions"][
                "natal_absolute"
            ] = "将命大绝取显式本命支，或明确birth_year_ganzhi的年支，与本次将神支核对京本四组配对；两者均缺仍未知，不以分析年日时、地分或行年替代本命"
            expected_ruleset["unresolved"].append(
                "京本行年换岁边界及己亥行年见甲人元所指课干未裁定，未认证综合喜用"
            )
            assert current["ruleset"] == expected_ruleset, "Undeclared ruleset change"
            current["ruleset"] = row["board"]["ruleset"]
            assert current == row["board"], (row["day"], row["ground"])
        legacy = dict(
            boards=720,
            full_old_board_preserved_except_declared_ruleset_metadata=True,
            baseline_sha256=sha(baseline),
            declared_ruleset_metadata_checked_on_all_boards=True,
        )
    after = {n: sha(ROOT / n) for n in names}
    assert before == after
    return dict(
        implementation_sha256=after,
        implementation_unchanged=True,
        reference_sha256=PINS,
        start_checks=starts,
        printed_age_checks=printed,
        printed_age_matches=sum(r["matched"] for r in printed),
        synthetic_ordinal_checks=len(matrix),
        synthetic_ordinal_sha256=hashlib.sha256(
            json.dumps(matrix, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        annual_course_checks=courses,
        initial_course_annotation_matches=sum(
            r["original_annotation_matched"] for r in courses
        ),
        corrected_course_annotation_matches=len(courses),
        parity_checks=len(parity),
        parity_counterexamples=0,
        five_combinations_on_annual_course=0,
        parity_digest=hashlib.sha256(
            json.dumps(parity, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        legacy_boards=legacy,
        engineering_checks_passed=all(r["matched"] for r in starts + printed + courses),
        age_boundary_classically_verified=False,
        comprehensive_year_fate_adjudicated=False,
        existing_64_pattern_conflicts_resolved=0,
        new_independent_empirical_events=0,
        full_calendar_acceptance=False,
        full_classical_acceptance=False,
        goal_complete=False,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--baseline", type=Path)
    args = p.parse_args()
    result = audit(args.baseline)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "printed_age_matches",
                    "synthetic_ordinal_checks",
                    "corrected_course_annotation_matches",
                    "initial_course_annotation_matches",
                    "parity_checks",
                    "engineering_checks_passed",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
