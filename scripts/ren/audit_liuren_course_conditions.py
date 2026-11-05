"""Replay frozen literal conditions without converting combinations to cases."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_course_conditions_v1"
FREEZE_SHA256 = "abd4c7e829539509eb3b700b6b627d89dd7fa5bba4beec47e26cb0e6d79b691e"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path: Path = CORPUS) -> dict[str, Any]:
    if sha(path / "freeze.json") != FREEZE_SHA256:
        raise ValueError("Frozen course source manifest changed")
    frozen = json.loads((path / "freeze.json").read_text())["files"]
    if set(frozen) != {
        "source.pdf",
        "readings.json",
        "life-reference.json",
        "chapter-catalog.json",
        "protocol.json",
    }:
        raise ValueError("Frozen course source inventory changed")
    if {p.name for p in path.iterdir()} != set(frozen) | {"freeze.json"}:
        raise ValueError("Frozen course source inventory has missing or extra files")
    for name, digest in frozen.items():
        if sha(path / name) != digest:
            raise ValueError("Frozen course source bytes changed: " + name)
    return dict(
        readings=json.loads((path / "readings.json").read_text()),
        life=json.loads((path / "life-reference.json").read_text()),
        catalog=json.loads((path / "chapter-catalog.json").read_text()),
        protocol=json.loads((path / "protocol.json").read_text()),
    )


def transmissions(branches: list[str], god: str, seat: str) -> dict[str, Any]:
    return {
        p: dict(branch=b, god=god, earth_branch=seat)
        for p, b in zip(("initial", "middle", "final"), branches)
    }


def audit() -> dict[str, Any]:
    from fatebridge.core.metaphysics.liureng_course_conditions import course_conditions

    ref = reference()
    clauses = ref["readings"]["selected_clauses"]
    stage_clauses = [c for c in clauses if c["id"].startswith("S")]
    god_clauses = [c for c in clauses if c["id"].startswith("G")]
    gods = [c["required_god"] for c in god_clauses]
    stages = [c["required_stage"] for c in stage_clauses]
    anchors = {r["stem"]: r for r in ref["life"]["anchors"]}
    counts = {c["id"]: 0 for c in clauses}
    failures = []
    rows = []
    implementation = (
        ROOT / "src/fatebridge/core/metaphysics/liureng_course_conditions.py"
    )
    before = sha(implementation)
    for n, branch, god in itertools.product(range(60), BRANCHES, gods):
        day = STEMS[n % 10] + BRANCHES[n % 12]
        anchor = anchors[day[0]]
        direction = 1 if anchor["direction"] == "顺" else -1
        stage = stages[
            (
                (BRANCHES.index(branch) - BRANCHES.index(anchor["changsheng"]))
                * direction
            )
            % 12
        ]
        actual = course_conditions(day, transmissions([branch, "寅", "卯"], god, "子"))
        expected_ids = [
            c["id"]
            for c in stage_clauses
            if c["required_stage"] == stage and c["required_god"] == god
        ]
        expected_ids += [c["id"] for c in god_clauses if c["required_god"] == god]
        got = [i for i in actual["matched_ids"] if i.startswith(("S", "G"))]
        ok = expected_ids == got and actual["initial_stage"] == stage
        row = dict(
            day=day,
            initial_branch=branch,
            god=god,
            stage=stage,
            expected_ids=expected_ids,
            actual=got,
            passed=ok,
        )
        rows.append(row)
        if not ok:
            failures.append(row)
        for i in got:
            counts[i] += 1
    structural = []
    # Literal B01: both 辰/戌 AND sitting on the day stem house/day branch.
    houses = dict(zip(STEMS, "寅辰巳未巳未申戌亥丑"))
    for n, first, seat in itertools.product(range(60), BRANCHES, BRANCHES):
        day = STEMS[n % 10] + BRANCHES[n % 12]
        got = course_conditions(day, transmissions([first, "寅", "卯"], "贵人", seat))[
            "structural_patterns"
        ][0]["matched"]
        expected = first in "辰戌" and seat in {houses[day[0]], day[1]}
        row = dict(
            id="B01",
            day=day,
            first=first,
            seat=seat,
            expected=expected,
            actual=got,
            passed=expected == got,
        )
        structural.append(row)
        counts["B01"] += got
        if expected != got:
            failures.append(row)
    for triple in itertools.product(BRANCHES, repeat=3):
        got = course_conditions("甲子", transmissions(list(triple), "贵人", "子"))[
            "structural_patterns"
        ][1]["matched"]
        expected = list(triple) == clauses[-2]["required_branches"]
        row = dict(
            id="B02",
            branches=list(triple),
            expected=expected,
            actual=got,
            passed=expected == got,
        )
        structural.append(row)
        counts["B02"] += got
        if expected != got:
            failures.append(row)
    # Independent sexagenary positions: ten days per xun, last = first+9.
    for n, first, final in itertools.product(range(60), BRANCHES, BRANCHES):
        day = STEMS[n % 10] + BRANCHES[n % 12]
        got = course_conditions(day, transmissions([first, "寅", final], "贵人", "子"))[
            "structural_patterns"
        ][2]["matched"]
        expected = (
            first == BRANCHES[(n // 10 * 10) % 12]
            and final == BRANCHES[(n // 10 * 10 + 9) % 12]
        )
        row = dict(
            id="B03",
            day=day,
            first=first,
            final=final,
            expected=expected,
            actual=got,
            passed=expected == got,
        )
        structural.append(row)
        counts["B03"] += got
        if expected != got:
            failures.append(row)
    return dict(
        source_reference_sha256=FREEZE_SHA256,
        selected_literal_clauses=len(clauses),
        mathematical_stage_god_contexts=len(rows),
        structural_contexts=len(structural),
        match_counts=counts,
        failures=failures,
        stage_god_rows=rows,
        structural_rows=structural,
        implementation_unchanged=before == sha(implementation),
        engineering_checks_passed=not failures and before == sha(implementation),
        manual_source_review="single assistant; nonblind; no independent expert review",
        new_historical_events=0,
        new_empirical_events=0,
        full_classical_conformance=False,
        goal_complete=False,
        reality_validation="deferred_by_user",
    )
