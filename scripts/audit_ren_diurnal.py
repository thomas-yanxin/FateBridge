"""Audit choice provenance and named noble tables, never stellar observation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_diurnal_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/ren_diurnal.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_gods.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/audit_ren_diurnal.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference():
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    if set(freeze["files"]) != {"reference.json", "source-pages.pdf"}:
        raise ValueError("Diurnal source inventory changed")
    for name, checksum in freeze["files"].items():
        if sha(CORPUS / name) != checksum:
            raise ValueError(f"Diurnal source changed: {name}")
    return json.loads((CORPUS / "reference.json").read_text())


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    ref = reference()
    v1 = load("audit_ren_classical").load_frozen_corpus()
    v2 = load("audit_ren_depth").load_reference()
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou import _build_guishen_mapping
    from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
    from fatebridge.core.metaphysics.ren_gods import noble_start

    branches = (
        ref["software_policy"]["day_branches"]
        + ref["software_policy"]["night_branches"]
    )
    fixed = []
    for branch in branches:
        result = resolve_diurnal(branch)
        fixed.append(
            dict(
                hour=branch,
                actual=result,
                matched=(
                    result["is_diurnal"]
                    == (branch in ref["software_policy"]["day_branches"])
                    and result["explicit_choice"] is None
                    and result["selection_source"] == "hour_branch_convention"
                    and result["stellar_visibility_observed"] is None
                    and result["astronomical_boundary_computed"] is False
                ),
            )
        )
    explicit = []
    for case in ref["explicit_cases"]:
        result = resolve_diurnal(case["hour"], case["selected"])
        explicit.append(
            dict(
                input=case,
                actual=result,
                matched=(
                    result["is_diurnal"] is case["selected"]
                    and result["explicit_choice"] is case["selected"]
                    and result["selection_source"] == "explicit_parameter"
                    and result["stellar_visibility_observed"] is None
                ),
            )
        )
    common = {r["stem"]: r for r in v1["rules"]["guiren"]}
    tanyuan = {r["stem"]: r for r in v2["tanyuan-rules"]["noble_starts"]}
    checks = []
    for stem in common:
        for branch in branches:
            for choice in (None, False, True):
                selected = (
                    choice
                    if choice is not None
                    else branch in ref["software_policy"]["day_branches"]
                )
                period = "day" if selected else "night"
                jk = _build_guishen_mapping(stem, branch, choice)[0]
                lr = noble_start(
                    stem,
                    resolve_diurnal(branch, choice)["is_diurnal"],
                    "tanyuan_xieji_v1",
                )
                checks.append(
                    dict(
                        stem=stem,
                        hour=branch,
                        explicit_choice=choice,
                        jinkou_actual=jk,
                        jinkou_expected=common[stem][period],
                        tanyuan_actual=lr,
                        tanyuan_expected=tanyuan[stem][period],
                        matched=jk == common[stem][period]
                        and lr == tanyuan[stem][period],
                    )
                )
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return dict(
        audit_id="ren_diurnal_v1",
        source_sha256=sha(CORPUS / "reference.json"),
        fixed_hour_policy_checks=fixed,
        explicit_choice_checks=explicit,
        literal_start_labels=40,
        expanded_choice_matrix_count=len(checks),
        expanded_choice_matrix=checks,
        traditional_scope="Two named 20-entry tables. Expanded branch/override checks reuse those labels; not 720 independent original examples or actual stellar-visibility observations.",
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_checks_passed=unchanged
        and all(r["matched"] for r in fixed + explicit + checks),
        actual_stellar_observations=0,
        numeric_classical_stellar_threshold_adjudicated=False,
        classical_acceptance_passed=False,
        real_model_semantic_acceptance="separate_semantic_evaluation_required",
        goal_complete=False,
        limits=ref["limitations"],
    )


def main():
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
                    "literal_start_labels",
                    "expanded_choice_matrix_count",
                    "selected_checks_passed",
                    "classical_acceptance_passed",
                )
            }
        )
    )
    return 0 if result["classical_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
