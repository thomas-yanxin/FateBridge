"""Independent exhaustive graph oracle, counterfactual witnesses and false claims."""

import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import bodygraph
from fatebridge.core.human_design_bridging import definition_bridging
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/human-design-bridge-oracle.json").read_text()
)
PLAN = json.loads((ROOT / REFERENCE["plan_path"]).read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_autocrlf_checkout_preserves_every_hash_bound_oracle_input(tmp_path):
    git = shutil.which("git")
    assert git is not None, "Git is required to verify source-checkout byte integrity"
    worktree = tmp_path / "repository"
    checkout = tmp_path / "checkout"
    worktree.mkdir()
    paths = {
        "src/fatebridge/core/human_design_natal_sources.py",
        "src/fatebridge/validation/human_design_natal_sources.py",
        "src/fatebridge/validation/human_design_source_files.py",
        "scripts/check_human_design_natal_sources.py",
        "tests/fixtures/human-design-natal-source-plan.json",
        "docs/validation/human-design-natal-source-before.json",
        "docs/validation/human-design-natal-source-late-before.json",
        "docs/validation/human-design-sampling-before.json",
        "tests/fixtures/human-design-sampling-plan.json",
        "tests/fixtures/human-design-sampling-legacy-statements.json",
        "tests/fixtures/human-design-sampling-legacy-statements-linux.json",
        "src/fatebridge/core/human_design_sample_witness.py",
        "src/fatebridge/validation/human_design_sampling.py",
        "docs/validation/human-design-comparison-before.json",
        "tests/fixtures/human-design-comparison-plan.json",
        "tests/fixtures/human-design-comparison-legacy-statements.json",
        "src/fatebridge/core/human_design_node_comparisons.py",
        "src/fatebridge/validation/human_design_comparisons.py",
        REFERENCE["plan_path"],
        REFERENCE["oracle_source_path"],
        REFERENCE["source_table_path"],
        "scripts/build_human_design_bridge_reference.py",
        "scripts/gen_human_design_astronomy_reference.py",
        "scripts/gen_human_design_astronomy_horizons.py",
        "scripts/build_human_design_profile_reference.py",
        "scripts/build_human_design_circuit_group_reference.py",
        "scripts/build_human_design_circuit_pages.py",
        "scripts/build_human_design_cross_coverage.py",
        "scripts/read_human_design_official_pdf.py",
        "scripts/plan_human_design_cross_coverage.py",
        "src/fatebridge/core/human_design_cross_coverage.py",
        "src/fatebridge/data/human_design/cross-coverage-2026-reference.json",
        "tests/fixtures/human-design-cross-coverage-plan.json",
        "tests/fixtures/human-design-cross-coverage-observations.json",
        "tests/fixtures/human-design-official-cross-charts.json",
        "tests/fixtures/human-design-course-cross-disagreement.json",
        "scripts/check_human_design_transition_case.py",
        "src/fatebridge/core/human_design_transition.py",
        "src/fatebridge/validation/human_design_transition.py",
        "tests/fixtures/human-design-transition-plan.json",
        "tests/fixtures/human-design-transition-case.json",
        "src/fatebridge/data/human_design/circuit-group-2026-reference.json",
        "src/fatebridge/data/human_design/circuit-pages-1996-reference.json",
        "tests/fixtures/human-design-circuit-pages-plan.json",
        "tests/fixtures/human-design-circuit-pages-observations.json",
        "src/fatebridge/data/human_design/profile-2026-reference.json",
        "tests/fixtures/human-design-astronomy-plan.json",
        "tests/fixtures/human-design-astronomy-de440.json",
        "tests/fixtures/human-design-astronomy-horizons.json",
        "tests/fixtures/human-design-bridge-oracle.json",
        "tests/fixtures/human-design-authority-plan.json",
        *PLAN["source_fingerprints"],
    }
    (worktree / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    for name in paths:
        target = worktree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    command = [
        git,
        "-c",
        "core.autocrlf=true",
        "-c",
        "core.attributesFile=" + os.devnull,
    ]
    for args in (
        ["init", "-q"],
        ["add", "--", ".gitattributes", *sorted(paths)],
        ["checkout-index", "--all", "--force", "--prefix=" + checkout.as_posix() + "/"],
    ):
        subprocess.run(command + args, cwd=worktree, check=True, capture_output=True)
    for name in paths:
        assert (checkout / name).read_bytes() == (ROOT / name).read_bytes(), name


def test_oracle_is_bound_to_separate_code_frozen_source_and_complete_subset_counts():
    for path, expected in PLAN["source_fingerprints"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    assert (
        hashlib.sha256((ROOT / REFERENCE["plan_path"]).read_bytes()).hexdigest()
        == REFERENCE["plan_sha256"]
    )
    assert (
        hashlib.sha256(
            (ROOT / REFERENCE["oracle_source_path"]).read_bytes()
        ).hexdigest()
        == REFERENCE["oracle_source_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / REFERENCE["source_table_path"]).read_bytes()).hexdigest()
        == REFERENCE["source_table_sha256"]
    )
    assert (
        hashlib.sha256(
            (ROOT / "scripts/build_human_design_bridge_reference.py").read_bytes()
        ).hexdigest()
        == REFERENCE["generator_sha256"]
    )
    assert (
        hashlib.sha256(REFERENCE["raw_output"].encode()).hexdigest()
        == REFERENCE["raw_output_sha256"]
    )
    assert datetime.fromisoformat(PLAN["declared_at"]) < datetime.fromisoformat(
        REFERENCE["generated_at"]
    )
    generator = ast.parse(
        (ROOT / "scripts/build_human_design_bridge_reference.py").read_text()
    )
    imports = {
        alias.name
        for node in ast.walk(generator)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(generator)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(name.startswith("fatebridge") for name in imports)
    assert len(REFERENCE["cases"]) == len(PLAN["cases"]) == 22
    assert sum(r["candidate_subsets_checked"] for r in REFERENCE["cases"]) == 37_256_606
    for case, expected in zip(PLAN["cases"], REFERENCE["cases"]):
        assert case["id"] == expected["id"]
        count = expected["minimum_added_gate_count"]
        assert expected["candidate_subsets_checked"] == (
            sum(
                math.comb(64 - len(case["activated_gates"]), k)
                for k in range(count + 1)
            )
            if count is not None
            else 0
        )


@pytest.mark.parametrize("index", range(22), ids=[c["id"] for c in PLAN["cases"]])
def test_all_minimum_sets_match_exhaustive_independent_union_find_and_replay(index):
    case, expected = PLAN["cases"][index], REFERENCE["cases"][index]
    graph = bodygraph(case["activated_gates"], [])
    original = deepcopy(graph)
    report = definition_bridging(graph)
    assert graph == original  # counterfactual output never mutates natal structure
    assert report["original_component_count"] == expected["original_component_count"]
    assert report["minimum_added_gate_count"] == expected["minimum_added_gate_count"]
    assert [s["added_gates"] for s in report["minimum_solutions"]] == expected[
        "minimum_sets"
    ]
    assert report["minimum_solution_count"] == len(expected["minimum_sets"])
    assert report["minimum_solutions_preview"] == [
        {
            k: row[k]
            for k in (
                "added_gates",
                "newly_completed_channel_ids",
                "connects_all_original_components",
            )
        }
        for row in report["minimum_solutions"][:3]
    ]
    assert report["preview_is_truncated"] is (len(expected["minimum_sets"]) > 3)
    channels = {c["id"] for c in graph["channels"]}
    for row in report["minimum_solutions"]:
        assert (
            len(row["added_gates"])
            == len(set(row["added_gates"]))
            == expected["minimum_added_gate_count"]
        )
        assert not set(row["added_gates"]) & set(case["activated_gates"])
        replay = bodygraph(case["activated_gates"] + row["added_gates"], [])
        assert replay["definition"]["components"] == row["result_components"]
        assert (
            set(row["newly_completed_channel_ids"])
            == {c["id"] for c in replay["channels"]} - channels
        )
        assert row["connects_all_original_components"] is True
        assert replay["definition"]["kind"] == "single"


def test_a_partial_one_gate_merge_is_not_a_complete_bridge_for_three_components():
    case = next(c for c in PLAN["cases"] if c["id"] == "branch-1980-01-02")
    graph = bodygraph(case["activated_gates"], [])
    assert graph["definition"]["single_gate_bridges"]
    report = definition_bridging(graph)
    assert report["minimum_added_gate_count"] == 3
    assert report["minimum_solution_count"] == 23
    assert report["single_gate_merges"]
    for row in report["single_gate_merges"]:
        assert row["connects_all_original_components"] is False
        assert len(row["merged_original_component_indices"][0]) == 2


def test_shared_gate_costs_are_not_double_counted_across_channels():
    graph = bodygraph([25, 51, 43, 23, 28, 38], [])
    report = definition_bridging(graph)
    assert report["minimum_added_gate_count"] == 3
    assert report["minimum_solution_count"] == 1
    assert report["minimum_solutions"][0]["added_gates"] == [10, 20, 57]
    assert {"10-20", "10-57", "20-57"} <= set(
        report["minimum_solutions"][0]["newly_completed_channel_ids"]
    )


def test_paths_can_use_formerly_undefined_centers_and_all_six_long_route_options():
    graph = bodygraph([64, 47, 19, 49], [])
    assert graph["centers"]["throat"]["status"] == "completely_open"
    report = definition_bridging(graph)
    assert report["minimum_added_gate_count"] == 4
    assert report["minimum_solution_count"] == 6
    assert all(
        "throat" in row["result_components"][0] for row in report["minimum_solutions"]
    )


def test_bad_component_claim_cannot_be_used_as_a_bridge_input():
    graph = bodygraph([64, 47, 19, 49], [])
    graph["definition"]["components"] = [["head", "ajna", "root", "solar_plexus"]]
    with pytest.raises(ValueError, match="分组"):
        definition_bridging(graph)


@pytest.mark.parametrize(
    "tamper",
    [
        "minimum",
        "omitted_solution",
        "invented_gate",
        "preview",
        "scope",
        "boolean_type",
        "text",
    ],
)
def test_rehashed_false_bridge_and_its_description_are_rejected(tamper):
    run = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1980,
            birth_month=1,
            birth_day=2,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="Europe/London",
        ),
    )
    assert (
        verify_human_design_reading(run)["status"] == "verified_fixed_template_reading"
    )
    changed = deepcopy(run)
    report = changed["definition_bridging"]
    if tamper == "minimum":
        report["minimum_added_gate_count"] = 1
    elif tamper == "omitted_solution":
        report["minimum_solutions"].pop()
    elif tamper == "invented_gate":
        report["minimum_solutions"][0]["added_gates"][0] = 64
    elif tamper == "preview":
        report["preview_is_truncated"] = False
    elif tamper == "scope":
        report["scope"] = "这些门将在未来出现，并证明你需要某种伴侣。"
    elif tamper == "boolean_type":
        report["all_minimum_solutions_enumerated"] = 1
    else:
        changed["interpretation"][
            "definition_structure"
        ] = "加一个门就能连接整盘，原盘会变为单一定义。"
    changed["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "run_metadata"}
    )
    check = verify_human_design_reading(changed)
    assert check["status"] == "rejected"
    assert any(
        e.get("path") == "definition_bridging"
        or e["code"] == "text_or_template_basis_mismatch"
        for e in check["errors"]
    )
