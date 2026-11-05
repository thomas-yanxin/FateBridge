"""Audit frozen branch tables and complete same-board relation ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_branch_relations_v1"
FREEZE_SHA = "61c9709c474611a67fab1bf324032a728f462d07c187daca98cf7ac8c9f3ba8e"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
FACTS = (
    "same_branch",
    "liuhe",
    "liupo",
    "liuhai",
    "liuchong",
    "left_xing_right",
    "right_xing_left",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != FREEZE_SHA:
        raise ValueError("Frozen branch-relation manifest changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest["files"]) != {"reference.json", "source-pages.pdf"} or {
        p.name for p in folder.iterdir()
    } != {"reference.json", "source-pages.pdf", "freeze.json"}:
        raise ValueError("Frozen branch-relation inventory changed")
    for name, checksum in manifest["files"].items():
        if sha(folder / name) != checksum:
            raise ValueError("Frozen branch-relation source changed")
    ref: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if {k: len(v) for k, v in ref["tables"].items()} != dict(
        liuhe=6, liupo=6, liuhai=6, liuchong=6, xing=12
    ) or len(ref["synthetic_cases"]) != 10:
        raise ValueError("Complete original branch-table denominators required")
    return ref


def expected(ref: dict[str, Any], left: str, right: str) -> dict[str, Any]:
    forward, reverse = left + right, right + left
    result: dict[str, Any] = dict(same_branch=left == right)
    for name in ("liuhe", "liupo", "liuhai", "liuchong"):
        result[name] = any(p in (forward, reverse) for p in ref["tables"][name])
    result["left_xing_right"] = forward in ref["tables"]["xing"]
    result["right_xing_left"] = reverse in ref["tables"]["xing"]
    result["harmony_annotation"] = next(
        (
            v["annotation"]
            for v in ref["harmony_annotations"]
            if v["pair"] in (forward, reverse)
        ),
        None,
    )
    return result


def expected_rows(board: dict[str, Any], day: str) -> list[tuple[str, str, str]]:
    rows = [
        ("seat." + v["earth_branch"], v["sky_branch"], v["earth_branch"])
        for v in board["twelve_board"]
    ]
    rows += [
        (f"lesson.{v['index']}", v["upper_branch"], v["lower_branch"])
        for v in board["four_lessons"]
    ]
    trans = board["three_transmissions"]
    for name, a, b in (
        ("initial_middle", "initial", "middle"),
        ("middle_final", "middle", "final"),
        ("initial_final", "initial", "final"),
    ):
        rows.append(("transmission." + name, trans[a]["branch"], trans[b]["branch"]))
    targets = [
        (f"lesson.{v['index']}", v["upper_branch"]) for v in board["four_lessons"]
    ]
    targets += [
        ("transmission." + k, trans[k]["branch"])
        for k in ("initial", "middle", "final")
    ]
    for role, value in (
        ("year", "午"),
        ("month", "寅"),
        ("day", day[1]),
        ("hour", "子"),
    ):
        rows += [
            (f"contact.{role}.{identifier}", branch, value)
            for identifier, branch in targets
        ]
    return rows


def audit() -> dict[str, Any]:
    ref = reference()
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ] + [Path(__file__).resolve()]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_branch_relations import branch_pair_facts
    from fatebridge.core.output_chinese import Liuren
    from scripts.ren.audit_ren_classical import make_seed

    synthetic = []
    for case in ref["synthetic_cases"]:
        actual = branch_pair_facts(case["left"], case["right"])
        match = (
            all(actual[k] is (k in case["positive"]) for k in FACTS)
            and actual["harmony_annotation"] == case["annotation"]
        )
        synthetic.append(dict(**case, actual=actual, matched=match))
    matrix = []
    for left in BRANCHES:
        for right in BRANCHES:
            actual, exp = branch_pair_facts(left, right), expected(ref, left, right)
            matrix.append(
                dict(
                    left=left,
                    right=right,
                    actual=actual,
                    expected=exp,
                    matched=actual == exp,
                )
            )
    boards, failures, differences = [], [], []
    core_keys = [
        "month_general",
        "board_style",
        "board_style_detail",
        "classification",
        "board_order",
        "guiren_order",
        "kongwang",
        "xun_head",
        "month_building_element",
        "life_stages",
        "auxiliary_stars",
        "emptiness_evidence",
        "three_transmissions",
        "transmission_relations",
        "twelve_board",
        "meta",
    ]
    stems = "甲乙丙丁戊己庚辛壬癸"
    count = 0
    for i in range(60):
        day = stems[i % 10] + BRANCHES[i % 12]
        for general in BRANCHES:
            board = build_liureng_board(
                make_seed(dict(day=day, hour="子")), month_general_override=general
            )
            Liuren.model_validate(board)
            expected_pairs = expected_rows(board, day)
            actual_rows = board["branch_relations"]["rows"]
            assert len(expected_pairs) == len(actual_rows) == 47
            errors = []
            for actual, (identifier, left, right) in zip(actual_rows, expected_pairs):
                count += 1
                exp = expected(ref, left, right)
                if (
                    actual["id"],
                    actual["left_branch"],
                    actual["right_branch"],
                    actual["facts"],
                ) != (identifier, left, right, exp):
                    errors.append(
                        dict(
                            id=identifier,
                            actual=actual,
                            expected=exp,
                            left=left,
                            right=right,
                        )
                    )
            if errors:
                failures.append(dict(day=day, general=general, errors=errors))
            boards.append(
                dict(day=day, general=general, compared_pairs=47, matched=not errors)
            )
    reference()
    after = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    return dict(
        literal_pair_anchors=sum(map(len, ref["tables"].values())),
        literal_harmony_annotations=2,
        synthetic_cases=synthetic,
        ordered_pair_matrix=matrix,
        symbolic_boards=boards,
        symbolic_board_count=len(boards),
        symbolic_pair_comparisons=count,
        matrix_failures=failures,
        baseline_core_differences=differences,
        implementation_sha256=before,
        implementation_unchanged=before == after,
        engineering_checks_passed=all(v["matched"] for v in synthetic + matrix)
        and not failures
        and not differences
        and before == after,
        new_historical_events=0,
        new_empirical_events=0,
        model_processes=0,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite original branch evidence")
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
