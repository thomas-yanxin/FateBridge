"""Versioned engineering projection; original raw output gates remain negative.

New table states were checked against the preimplementation visual literals.
The approved payload dictionary is a later engineering receipt, not an oracle
for classical authority or real-world prediction.
"""

import gzip
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from tests.meihua_guard_originals import original_helper
from tests.meihua_volume5_source_scope import (
    NEW,
    SEASONAL,
    assert_old_iso_guard_body_preserved,
    assert_only_volume5_comparison_added,
)

FOLDER = Path(__file__).parent / "fixtures/meihua_volume5_evolution_v67"
MANIFEST_SHA256 = "d64af6ee647e36df1acc851d24a28522e43cce63bda592b8efb97d715ad976dd"
INPUT_FOLDER = FOLDER.parent / "meihua_volume5_strength_v1"
INPUT_SHA256 = "90964bebd6127adc8e1e78acb0eafaf4ed14021321aa45aa20f8243abc49bb97"
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate volume-five reference key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Nonfinite volume-five reference: " + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def _manifest():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Volume-five evolution manifest changed")
    return read_json(raw)


def _checked(name, manifest):
    raw = (FOLDER / name).read_bytes()
    require(
        sha(raw) == manifest["files"][name], "Volume-five reference changed: " + name
    )
    return raw


def load():
    manifest = _manifest()
    for name in manifest["files"]:
        _checked(name, manifest)
    raw = (INPUT_FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == INPUT_SHA256, "Volume-five input manifest changed")
    for name, h in read_json(raw)["files"].items():
        require(
            sha((INPUT_FOLDER / name).read_bytes()) == h,
            "Volume-five input changed: " + name,
        )
    data = read_json(_checked("binding.json", manifest))
    require(
        data["input_manifest_sha256"] == INPUT_SHA256,
        "Volume-five input binding changed",
    )
    require(
        data["before_source_guard_count"] == 125
        and data["declared_after_full_source_guard_count"] == 127
        and data["named_AST_count"] == 30,
        "Volume-five source guard scope changed",
    )
    require(
        data["raw_after_guard_passed"] is False
        and data["raw_original_complete_output_equality_relabelled_passed"] is False
        and data["raw_complete_output_changes"] == 21991
        and data["original_weather_output_hashes_unchanged"] == 1936
        and data["new_model_evaluations"] == data["new_real_prediction_outcomes"] == 0
        and all(value is False for value in data["four_full_score_flags"].values()),
        "Original failures or evidence scope relabelled",
    )
    require(
        sha(original_helper("meihua_volume5_source_scope.py").read_bytes())
        == data["scope_helper_sha256"],
        "Volume-five scope reviewer changed",
    )
    for name in [
        "meihua_candidate_history_reference.py",
        "meihua_clock_evolution_reference.py",
        "meihua_source_evolution_reference.py",
    ]:
        require(
            original_helper(name).read_bytes()
            == (FOLDER / ("before-" + name)).read_bytes(),
            "Original historical helper changed: " + name,
        )
    followup_fingerprints()
    return data


