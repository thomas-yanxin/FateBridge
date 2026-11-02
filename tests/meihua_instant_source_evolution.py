"""A stricter input-moment guard cannot erase any old output or source gate."""

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from tests.meihua_guard_originals import original_helper
from tests.meihua_instant_binding_reference import FOLDER as INPUT_FOLDER
from tests.meihua_instant_binding_reference import (
    MANIFEST_SHA256 as INPUT_MANIFEST_SHA256,
)
from tests.meihua_instant_binding_reference import load as input_reference

FOLDER = Path(__file__).parent / "fixtures/meihua_instant_evolution_v64"
MANIFEST_SHA256 = "19b075b114c2b9329d6cc255a908c39f0854d3192eb7c0604113984e2a382834"
DEPENDENCIES = {
    "utils/civil_clock.py",
    "utils/timezones.py",
    "utils/tzif_transitions.py",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return sha(canonical(value).encode())


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate instant reference key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Non-finite instant reference value: " + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def ast_hash(path):
    return sha(
        ast.dump(ast.parse(path.read_bytes()), include_attributes=False).encode()
    )


def default_zone_ast(path):
    found = []
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(t, ast.Name) and t.id == "DEFAULT_BIRTH_TIMEZONE"
                for t in targets
            ):
                found.append(node)
    require(len(found) == 1, "Default timezone declaration missing or duplicated")
    return sha(ast.dump(found[0], include_attributes=False).encode())


def fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Instant evolution manifest changed")
    for name, expected in parse(raw)["files"].items():
        require(
            sha((FOLDER / name).read_bytes()) == expected,
            "Instant evolution reference changed: " + name,
        )
    input_reference()
    from tests import meihua_instant_binding_reference as faults
    from tests import meihua_instant_source_scope as scope

    require(
        sha(original_helper(Path(faults.__file__).name).read_bytes())
        == parse((FOLDER / "frozen-fault-helper-lock.json").read_bytes())["sha256"]
        == sha((FOLDER / "frozen-fault-helper.py").read_bytes()),
        "Pre-change instant fault helper changed",
    )
    require(
        original_helper(Path(scope.__file__).name).read_bytes()
        == (FOLDER / "reviewed-source-scope.py").read_bytes(),
        "Instant reverse-AST helper changed",
    )
    from tests import meihua_clock_evolution_reference as clock

    clock.fingerprints()


def rows(name):
    return parse(gzip.decompress((FOLDER / name).read_bytes()))


