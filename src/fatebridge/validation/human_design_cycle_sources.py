"""Verify source-context relationships, not the authenticity of supplied bytes."""

from typing import Any

from fatebridge.core.human_design_cycle_sources import SOURCE_SCOPE
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.public_output import same_public_value as _same_value
from fatebridge.validation.human_design_source_files import verify_source_files


def verify_cycle_sources(source: dict[str, Any], bodies: list[dict[str, Any]]) -> None:
    """Raise on malformed facts, unsupported sources or unbound observations."""
    files = source["files"]
    by_id = verify_source_files(files)
    contexts = source["contexts"]
    used_contexts: set[int] = set()
    used_files: set[str] = set()
    contexts_seen = set()
    editions: dict[tuple[str, str, int], int] = {}
    for context in contexts:
        body, model, status, ids = (
            context[k]
            for k in ("body", "native_return_flag_model", "status", "file_ids")
        )
        if body not in {"Saturn", "Uranus", "Chiron"} or model not in {
            "swieph",
            "moshier",
            "jpl",
        }:
            raise ValueError("Invalid cycle source body/model")
        if ids != sorted(set(ids)) or not set(ids) <= set(by_id):
            raise ValueError("Unbound cycle file ids")
        if status == "library_builtin":
            if model != "moshier" or body == "Chiron" or ids:
                raise ValueError("Asteroid orbit cannot be library-builtin")
        elif status == "identity_unavailable":
            if ids or (model == "moshier" and body != "Chiron"):
                raise ValueError("Invalid unidentified source context")
        elif status == "file_contexts_observed":
            required = ({0} if model != "moshier" else set()) | (
                {2} if body == "Chiron" else set()
            )
            allowed = (
                {0, 1} if model == "swieph" else {0} if model == "jpl" else set()
            ) | ({2} if body == "Chiron" else set())
            slots = {by_id[i]["slot"] for i in ids}
            if not required <= slots <= allowed or len(ids) != len(slots) or not ids:
                raise ValueError("Missing/irrelevant cycle source slot")
            for identity in ids:
                file = by_id[identity]
                expected_prefix = (
                    "jpl:" if model == "jpl" and file["slot"] == 0 else "se1:"
                )
                if not identity.startswith(expected_prefix):
                    raise ValueError("Asteroid and native-Earth source conflated")
                key = body, model, file["slot"]
                if key in editions and editions[key] != file["de_number"]:
                    raise ValueError("Cycle source edition changed")
                editions[key] = file["de_number"]
        else:
            raise ValueError("Invalid cycle source context status")
        expected_context = {
            "body": body,
            "native_return_flag_model": model,
            "status": status,
            "file_ids": ids,
        }
        key_context = body, model, status, tuple(ids)
        if key_context in contexts_seen or not _same_value(context, expected_context):
            raise ValueError("Duplicate or malformed cycle source context")
        contexts_seen.add(key_context)
        used_files.update(ids)
    for body in bodies:
        rows, indices = (
            body["evaluation_witnesses"],
            body["evaluation_source_context_indices"],
        )
        if len(rows) != len(indices):
            raise ValueError("Missing cycle source indices")
        for row, index in zip(rows, indices):
            if type(index) is not int or not 0 <= index < len(contexts):
                raise ValueError("Invalid cycle source index")
            context = contexts[index]
            if context["body"] != body["body"] or context[
                "native_return_flag_model"
            ] != position_flag_model(row[3]):
                raise ValueError("Cycle evaluation source mismatch")
            used_contexts.add(index)
    if used_contexts != set(range(len(contexts))) or used_files != set(by_id):
        raise ValueError("Unused cycle source contexts/files")
    unidentified = any(c["status"] == "identity_unavailable" for c in contexts)
    expected_source = {
        "method_id": "human_design_cycle_file_contexts_v1",
        "status": (
            "identity_incomplete"
            if unidentified
            else "observed_contexts_endpoint_verified"
        ),
        "files": files,
        "contexts": contexts,
        "has_unidentified_sources": unidentified,
        "configuration_checked": True,
        "endpoint_file_hashes_checked": True,
        "atomic_file_read_proven": False,
        "accuracy_certified": False,
        "scope": SOURCE_SCOPE,
    }
    if not _same_value(source, expected_source):
        raise ValueError("Cycle source policy or scope mismatch")
