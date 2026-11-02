"""Frozen original readings versus synthetic earth/sky empty conditions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_empty_scope_v1"
FROZEN_SHA256 = "5b9b88dcf9553024ea2f34d4ae45e01f3c02de6d3e453ea6d86cfd6664b4d803"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
WATCH = (
    "src/fatebridge/core/metaphysics/liureng_emptiness.py",
    "src/fatebridge/core/output_liuren_emptiness.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/core/export_contracts.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/audit_liuren_emptiness.py",
    "uv.lock",
    "pyproject.toml",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != FROZEN_SHA256:
        raise ValueError("Frozen emptiness manifest changed")
    frozen = json.loads((corpus / "freeze.json").read_text())
    names = {"reference.json", "source-pages.pdf"}
    if set(frozen["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen emptiness inventory changed")
    if any(sha(corpus / n) != frozen["files"][n] for n in names):
        raise ValueError("Frozen emptiness source changed")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    if len(result["literal_xun_pairs"]) != 6 or len(result["synthetic_cases"]) != 6:
        raise ValueError("Frozen emptiness denominator changed")
    return result


def context(case: dict[str, Any]) -> dict[str, Any]:
    return dict(
        day_ganzhi=case["day"],
        year_branch=case["year"],
        month_branch=case["month"],
        month_general_branch=case["general"],
        hour_branch=case["hour"],
        sky_by_earth={
            b: BRANCHES[(i + case["sky_shift"]) % 12] for i, b in enumerate(BRANCHES)
        },
    )


def audit() -> dict[str, Any]:
    r = reference()
    before = {p: sha(ROOT / p) for p in WATCH}
    from fatebridge.core.metaphysics.liureng_emptiness import emptiness_evidence

    literal = []
    for day, expected in r["literal_xun_pairs"]:
        v = emptiness_evidence(
            **context(
                dict(
                    day=day, year="子", month="寅", general="子", hour="子", sky_shift=0
                )
            )
        )
        literal.append(
            dict(
                day=day,
                expected=list(expected),
                actual=v["empty_branches"],
                matched=v["empty_branches"] == list(expected),
            )
        )
    example = r["literal_partial_example"]
    value = emptiness_evidence(
        **context(
            dict(
                day=example["day"],
                year="子",
                month="寅",
                general="子",
                hour="子",
                sky_shift=0,
            )
        )
    )
    row = next(z for z in value["rows"] if z["earth_branch"] == example["earth_branch"])
    partial = dict(
        day=example["day"],
        matched=value["day_stem_house"] == example["day_stem_house"]
        and value["empty_branches"] == example["empty_branches"]
        and row["earth_xun_kong"] is example["earth_branch_xun_kong"]
        and row["earth_stem_house_exception"] is example["earth_stem_house_exception"]
        and row["sky_xun_kong"] is example["sky_branch_xun_kong"],
        scope="One partial source example. Identity rotation is a harness, not a reconstructed historical board.",
    )
    synthetic = []
    for c in r["synthetic_cases"]:
        v = emptiness_evidence(**context(c))
        rows = {z["sky_branch"]: z for z in v["rows"]}
        results = []
        for e in c["selected_rows"]:
            z = rows[e["sky"]]
            results.append(
                z["earth_branch"] == e["earth"]
                and z["sky_xun_kong"] is e["sky_empty"]
                and z["earth_xun_kong"] is e["earth_empty"]
                and z["earth_stem_house_exception"] is e["seat_exception"]
                and z["sky_authority_roles"] == e["roles"]
                and z["effective_empty"] is None
            )
        synthetic.append(
            dict(
                id=c["id"],
                selected_rows=results,
                matched=all(results)
                and [z["branch_xun_kong"] for z in v["role_conditions"]]
                == c["roles_empty"]
                and v["hour_branch_xun_kong"] is c["hour_empty"],
            )
        )
    matrix_failures = []
    matrix_count = 0
    for d in range(60):
        day = STEMS[d % 10] + BRANCHES[d % 12]
        expected_empty = r["literal_xun_pairs"][d // 10][1]
        for shift in range(12):
            for h, hour in enumerate(BRANCHES):
                c = dict(
                    day=day,
                    year=hour,
                    month=BRANCHES[(h + 5) % 12],
                    general=BRANCHES[(h + shift) % 12],
                    hour=hour,
                    sky_shift=shift,
                )
                v = emptiness_evidence(**context(c))
                roles = list(
                    zip(("太岁", "月建", "月将"), (c["year"], c["month"], c["general"]))
                )
                ok = v["empty_branches"] == list(expected_empty) and v[
                    "hour_branch_xun_kong"
                ] is (hour in expected_empty)
                ok = ok and len(v["rows"]) == 12 and len(v["role_conditions"]) == 3
                for z, (name, branch) in zip(v["role_conditions"], roles):
                    ok = ok and z == dict(
                        role=name,
                        branch=branch,
                        branch_xun_kong=branch in expected_empty,
                    )
                for i, z in enumerate(v["rows"]):
                    earth, sky = BRANCHES[i], BRANCHES[(i + shift) % 12]
                    ok = ok and z["earth_branch"] == earth and z["sky_branch"] == sky
                    ok = (
                        ok
                        and z["earth_xun_kong"] is (earth in expected_empty)
                        and z["sky_xun_kong"] is (sky in expected_empty)
                    )
                    ok = ok and z["sky_authority_roles"] == [
                        name for name, branch in roles if branch == sky
                    ]
                    ok = ok and z["effective_empty"] is None
                ok = (
                    ok
                    and v["comprehensive_judgement"] is None
                    and v["complete_classical_conformance"] is False
                )
                if not ok:
                    matrix_failures.append(c)
                matrix_count += 1
    reference()
    after = {p: sha(ROOT / p) for p in WATCH}
    passed = (
        all(z["matched"] for z in literal + synthetic)
        and partial["matched"]
        and not matrix_failures
        and before == after
    )
    return dict(
        frozen_reference_sha256=sha(CORPUS / "reference.json"),
        implementation_sha256=after,
        implementation_unchanged=before == after,
        literal_xun_anchors=literal,
        literal_partial_example=partial,
        synthetic_cases=synthetic,
        synthetic_context_count=matrix_count,
        synthetic_row_comparisons=matrix_count * 12,
        synthetic_role_comparisons=matrix_count * 3,
        synthetic_matrix_failures=matrix_failures,
        matrix_scope="Base sky/earth xun membership, three explicit roles, hour membership and retained unknown verdicts. The matrix does not independently certify all ten stem houses or resolve seasonal empty conditions.",
        engineering_checks_passed=passed,
        new_independent_astronomical_events=0,
        new_historical_events=0,
        new_empirical_events=0,
        full_classical_conformance=False,
        real_world_validation="deferred_by_user",
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
