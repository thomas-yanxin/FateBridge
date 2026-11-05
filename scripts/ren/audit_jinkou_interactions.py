"""Check frozen ordered clauses without counting expansions as古例."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations, product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_interactions_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_interactions.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/jinkou_strength.py",
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_jinkou_interactions.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/ren/audit_jinkou_interactions.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(freeze["files"]) | {"freeze.json"}:
        raise ValueError("Frozen interaction inventory changed")
    for name, value in freeze["files"].items():
        if sha(corpus / name) != value:
            raise ValueError(f"Frozen interaction source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    return result


def symbolic_rows(ref: dict[str, Any], elements: list[str]) -> list[dict[str, Any]]:
    return [dict(label=p, element=e) for p, e in zip(ref["positions"], elements)]


def expected_condition(ref: dict[str, Any], a: str, b: str, relation: str) -> bool:
    if relation == "比和":
        return a == b
    edges = ref["phase_generations" if relation == "生" else "phase_controls"]
    return [a, b] in edges


def expected_rule(
    ref: dict[str, Any], rule: dict[str, Any], elements: list[str]
) -> bool:
    at = dict(zip(ref["positions"], elements))
    values = [
        expected_condition(ref, at[c["source"]], at[c["target"]], c["relation"])
        for c in rule["conditions"]
    ]
    return any(values) if rule["quantifier"] == "any" else all(values)


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_interactions import position_interactions

    original = position_interactions(symbolic_rows(ref, list("木火土金")))
    at_id = {r["id"]: r for r in original["rule_evaluations"]}
    definitions = []
    for expected in ref["rules"]:
        row = at_id.get(expected["id"])
        actual = (
            None
            if row is None
            else dict(
                id=row["id"],
                name=row["name"],
                quantifier=row["quantifier"],
                conditions=[
                    dict(
                        source=c["source_position"],
                        target=c["target_position"],
                        relation=c["relation"],
                    )
                    for c in row["condition_checks"]
                ],
                original_pdf_pages=row["original_pdf_pages"],
            )
        )
        definitions.append(
            dict(
                id=expected["id"],
                expected=expected,
                actual=actual,
                matched=actual == expected,
            )
        )
    probes = []
    for probe in ref["probes"]:
        actual = position_interactions(symbolic_rows(ref, probe["elements"]))
        row = next(
            (r for r in actual["rule_evaluations"] if r["id"] == probe["rule_id"]), None
        )
        observed = row["matched"] if row is not None else None
        probes.append(
            dict(**probe, actual=observed, matched=observed is probe["expected"])
        )
    failures: list[dict[str, Any]] = []
    rule_matches = pair_matches = combinations_count = 0
    rule_checks = pair_checks = 0
    for phase_tuple in product("木火土金水", repeat=4):
        elements = list(phase_tuple)
        combinations_count += 1
        result = position_interactions(symbolic_rows(ref, elements))
        evaluated = {r["id"]: r for r in result["rule_evaluations"]}
        pairs = {(p["upper_position"], p["lower_position"]): p for p in result["pairs"]}
        if len(result["rule_evaluations"]) != 14 or set(evaluated) != {
            r["id"] for r in ref["rules"]
        }:
            failures.append(
                dict(elements=elements, reason="source rule inventory changed")
            )
        if len(result["pairs"]) != 6 or set(pairs) != set(
            combinations(ref["positions"], 2)
        ):
            failures.append(dict(elements=elements, reason="pair inventory changed"))
        for rule in ref["rules"]:
            rule_checks += 1
            expected = expected_rule(ref, rule, elements)
            row = evaluated.get(rule["id"])
            matched = row is not None and row["matched"] is expected
            rule_matches += matched
            if not matched:
                failures.append(
                    dict(
                        elements=elements,
                        rule_id=rule["id"],
                        expected=expected,
                        actual=row,
                    )
                )
        for i, j in combinations(range(4), 2):
            pair_checks += 1
            a, b = elements[i], elements[j]
            relation = (
                "比和"
                if a == b
                else (
                    "上生下"
                    if [a, b] in ref["phase_generations"]
                    else (
                        "下生上"
                        if [b, a] in ref["phase_generations"]
                        else "上克下" if [a, b] in ref["phase_controls"] else "下克上"
                    )
                )
            )
            expected_pair = dict(
                upper_position=ref["positions"][i],
                lower_position=ref["positions"][j],
                upper_element=a,
                lower_element=b,
                adjacent=j - i == 1,
                relation=relation,
            )
            row = pairs.get((ref["positions"][i], ref["positions"][j]))
            matched = row == expected_pair
            pair_matches += matched
            if not matched:
                failures.append(
                    dict(elements=elements, expected_pair=expected_pair, actual=row)
                )
        expected_ids = [
            r["id"] for r in ref["rules"] if expected_rule(ref, r, elements)
        ]
        has_control = any(
            [a, b] in ref["phase_controls"] for a in elements for b in elements
        )
        if (
            result["matched_rule_ids"] != expected_ids
            or result["has_any_control"] is not has_control
        ):
            failures.append(
                dict(elements=elements, reason="summary differs from full facts")
            )
        if result["complete_classical_conformance"] is not False:
            failures.append(dict(elements=elements, reason="overclaimed conformance"))
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    return dict(
        audit_id="jinkou_interactions_v1",
        source_clause_count=14,
        definition_checks=definitions,
        definition_matches=sum(r["matched"] for r in definitions),
        synthetic_clause_probes=probes,
        synthetic_probe_matches=sum(r["matched"] for r in probes),
        synthetic_combinations=combinations_count,
        derived_rule_checks=rule_checks,
        derived_rule_matches=rule_matches,
        derived_pair_checks=pair_checks,
        derived_pair_matches=pair_matches,
        failures=failures,
        source_sha256=ref["source_sha256"],
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_clause_checks_passed=unchanged
        and not failures
        and len(definitions) == 14
        and len(probes) == 30
        and combinations_count == 625
        and rule_checks == rule_matches == 8750
        and pair_checks == pair_matches == 3750
        and all(r["matched"] for r in definitions + probes),
        classical_acceptance_passed=False,
        goal_complete=False,
        new_historical_examples=0,
        new_real_world_outcomes=0,
        model_invocations=0,
        unresolved_research=ref["unresolved_research"],
        limits=ref["limits"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "definition_matches",
                    "synthetic_probe_matches",
                    "derived_rule_matches",
                    "derived_pair_matches",
                    "selected_clause_checks_passed",
                )
            }
        )
    )
    return 0 if result["selected_clause_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