@lru_cache(maxsize=2)
def _load(folder_key, manifest_key):
    data = parse((FOLDER / "binding.json").read_bytes())
    require(
        data["id"] == "meihua_instant_validation_evolution_v64"
        and data["original_instant_truth_manifest_sha256"] == INPUT_MANIFEST_SHA256,
        "Instant source evolution rebound",
    )
    require(
        data["phase"]
        == "after_one_production_file_and_verified_complete_native_and_guarded_public_receipts_before_source_guard_migration",
        "Unknown instant evolution phase",
    )
    require(
        data["production_modules_changed"] == 1
        and data["astronomy_lunar_or_chapter_rules_changed"] is False
        and data["existing_clock_binding_AST_reversed_exactly_to_before"] is True,
        "Instant production scope widened",
    )
    require(
        data["data_are_after_production_engineering_receipts_not_independent_truth"]
        is True
        and data["new_model_evaluations"] == data["new_real_prediction_outcomes"] == 0
        and data["physical_clock_or_prediction_accuracy_certified"] is False,
        "Instant engineering receipts relabelled as accuracy",
    )
    require(
        data["original_v63_source_guard_relabelled_passed"] is False
        and data["original_raw_23595_gate_still_eight_changes"] is True
        and data["original_9272_gate_relabelled_passed"] is False,
        "Original failed gates erased",
    )
    from tests import meihua_clock_evolution_reference as clock

    old = parse(gzip.decompress((clock.FOLDER / "native-after.json.gz").read_bytes()))
    before, after = rows("before-native23927.json.gz"), rows(
        "after-native23927.json.gz"
    )
    require(
        len(old) == len(before) == len(after) == data["native_cases"] == 23927,
        "Instant native queue shrunk",
    )
    seen = set()
    for i, (a, z, original) in enumerate(zip(before, after, old, strict=True)):
        identity = canonical({"tool": a["tool"], "arguments": a["arguments"]})
        require(
            identity not in seen
            and a == z
            and a["index"] == original["index"] == i
            and a["tool"] == original["tool"]
            and a["arguments"] == original["arguments"]
            and a["expected_sha256"] == a["actual_sha256"] == original["sha256"],
            "Instant native identity or complete output changed",
        )
        seen.add(identity)
    public_before, public_after = rows("before-public-time340.json.gz"), rows(
        "after-public-time340.json.gz"
    )
    time_rows = [r for r in old if r["tool"] == "meihua_analysis"]
    require(
        len(public_before)
        == len(public_after)
        == len(time_rows)
        == data["guarded_public_time_contexts"]
        == 340,
        "Guarded public time queue shrunk",
    )
    for a, z, original in zip(public_before, public_after, time_rows, strict=True):
        require(
            a == z
            and a["index"] == original["index"]
            and a["arguments"] == original["arguments"],
            "Guarded public time identity or output changed",
        )
    cases, protocol = input_reference()
    bound_before, bound_after = rows("before-bound-clock25.json.gz"), rows(
        "after-bound-clock25.json.gz"
    )
    packets = [
        parse(s)
        for s in gzip.open(
            FOLDER / "valid25-before-packets.jsonl.gz", "rt", encoding="utf-8"
        )
    ]
    require(
        len(bound_before)
        == len(bound_after)
        == len(packets)
        == data["bound_new_clock_contexts"]
        == 25,
        "Bound input clock queue shrunk",
    )
    for a, z, case, packet in zip(
        bound_before, bound_after, cases, packets, strict=True
    ):
        require(
            a == z
            and a["id"] == case["id"] == packet["id"]
            and a["arguments"] == case["arguments"] == packet["request"]
            and a["sha256"] == digest(packet["result"]),
            "Complete bound clock packet or identity changed",
        )
        actual = packet["result"]["meihua"]["calendar_policy"]["civil_clock_resolution"]
        require(
            actual["instant_utc"] == case["expected_utc"]
            and actual["local_datetime"] == case["expected_local"]
            and type(actual["fold"]) is int
            and actual["fold"] == case["expected_fold"],
            "Hand-derived clock fact rebound",
        )
    initial = parse((FOLDER / "instant-binding-before.json").read_bytes())
    prior = parse((FOLDER / "instant-public-before.json").read_bytes())
    current = parse((FOLDER / "instant-public-after.json").read_bytes())
    require(
        initial["false_acceptances"]
        == data["standalone_before_guard_false_acceptances"]
        == 34
        and prior["before_public_false_acceptances"]
        == data["public_before_false_acceptances"]
        == 30
        and current["after_public_false_acceptances"]
        == data["public_after_false_acceptances"]
        == 0,
        "Original or new fault results relabelled",
    )
    negatives = protocol["faults"]
    require(
        len(prior["before_public_execute_tool_rows"])
        == len(current["after_public_execute_tool_rows"])
        == len(negatives)
        == 34,
        "Fault input queue shrunk",
    )
    old_rejections = []
    for p, z, expected in zip(
        prior["before_public_execute_tool_rows"],
        current["after_public_execute_tool_rows"],
        negatives,
        strict=True,
    ):
        require(
            p["id"] == z["id"] == expected["id"]
            and z["after_public_execute_tool_accepts"] is False
            and z["status_code"] == 500
            and z["error_code"] == "internal_error",
            "Fault identity or rejection changed",
        )
        if not p["before_public_execute_tool_accepts"]:
            old_rejections.append(p["id"])
    require(
        old_rejections
        == [
            "month_elapsed_basis_wall",
            "month_start_timestamp_changed",
            "month_next_timestamp_changed",
            "month_elapsed_bool",
        ],
        "Original typed-output rejections changed",
    )
    negative = parse((FOLDER / "original-v63-source-guard.json").read_bytes())
    require(
        negative["original_source_guard_passed"] is False
        and negative["exact_original_source_guard_executed"] is True
        and negative["message"]
        == "Listed source file changed: application/meihua_clock_binding.py",
        "Original v63 source guard relabelled passing",
    )
    entry = data["changed_complete_source_guard"]
    require(
        entry["path"] == "application/meihua_clock_binding.py"
        and sha((FOLDER / "before-clock-binding.py").read_bytes())
        == entry["before_sha256"]
        and ast_hash(FOLDER / "before-clock-binding.py")
        == entry["before_module_ast_sha256"]
        and (FOLDER / "before-clock-binding.py").read_bytes()
        == (INPUT_FOLDER / "before-clock-binding.py").read_bytes()
        and sha((FOLDER / "after-clock-binding.py").read_bytes())
        == entry["after_sha256"]
        and ast_hash(FOLDER / "after-clock-binding.py")
        == entry["after_module_ast_sha256"],
        "Instant changed source binding differs",
    )
    # Mirror the real module path without importing either frozen producer.
    import tempfile

    from tests.meihua_instant_source_scope import assert_only_instant_validation_added

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "application/meihua_clock_binding.py"
        target.parent.mkdir()
        target.write_bytes((FOLDER / "after-clock-binding.py").read_bytes())
        assert_only_instant_validation_added(
            Path(tmp), FOLDER / "before-clock-binding.py"
        )
    require(
        set(data["additional_complete_source_guards"]) == DEPENDENCIES,
        "Instant dependency guard scope changed",
    )
    for path, h in data["additional_complete_source_guards"].items():
        require(
            sha((FOLDER / "dependency-before" / path).read_bytes()) == h,
            "Unchanged dependency preimage differs",
        )
    require(
        set(data["additional_named_ast_guards"]) == {"utils/places.py"}
        and data["additional_named_ast_guards"]["utils/places.py"]
        == {"DEFAULT_BIRTH_TIMEZONE": default_zone_ast(FOLDER / "before-places.py")},
        "Default timezone guard scope widened",
    )
    require(
        data["full_source_guard_count_before"] == 120
        and data["full_source_guard_count_after"] == 123
        and data["named_AST_count_before"] == 29
        and data["named_AST_count_after"] == 30,
        "Instant source guard count changed",
    )
    return data


