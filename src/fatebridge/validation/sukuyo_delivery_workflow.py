"""Prepare complete evidence, then bind real external generation and review.

This module never calls a model or assigns substantive semantic judgments.
An external-role receipt is a declaration whose bytes are checked, not an
authenticated account of earlier model behavior or a trusted timestamp.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.validation.sukuyo_engineering import (
    Artifact,
    _ArtifactReader,
    _fields,
    _finite_float,
    _nonfinite,
    _object,
    _sequence,
    _text,
)
from fatebridge.validation.sukuyo_semantic_packet import (
    build_whole_answer_review_packet,
)

PREPARED = "sukuyo_whole_delivery_prepared_v2"
GENERATED = "sukuyo_whole_delivery_generation_v2"
REVIEW_INPUT = "sukuyo_whole_delivery_review_input_v2"
ISSUES = ("material_errors", "important_omissions", "unassessed_material_claims")


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _descriptor(value: Artifact) -> dict[str, str]:
    return {
        "path": str(value.path.resolve()),
        "sha256": value.sha256,
        "source_version": value.source_version,
    }


def _artifact(value: Any, base: Path) -> Artifact:
    row = _fields(value, {"path", "sha256", "source_version"}, set())
    if re.fullmatch(r"[0-9a-f]{64}", _text(row["sha256"])) is None:
        raise ValueError("Artifact requires a full SHA256 fingerprint")
    return Artifact(
        base / _text(row["path"]), _text(row["sha256"]), _text(row["source_version"])
    )


def _strict(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_object,
        parse_constant=_nonfinite,
        parse_float=_finite_float,
    )


def _seal(value: dict[str, Any], name: str) -> dict[str, Any]:
    return {**value, name: _digest(value)}


def _check_seal(value: Any, name: str, format_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("format") != format_name:
        raise ValueError("Unexpected delivery stage")
    body = {key: item for key, item in value.items() if key != name}
    if _digest(body) != value.get(name):
        raise ValueError("Delivery stage content changed")
    return body


def _encode(value: Any, pool: dict[str, Any]) -> Any:
    if not isinstance(value, (dict, list)):
        return value
    identity = _digest(value)
    large = len(json.dumps(value, ensure_ascii=False)) >= 4096
    if large and identity in pool:
        return {"ref": identity}
    if isinstance(value, dict):
        node = {"dict": [[key, _encode(item, pool)] for key, item in value.items()]}
    else:
        node = {"list": [_encode(item, pool) for item in value]}
    if large:
        pool[identity] = node
        return {"ref": identity}
    return node


def expand_prepared(value: dict[str, Any]) -> dict[str, Any]:
    """Losslessly expand tagged JSON trees; literal marker-shaped data is safe."""
    _check_seal(value, "prepared_input_sha256", PREPARED)
    pool = value["shared_values"]
    if not isinstance(pool, dict):
        raise ValueError("A shared-value pool is required")
    seen: set[str] = set()
    active: set[str] = set()
    cache: dict[str, Any] = {}

    def decode(node: Any) -> Any:
        if not isinstance(node, dict):
            if isinstance(node, list):
                raise ValueError("Untagged list in shared tree")
            return node
        if set(node) == {"ref"}:
            key = node["ref"]
            if not isinstance(key, str) or key not in pool or key in active:
                raise ValueError("Missing or cyclic shared reference")
            seen.add(key)
            if key not in cache:
                active.add(key)
                expanded = decode(pool[key])
                active.remove(key)
                if _digest(expanded) != key:
                    raise ValueError("Shared value fingerprint changed")
                cache[key] = expanded
            return deepcopy(cache[key])
        if set(node) == {"list"} and isinstance(node["list"], list):
            return [decode(item) for item in node["list"]]
        if set(node) == {"dict"} and isinstance(node["dict"], list):
            pairs = []
            for pair in node["dict"]:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Invalid tagged object")
                key, item = pair
                if not isinstance(key, str):
                    raise ValueError("Non-text JSON object key")
                pairs.append((key, decode(item)))
            return _object(pairs)
        raise ValueError("Invalid tagged shared tree")

    expanded = deepcopy(value)
    for row in expanded["cases"]:
        row["scientific_value"] = decode(row["scientific_value"])
    for context in expanded["contexts"]:
        if context["status"] == "available":
            context["value"] = decode(context["value"])
    if seen != set(pool):
        raise ValueError("Unreachable shared values")
    complete = {"cases": expanded["cases"], "contexts": expanded["contexts"]}
    if _digest(complete) != value["complete_values_sha256"]:
        raise ValueError("Complete scientific or context values changed")
    expanded.pop("shared_values")
    return expanded


def _protocols(
    reader: _ArtifactReader, artifact: Artifact
) -> tuple[dict[str, Any], list[Any], str, dict[str, dict[str, Any]]]:
    definition = _fields(
        reader.bind(artifact)["value"],
        {"original_protocol", "scientific_protocol", "required_contexts"},
        set(),
    )
    base = artifact.path.resolve().parent
    original_artifact = _artifact(definition["original_protocol"], base)
    scientific_artifact = _artifact(definition["scientific_protocol"], base)
    original = reader.bind(original_artifact)["value"]
    scientific = reader.bind(scientific_artifact)["value"]
    original_cases = _sequence(original["cases"])
    cases = _sequence(scientific["cases"])
    original_questions = [
        (_text(row["case_id"]), _text(row["question"])) for row in original_cases
    ]
    if (
        original_questions
        != [(_text(row["case_id"]), _text(row["question"])) for row in cases]
        or original["review_standard"] != scientific["review_standard"]
    ):
        raise ValueError("Original whole questions, order or standard changed")
    required: dict[str, dict[str, Any]] = {}
    for entry in _sequence(definition["required_contexts"]):
        row = _fields(entry, {"name", "artifact"}, {"pointer"})
        name = _text(row["name"])
        pointer = row.get("pointer", "")
        if name in required or not isinstance(pointer, str):
            raise ValueError("Duplicate or invalid required context")
        expected = _artifact(row["artifact"], base)
        required[name] = {"artifact": expected, "pointer": pointer}
    for parent, parent_artifact in (
        (original, original_artifact),
        (scientific, scientific_artifact),
    ):
        common = parent.get("common_source_context", {})
        if not isinstance(common, dict):
            raise ValueError("Protocol common contexts need an explicit mapping")
        for value in common.values():
            if isinstance(value, str):
                name, identity = value, None
            elif isinstance(value, dict) and "file" in value:
                name, identity = _text(value["file"]), value.get("sha256")
            else:
                raise ValueError("Unsupported protocol context declaration")
            path = (parent_artifact.path.resolve().parent / name).resolve()
            if not any(
                entry["artifact"].path.resolve() == path
                and entry["pointer"] == ""
                and (identity is None or entry["artifact"].sha256 == identity)
                for entry in required.values()
            ):
                raise ValueError("Required inventory omits a complete protocol context")
    bindings = {
        "original_protocol_artifact": _descriptor(original_artifact),
        "scientific_protocol_artifact": _descriptor(scientific_artifact),
    }
    return bindings, cases, _text(original["review_standard"]), required


def prepare_delivery(request: Artifact) -> dict[str, Any]:
    """Actually read every declared case view before external generation."""
    reader = _ArtifactReader()
    bound = reader.bind(request)
    data = _fields(
        bound["value"],
        {"protocol", "contexts", "case_kinds", "case_requirements"},
        set(),
    )
    base = request.path.resolve().parent
    protocol_artifact = _artifact(data["protocol"], base)
    protocol_bindings, cases, standard, required = _protocols(reader, protocol_artifact)
    scientific_base = Path(
        protocol_bindings["scientific_protocol_artifact"]["path"]
    ).parent
    if not cases:
        raise ValueError("The full protocol cannot be empty")
    identities = [_text(row["case_id"]) for row in cases]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate protocol case id")
    for name in ("case_kinds", "case_requirements"):
        if not isinstance(data[name], dict) or set(data[name]) != set(identities):
            raise ValueError(
                "Every original case needs a declared route and requirements"
            )
    contexts = []
    names: set[str] = set()
    for entry in _sequence(data["contexts"]):
        row = _fields(entry, {"name"}, {"artifact", "pointer", "unavailable_reason"})
        name = _text(row["name"])
        if name in names:
            raise ValueError("Duplicate context name")
        if name not in required:
            raise ValueError("Context not present in the frozen required inventory")
        names.add(name)
        expected = required[name]
        if "unavailable_reason" in row:
            if "artifact" in row or "pointer" in row:
                raise ValueError("Unavailable evidence cannot also supply an artifact")
            contexts.append(
                {
                    "name": name,
                    "status": "unavailable",
                    "reason": _text(row["unavailable_reason"]),
                    "expected_artifact": _descriptor(expected["artifact"]),
                    "expected_pointer": expected["pointer"],
                }
            )
        else:
            artifact = _artifact(row["artifact"], base)
            pointer = row.get("pointer", "")
            if (
                _descriptor(artifact) != _descriptor(expected["artifact"])
                or pointer != expected["pointer"]
            ):
                raise ValueError("Required context identity or selection changed")
            selected = reader.bind(artifact, pointer)
            contexts.append({"name": name, "status": "available", **selected})
    if names != set(required):
        raise ValueError("Missing required context declarations")
    loaded = []
    for row, case_id in zip(cases, identities, strict=True):
        question = _text(row["question"])
        kind = data["case_kinds"][case_id]
        if kind not in {"domain", "engineering", "uncertain"}:
            raise ValueError("Unknown declared route")
        requirements = _sequence(data["case_requirements"][case_id])
        if not requirements:
            raise ValueError("Whole-question requirements cannot be empty")
        for text in requirements:
            _text(text)
        path = scientific_base / _text(row["view_file"])
        raw = path.read_bytes()
        identity = _text(row["view_sha256"])
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ValueError("Scientific view byte fingerprint changed")
        encoding = row.get("view_encoding", "utf8_json")
        if encoding == "gzip_utf8_json":
            decoded = gzip.decompress(raw)
            if hashlib.sha256(decoded).hexdigest() != row.get(
                "decompressed_view_sha256"
            ):
                raise ValueError("Decompressed scientific view fingerprint changed")
        elif encoding == "utf8_json":
            decoded = raw
        else:
            raise ValueError("Unknown scientific-view encoding")
        science = _strict(decoded)
        if (
            not isinstance(science, dict)
            or science.get("case_id") != case_id
            or science.get("question") != question
        ):
            raise ValueError("Scientific view does not belong to the exact question")
        loaded.append(
            {
                "case_id": case_id,
                "question": question,
                "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
                "request_kind": kind,
                "requirements": requirements,
                "scientific_binding": {
                    "path": str(path.resolve()),
                    "sha256": identity,
                    "bytes": len(raw),
                    "encoding": encoding,
                    "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
                    "decoded_bytes": len(decoded),
                },
                "scientific_value": science,
            }
        )
    complete = _digest({"cases": loaded, "contexts": contexts})
    pool: dict[str, Any] = {}
    for row in loaded:
        row["scientific_value"] = _encode(row["scientific_value"], pool)
    for context in contexts:
        if context["status"] == "available":
            context["value"] = _encode(context["value"], pool)
    result = _seal(
        {
            "format": PREPARED,
            "request_artifact": _descriptor(request),
            "protocol_artifact": _descriptor(protocol_artifact),
            **protocol_bindings,
            "review_standard": standard,
            "case_count": len(loaded),
            "cases": loaded,
            "contexts": contexts,
            "shared_values": pool,
            "complete_values_sha256": complete,
            "status": "prepared_not_generated",
            "semantic_verdict": "not_assessed",
            "original_gate_verdict": "not_assessed",
            "real_world_efficacy": "not_assessed",
        },
        "prepared_input_sha256",
    )
    expand_prepared(result)
    return result


def _prepared(artifact: Artifact) -> dict[str, Any]:
    value = _ArtifactReader().bind(artifact)["value"]
    if not isinstance(value, dict):
        raise ValueError("Prepared input must be an object")
    expand_prepared(value)
    request = _artifact(value["request_artifact"], artifact.path.resolve().parent)
    if prepare_delivery(request) != value:
        raise ValueError("Prepared input or its source files drifted")
    return value


def _receipt(receipt: Artifact, input_sha: str, output_sha: str) -> dict[str, Any]:
    bound = _ArtifactReader().bind_utf8_file(receipt)
    value = bound["value"]
    if (
        not isinstance(value, dict)
        or value.get("input_sha256") != input_sha
        or value.get("output_sha256") != output_sha
    ):
        raise ValueError("External-role receipt does not bind this input and output")
    return bound


def capture_generation(
    prepared: Artifact, answers: Artifact, receipt: Artifact
) -> dict[str, Any]:
    """Bind an external role's first output; this function never generates it."""
    plan = _prepared(prepared)
    bound = _ArtifactReader().bind_utf8_file(answers)
    output = bound["value"]
    if output.get("prepared_input_sha256") != plan["prepared_input_sha256"]:
        raise ValueError("Answers refer to a different generation input")
    rows = _sequence(output["answers"])
    if [row.get("case_id") for row in rows] != [
        row["case_id"] for row in plan["cases"]
    ]:
        raise ValueError("Answer case order and set must preserve the entire protocol")
    for answer, question in zip(rows, plan["cases"], strict=True):
        if answer.get("question") != question["question"]:
            raise ValueError("Answer question changed")
        _text(answer.get("answer"))
    source_hashes = {
        plan["request_artifact"]["sha256"],
        plan["protocol_artifact"]["sha256"],
        plan["original_protocol_artifact"]["sha256"],
        plan["scientific_protocol_artifact"]["sha256"],
    }
    source_hashes.update(row["scientific_binding"]["sha256"] for row in plan["cases"])
    source_hashes.update(
        row["sha256"] for row in plan["contexts"] if row["status"] == "available"
    )
    if answers.sha256 in source_hashes:
        raise ValueError("Answers cannot serve as their own evidence")
    declared = _receipt(receipt, plan["prepared_input_sha256"], answers.sha256)
    return {
        "format": GENERATED,
        "prepared_artifact": _descriptor(prepared),
        "answers_artifact": _descriptor(answers),
        "execution_receipt_artifact": _descriptor(receipt),
        "execution_receipt": declared,
        "case_count": len(rows),
        "status": "external_output_bound_not_reviewed",
        "external_execution_authenticated": False,
        "semantic_verdict": "not_assessed",
    }


