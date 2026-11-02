"""Compare Jingben trine clauses without treating membership as transformation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_combinations_v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_combinations.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/export_contracts.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/audit_jinkou_combinations.py",
    "scripts/audit_jinkou_patterns.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    frozen = json.loads((corpus / "freeze.json").read_text())
    expected = {"reference.json", "source-pages.pdf"}
    if set(frozen["files"]) != expected or {
        p.name for p in corpus.iterdir()
    } != expected | {"freeze.json"}:
        raise ValueError("Frozen combinations inventory changed")
    for name, checksum in frozen["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Frozen combinations reference changed: {name}")
    ref = json.loads((corpus / "reference.json").read_text())
    for name, checksum in ref["references"].items():
        if sha(ROOT / name) != checksum:
            raise ValueError(f"Referenced original corpus changed: {name}")
    return ref


def symbolic_rows(stem: str, branches: list[str]) -> list[dict[str, Any]]:
    # Isolated membership/phase clauses, not generated or historical charts.
    return [
        dict(
            label=label, content=value, dun_stem=None, xun_kong=False, si_da_kong=False
        )
        for label, value in zip(("人元", "贵神", "将神", "地分"), [stem, *branches])
    ]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit() -> dict[str, Any]:
    ref = reference()
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_combinations import trine_evidence

    clauses = []
    for trine in ref["trines"]:
        for example in trine["stem_examples"]:
            result = trine_evidence(
                symbolic_rows(example["stem"], trine["branches"]),
                day_branch="子",
                month_branch="寅",
            )
            row = next(r for r in result["trines"] if r["name"] == trine["name"])
            clauses.append(
                dict(
                    source_page=trine["pdf_page"],
                    name=trine["name"],
                    human_stem=example["stem"],
                    expected_relation=example["relation"],
                    actual_relation=row["human_stem_relation"],
                    matched=(
                        row["human_stem_relation"] == example["relation"]
                        and row["structural_status"]
                        == "branches_complete_requires_adjudication"
                        and row["transformation_confirmed"] is None
                        and row["source_listed_disruptors"]
                        == trine["listed_disruptors"]
                    ),
                )
            )
    waiting = []
    for example in ref["waiting_examples"]:
        result = trine_evidence(
            symbolic_rows("甲", [*example["present"], example["present"][0]]),
            day_branch="子",
            month_branch="寅",
        )
        row = next(r for r in result["trines"] if r["partial_name"] == example["name"])
        waiting.append(
            dict(
                source_page=example["pdf_page"],
                present=example["present"],
                expected_missing=example["missing"],
                actual_missing=row["waiting_branch"],
                matched=(
                    row["waiting_branch"] == example["missing"]
                    and row["structural_status"] == "missing_one_requires_adjudication"
                    and row["calendar_candidates"] is None
                    and row["transformation_confirmed"] is None
                ),
            )
        )
    failures = []
    counts = {"branches_complete": 0, "missing_one": 0, "insufficient_members": 0}
    for branches in itertools.product(BRANCHES, repeat=3):
        result = trine_evidence(
            symbolic_rows("甲", list(branches)), day_branch="子", month_branch="寅"
        )
        for expected, actual in zip(ref["trines"], result["trines"]):
            present = [b for b in expected["branches"] if b in branches]
            missing = [b for b in expected["branches"] if b not in branches]
            count = len(set(branches) & set(expected["branches"]))
            counts[
                (
                    "branches_complete"
                    if count == 3
                    else "missing_one" if count == 2 else "insufficient_members"
                )
            ] += 1
            if (
                actual["present_branches"] != present
                or actual["missing_branches"] != missing
                or actual["structural_status"]
                != (
                    "branches_complete_requires_adjudication"
                    if count == 3
                    else (
                        "missing_one_requires_adjudication"
                        if count == 2
                        else "insufficient_members"
                    )
                )
                or actual["waiting_branch"] != (missing[0] if count == 2 else None)
                or actual["transformation_confirmed"] is not None
                or actual["du_he"] is not None
                or actual["calendar_candidates"] is not None
                or (
                    count < 2
                    and (
                        actual["human_stem_relation"] is not None
                        or actual["controlling_dun_stems"]
                    )
                )
            ):
                failures.append(dict(branches=branches, name=expected["name"]))
    patterns = load_script("audit_jinkou_patterns")
    old = patterns.audit()
    original_rules = load_script("audit_ren_classical").load_frozen_corpus()["rules"]
    auxiliary_failures = []
    auxiliary_checks = 0
    for day, label in original_rules["empty"].items():
        empty_phase = None if label == "无四大空亡" else label[0]
        for stem in "甲丙戊庚壬":
            rows = patterns.literal_rows(
                {"day": day, "positions": [stem, "玄武", "酉", "寅"]},
                original_rules["inherent"],
            )
            for row in rows:
                auxiliary_checks += 1
                if row["si_da_kong"] != (row["element"] == empty_phase):
                    auxiliary_failures.append(dict(day=day, position=row["label"]))
    corrections = []
    cycle = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + BRANCHES[i % 12] for i in range(60)]
    for case in patterns.load_reference()["cases"]:
        old_phase = {0: "水", 3: "水", 1: "金", 4: "金"}.get(
            cycle.index(case["day"] or "甲子") // 10
        )
        for row in patterns.literal_rows(case, original_rules["inherent"]):
            old_flag = row["element"] == old_phase
            if old_flag != row["si_da_kong"]:
                corrections.append(
                    dict(
                        case_id=case["id"],
                        day=case["day"],
                        position=row["label"],
                        element=row["element"],
                        previous_derived_flag=old_flag,
                        corrected_derived_flag=row["si_da_kong"],
                    )
                )
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    selected = (
        unchanged
        and all(r["matched"] for r in clauses + waiting)
        and not failures
        and not auxiliary_failures
    )
    return dict(
        audit_id="jinkou_combinations_v1",
        primary_stem_clause_count=len(clauses),
        primary_stem_clauses=clauses,
        primary_waiting_clause_count=len(waiting),
        primary_waiting_clauses=waiting,
        synthetic_matrix_count=4 * 12**3,
        synthetic_matrix_classifications=counts,
        synthetic_matrix_failures=failures,
        synthetic_scope="All 1,728 ordered branch triples times four named groups. Source-rule engineering checks, not 6,912 original cases or predictions.",
        auxiliary_empty_checks=auxiliary_checks,
        auxiliary_empty_failures=auxiliary_failures,
        auxiliary_flag_corrections=corrections,
        auxiliary_scope="Existing frozen 子午水空/寅申金空 rules; correct derived literal-row inputs, never edit original case labels. Prior helper confused xun order 子戌申午辰寅 with ordinary branch ordinals.",
        prior_64_case_comparison={
            key: old[key]
            for key in (
                "corpus_case_count",
                "matched_semantic_cases",
                "unevaluated_definitions",
                "matched_source_day_cases",
                "semantic_failures",
            )
        },
        textual_variants=ref["variants"],
        unresolved=ref["unresolved"],
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_checks_passed=selected,
        classical_acceptance_passed=False,
        real_world_prediction="deferred_by_user",
        goal_complete=False,
        source_sha256=sha(CORPUS / "reference.json"),
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
                    "primary_stem_clause_count",
                    "primary_waiting_clause_count",
                    "synthetic_matrix_count",
                    "selected_checks_passed",
                    "classical_acceptance_passed",
                )
            }
        )
    )
    return 0 if result["classical_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