def load():
    fingerprints()
    return deepcopy(_load(str(FOLDER.resolve()), MANIFEST_SHA256))


def additional_source_paths():
    load()
    return DEPENDENCIES | {"utils/places.py"}


def extend_instant_guards(full, named, root):
    data = load()
    entry = data["changed_complete_source_guard"]
    require(
        len(full) == 120
        and sum(len(v) for v in named.values()) == 29
        and full[entry["path"]] == entry["before_sha256"],
        "Original instant guard scope or preimage changed",
    )
    full[entry["path"]] = entry["after_sha256"]
    for path, h in data["additional_complete_source_guards"].items():
        require(path not in full, "New dependency guard replaced old source scope")
        full[path] = h
    for path, guards in data["additional_named_ast_guards"].items():
        require(path not in named, "Default timezone guard replaced old members")
        named[path] = deepcopy(guards)
    require(
        default_zone_ast(root / "utils/places.py")
        == named["utils/places.py"]["DEFAULT_BIRTH_TIMEZONE"],
        "Instant default-timezone AST changed",
    )
    from tests.meihua_instant_source_scope import assert_only_instant_validation_added

    assert_only_instant_validation_added(root, FOLDER / "before-clock-binding.py")
    require(
        ast_hash(root / entry["path"]) == entry["after_module_ast_sha256"],
        "Instant validation AST changed",
    )
    require(
        len(full) == 123 and sum(len(v) for v in named.values()) == 30,
        "Instant source guard scope changed",
    )
    return full, named