def overlay(root):
    """Link read-only source bytes, detach only the seasonal preimage."""
    manager = tempfile.TemporaryDirectory()
    target = Path(manager.name)
    for file in Path(root).rglob("*"):
        if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
            continue
        path = target / file.relative_to(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(file, path)
    path = target / SEASONAL
    path.unlink()
    path.write_bytes((FOLDER / "before-seasonal-reading.py").read_bytes())
    return manager, target


def reviewed_volume5_guards(original_data, root, prior, previous, old_iso):
    data = load()
    root = Path(root)
    require(
        set(data["after_full_files"]) == NEW | {SEASONAL},
        "Volume-five source allowlist widened",
    )
    for path, h in data["after_full_files"].items():
        require(
            sha((root / path).read_bytes()) == h,
            "Volume-five source file changed: " + path,
        )
    assert_only_volume5_comparison_added(root, FOLDER / "before-seasonal-reading.py")
    assert_old_iso_guard_body_preserved(
        original_helper("meihua_iso_clock_source_evolution.py"),
        FOLDER / "before-meihua_iso_clock_source_evolution.py",
    )
    manager, normalized = overlay(root)
    try:
        full, named = old_iso(original_data, normalized, prior, previous)
    finally:
        manager.cleanup()
    require(
        len(full) == 125 and sum(map(len, named.values())) == 30,
        "Prior complete source scope changed",
    )
    require(
        full[SEASONAL] == data["before_seasonal_sha256"] and not NEW & full.keys(),
        "Volume-five preimage changed",
    )
    full.update(data["after_full_files"])
    require(len(full) == 127, "Volume-five complete source scope differs")
    for path, h in full.items():
        require(
            sha((root / path).read_bytes()) == h, "Listed source file changed: " + path
        )
    return full, named


@lru_cache(maxsize=1)
def _layers(raw):
    data = read_json(gzip.decompress(raw))
    require(len(data) == 5112, "Approved added-layer scope changed")
    for h, layer in data.items():
        require(
            sha(canonical(layer).encode()) == h, "Approved added-layer identity differs"
        )
    return data


def reviewed_previous_output_shape(value):
    """Remove only validated added comparisons; preserve every other field.

    This is intentionally not an identity projection of current full outputs.
    Historical adapters below still validate the complete remaining output.
    """
    manifest = _manifest()
    approved = _layers(_checked("added-layer-deduplicated.json.gz", manifest))
    result = deepcopy(value)
    interpretation = result["interpretation"]
    parents = [interpretation] + list(interpretation.get("casting_readings") or [])
    for parent in parents:
        q = parent.get("seasonal_qualification")
        if q is None:
            continue
        require(
            isinstance(q, dict) and "volume5_table_comparison" in q,
            "Native current output lost volume-five comparison",
        )
        layer = q["volume5_table_comparison"]
        key = sha(canonical(layer).encode())
        require(
            key in approved and layer == approved[key],
            "Native current output has an unapproved volume-five comparison",
        )
        require(
            layer["month_branch"] == q["month_branch"],
            "Native current output has a foreign comparison month",
        )
        require(
            layer["primary_month_basis"] == q["basis"],
            "Native current output has a foreign comparison basis",
        )
        require(
            len(layer["roles"]) == len(q["roles"]) == 5,
            "Native current output comparison lost roles",
        )
        for current, old in zip(layer["roles"], q["roles"], strict=True):
            require(
                all(current[k] == old[k] for k in ["role", "trigram", "element"])
                and current["trigram_fact_path"] == old["fact_path"]
                and current["primary_strength"] == old["strength"]
                and current["primary_strength_fact_path"] == old["strength_fact_path"],
                "Native current output comparison belongs to different roles",
            )
        del q["volume5_table_comparison"]
    return result


def reviewed_restore_pre_v58_candidate_summary(value, *, tool, arguments):
    from tests import meihua_candidate_history_reference as history

    try:
        previous_shape = reviewed_previous_output_shape(value)
    except (KeyError, TypeError, ValueError) as error:
        raise history.HistoryBindingError(str(error)) from error
    return history.restore_pre_v58_candidate_summary(
        previous_shape, tool=tool, arguments=arguments
    )


def reviewed_restore_clock_before_native(value, arguments):
    from tests.meihua_clock_evolution_reference import restore_clock_before_native

    return restore_clock_before_native(reviewed_previous_output_shape(value), arguments)


PARTIAL_FOLDER = FOLDER.parent / "meihua_volume5_partial_v67"
PARTIAL_SHA256 = "235b0dfbc6ec4d5c102ddf0ddb3d3cd7a8d9f069ebd2c5f76559f053005c5399"
RAW_FOLDER = FOLDER.parent / "meihua_volume5_raw9272_v67"
RAW_SHA256 = "0f6938e47c8579d88e6bd556b0a2c23d090a0637b7ba6da882f2d49fabdf0162"


def followup_fingerprints():
    for folder, expected in [
        (PARTIAL_FOLDER, PARTIAL_SHA256),
        (RAW_FOLDER, RAW_SHA256),
    ]:
        raw = (folder / "manifest.json").read_bytes()
        require(sha(raw) == expected, "Volume-five followup manifest changed")
        for name, h in read_json(raw)["files"].items():
            require(
                sha((folder / name).read_bytes()) == h,
                "Volume-five followup reference changed: " + name,
            )
    require(
        original_helper("meihua_time_history_reference.py").read_bytes()
        == (PARTIAL_FOLDER / "before-meihua_time_history_reference.py").read_bytes(),
        "Original partial time helper changed",
    )
    policy = read_json((RAW_FOLDER / "policy.json").read_bytes())
    business = INPUT_FOLDER.parent / "meihua_trigram_symbols_v1/old-business.json.gz"
    require(
        sha(business.read_bytes()) == policy["original_business_gz_sha256"],
        "Original 9272 inputs changed",
    )
    require(
        policy["current_raw_original_equality_gate_expected_to_remain_failed"] is True
        and policy["prior_shape_original36_mismatch_gate_also_remains_failed"] is True,
        "Original 9272 failures relabelled",
    )
    return policy


def reviewed_current_raw_failed_indices():
    followup_fingerprints()
    result = read_json(
        (RAW_FOLDER / "expected-current-raw-failed-indices.json").read_bytes()
    )
    require(
        len(result) == len(set(result)) == 7352,
        "Current raw 9272 failure scope changed",
    )
    return result


def reviewed_restore_old_time_fixture_view(value):
    """Validate the same addition before delegating to unchanged old time checks."""
    from tests.meihua_time_history_reference import restore_old_time_fixture_view

    try:
        followup_fingerprints()
        previous_shape = reviewed_previous_output_shape(value)
    except (KeyError, TypeError, ValueError) as error:
        raise AssertionError(str(error)) from error
    return restore_old_time_fixture_view(previous_shape)
