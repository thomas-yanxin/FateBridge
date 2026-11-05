"""Frozen named-pair rules, distinct from historical or empirical events."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_natal_v1"
FROZEN_SHA256 = "17ee6f38accc324fed406915a381b5d9bc6f9ae4b6b7ab810def37f836ec4e02"
WATCH = (
    "src/fatebridge/core/metaphysics/jinkou_relations.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_jinkou_natal.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/core/requests/metaphysics.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/services/catalog/metaphysics.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/ren/audit_jinkou_natal.py",
    "pyproject.toml",
    "uv.lock",
)


def hashes() -> dict[str, str]:
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in WATCH}


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FROZEN_SHA256
    ):
        raise ValueError("Frozen natal manifest changed")
    f = json.loads((corpus / "freeze.json").read_text())
    names = {"reference.json", "source-page.pdf"}
    if set(f["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen natal source inventory changed")
    for name in names:
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != f["files"][name]:
            raise ValueError("Frozen natal source changed")
    r: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if len(r["pairs"]) != 4 or len(r["cases"]) != 9 or r["new_historical_events"] != 0:
        raise ValueError("Predeclared natal source coverage changed")
    return r


def audit() -> dict[str, Any]:
    r = reference()
    before = hashes()
    from fatebridge.core.metaphysics.jinkou_relations import natal_absolute

    # Expected phases come only from the independently frozen named pair table.
    expected = {frozenset(p["branches"]): p["element"] for p in r["pairs"]}
    matrix = []
    for general in "子丑寅卯辰巳午未申酉戌亥":
        for natal in "子丑寅卯辰巳午未申酉戌亥":
            phase = expected.get(frozenset((general, natal)))
            v = natal_absolute(general, natal)
            matrix.append(
                {
                    "general": general,
                    "natal": natal,
                    "expected_match": phase is not None,
                    "expected_element": phase,
                    "matched": v["matched"] is (phase is not None)
                    and v["element"] == phase,
                }
            )
    contexts = []
    for c in r["cases"]:
        v = natal_absolute(c["general"], c["natal"])
        contexts.append(
            dict(
                c, correct=v["matched"] is c["matched"] and v["element"] == c["element"]
            )
        )
    unknowns = [natal_absolute(b, None) for b in "子丑寅卯辰巳午未申酉戌亥"]
    missing_ok = all(
        v["matched"] is None
        and v["element"] is None
        and v["right_branch"] is None
        and v["status"] == "missing_birth_branch"
        and v["input_source"] == "not_provided"
        for v in unknowns
    )
    reference()
    after = hashes()
    return {
        "implementation_sha256": after,
        "implementation_unchanged": before == after,
        "reference_sha256": hashlib.sha256(
            (CORPUS / "freeze.json").read_bytes()
        ).hexdigest(),
        "synthetic_matrix_count": len(matrix),
        "synthetic_positive_count": sum(v["expected_match"] for v in matrix),
        "synthetic_matrix": matrix,
        "predeclared_symbolic_contexts": contexts,
        "missing_natal_contexts": len(unknowns),
        "missing_natal_preserved_unknown": missing_ok,
        "selected_rule_checks_passed": all(v["matched"] for v in matrix)
        and all(v["correct"] for v in contexts)
        and missing_ok
        and before == after,
        "new_historical_events": 0,
        "new_empirical_outcomes": 0,
        "model_invocations": 0,
        "full_classical_conformance": False,
        "goal_complete": False,
        "scope": "One missing input path completed for the selected Jingben 将命 named-pair rule; not a complete book, calendar, free-text or empirical acceptance.",
    }
