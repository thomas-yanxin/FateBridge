"""Audit bounded textual corroboration against frozen pages and prior full outputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
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


def legacy(before_dir: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.services.tool_catalog import CATALOG
    from scripts.audit_ren_classical import make_seed
    from scripts.jinkou_break_witnesses_archive import without_break_witnesses

    if sha(before_dir / "before-capture-receipt.json") != BEFORE_PIN:
        raise ValueError("Before-witness capture identity changed")
    receipt = json.loads((before_dir / "before-capture-receipt.json").read_text())
    for name, digest in receipt["files"].items():
        if sha(before_dir / name) != digest:
            raise ValueError("Before-witness captured bytes changed")
    failures, count = [], 0
    with gzip.open(before_dir / "before-boards.jsonl.gz", "rt") as stream:
        for line in stream:
            record = json.loads(line)
            case = record["input"]
            actual = build_jinkou_board(
                make_seed(case),
                {"month_general": {"branch": case["general"]}},
                di_fen=case["ground"],
                is_diurnal_override=True,
            )
            if without_break_witnesses(actual, evidence) != record["board"]:
                failures.append(dict(kind="symbolic", input=case))
            count += 1
    spec = next(s for s in CATALOG if s.key == "jinkou")
    businesses = json.loads((before_dir / "before-business.json").read_text())
    for case in businesses:
        fn, args, kwargs = spec.bind(spec.request_model.model_validate(case["input"]))
        if without_break_witnesses(fn(*args, **kwargs), evidence) != case["body"]:
            failures.append(dict(kind="full_business", input=case["input"]))
    return dict(
        baseline_pin=BEFORE_PIN,
        symbolic_count=count,
        full_business_count=len(businesses),
        failures=failures,
        passed=count == 720 and len(businesses) == 3 and not failures,
        inverse_scope="only witness_evidence on the course block and its unique trace; no version, text or calculation normalization",
    )


def audit(before_dir: Path | None = None) -> dict[str, Any]:
    evidence = reference()
    from scripts.audit_jinkou_branch_breaks import reference as seven_pair_reference

    seven = seven_pair_reference()
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "src/fatebridge/data/jinkou_break_pair_witnesses.json",
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__),
        ROOT / "scripts/jinkou_break_witnesses_archive.py",
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
    old = legacy(before_dir, evidence) if before_dir else dict(status="not_assessed")
    if before != {str(p.relative_to(ROOT)): sha(p) for p in paths}:
        raise ValueError("Source changed during textual-witness audit")
    return dict(
        reference_pin=PIN,
        independent_evidence=evidence,
        matrix_count=144,
        matrix_failures=matrix_failures,
        triple_count=len(seven["reference"]["contexts"]),
        failures=failures,
        legacy=old,
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
    parser.add_argument("--before-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    options = parser.parse_args()
    result = audit(options.before_dir)
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
