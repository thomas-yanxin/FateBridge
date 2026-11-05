"""Check source-derived relation matrices, keeping missing scope unapproved."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_relations_v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
PHASES = dict(zip(BRANCHES, "水土木木土火火土金金土水"))
STEMS = dict(zip("木火土金水", "甲丙戊庚壬"))
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_relations.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "src/fatebridge/core/metaphysics/jinkou_strength.py",
    "src/fatebridge/core/metaphysics/jinkou_qi.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/ren/audit_jinkou_relations.py",
    "scripts/ren/audit_jinkou_patterns.py",
    "scripts/ren/audit_ren_classical.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    names = {"reference.json", "source-pages.pdf", "transcription.html"}
    if set(manifest["files"]) != names or {
        p.name for p in corpus.iterdir()
    } != names | {"freeze.json"}:
        raise ValueError("Frozen relation inventory changed")
    for name, checksum in manifest["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Frozen relation reference changed: {name}")
    return json.loads((corpus / "reference.json").read_text())


def literal_rows(values: dict[str, str]) -> list[dict[str, str]]:
    # Synthetic source-rule probes; never represented as a dated original case.
    return [
        {
            "label": label,
            "content": values[label],
            "element": (
                next(phase for phase, stem in STEMS.items() if stem == values[label])
                if label == "人元"
                else PHASES[values[label]]
            ),
        }
        for label in ("人元", "贵神", "将神", "地分")
    ]


def reconstruction_diagnostics() -> dict[str, Any]:
    def module(name: str, filename: str):
        spec = importlib.util.spec_from_file_location(name, ROOT / filename)
        assert spec and spec.loader
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    patterns = module("frozen_pattern_cases", "scripts/ren/audit_jinkou_patterns.py")
    pattern_ref = patterns.load_reference()
    cases = pattern_ref["cases"]
    prior = module("frozen_classical_cases", "scripts/ren/audit_ren_classical.py")
    prior.load_frozen_corpus()
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board

    results = []
    for case in cases:
        if case["day"] is None:
            results.append(
                dict(
                    id=case["id"],
                    status="missing_source_day",
                    default_matched=False,
                    either_override_matched=False,
                )
            )
            continue
        inputs = dict(
            day=case["day"],
            hour=case["hour"],
            ground=case["positions"][3],
            month=BRANCHES[(case["lunar_month"] + 1) % 12],
            general=BRANCHES[(12 - case["lunar_month"]) % 12],
        )
        expected = case["positions"].copy()
        expected[1] = patterns.GOD_NAMES.get(expected[1], expected[1])
        observed = {}
        for name, mode in (("default", None), ("day", True), ("night", False)):
            board = build_jinkou_board(
                prior.make_seed(inputs),
                {"month_general": {"branch": inputs["general"]}},
                di_fen=inputs["ground"],
                is_diurnal_override=mode,
            )
            observed[name] = [
                board["rows"][0]["content"],
                board["overview"]["guishen"]["name"],
                board["rows"][2]["content"],
                board["rows"][3]["content"],
            ]
        results.append(
            dict(
                id=case["id"],
                status="compared_symbolic_source_inputs",
                expected=expected,
                observed=observed,
                default_matched=observed["default"] == expected,
                either_override_matched=expected
                in (observed["day"], observed["night"]),
            )
        )
    return dict(
        source_file=pattern_ref["source_files"][1],
        source_fixture_sha256=sha(
            ROOT / "tests/fixtures/jinkou_patterns_v1/cases.json"
        ),
        case_count=len(results),
        missing_source_day=sum(
            row["status"] == "missing_source_day" for row in results
        ),
        default_matched=sum(row["default_matched"] for row in results),
        either_override_matched=sum(row["either_override_matched"] for row in results),
        alternate_only_ids=[
            row["id"]
            for row in results
            if row["either_override_matched"] and not row["default_matched"]
        ],
        cases=results,
        scope="Diagnostic sensitivity only. Matching an explicit alternate mode does not establish original daylight, correctness or acceptance. No case-specific override is applied to production, and original default failures stay failures.",
    )


def audit() -> dict[str, Any]:
    ref = reference()
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_relations import structural_relations

    failures = []
    totals = {"si_jue": 0, "si_bai_seats": 0, "calendar": 0}
    default = dict(
        人元="甲", 贵神="丑", 将神="寅", 地分="辰", 日支="子", 时支="巳", 年支="午"
    )
    for context in ref["si_jue_contexts"]:
        for left in BRANCHES:
            for right in BRANCHES:
                inputs = {**default, context["left"]: left, context["right"]: right}
                result = structural_relations(
                    literal_rows(inputs),
                    year_branch=inputs["年支"],
                    day_branch=inputs["日支"],
                    hour_branch=inputs["时支"],
                )
                item = next(
                    row
                    for row in result["si_jue"]["checks"]
                    if row["left_position"] == context["left"]
                    and row["right_position"] == context["right"]
                )
                expected = next(
                    (
                        pair["element"]
                        for pair in ref["si_jue"]
                        if sorted(pair["branches"]) == sorted([left, right])
                    ),
                    None,
                )
                totals["si_jue"] += 1
                if (
                    item["matched"],
                    item["element"],
                    item["classification"],
                    item["original_pdf_page"],
                ) != (
                    expected is not None,
                    expected,
                    context["classification"],
                    context["pdf_page"],
                ):
                    failures.append(
                        dict(
                            layer="si_jue",
                            context=context["id"],
                            inputs=[left, right],
                            expected=expected,
                            actual=item,
                        )
                    )
    phase_branch = dict(zip("木火土金水", "寅午辰申子"))
    for position in ("人元", "贵神", "将神"):
        for phase, target in ref["si_bai"].items():
            for ground in BRANCHES:
                value = STEMS[phase] if position == "人元" else phase_branch[phase]
                inputs = {**default, position: value, "地分": ground}
                result = structural_relations(
                    literal_rows(inputs),
                    year_branch="子",
                    day_branch="子",
                    hour_branch="巳",
                )
                item = next(
                    row
                    for row in result["si_bai"]["checks"]
                    if row["position"] == position
                )
                totals["si_bai_seats"] += 1
                if (
                    item["matched"] != (ground == target)
                    or item["bai_branch"] != target
                ):
                    failures.append(
                        dict(
                            layer="si_bai",
                            position=position,
                            phase=phase,
                            ground=ground,
                            expected=target,
                            actual=item,
                        )
                    )
    for rule in ref["calendar_rules"]:
        for position in rule["positions"]:
            for time_branch in BRANCHES:
                for branch in BRANCHES:
                    key = "年支" if rule["id"].startswith("year") else "日支"
                    inputs = {**default, position: branch, key: time_branch}
                    result = structural_relations(
                        literal_rows(inputs),
                        year_branch=inputs["年支"],
                        day_branch=inputs["日支"],
                        hour_branch=inputs["时支"],
                    )
                    item = next(
                        row
                        for row in result["calendar"]["checks"]
                        if row["rule_id"] == rule["id"] and row["position"] == position
                    )
                    target = (
                        time_branch
                        if rule["id"].endswith("build")
                        else ref["branch_oppositions"][time_branch]
                    )
                    totals["calendar"] += 1
                    if (
                        item["matched"] != (branch == target)
                        or item["original_pdf_page"] != rule["pdf_page"]
                    ):
                        failures.append(
                            dict(
                                layer="calendar",
                                rule=rule["id"],
                                position=position,
                                inputs=[time_branch, branch],
                                expected=branch == target,
                                actual=item,
                            )
                        )
    reconstruction = reconstruction_diagnostics()
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return dict(
        audit_id="jinkou_relations_v1",
        source_url=ref["source_url"],
        source_sha256=ref["source_sha256"],
        comparison_scope="Rule-derived synthetic matrices, not additional historical examples or Gregorian dates",
        totals=totals,
        failures=failures,
        selected_rule_checks_passed=not failures and unchanged,
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        transcription_variants=ref["transcription_variants"],
        source_reconstruction_diagnostics=reconstruction,
        classical_acceptance_passed=False,
        goal_complete=False,
        incomplete_requirements=[
            "本命支未输入，大绝未算，不当作不成立",
            "四败仅五行临地分一层，遇字全部位置范围未认证",
            "六十四课原例及六条定义未决保持原状",
            "日下完整五态及综合取用先后尚未裁定",
            "完整历法域及真实模型自由文本尚未验收",
        ],
        limits=ref["limits"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-full-conformance", action="store_true")
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "totals",
                    "selected_rule_checks_passed",
                    "classical_acceptance_passed",
                    "goal_complete",
                )
            }
        )
    )
    return (
        0
        if report["selected_rule_checks_passed"] and not args.require_full_conformance
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
