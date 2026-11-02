"""Verify a frozen nine-case development replay without starting any model."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "tests/fixtures/agent_behavior/ren_semantic_refresh_cases_v1.json"
PIN = "69a57a9fe00e0014426eb443b1dbeebc23e847ececaa297e579ffd21de72ac2c"
OLD_PIN = "c3a32dd38776d57763a1f12ecb71f0de0feb2487c46a749ec2e90801f87f592b"
OLD_REPORT_PIN = "38d655e038a8f1a7ef14f4d901ee55abccc8efda396c841f1a27e661c97482ae"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset(path: Path = DATASET) -> dict[str, Any]:
    if sha(path) != PIN:
        raise ValueError("Frozen Ren replay dataset identity changed")
    old = ROOT / "tests/fixtures/agent_behavior/ren_semantic_cases.json"
    report = ROOT / "tests/fixtures/ren_semantic_run_v1/report.json"
    if sha(old) != OLD_PIN or sha(report) != OLD_REPORT_PIN:
        raise ValueError("Original six-case inputs or first report identity changed")
    value: dict[str, Any] = json.loads(path.read_text())
    original = json.loads(old.read_text())
    cases = value["cases"]
    if (
        len(cases) != 9
        or cases[:6] != original["cases"]
        or len({c["id"] for c in cases}) != 9
        or sum(len(c["manual_review"]) for c in cases[:6]) != 21
        or sum(len(c["manual_review"]) for c in cases[6:]) != 11
    ):
        raise ValueError("Original cases, criteria or supplementary queue differs")
    return value


def coverage(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Coverage probes inspect reference facts; they never grade a future answer."""
    board = payload["jinkou"]
    rows = board["rows"]
    checks = {
        "four_positions_present": [r["label"] for r in rows]
        == ["人元", "贵神", "将神", "地分"],
        "explicit_day_choice": board["overview"]["diurnal_evidence"]["explicit_choice"]
        is True,
        "no_observation_invented": board["overview"]["diurnal_evidence"][
            "stellar_visibility_observed"
        ]
        is None,
    }
    selected: dict[str, Any] = dict(rows=rows)
    if case_id == "ren_refresh_explicit_four_positions":
        checks["both_strength_layers_present"] = all(
            "seasonal_power" in r and "internal_power" in r for r in rows
        )
    else:
        choices = {
            "ren_refresh_complete_water_trine": ("水", "申子辰", "辰"),
            "ren_refresh_complete_metal_trine": ("金", "巳酉丑", "巳"),
        }
        if case_id not in choices:
            raise ValueError("Unknown supplemental coverage case")
        element, branches, member = choices[case_id]
        group = next(
            g for g in board["combinations"]["trines"] if g["element"] == element
        )
        god = rows[1]
        checks.update(
            exact_complete_members=group["present_branches"] == list(branches)
            and group["missing_branches"] == [],
            structural_complete_but_not_adjudicated=group["structural_status"]
            == "branches_complete_requires_adjudication",
            complete_members_have_no_waiting_symbol=group["waiting_branch"] is None,
            transformation_and_dates_unknown=all(
                group[k] is None
                for k in ("du_he", "transformation_confirmed", "calendar_candidates")
            ),
            self_member_also_in_source_list=member in group["present_branches"]
            and member in group["source_listed_disruptors"],
            no_presence_only_disruption=group["disruptor_application"]
            == "context_unadjudicated_not_presence_rule",
            intrinsic_and_daily_stems_differ=god["intrinsic_ganzhi"][0]
            != god["dun_stem"],
            actual_member_conditions_present=len(group["member_conditions"]) == 3
            and all(
                all(
                    k in row
                    for k in ("xun_kong", "si_da_kong", "day_clash", "month_break")
                )
                for row in group["member_conditions"]
            ),
        )
        selected.update(trine=group)
    return dict(
        case=case_id,
        actual_reference_run_id=payload["run_metadata"]["run_id"],
        checks=checks,
        coverage_ready=all(checks.values()),
        reference_facts=selected,
        future_model_semantics="not_run",
    )


