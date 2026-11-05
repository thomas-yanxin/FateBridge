"""Collate P63/P64 by typed four-position roles, retaining the full old corpus."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_gate_roles_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "scripts/ren/audit_jinkou_patterns.py",
    "scripts/ren/audit_jinkou_gate_roles.py",
)
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
PHASES = dict(zip(BRANCHES, "水土木木土火火土金金土水"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen gate-role inventory changed")
    for name, digest in manifest["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError(f"Frozen gate-role source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    return result


def prior_auditor() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gate_prior", ROOT / "scripts/ren/audit_jinkou_patterns.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_rows(god: str, general: str, ground: str) -> list[dict[str, Any]]:
    # Role permutations, deliberately not asserted to be attainable civil charts.
    return [
        dict(
            label=label,
            content=value,
            element="土" if i == 0 else PHASES[value],
            dun_stem=None,
            xun_kong=False,
            si_da_kong=False,
        )
        for i, (label, value) in enumerate(
            zip(("人元", "贵神", "将神", "地分"), ("戊", god, general, ground))
        )
    ]


def audit() -> dict[str, Any]:
    ref = reference()
    before = {n: sha(ROOT / n) for n in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns

    old = prior_auditor()
    complete = old.audit()
    literal = []
    for case in ref["literal_cases"]:
        observed = next(r for r in complete["semantic_checks"] if r["id"] == case["id"])
        if observed["literal_positions"] != case["positions"]:
            raise ValueError("Original four-position labels changed")
        literal.append(
            dict(
                id=case["id"],
                expected=case["matched"],
                actual=observed["matched"],
                matched=observed["matched"] is case["matched"],
            )
        )
    rules = ref["synthetic_rule"]
    failures = []
    matches = {"P63": 0, "P64": 0}
    prior_false_positive = prior_false_negative = 0
    for god, general, ground in itertools.product(BRANCHES, repeat=3):
        roles = dict(贵神=god, 将神=general)
        result = structural_patterns(
            synthetic_rows(god, general, ground), day_ganzhi="乙卯"
        )
        actual = {r["id"]: r["matched"] for r in result["evaluations"]}
        for key, rule in rules.items():
            expected = (
                roles[rule["position"]] == rule["branch"] and ground == rule["ground"]
            )
            matches[key] += actual[key] is True
            if actual[key] is not expected:
                failures.append(
                    dict(
                        id=key,
                        god=god,
                        general=general,
                        ground=ground,
                        expected=expected,
                        actual=actual[key],
                    )
                )
        prior = ground == "辰" and god == "戌"
        expected = (
            roles[rules["P64"]["position"]] == rules["P64"]["branch"]
            and ground == rules["P64"]["ground"]
        )
        prior_false_positive += prior and not expected
        prior_false_negative += expected and not prior
    stable = before == {n: sha(ROOT / n) for n in IMPLEMENTATION}
    return dict(
        audit_id="jinkou_gate_roles_v1",
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=stable,
        literal_structure_checks=literal,
        literal_structure_count=2,
        synthetic_role_tuple_count=12**3,
        synthetic_predicate_comparison_count=2 * 12**3,
        synthetic_matches=matches,
        synthetic_failures=failures,
        old_p64_formula_synthetic_false_positives=prior_false_positive,
        old_p64_formula_synthetic_false_negatives=prior_false_negative,
        synthetic_scope="Derived role permutations, not independent source examples or necessarily attainable charts.",
        prior_64_case_comparison=complete,
        selected_role_checks_passed=stable
        and not failures
        and all(r["matched"] for r in literal),
        classical_acceptance_passed=False,
        full_supported_calendar_domain_certified=False,
        free_text_semantic_acceptance_passed=False,
        goal_complete=False,
        model_invocations=0,
        limits=ref["limits"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "literal_structure_count",
                    "synthetic_role_tuple_count",
                    "selected_role_checks_passed",
                    "goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["selected_role_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