def submit_review(generation: Artifact) -> dict[str, Any]:
    """Make the full original question/answer/evidence input for an external reviewer."""
    value = _ArtifactReader().bind(generation)["value"]
    if not isinstance(value, dict) or value.get("format") != GENERATED:
        raise ValueError("A generation record is required")
    base = generation.path.resolve().parent
    prepared = _artifact(value["prepared_artifact"], base)
    answers = _artifact(value["answers_artifact"], base)
    receipt = _artifact(value["execution_receipt_artifact"], base)
    if capture_generation(prepared, answers, receipt) != value:
        raise ValueError("Generation record changed")
    packet = build_whole_answer_review_packet(prepared, answers, id_field="case_id")
    return _seal(
        {
            "format": REVIEW_INPUT,
            "generation_artifact": _descriptor(generation),
            "whole_review_packet": packet,
            "review_standard": packet["request"]["value"]["review_standard"],
            "status": "awaiting_external_review",
            "semantic_verdict": "not_assessed",
            "original_gate_verdict": "not_assessed",
        },
        "review_input_sha256",
    )


def finalize_delivery(
    review_input: Artifact, review: Artifact, receipt: Artifact
) -> dict[str, Any]:
    """Summarize complete declared judgments, preserving failed and unknown claims."""
    reader = _ArtifactReader()
    ready = reader.bind(review_input)["value"]
    _check_seal(ready, "review_input_sha256", REVIEW_INPUT)
    generation = _artifact(
        ready["generation_artifact"], review_input.path.resolve().parent
    )
    if submit_review(generation) != ready:
        raise ValueError("Review input or its dependencies changed")
    bound = reader.bind_utf8_file(review)
    value = bound["value"]
    if value.get("review_input_sha256") != ready["review_input_sha256"]:
        raise ValueError("Review refers to a different whole-answer input")
    declared = _receipt(receipt, ready["review_input_sha256"], review.sha256)
    rows = _sequence(value["reviews"])
    cases = ready["whole_review_packet"]["items"]
    if [row.get("case_id") for row in rows] != [row["case_id"] for row in cases]:
        raise ValueError("Review must cover every original case exactly in order")
    totals = {"pass": 0, "needs_revision": 0, **{name: 0 for name in ISSUES}}
    for row in rows:
        verdict = row.get("verdict")
        if verdict not in {"pass", "needs_revision"}:
            raise ValueError("Explicit whole-answer verdict required")
        for name in ISSUES:
            if name not in row or not isinstance(row[name], list):
                raise ValueError("Missing issue arrays are unknown, never zero")
            totals[name] += len(row[name])
        if verdict == "pass" and any(row[name] for name in ISSUES):
            raise ValueError("Passing review conflicts with substantive issues")
        totals[verdict] += 1
    return {
        "format": "sukuyo_whole_delivery_final_v2",
        "review_input": reader.bind_utf8_file(review_input),
        "review": bound,
        "execution_receipt": declared,
        "case_count": len(cases),
        "totals": totals,
        "all_whole_answers_passed_declared_review": totals["pass"] == len(cases),
        "status": "complete_external_declarations_bound",
        "semantic_judgments_independently_verified": False,
        "external_execution_authenticated": False,
        "original_gate_verdict": "not_assessed",
        "source_independence": "not_assessed",
        "real_world_efficacy": "not_assessed",
        "scope": "Whole-question external delivery, not a replacement of historical native results or proof of source/prediction truth.",
    }
