"""Audit source readings separately from synthetic transmission contexts."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import permutations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/liuren_transmission_relations_v1"
WATCH = (
    "src/fatebridge/core/metaphysics/liureng_transmission_relations.py",
    "src/fatebridge/core/output_liuren_transmission_relations.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/liureng_life_stages.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_liuren_transmission_relations.py",
    "uv.lock",
    "pyproject.toml",
)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> tuple[dict[str, Any], dict[str, Any]]:
    f = json.loads((corpus / "freeze.json").read_text())
    names = {"rules.json", "synthetic-cases.json", "source-pages.pdf"}
    if set(f["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen transmission-relation inventory changed")
    for n in names:
        if sha(corpus / n) != f["files"][n]:
            raise ValueError("Frozen transmission-relation reference changed")
    r = json.loads((corpus / "rules.json").read_text())
    c = json.loads((corpus / "synthetic-cases.json").read_text())
    if len(r["god_elements"]) != 12 or len(r["trines"]) != 4 or len(c["cases"]) != 10:
        raise ValueError("Complete predeclared transmission reference required")
    return r, c


def context(
    day: str,
    branches: list[str],
    gods: list[str] | None = None,
    uppers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "day_ganzhi": day,
        "lessons": [
            {"index": i + 1, "upper_branch": b}
            for i, b in enumerate(uppers or ["寅", "戌", "午", "子"])
        ],
        "transmissions": {
            p: dict(branch=b, god=g, earth_branch=b)
            for p, b, g in zip(
                ("initial", "middle", "final"), branches, gods or ["贵人"] * 3
            )
        },
    }


def audit() -> dict[str, Any]:
    r, c = reference()
    before = {p: sha(ROOT / p) for p in WATCH}
    from fatebridge.core.metaphysics.liureng_transmission_relations import (
        GOD_ELEMENTS,
        TRINES,
        transmission_relations,
    )

    phase = dict(zip("子丑寅卯辰巳午未申酉戌亥", "水土木木土火火土金金土水"))
    matrix = c["five_phase_matrix"]
    cols = c["column_order"]
    kin = {"比和": "兄弟", "生": "子孙", "受生": "父母", "克": "妻财", "受克": "官鬼"}
    examples = []
    for clause in r["clauses"]:
        for e in clause.get("examples", []):
            value = transmission_relations(
                **context("甲子", [e["branch"]] * 3, [e["god"]] * 3)
            )
            examples.append(
                dict(
                    **e,
                    actual=value["rows"][0]["war"],
                    matched=value["rows"][0]["war"] == e["expected"],
                )
            )
    pairs = []
    for god, ge in r["god_elements"].items():
        for branch, be in phase.items():
            row = transmission_relations(**context("甲子", [branch] * 3, [god] * 3))[
                "rows"
            ][0]
            expected = matrix[ge][cols.index(be)]
            pairs.append(
                row["god_to_spirit"] == expected
                and row["war"] == {"克": "外战", "受克": "内战"}.get(expected)
                and row["day_relation"] == kin[matrix["木"][cols.index(be)]]
            )
    synthetic = []
    for case in c["cases"]:
        value = transmission_relations(
            **context(case["day"], case["branches"], uppers=case["lesson_uppers"])
        )
        flags = {v["id"]: v["matched"] for v in value["rules"]}
        synthetic.append(
            dict(
                id=case["id"],
                matched=all(flags[i] for i in case["must_match"])
                and all(not flags[i] for i in case["must_not_match"]),
            )
        )
    triads = []
    for t in r["trines"]:
        for seq in permutations(t["branches"]):
            for i, s in enumerate("甲乙丙丁戊己庚辛壬癸"):
                d = s + "子丑寅卯辰巳午未申酉"[i]
                v = transmission_relations(**context(d, list(seq)))
                found = [z for z in v["trines"] if z["branches_complete"]]
                de = "木木火火土土金金水水"[i]
                expected = kin[matrix[de][cols.index(t["element"])]]
                triads.append(
                    len(found) == 1
                    and found[0]["nominal_day_relation"] == expected
                    and found[0]["transformation_confirmed"] is None
                    and [z["element"] for z in v["rows"]] == [phase[b] for b in seq]
                )
    anchors = GOD_ELEMENTS == r["god_elements"] and list(TRINES) == [
        (t["branches"], t["element"]) for t in r["trines"]
    ]
    after = {p: sha(ROOT / p) for p in WATCH}
    reference()
    return dict(
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        implementation_unchanged_during_audit=before == after,
        literal_god_phase_anchors=12,
        literal_trine_anchors=4,
        literal_control_examples=examples,
        source_anchor_tables_matched=anchors,
        synthetic_god_branch_pairs=len(pairs),
        synthetic_god_branch_pairs_matched=sum(pairs),
        synthetic_named_contexts=synthetic,
        synthetic_trine_permutation_day_contexts=len(triads),
        synthetic_trine_contexts_matched=sum(triads),
        new_historical_events=0,
        model_invocations=0,
        engineering_checks_passed=anchors
        and all(e["matched"] for e in examples)
        and all(pairs)
        and all(x["matched"] for x in synthetic)
        and all(triads)
        and before == after,
        full_classical_conformance=False,
        goal_complete=False,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    r = audit()
    s = json.dumps(r, ensure_ascii=False, indent=2) + "\n"
    a.output.write_text(s)
    print(s)
    return 0 if r["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
