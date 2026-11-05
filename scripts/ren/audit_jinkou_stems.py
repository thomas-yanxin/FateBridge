"""Freeze literal stem anchors separately from symbolic pair expansions."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_stem_relations_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_stems.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_jinkou_stems.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/ren/audit_jinkou_stems.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(freeze["files"]) | {"freeze.json"}:
        raise ValueError("Frozen stem-reference inventory changed")
    for name, value in freeze["files"].items():
        if sha(corpus / name) != value:
            raise ValueError(f"Frozen stem-reference source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    return result


def cycle(ref: dict[str, Any]) -> list[str]:
    return [ref["stems"][i % 10] + ref["branches"][i % 12] for i in range(60)]


def expected_dun(ref: dict[str, Any], day: str, target: str) -> str:
    group = next(g for g in ref["wuzi_groups"] if day in g["day_stems"])
    cursor = ref["stems"].index(group["zi_stem"])
    for branch in ref["branches"]:
        if branch == target:
            return str(ref["stems"][cursor])
        cursor = (cursor + 1) % 10
    raise ValueError("invalid reference branch")


def symbolic_rows(
    ref: dict[str, Any], day: str, god: str, general: str
) -> list[dict[str, Any]]:
    # Inactive fields are explicitly synthetic. The intrinsic tag is a valid
    # cycle pair with this branch, not a new historical god-identity label.
    intrinsic = next(p for p in cycle(ref) if p[1] == god)
    return [
        dict(label="人元", content=expected_dun(ref, day, "子")),
        dict(
            label="贵神",
            content=god,
            element=ref["branch_elements"][god],
            shenjiang="模拟贵神",
            dun_stem=expected_dun(ref, day, god),
            intrinsic_ganzhi=intrinsic,
            xun_kong=False,
            si_da_kong=False,
        ),
        dict(
            label="将神",
            content=general,
            element=ref["branch_elements"][general],
            shenjiang="模拟将神",
            dun_stem=expected_dun(ref, day, general),
            xun_kong=False,
            si_da_kong=False,
        ),
        dict(label="地分", content="子"),
    ]


def expected_pair(ref: dict[str, Any], left: str, right: str) -> dict[str, Any]:
    match = next(
        (r for r in ref["stem_pairs"] if set(r["stems"]) == {left[0], right[0]}), None
    )
    branch_harmony = any(set(p) == {left[1], right[1]} for p in ref["branch_pairs"])
    sequence = cycle(ref)
    left_head = sequence[sequence.index(left) // 10 * 10]
    right_head = sequence[sequence.index(right) // 10 * 10]
    return dict(
        left_ganzhi=left,
        right_ganzhi=right,
        stem_harmony_matched=match is not None,
        canonical_stem_pair=match["stems"] if match else None,
        candidate_element=match["candidate_element"] if match else None,
        branch_harmony_matched=branch_harmony,
        both_harmonies_matched=match is not None and branch_harmony,
        left_ganzhi_xun_head=left_head,
        right_ganzhi_xun_head=right_head,
        same_ganzhi_xun=left_head == right_head,
        transformation_confirmed=None,
        du_he=None,
    )


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_stems import (
        build_stem_relations,
        ganzhi_pair_facts,
        wuzidun_stem,
    )

    starts = [
        dict(
            **g,
            actual=wuzidun_stem(g["day_stems"][0], "子"),
            matched=wuzidun_stem(g["day_stems"][0], "子") == g["zi_stem"],
        )
        for g in ref["wuzi_groups"]
    ]
    dun_checks = [
        dict(
            day_stem=d,
            branch=b,
            expected=expected_dun(ref, d, b),
            actual=wuzidun_stem(d, b),
            matched=wuzidun_stem(d, b) == expected_dun(ref, d, b),
        )
        for d in ref["stems"]
        for b in ref["branches"]
    ]
    sample = ref["six_yi_example"]
    literal_anchors = [
        dict(
            position=p,
            expected=expected,
            actual=wuzidun_stem(sample["day_stem"], branch),
            matched=wuzidun_stem(sample["day_stem"], branch) == expected,
        )
        for p, branch, expected in (
            ("贵神", sample["god_branch"], sample["expected_god_dun_stem"]),
            ("将神", sample["general_branch"], sample["expected_general_dun_stem"]),
        )
    ]
    first = build_stem_relations(
        day_stem="甲", rows=symbolic_rows(ref, "甲", "子", "卯")
    )
    actual_rules = {r["id"]: r for r in first["rule_evaluations"]}
    clauses = []
    for r in ref["directed_rules"]:
        row = actual_rules.get(r["id"])
        expected = {k: v for k, v in r.items() if k != "motion_analogue"}
        actual = (
            None
            if row is None
            else dict(
                id=row["id"],
                relation=row["relation"],
                source=row["source_position"],
                target=row["target_position"],
                phase_relation=row["phase_relation"],
            )
        )
        clauses.append(
            dict(
                id=r["id"],
                expected=expected,
                actual=actual,
                matched=actual == expected
                and row is not None
                and row["original_pdf_pages"] == [63],
            )
        )
    stem_pairs = []
    for r in ref["stem_pairs"]:
        a, b = [next(p for p in cycle(ref) if p[0] == stem) for stem in r["stems"]]
        actual = ganzhi_pair_facts(a, b)
        stem_pairs.append(
            dict(
                **r,
                actual=actual,
                matched=actual["stem_harmony_matched"]
                and actual["candidate_element"] == r["candidate_element"]
                and actual["canonical_stem_pair"] == r["stems"],
            )
        )
    written = []
    for r in ref["written_ganzhi_examples"]:
        actual = ganzhi_pair_facts(r["left"], r["right"])
        written.append(
            dict(
                **r,
                actual=actual,
                literal_stem_match=actual["stem_harmony_matched"] is r["stem_harmony"],
                derived_annotation_match=actual["branch_harmony_matched"]
                is r["derived_branch_harmony"]
                and actual["same_ganzhi_xun"] is r["derived_same_xun"],
            )
        )
    failures: list[dict[str, Any]] = []
    contexts = rule_checks = rule_matches = context_matches = 0
    for day, god, general in product(ref["stems"], ref["branches"], ref["branches"]):
        contexts += 1
        result = build_stem_relations(
            day_stem=day, rows=symbolic_rows(ref, day, god, general)
        )
        god_stem, general_stem = expected_dun(ref, day, god), expected_dun(
            ref, day, general
        )
        at = {
            "贵神": ref["stem_elements"][god_stem],
            "将神": ref["stem_elements"][general_stem],
        }
        at_id = {r["id"]: r for r in result["rule_evaluations"]}
        if len(result["rule_evaluations"]) != 4 or set(at_id) != {
            r["id"] for r in ref["directed_rules"]
        }:
            failures.append(
                dict(
                    day=day,
                    god=god,
                    general=general,
                    reason="four-rule inventory changed",
                )
            )
        expected_relation, expected_motion = "两干比和", None
        for rule in ref["directed_rules"]:
            rule_checks += 1
            edges = ref[
                (
                    "phase_generations"
                    if rule["phase_relation"] == "生"
                    else "phase_controls"
                )
            ]
            expected_match = [at[rule["source"]], at[rule["target"]]] in edges
            row = at_id.get(rule["id"])
            matched = row is not None and row["matched"] is expected_match
            rule_matches += matched
            if not matched:
                failures.append(
                    dict(
                        day=day,
                        god=god,
                        general=general,
                        rule=rule["id"],
                        expected=expected_match,
                        actual=row,
                    )
                )
            if expected_match:
                expected_relation, expected_motion = (
                    rule["relation"],
                    rule["motion_analogue"],
                )
        expected_facts = expected_pair(ref, god_stem + god, general_stem + general)
        matched = (
            result["relation"] == expected_relation
            and result["motion_analogue"] == expected_motion
            and result["pair_facts"] == expected_facts
            and result["god"]["dun_element"] == at["贵神"]
            and result["general"]["dun_element"] == at["将神"]
            and result["complete_classical_conformance"] is False
        )
        context_matches += matched
        if not matched:
            failures.append(
                dict(
                    day=day,
                    god=god,
                    general=general,
                    reason="summary or pair facts changed",
                    actual=result,
                )
            )
    pair_checks = pair_matches = 0
    for left, right in product(cycle(ref), repeat=2):
        pair_checks += 1
        actual, expected = ganzhi_pair_facts(left, right), expected_pair(
            ref, left, right
        )
        matched = actual == expected
        pair_matches += matched
        if not matched:
            failures.append(
                dict(left=left, right=right, expected=expected, actual=actual)
            )
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    literal_ok = all(
        r["matched"] for r in starts + literal_anchors + clauses + stem_pairs
    )
    written_ok = all(
        r["literal_stem_match"] and r["derived_annotation_match"] for r in written
    )
    return dict(
        audit_id="jinkou_stem_relations_v1",
        literal_wuzi_groups=starts,
        expanded_dun_checks=dun_checks,
        expanded_dun_match_count=sum(r["matched"] for r in dun_checks),
        literal_partial_example_count=1,
        literal_example_anchor_checks=literal_anchors,
        directed_clause_checks=clauses,
        literal_stem_pair_checks=stem_pairs,
        written_ganzhi_examples=written,
        written_stem_matches=sum(r["literal_stem_match"] for r in written),
        written_branch_harmony_count=sum(
            r["actual"]["branch_harmony_matched"] for r in written
        ),
        written_same_xun_count=sum(r["actual"]["same_ganzhi_xun"] for r in written),
        synthetic_contexts=contexts,
        synthetic_context_matches=context_matches,
        derived_rule_checks=rule_checks,
        derived_rule_matches=rule_matches,
        all_sexagenary_pair_checks=pair_checks,
        all_sexagenary_pair_matches=pair_matches,
        failures=failures,
        source_sha256=ref["source_sha256"],
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_stem_checks_passed=unchanged
        and literal_ok
        and written_ok
        and not failures
        and len(starts) == 5
        and len(literal_anchors) == 2
        and len(clauses) == 4
        and len(stem_pairs) == 5
        and len(written) == 6
        and len(dun_checks) == 120
        and all(r["matched"] for r in dun_checks)
        and contexts == context_matches == 1440
        and rule_checks == rule_matches == 5760
        and pair_checks == pair_matches == 3600,
        classical_acceptance_passed=False,
        goal_complete=False,
        new_historical_events=0,
        new_empirical_outcomes=0,
        model_invocations=0,
        interpretation_limits=ref["interpretation_limits"],
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
                    "expanded_dun_match_count",
                    "written_stem_matches",
                    "written_branch_harmony_count",
                    "derived_rule_matches",
                    "all_sexagenary_pair_matches",
                    "selected_stem_checks_passed",
                )
            }
        )
    )
    return 0 if result["selected_stem_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
