"""Full delivery identity checks; synthetic role fixtures are not model grades."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_delivery_workflow import (
    capture_generation,
    expand_prepared,
    finalize_delivery,
    prepare_delivery,
    submit_review,
)
from fatebridge.validation.sukuyo_engineering import Artifact


def artifact(tmp_path, name, value):
    path = tmp_path / name
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
    path.write_bytes(raw)
    return Artifact(path, hashlib.sha256(raw).hexdigest(), "synthetic-fixture")


def descriptor(value):
    return {
        "path": str(value.path),
        "sha256": value.sha256,
        "source_version": value.source_version,
    }


def request(tmp_path):
    cases = []
    for case_id, question, encoding in [
        ("one", " 🌙全部条件？\n不要删未知。 ", "gzip_utf8_json"),
        ("two", "旧执行与本次执行能混用吗？", "utf8_json"),
    ]:
        scientific = {
            "case_id": case_id,
            "question": question,
            "evidence": {
                "negative": [False, None],
                "outside": ["0000-12-31"],
                "ref": "literal-not-a-reference",
                "large": "甲" * 5000,
            },
        }
        raw = json.dumps(scientific, ensure_ascii=False).encode()
        packed = gzip.compress(raw, mtime=0) if encoding == "gzip_utf8_json" else raw
        path = tmp_path / (case_id + ".view")
        path.write_bytes(packed)
        cases.append(
            {
                "case_id": case_id,
                "question": question,
                "view_file": str(path),
                "view_encoding": encoding,
                "view_sha256": hashlib.sha256(packed).hexdigest(),
                "decompressed_view_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    context = artifact(
        tmp_path,
        "context.json",
        {
            "failed": [1, None],
            "ref": {"dict": [["literal", "value"]]},
            "literal_ref": {"ref": "0" * 64},
        },
    )
    missing = Artifact(tmp_path / "not-acquired.json", "0" * 64, "synthetic-missing")
    protocol = artifact(
        tmp_path,
        "protocol.json",
        {
            "cases": cases,
            "review_standard": "whole question; zero substantive issues",
            "common_source_context": {
                "history": {"file": str(context.path), "sha256": context.sha256},
                "original": {"file": str(missing.path), "sha256": missing.sha256},
            },
        },
    )
    delivery_protocol = artifact(
        tmp_path,
        "delivery-protocol.json",
        {
            "original_protocol": descriptor(protocol),
            "scientific_protocol": descriptor(protocol),
            "required_contexts": [
                {"name": "history", "artifact": descriptor(context)},
                {"name": "original", "artifact": descriptor(missing)},
            ],
        },
    )
    return artifact(
        tmp_path,
        "request.json",
        {
            "protocol": descriptor(delivery_protocol),
            "contexts": [
                {"name": "history", "artifact": descriptor(context)},
                {"name": "original", "unavailable_reason": "not acquired"},
            ],
            "case_kinds": {"one": "domain", "two": "engineering"},
            "case_requirements": {
                "one": ["all date/half branches"],
                "two": ["version and execution scope"],
            },
        },
    )


def answer_chain(tmp_path):
    prepared = artifact(tmp_path, "prepared.json", prepare_delivery(request(tmp_path)))
    plan = json.loads(prepared.path.read_bytes())
    answers = artifact(
        tmp_path,
        "answers.json",
        {
            "prepared_input_sha256": plan["prepared_input_sha256"],
            "answers": [
                {
                    "case_id": row["case_id"],
                    "question": row["question"],
                    "answer": "synthetic whole answer; not semantic evidence",
                }
                for row in plan["cases"]
            ],
        },
    )
    receipt = artifact(
        tmp_path,
        "generation-receipt.json",
        {
            "data_kind": "synthetic",
            "input_sha256": plan["prepared_input_sha256"],
            "output_sha256": answers.sha256,
        },
    )
    generation = artifact(
        tmp_path, "generation.json", capture_generation(prepared, answers, receipt)
    )
    review_input = artifact(tmp_path, "review-input.json", submit_review(generation))
    return prepared, answers, generation, review_input


def test_all_scientific_values_and_literal_marker_objects_roundtrip(tmp_path):
    prepared = prepare_delivery(request(tmp_path))
    expanded = expand_prepared(prepared)
    assert [r["case_id"] for r in expanded["cases"]] == ["one", "two"]
    for row in expanded["cases"]:
        assert row["scientific_value"]["evidence"]["negative"] == [False, None]
        assert row["scientific_value"]["evidence"]["outside"] == ["0000-12-31"]
        assert row["scientific_value"]["evidence"]["ref"] == "literal-not-a-reference"
    assert expanded["contexts"][0]["value"]["ref"] == {"dict": [["literal", "value"]]}
    assert expanded["contexts"][0]["value"]["literal_ref"] == {"ref": "0" * 64}
    assert expanded["contexts"][1]["status"] == "unavailable"
    assert prepared["status"] == "prepared_not_generated"
    assert prepared["semantic_verdict"] == "not_assessed"


@pytest.mark.parametrize(
    "change", ["gzip", "decoded", "duplicate", "nonfinite", "question"]
)
def test_entire_view_is_verified_before_selection(tmp_path, change):
    req = request(tmp_path)
    data = json.loads(req.path.read_bytes())
    wrapper = json.loads(Path(data["protocol"]["path"]).read_bytes())
    protocol_path = Path(wrapper["scientific_protocol"]["path"])
    protocol = json.loads(protocol_path.read_bytes())
    row = protocol["cases"][0]
    path = Path(row["view_file"])
    raw = gzip.decompress(path.read_bytes())
    if change == "gzip":
        path.write_bytes(path.read_bytes() + b"corrupt")
    elif change == "decoded":
        row["decompressed_view_sha256"] = "0" * 64
    else:
        if change == "duplicate":
            raw = raw[:-1] + b', "hidden": 1, "hidden": 2}'
        elif change == "nonfinite":
            raw = raw[:-1] + b', "hidden": 1e999}'
        else:
            value = json.loads(raw)
            value["question"] = "changed original question"
            raw = json.dumps(value).encode()
        packed = gzip.compress(raw, mtime=0)
        path.write_bytes(packed)
        row["view_sha256"] = hashlib.sha256(packed).hexdigest()
        row["decompressed_view_sha256"] = hashlib.sha256(raw).hexdigest()
    new_protocol = artifact(tmp_path, "protocol2.json", protocol)
    wrapper["scientific_protocol"] = descriptor(new_protocol)
    data["protocol"] = descriptor(artifact(tmp_path, "delivery2.json", wrapper))
    req = artifact(tmp_path, "request2.json", data)
    with pytest.raises((ValueError, OSError)):
        prepare_delivery(req)


@pytest.mark.parametrize(
    "change", ["drop", "reorder", "duplicate", "question", "input"]
)
def test_capture_rejects_changed_scope_or_input(tmp_path, change):
    prepared, answers, _, _ = answer_chain(tmp_path)
    data = json.loads(answers.path.read_bytes())
    if change == "drop":
        data["answers"].pop()
    elif change == "reorder":
        data["answers"].reverse()
    elif change == "duplicate":
        data["answers"][1] = deepcopy(data["answers"][0])
    elif change == "question":
        data["answers"][0]["question"] = data["answers"][0]["question"].strip()
    else:
        data["prepared_input_sha256"] = "0" * 64
    changed = artifact(tmp_path, "changed.json", data)
    receipt = artifact(
        tmp_path,
        "changed-receipt.json",
        {
            "input_sha256": data["prepared_input_sha256"],
            "output_sha256": changed.sha256,
        },
    )
    with pytest.raises(ValueError):
        capture_generation(prepared, changed, receipt)


def test_source_drift_after_preparation_is_not_rebound_to_current_bytes(tmp_path):
    prepared, answers, _, _ = answer_chain(tmp_path)
    Path(tmp_path / "context.json").write_text('{"new": true}')
    plan = json.loads(prepared.path.read_bytes())
    receipt = artifact(
        tmp_path,
        "receipt2.json",
        {
            "input_sha256": plan["prepared_input_sha256"],
            "output_sha256": answers.sha256,
        },
    )
    with pytest.raises(ValueError, match="SHA mismatch"):
        capture_generation(prepared, answers, receipt)


@pytest.mark.parametrize(
    "mode",
    ["missing_row", "missing_array", "wrong_input", "false_pass", "adverse", "pass"],
)
def test_finalization_requires_complete_explicit_review(tmp_path, mode):
    _, _, _, ready = answer_chain(tmp_path)
    value = json.loads(ready.path.read_bytes())
    review = {
        "review_input_sha256": value["review_input_sha256"],
        "reviews": [
            {
                "case_id": row["case_id"],
                "verdict": "pass",
                "material_errors": [],
                "important_omissions": [],
                "unassessed_material_claims": [],
            }
            for row in value["whole_review_packet"]["items"]
        ],
    }
    if mode == "missing_row":
        review["reviews"].pop()
    elif mode == "missing_array":
        review["reviews"][0].pop("important_omissions")
    elif mode == "wrong_input":
        review["review_input_sha256"] = "0" * 64
    elif mode in {"false_pass", "adverse"}:
        review["reviews"][0]["unassessed_material_claims"] = [
            "unknown substantive assertion"
        ]
        if mode == "adverse":
            review["reviews"][0]["verdict"] = "needs_revision"
    judgment = artifact(tmp_path, "review.json", review)
    receipt = artifact(
        tmp_path,
        "review-receipt.json",
        {
            "data_kind": "synthetic",
            "input_sha256": review["review_input_sha256"],
            "output_sha256": judgment.sha256,
        },
    )
    if mode in {"missing_row", "missing_array", "wrong_input", "false_pass"}:
        with pytest.raises(ValueError):
            finalize_delivery(ready, judgment, receipt)
    else:
        final = finalize_delivery(ready, judgment, receipt)
        assert final["all_whole_answers_passed_declared_review"] == (mode == "pass")
        assert final["totals"]["unassessed_material_claims"] == (mode == "adverse")
        assert not final["semantic_judgments_independently_verified"]
        assert final["original_gate_verdict"] == "not_assessed"
        assert final["real_world_efficacy"] == "not_assessed"


def test_cli_prepares_real_files_and_never_overwrites(tmp_path):
    req = request(tmp_path)
    output = tmp_path / "cli-prepared.json"
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts/sukuyo/sukuyo_delivery_workflow.py"
    )
    command = [
        sys.executable,
        str(script),
        "prepare",
        "--request",
        str(req.path),
        "--request-sha256",
        req.sha256,
        "--request-version",
        req.source_version,
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True)
    assert first.returncode == 0, first.stderr
    raw = output.read_bytes()
    assert json.loads(raw)["case_count"] == 2
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == raw


def reseal(value, field):
    body = {key: item for key, item in value.items() if key != field}
    raw = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return {**body, field: hashlib.sha256(raw).hexdigest()}


@pytest.mark.parametrize(
    "change,message",
    [
        ("missing", "Missing or cyclic"),
        ("cycle", "Missing or cyclic"),
        ("corrupt", "Shared value fingerprint"),
        ("unreachable", "Unreachable shared"),
        ("tag", "Invalid tagged"),
    ],
)
def test_valid_outer_seal_does_not_hide_bad_shared_tree(tmp_path, change, message):
    value = prepare_delivery(request(tmp_path))
    key = value["cases"][0]["scientific_value"]["ref"]
    if change == "missing":
        value["cases"][0]["scientific_value"] = {"ref": "f" * 64}
    elif change == "cycle":
        value["shared_values"][key] = {"ref": key}
    elif change == "corrupt":
        value["shared_values"][key] = {"dict": [["changed", True]]}
    elif change == "unreachable":
        value["shared_values"]["a" * 64] = {"dict": []}
    else:
        value["cases"][0]["scientific_value"] = {"bad_tag": []}
    value = reseal(value, "prepared_input_sha256")
    with pytest.raises(ValueError, match=message):
        expand_prepared(value)


@pytest.mark.parametrize(
    "change", ["all", "one", "duplicate", "selection", "identity", "inventory_omission"]
)
def test_required_protocol_contexts_cannot_be_silently_omitted(tmp_path, change):
    req = request(tmp_path)
    data = json.loads(req.path.read_bytes())
    if change == "all":
        data["contexts"] = []
    elif change == "one":
        data["contexts"].pop()
    elif change == "duplicate":
        data["contexts"][1] = deepcopy(data["contexts"][0])
    elif change == "selection":
        data["contexts"][0]["pointer"] = "/failed"
    elif change == "identity":
        data["contexts"][0]["artifact"]["source_version"] = "another version"
    else:
        wrapper = json.loads(Path(data["protocol"]["path"]).read_bytes())
        wrapper["required_contexts"].pop()
        data["contexts"].pop()
        data["protocol"] = descriptor(
            artifact(tmp_path, "changed-wrapper.json", wrapper)
        )
    changed = artifact(tmp_path, "changed-request.json", data)
    with pytest.raises(ValueError):
        prepare_delivery(changed)


def test_named_unavailable_context_keeps_its_required_identity(tmp_path):
    value = prepare_delivery(request(tmp_path))
    missing = value["contexts"][1]
    assert missing["status"] == "unavailable"
    assert missing["expected_artifact"]["path"].endswith("not-acquired.json")
    assert missing["expected_pointer"] == ""
    assert missing["reason"] == "not acquired"


@pytest.mark.parametrize("change", ["standard", "order"])
def test_scientific_protocol_cannot_change_original_scope(tmp_path, change):
    req = request(tmp_path)
    data = json.loads(req.path.read_bytes())
    wrapper = json.loads(Path(data["protocol"]["path"]).read_bytes())
    scientific = json.loads(Path(wrapper["scientific_protocol"]["path"]).read_bytes())
    if change == "standard":
        scientific["review_standard"] = "one easier passing subset"
    else:
        scientific["cases"].reverse()
    wrapper["scientific_protocol"] = descriptor(
        artifact(tmp_path, "changed-scientific.json", scientific)
    )
    data["protocol"] = descriptor(artifact(tmp_path, "changed-wrapper.json", wrapper))
    with pytest.raises(ValueError, match="Original whole questions"):
        prepare_delivery(artifact(tmp_path, "changed-request.json", data))


def review_value(ready):
    value = json.loads(ready.path.read_bytes())
    return {
        "review_input_sha256": value["review_input_sha256"],
        "reviews": [
            {
                "case_id": row["case_id"],
                "verdict": "pass",
                "material_errors": [],
                "important_omissions": [],
                "unassessed_material_claims": [],
            }
            for row in value["whole_review_packet"]["items"]
        ],
    }


@pytest.mark.parametrize("role", ["generation", "review"])
@pytest.mark.parametrize("field", ["input_sha256", "output_sha256"])
def test_external_receipts_cannot_be_reused_for_other_artifacts(tmp_path, role, field):
    prepared, answers, _, ready = answer_chain(tmp_path)
    if role == "generation":
        plan = json.loads(prepared.path.read_bytes())
        proof = {
            "input_sha256": plan["prepared_input_sha256"],
            "output_sha256": answers.sha256,
        }
        proof[field] = "0" * 64
        receipt = artifact(tmp_path, "wrong-receipt.json", proof)
        with pytest.raises(ValueError, match="receipt"):
            capture_generation(prepared, answers, receipt)
    else:
        value = review_value(ready)
        judgment = artifact(tmp_path, "review.json", value)
        proof = {
            "input_sha256": value["review_input_sha256"],
            "output_sha256": judgment.sha256,
        }
        proof[field] = "0" * 64
        receipt = artifact(tmp_path, "wrong-receipt.json", proof)
        with pytest.raises(ValueError, match="receipt"):
            finalize_delivery(ready, judgment, receipt)


@pytest.mark.parametrize(
    "changed", ["answers.json", "generation.json", "review-input.json", "protocol.json"]
)
def test_actual_dependency_drift_between_stages_is_rejected(tmp_path, changed):
    _, _, generation, ready = answer_chain(tmp_path)
    value = review_value(ready)
    judgment = artifact(tmp_path, "review.json", value)
    receipt = artifact(
        tmp_path,
        "review-receipt.json",
        {
            "input_sha256": value["review_input_sha256"],
            "output_sha256": judgment.sha256,
        },
    )
    (tmp_path / changed).write_text('{"drift": true}')
    with pytest.raises(ValueError, match="SHA mismatch"):
        if changed == "review-input.json":
            finalize_delivery(ready, judgment, receipt)
        else:
            submit_review(generation)


@pytest.mark.parametrize(
    "field", ["material_errors", "important_omissions", "unassessed_material_claims"]
)
@pytest.mark.parametrize("bad", [None, {}, "missing"])
def test_all_issue_arrays_must_be_explicit_lists(tmp_path, field, bad):
    _, _, _, ready = answer_chain(tmp_path)
    value = review_value(ready)
    if bad == "missing":
        value["reviews"][0].pop(field)
    else:
        value["reviews"][0][field] = bad
    judgment = artifact(tmp_path, "review.json", value)
    receipt = artifact(
        tmp_path,
        "review-receipt.json",
        {
            "input_sha256": value["review_input_sha256"],
            "output_sha256": judgment.sha256,
        },
    )
    with pytest.raises(ValueError, match="Missing issue arrays"):
        finalize_delivery(ready, judgment, receipt)


@pytest.mark.parametrize("change", ["duplicate", "order", "verdict"])
def test_review_scope_and_verdict_are_not_silently_normalized(tmp_path, change):
    _, _, _, ready = answer_chain(tmp_path)
    value = review_value(ready)
    if change == "duplicate":
        value["reviews"][1] = deepcopy(value["reviews"][0])
    elif change == "order":
        value["reviews"].reverse()
    else:
        value["reviews"][0]["verdict"] = "maybe_pass"
    judgment = artifact(tmp_path, "review.json", value)
    receipt = artifact(
        tmp_path,
        "review-receipt.json",
        {
            "input_sha256": value["review_input_sha256"],
            "output_sha256": judgment.sha256,
        },
    )
    with pytest.raises(ValueError):
        finalize_delivery(ready, judgment, receipt)
