"""Caller mutation cannot change cached metadata or any numeric calculation."""

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.timing import _copy_timing_info

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-timing-cache-isolation-v1"
PROTOCOL = json.loads((STUDY / "protocol.json").read_text())


def without_declared_copy_change(text, after):
    tree = ast.parse(text)
    copied_helper = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_copy_timing_info"
    ]
    assert len(copied_helper) == 1
    tree.body.remove(copied_helper[0])
    imports = [
        n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "copy"
    ]
    assert len(imports) == int(after)
    if after:
        assert [(a.name, a.asname) for a in imports[0].names] == [("deepcopy", None)]
        tree.body.remove(imports[0])
    return ast.dump(tree, include_attributes=False)


def test_every_other_current_timing_ast_node_is_exact_published_nominal_policy():
    name = "src/fatebridge/core/timing.py"
    before = STUDY / "before" / name
    assert (
        hashlib.sha256(before.read_bytes()).hexdigest()
        == PROTOCOL["before_files"][name]
    )
    assert without_declared_copy_change(before.read_text(), False) == (
        without_declared_copy_change((ROOT / name).read_text(), True)
    )


def test_scope_guard_rejects_a_numeric_change_outside_the_copy_helper():
    before = (STUDY / "before/src/fatebridge/core/timing.py").read_text()
    current = (ROOT / "src/fatebridge/core/timing.py").read_text()
    assert "delta_days / 3" in current
    changed = current.replace("delta_days / 3", "delta_days / 4", 1)
    assert without_declared_copy_change(before, False) != (
        without_declared_copy_change(changed, True)
    )


def mutable_ids(value):
    found = set()
    if isinstance(value, dict):
        found.add(id(value))
        for v in value.values():
            found.update(mutable_ids(v))
    elif isinstance(value, (list, tuple)):
        if isinstance(value, list):
            found.add(id(value))
        for v in value:
            found.update(mutable_ids(v))
    return found


@pytest.mark.parametrize(
    "nested",
    [
        {"solver": {"precision": {"verified": False}}},
        {"retflags": [1, 2, 4]},
        {"solver": [{"samples": [1.25, 2.5]}, {"versions": ["v1"]}]},
        {"tuple": ({"a": [1, {"b": 2}]},)},
    ],
)
def test_each_return_and_cache_own_every_nested_mutable_container(nested):
    source = {
        "pillar": "甲子",
        "solar_term_window": {
            "start_term": {"solar_model_details": nested},
            "next_term": {"solar_model_details": deepcopy(nested)},
            "days_since_start": 1.25,
        },
    }
    expected = deepcopy(source)
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    assert first == second == expected
    assert not mutable_ids(source) & mutable_ids(first)
    assert not mutable_ids(source) & mutable_ids(second)
    assert not mutable_ids(first) & mutable_ids(second)
    first["solar_term_window"]["start_term"]["solar_model_details"].clear()
    assert source == second == expected


def test_no_window_scalar_cache_payload_is_also_a_new_caller_owned_dictionary():
    source = {"pillar": "甲子", "hour": 3}
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    first.clear()
    assert source == second == {"pillar": "甲子", "hour": 3}


def test_all5_saved_actual_initial_objects_are_preserved_after_caller_mutation():
    before = json.loads(
        (
            ROOT
            / "docs/validation/bazi-nominal-elapsed-policy-v1/cache-policy-first.json"
        ).read_text()
    )
    after = json.loads((STUDY / "cache-after-first.json").read_text())
    assert before["mismatches"] == 4 and after["mismatches"] == 0
    assert [r["case"] for r in before["records"]] == [
        r["case"] for r in after["records"]
    ]
    for old, new in zip(before["records"], after["records"]):
        assert old["before_mutation"] == new["before_mutation"]
        assert old["before_mutation"] == new["after_mutation"]
        assert new["changed_paths"] == []
