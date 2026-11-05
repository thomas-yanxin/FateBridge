"""Replay all day-placement conditions and unchanged symbolic contexts."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_day_placements_v1"
PIN = "7d28a07e226ba07877428cc7e1574fae3f1a128268087142614f5617d942694d"
SOURCE_SHA = "e8e6e0d5ce10c5d5d68282e5fd38a0b0317a8863c381e341b4a926575e86a59d"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen day-placement identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Frozen day-placement inventory changed")
    if any(sha(folder / n) != h for n, h in files.items()):
        raise ValueError("Frozen day-placement content changed")
    if (
        sha(ROOT / "tests/fixtures/liuren_course_conditions_v1/source.pdf")
        != SOURCE_SHA
    ):
        raise ValueError("Original primary book changed")
    from tests.support.ren_source_arithmetic import day_placements

    if day_placements(folder) != json.loads((folder / "reference.json").read_text()):
        raise ValueError("Independent source arithmetic differs")
    data: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    data["reading"] = json.loads((folder / "readings.json").read_text())
    return data


def expected_facts(case: dict[str, Any], reading: dict[str, Any]) -> dict[str, Any]:
    return dict(
        day_ganzhi=case["day_ganzhi"],
        day_stem_house="寅辰巳未巳未申戌亥丑"[STEMS.index(case["day_ganzhi"][0])],
        day_stem_element="木火土金水"[STEMS.index(case["day_ganzhi"][0]) // 2],
        day_branch_element="水土木木土火火土金金土水"[
            BRANCHES.index(case["day_ganzhi"][1])
        ],
        sky_by_earth=case["sky_by_earth"],
        placements=case["placements"],
        element_relations=case["element_relations"],
        evaluations=[
            {
                **{
                    k: c[k]
                    for k in (
                        "id",
                        "name",
                        "condition",
                        "placement",
                        "relation",
                        "definition_adjudicated",
                    )
                },
                "placement_matches": case["placements"][c["placement"]],
                "relation_matches": (
                    case["element_relations"][c["relation"]]
                    if c["definition_adjudicated"]
                    else None
                ),
                "matched": row["matched"],
            }
            for c, row in zip(reading["clauses"], case["evaluations"], strict=True)
        ],
        matched_ids=case["matched_ids"],
        unresolved_ids=["D11", "D12"],
        evaluated_count=10,
        unresolved_count=2,
        source_sha256=SOURCE_SHA,
        source_url=reading["source_url"],
        original_pdf_pages=[77, 78, 110],
        complete_classical_conformance=False,
        comprehensive_judgement=None,
    )


def audit() -> dict[str, Any]:
    data = reference()  # Reconstruct independent literals before production import.
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_day_placements import (
        day_placement_patterns,
        day_placements_trace,
    )
    from fatebridge.core.output_liuren_day_placements import LiurenDayPlacements
    from scripts.ren.audit_ren_classical import make_seed

    paths = [
        p
        for p in (ROOT / "src").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"
    ] + [Path(__file__)]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    literals, boards, failures = [], [], []
    canonical = lambda v: json.dumps(
        v, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    for case in data["contexts"]:
        expected = expected_facts(case, data["reading"])
        actual = day_placement_patterns(case["day_ganzhi"], case["sky_by_earth"])
        LiurenDayPlacements.model_validate(actual)
        observed = {k: actual[k] for k in expected}
        ok = canonical(expected) == canonical(observed)
        row = dict(
            day_ganzhi=case["day_ganzhi"],
            rotation=case["rotation"],
            expected=expected,
            actual=observed,
            passed=ok,
        )
        literals.append(row)
        if not ok:
            failures.append(dict(kind="literal", **row))
        for profile in ("liuren_common_v1", "tanyuan_xieji_v1"):
            for diurnal in (True, False):
                board = build_liureng_board(
                    make_seed(dict(day=case["day_ganzhi"], hour="子")),
                    month_general_override=BRANCHES[case["rotation"]],
                    is_diurnal_override=diurnal,
                    guiren_profile=profile,
                )
                evidence = board["day_placement_patterns"]
                traces = [
                    t
                    for t in board["rule_trace"]
                    if t["rule_id"] == "liuren.day_placement_patterns"
                ]
                ok = canonical({k: evidence[k] for k in expected}) == canonical(
                    expected
                ) and canonical(traces) == canonical([day_placements_trace(evidence)])
                row = dict(
                    day_ganzhi=case["day_ganzhi"],
                    rotation=case["rotation"],
                    guiren_profile=profile,
                    is_diurnal=diurnal,
                    actual_evaluations=evidence["evaluations"],
                    actual_matched_ids=evidence["matched_ids"],
                    unresolved_ids=evidence["unresolved_ids"],
                    passed=ok,
                )
                boards.append(row)
                if not ok:
                    failures.append(dict(kind="board", **row))
    stable = before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    return dict(
        source_pin=PIN,
        implementation_sha256=before,
        implementation_unchanged=stable,
        literal_contexts=len(literals),
        literal_rows=literals,
        symbolic_contexts=len(boards),
        symbolic_rows=boards,
        failures=failures,
        engineering_checks_passed=stable
        and len(literals) == 720
        and len(boards) == 2880
        and not failures,
        adjudicated_definition_count=10,
        unresolved_definition_count=2,
        unresolved_ids=["D11", "D12"],
        new_historical_events=0,
        new_empirical_events=0,
        full_classical_conformance=False,
        original_gates_reclassified=False,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"literal_rows", "symbolic_rows", "implementation_sha256"}
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
