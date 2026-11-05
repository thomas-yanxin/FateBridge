"""Audit bounded textual corroboration against frozen pages and prior full outputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_break_witnesses_v1"
PIN = "0ecb5f46f2269ea6d887d8a18385965e10babd275963a562957c927f8f54215c"
BEFORE_PIN = "dd2ff8544f27f0ad4a2fc7f726ba638ff31a3b642ab6bc2fbef6010e7df82f42"
PDFS = [
    ROOT / "tests/fixtures/jinkou_waseda_strength_v1/source.pdf",
    ROOT / "tests/fixtures/jinkou_cnts_47977020_v1/source.pdf",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != PIN:
        raise ValueError("Frozen textual-witness identity changed")
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen textual-witness inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError("Frozen textual-witness bytes changed: " + name)
    evidence = json.loads((corpus / "evidence.json").read_text())
    for path, witness in zip(PDFS, evidence["witnesses"]):
        if (
            sha(path) != witness["source_sha256"]
            or path.stat().st_size != witness["source_bytes"]
        ):
            raise ValueError("Original witness PDF identity changed")
    return evidence


def audit() -> dict[str, Any]:
    evidence = reference()
    from scripts.ren.audit_jinkou_branch_breaks import reference as seven_pair_reference

    seven = seven_pair_reference()
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "src/fatebridge/data/jinkou_break_pair_witnesses.json",
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.metaphysics.jinkou_branch_breaks import (
        branch_breaks,
        pair_facts,
    )

    matrix_failures = []
    for expected in seven["reference"]["pair_matrix"]:
        actual = pair_facts(expected["left_branch"], expected["right_branch"])
        if actual != expected:
            matrix_failures.append(dict(expected=expected, actual=actual))
    failures = []
    for case in seven["reference"]["contexts"]:
        actual = branch_breaks(*case["branches"])
        if actual.get("witness_evidence") != evidence or actual["rows"] != case["rows"]:
            failures.append(dict(expected=case, actual=actual))
    if before != {str(p.relative_to(ROOT)): sha(p) for p in paths}:
        raise ValueError("Source changed during textual-witness audit")
    return dict(
        reference_pin=PIN,
        independent_evidence=evidence,
        matrix_count=144,
        matrix_failures=matrix_failures,
        triple_count=len(seven["reference"]["contexts"]),
        failures=failures,
        bounded_textual_evidence_passed=not matrix_failures and not failures,
        implementation_sha256=before,
        implementation_unchanged=True,
        author_intent_adjudicated=False,
        independent_transmission_established=False,
        classical_acceptance_passed=False,
        new_model_processes=0,
        new_independent_real_events=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    options = parser.parse_args()
    result = audit()
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if options.output:
        with options.output.open("x") as stream:
            stream.write(content)
    else:
        print(content, end="")
    passed = result["bounded_textual_evidence_passed"] and result["legacy"].get(
        "passed", True
    )
    return 0 if passed and not options.require_full_conformance else 1


if __name__ == "__main__":
    raise SystemExit(main())
