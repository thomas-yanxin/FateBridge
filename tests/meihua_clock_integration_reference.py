"""Keep the initial clock evidence while proving the same edit on a parallel baseline."""

import ast
import gzip
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from tests.meihua_clock_evolution_reference import (
    INPUT_FOLDER,
)
from tests.meihua_clock_evolution_reference import (
    MANIFEST_SHA256 as INITIAL_MANIFEST_SHA256,
)
from tests.meihua_clock_evolution_reference import canonical, read_json, require, sha
from tests.meihua_clock_source_scope import SCOPE, assert_clock_source_scope

FOLDER = Path(__file__).parent / "fixtures/meihua_clock_integration_v63"
MANIFEST_SHA256 = "83c109f00da2d30044cecbec056d276b804a9db988e089f0d8db92c7529708f6"


def scope_before_folder():
    return FOLDER / "scope-before"


def ast_hash(path):
    return sha(
        ast.dump(ast.parse(path.read_bytes()), include_attributes=False).encode()
    )


def fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Parallel clock manifest changed")
    for name, expected in read_json(raw)["files"].items():
        require(
            sha((FOLDER / name).read_bytes()) == expected,
            "Parallel clock reference changed: " + name,
        )


@lru_cache(maxsize=2)
def _load(folder_key, manifest_key, initial_key):
    initial = read_json(initial_key)
    binding = read_json((FOLDER / "binding.json").read_bytes())
    require(
        binding["id"] == "meihua_clock_parallel_integration_v63"
        and binding["initial_clock_evolution_manifest_sha256"]
        == INITIAL_MANIFEST_SHA256,
        "Parallel clock initial evidence rebound",
    )
    require(
        binding["same_seven_module_inverse_proved_for_both_baselines"] is True
        and binding["full_source_scope_narrowed"] is False
        and binding["independent_truth_or_new_prediction_evidence"] is False
        and binding["original_eight_raw_mismatches_remain"] is True
        and binding["parallel_changes_are_not_credited_as_owned_work"] is True,
        "Parallel clock evidence scope changed",
    )
    policy = binding["current_source_policy"]
    for key in [
        "clock_full_file_before_sha256",
        "clock_full_file_after_sha256",
        "changed_named_ast_guards",
        "additional_complete_source_guards",
    ]:
        require(
            policy[key] == initial[key], "Owned clock guards changed in integration"
        )
    require(
        set(policy["seven_modified_module_ast_scope"]) == set(SCOPE),
        "Parallel clock module scope changed",
    )
    for name, (before_name, _) in SCOPE.items():
        first = FOLDER / "initial-after" / name
        require(
            ast_hash(first)
            == initial["seven_modified_module_ast_scope"][name][
                "after_module_ast_sha256"
            ],
            "Initial clock module rebound",
        )
        entry = policy["seven_modified_module_ast_scope"][name]
        before = FOLDER / entry["before_file"]
        after = FOLDER / entry["integration_after_file"]
        require(
            sha(before.read_bytes()) == entry["before_sha256"]
            and ast_hash(before) == entry["before_module_ast_sha256"]
            and ast_hash(after) == entry["after_module_ast_sha256"]
            and before.read_bytes()
            == (scope_before_folder() / before_name).read_bytes(),
            "Parallel clock module source rebound",
        )
    assert_clock_source_scope(FOLDER / "initial-after", INPUT_FOLDER)
    assert_clock_source_scope(FOLDER / "integration-after", scope_before_folder())
    require(
        set(policy["additional_named_ast_guards"])
        == set(initial["additional_named_ast_guards"]),
        "Parallel named clock scope changed",
    )
    changed = []
    for path, members in initial["additional_named_ast_guards"].items():
        require(
            set(policy["additional_named_ast_guards"][path]) == set(members),
            "Parallel named clock member scope changed",
        )
        for name, old in members.items():
            if policy["additional_named_ast_guards"][path][name] != old:
                changed.append(path + ":" + name)
    require(
        changed
        == binding["additional_named_AST_changed_by_parallel_baseline"]
        == ["application/execution.py:validate_output"],
        "Parallel named clock changes widened",
    )
    # This is a full output comparison, not a replacement oracle for the old gates.
    from tests import meihua_clock_evolution_reference as clock

    expected = read_json(
        gzip.decompress((clock.FOLDER / "native-after.json.gz").read_bytes())
    )
    rows = read_json(gzip.decompress((FOLDER / "native-rows.json.gz").read_bytes()))
    require(
        len(rows) == len(expected) == binding["native_cases"] == 23927
        and binding["native_output_changes_since_initial_component_after"] == 0,
        "Parallel native clock queue shrunk",
    )
    for i, (row, old) in enumerate(zip(rows, expected, strict=True)):
        require(
            row["index"] == old["index"] == i
            and row["tool"] == old["tool"]
            and row["arguments"] == old["arguments"]
            and row["actual_sha256"] == row["expected_sha256"] == old["sha256"],
            "Parallel native clock output changed",
        )
    return policy


def source_policy(initial):
    fingerprints()
    return deepcopy(_load(str(FOLDER.resolve()), MANIFEST_SHA256, canonical(initial)))
