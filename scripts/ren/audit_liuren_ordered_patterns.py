"""Keep three literal source anchors apart from mathematical expansions."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_ordered_patterns_v1"
FREEZE_SHA256 = "3aec2c837246e7b76944af2b34aa1a1ae3bd75e62842dba44653d78eae1c7903"
WATCH = (
    "src/fatebridge/core/metaphysics/liureng_ordered_patterns.py",
    "src/fatebridge/core/output_liuren_ordered_patterns.py",
    "src/fatebridge/core/metaphysics/liureng_transmission_relations.py",
    "src/fatebridge/core/output_liuren_transmission_relations.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_liuren_ordered_patterns.py",
    "uv.lock",
    "pyproject.toml",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != FREEZE_SHA256:
        raise ValueError("Frozen ordered-pattern reference manifest changed")
    frozen = json.loads((corpus / "freeze.json").read_text())
    names = {"readings.json", "protocol.json", "source-pages.pdf"}
    if set(frozen["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen ordered-pattern inventory changed")
    if any(sha(corpus / n) != frozen["files"][n] for n in names):
        raise ValueError("Frozen ordered-pattern source or readings changed")
    readings: dict[str, Any] = json.loads((corpus / "readings.json").read_text())
    return readings


def audit() -> dict[str, Any]:
    readings = reference()
    before = {p: sha(ROOT / p) for p in WATCH}
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_ordered_patterns import (
        ordered_transmission_patterns,
    )
    from scripts.ren.audit_ren_classical import make_seed

    alphabet = "子丑寅卯辰巳午未申酉戌亥"
    clauses = readings["clauses"]

    def expected(branches: list[str]) -> list[str]:
        return [r["id"] for r in clauses if branches == r["branches"]]

    literal = []
    for clause in clauses:
        value = ordered_transmission_patterns(clause["branches"])
        literal.append(
            dict(
                id=clause["id"],
                actual=value["matched_ids"],
                matched=value["matched_ids"] == [clause["id"]],
            )
        )
    failures = []
    counts: dict[str, int] = {r["id"]: 0 for r in clauses}
    counts["none"] = 0
    rows = []
    for triple in itertools.product(alphabet, repeat=3):
        branches = list(triple)
        wanted = expected(branches)
        value = ordered_transmission_patterns(branches)
        correct = value["matched_ids"] == wanted and [
            r["matched"] for r in value["evaluations"]
        ] == [branches == r["branches"] for r in clauses]
        row = dict(
            branches=branches,
            expected=wanted,
            actual=value["matched_ids"],
            matched=correct,
        )
        rows.append(row)
        counts[wanted[0] if wanted else "none"] += 1
        if not correct:
            failures.append(row)
    boards = []
    for n in range(60):
        day = "甲乙丙丁戊己庚辛壬癸"[n % 10] + alphabet[n % 12]
        for offset, general in enumerate(alphabet):
            board = build_liureng_board(
                make_seed(dict(day=day, hour="子")), month_general_override=general
            )
            branches = [
                board["three_transmissions"][p]["branch"]
                for p in ("initial", "middle", "final")
            ]
            value = board["transmission_relations"]["named_structures"]
            row = dict(
                day=day,
                offset=offset,
                branches=branches,
                actual=value["matched_ids"],
                expected=expected(branches),
            )
            row["matched"] = (
                row["actual"] == row["expected"] and value["branches"] == branches
            )
            boards.append(row)
            if not row["matched"]:
                failures.append(row)
    after = {p: sha(ROOT / p) for p in WATCH}
    reference()
    return dict(
        reference_sha256=FREEZE_SHA256,
        implementation_sha256=after,
        implementation_unchanged=before == after,
        literal_anchors=literal,
        mathematical_cases=len(rows),
        mathematical_counts=counts,
        mathematical_rows=rows,
        symbolic_board_count=len(boards),
        symbolic_boards=boards,
        failures=failures,
        engineering_checks_passed=not failures
        and all(r["matched"] for r in literal)
        and before == after,
        blind_reference=False,
        independent_expert_review=False,
        new_historical_events=0,
        new_empirical_events=0,
        original_legacy_gates_unchanged=True,
        full_classical_conformance=False,
        goal_complete=False,
    )