def audit(preparation: Path) -> dict[str, Any]:
    from scripts.evaluate_agent import model_prompt, prepare_workspace, source_manifest

    document = dataset()
    if sha(preparation / "case-dataset.json") != PIN:
        raise ValueError("Prepared dataset differs from the fixed replay proposal")
    prepared = json.loads((preparation / "preparation.json").read_text())
    source = preparation / "source"
    manifest = json.loads((preparation / "source-manifest.json").read_text())
    if (
        prepared["dataset_sha256"] != PIN
        or prepared["model_invocations"] != 0
        or prepared["selected_case_count"] != 9
        or prepared["semantic_acceptance"] != "not_run"
        or prepared["source_snapshot_profile"] != "runtime"
        or source_manifest(source, "runtime") != manifest
        or prepared["source_manifest_sha256"]
        != sha(preparation / "source-manifest.json")
    ):
        raise ValueError("Prepared source or no-model receipt differs")
    cases = document["cases"]
    references = prepared["references"]
    if [r["case"] for r in references] != [c["id"] for c in cases]:
        raise ValueError("Prepared reference queue differs")
    readiness = []
    for case, item in zip(cases, references, strict=True):
        path = preparation / item["payload_file"]
        if sha(path) != item["payload_sha256"]:
            raise ValueError("Prepared reference payload identity changed")
        raw = json.loads(path.read_text())
        if raw["is_error"] or raw["structured_content"] is None:
            raise ValueError("Prepared reference MCP failed")
        expected_arguments = {
            **case["reference_request"]["arguments"],
            "fields": None,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        }
        if (
            raw["tool"] != case["reference_request"]["tool"]
            or raw["arguments"] != expected_arguments
            or raw["structured_content"]["run_metadata"]["run_id"] != item["run_id"]
        ):
            raise ValueError("Prepared reference input or run identity differs")
        prompt = preparation / "model-prompts" / (case["id"] + ".txt")
        if prompt.read_text() != model_prompt(case):
            raise ValueError("Model-facing prompt changed or reviewer criteria leaked")
        if case in cases[6:]:
            readiness.append(coverage(case["id"], raw["structured_content"]))
    proposal = json.loads((preparation / "proposed-execution.json").read_text())
    command = proposal["command"]
    if (
        proposal["requires_session_authorization_for_independent_model"] is not True
        or "--model" in command
        or "--timeout" not in command
        or command[command.index("--timeout") + 1] != "240"
        or "--stop-on-execution-failure" not in command
    ):
        raise ValueError("Model replay authorization or process conditions changed")
    if (preparation / "model-run").exists():
        raise ValueError("Model-run output already exists; not an unused preparation")
    with tempfile.TemporaryDirectory(prefix="ren-replay-workspace-check-") as name:
        workspace = Path(name)
        prepare_workspace(workspace, source)
        hidden = [
            "docs/liuren-jinkou-audit.md",
            "docs/validation",
            "tests",
            "scripts",
        ]
        if any((workspace / p).exists() for p in hidden):
            raise ValueError("Reviewer data leaked into the model workspace")
        retained = [
            "AGENTS.md",
            "skills/onda-zhanbu/references/ren-evidence.md",
            "docs/contracts/jinkou.json",
            "docs/contracts/liureng_gods.json",
            "src/fatebridge/core/metaphysics/jinkou.py",
        ]
        if any(not (workspace / p).is_file() for p in retained):
            raise ValueError(
                "Required runtime guide, contract or calculation was removed"
            )
    return dict(
        dataset_sha256=PIN,
        old_dataset_sha256=OLD_PIN,
        old_first_report_sha256=OLD_REPORT_PIN,
        original_six_objects_and_21_criteria_unchanged=True,
        selected_cases=9,
        supplemental_cases=3,
        supplemental_criteria=11,
        supplemental_coverage=readiness,
        preparation_checks_passed=all(r["coverage_ready"] for r in readiness),
        reviewer_document_excluded_from_model_workspace=True,
        reviewer_document_retained_in_frozen_source=(
            source / "docs/liuren-jinkou-audit.md"
        ).is_file(),
        runtime_guides_and_contracts_retained=True,
        source_manifest_sha256=sha(preparation / "source-manifest.json"),
        proposed_execution_sha256=sha(preparation / "proposed-execution.json"),
        model_started_by_this_auditor=False,
        model_semantic_acceptance="not_run",
        session_authorization_required=True,
        original_first_mechanical_result="5/6",
        original_first_manual_result="18/21",
        combined_best_of_runs_score_allowed=False,
        holdout_claim=False,
        calendar_or_classical_truth_validated_by_reference_calls=False,
        real_world_prediction="deferred_by_user",
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing preparation audit")
    result = audit(args.preparation)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "selected_cases",
                    "preparation_checks_passed",
                    "model_semantic_acceptance",
                    "goal_complete",
                )
            }
        )
    )
    return 0 if result["preparation_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
