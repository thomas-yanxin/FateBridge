"""Validate and seal external evaluation inputs without exposing the other split.

These are public competition cases, not independently verified outcomes. Runtime
checks and semantic review are separate denominators; neither is prediction proof.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SUITE_ID = "mingli-bench-v1"
DATASET_KIND = "public_competition"
SPLITS = ("development", "holdout")
LAYERS = ("input_quality", "interpretation_fidelity", "consultation_boundary")


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(data: bytes, description: str) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {description}: expected an object")
    return value


def _safe_file(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("External manifest file path must be nonempty")
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(
        root.resolve()
    ):
        raise ValueError("External manifest path escapes the suite")
    if not path.is_file() or path.is_symlink():
        raise ValueError("External manifest file missing or symlinked: " + relative)
    return path


def _cases(document: dict[str, Any]) -> list[dict[str, Any]]:
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("External suite must contain cases")
    ids: set[str] = set()
    source_splits: dict[str, str] = {}
    identity_splits: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Invalid external case")
        name = case.get("id")
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("External case IDs must be nonempty and unique")
        if name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError("Unsafe external case ID")
        ids.add(name)
        split = case.get("split")
        if split not in SPLITS or case.get("evaluation_layer") not in LAYERS:
            raise ValueError("Unknown external split or evaluation layer")
        for field, seen in (
            ("source_case_id", source_splits),
            ("identity_key", identity_splits),
        ):
            identity = case.get(field)
            if not isinstance(identity, str) or not identity:
                raise ValueError("Missing external case " + field)
            if identity in seen and seen[identity] != split:
                raise ValueError("External birth identity leaks across splits")
            seen[identity] = split
        if (
            not case.get("prompt")
            or not case.get("manual_review")
            or not case.get("source")
        ):
            raise ValueError(
                "External case lacks prompt, review criteria or provenance"
            )
        if case.get("reference_request") and case.get("no_calculation"):
            raise ValueError("No-calculation cases cannot have reference calculations")
    return cases


def _select(
    cases: list[dict[str, Any]], split: str, case_ids: Iterable[str] | None
) -> list[dict[str, Any]]:
    if split not in SPLITS:
        raise ValueError("Unknown external split")
    available = {case["id"] for case in cases if case["split"] == split}
    requested = list(case_ids or [])
    if len(requested) != len(set(requested)):
        raise ValueError("Duplicate requested external case IDs")
    if set(requested) - available:
        raise ValueError(
            "Unknown case or case outside selected split: "
            + ", ".join(sorted(set(requested) - available))
        )
    selected = [
        case
        for case in cases
        if case["split"] == split and (not requested or case["id"] in requested)
    ]
    if not selected:
        raise ValueError("Selected external split is empty")
    return selected


def load_external_suite(
    root: Path, split: str = "development", case_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Verify the full source corpus before selecting a single immutable split."""
    manifest_data = (root / "manifest.json").read_bytes()
    manifest = _object(manifest_data, "external manifest")
    if manifest.get("schema_version") != 1 or manifest.get("suite_id") != SUITE_ID:
        raise ValueError("Unsupported external suite manifest")
    if manifest.get("dataset_kind", manifest.get("dataset_type")) != DATASET_KIND:
        raise ValueError("External suite must be labelled public_competition")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("External manifest must freeze all corpus artifacts")
    verified: dict[str, bytes] = {}
    for entry in files:
        name = entry["path"]
        if name in verified:
            raise ValueError("Duplicate external manifest file")
        data = _safe_file(root, name).read_bytes()
        if sha256(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError("External artifact integrity mismatch: " + name)
        verified[name] = data
    required = [
        manifest[key] for key in ("cases_file", "corpus_file", "split_manifest_file")
    ]
    if not set(required) <= verified.keys():
        raise ValueError("External manifest does not hash all required artifacts")
    document = _object(verified[manifest["cases_file"]], "external cases")
    cases = _cases(document)
    if (
        document.get("suite_id") != SUITE_ID
        or document.get("dataset_kind", document.get("dataset_type")) != DATASET_KIND
    ):
        raise ValueError("External case document kind or suite mismatch")
    assignments = _object(
        verified[manifest["split_manifest_file"]], "external split manifest"
    )
    identities = assignments.get("identities")
    if not isinstance(identities, list) or not identities:
        raise ValueError("External split manifest needs birth identities")
    sources: dict[str, dict[str, Any]] = {}
    seen_identity: dict[str, str] = {}
    for row in identities:
        source_id = row["source_case_id"]
        split_name = row["split"]
        if source_id in sources or split_name not in SPLITS:
            raise ValueError("Duplicate source case or unknown source split")
        for field in ("identity_key", "birth_fingerprint"):
            key = row.get(field)
            if not isinstance(key, str) or not key:
                raise ValueError("Missing source birth identity")
            identity = field + ":" + key
            if identity in seen_identity and seen_identity[identity] != split_name:
                raise ValueError("External birth identity leaks across source splits")
            seen_identity[identity] = split_name
        sources[source_id] = row
    for split_name in SPLITS:
        listed = assignments.get(split_name)
        expected = {key for key, row in sources.items() if row["split"] == split_name}
        if (
            not isinstance(listed, list)
            or len(listed) != len(set(listed))
            or set(listed) != expected
        ):
            raise ValueError(
                "External split membership disagrees with source identities"
            )
    for case in cases:
        source = sources.get(case["source_case_id"])
        if source is None or any(
            case[key] != source[key]
            for key in ("identity_key", "birth_fingerprint", "split")
        ):
            raise ValueError("External case disagrees with source split identity")
        if case["source"].get("commit") != manifest.get("source_commit"):
            raise ValueError("External case source revision disagrees with manifest")
        if (
            case["source"].get("raw_file")
            and case["source"]["raw_file"] not in verified
        ):
            raise ValueError("External case source artifact lacks an integrity hash")
    corpus = _object(verified[manifest["corpus_file"]], "external corpus")
    records = corpus.get("records")
    if not isinstance(records, list) or len(records) != len(sources):
        raise ValueError("External corpus and source identity coverage disagree")
    record_ids: set[str] = set()
    for record in records:
        source_id = record["source_case_id"]
        source = sources.get(source_id)
        if (
            source_id in record_ids
            or source is None
            or any(
                record[key] != source[key]
                for key in ("identity_key", "birth_fingerprint", "split")
            )
        ):
            raise ValueError("External corpus disagrees with source split identity")
        normalized = record.get("normalized_input")
        if not isinstance(normalized, dict):
            raise ValueError("External corpus needs normalized birth identity inputs")
        identity_inputs = {
            key: normalized[key]
            for key in ("gender", "year", "month", "day", "time_expression")
        }
        # Keep this independently checked against the importer's documented v1
        # recipe. Stored labels alone must not hide duplicate source births.
        fingerprint = sha256(
            (json.dumps(identity_inputs, ensure_ascii=False, indent=2) + "\n").encode()
        )
        if (
            record["birth_fingerprint"] != fingerprint
            or record["identity_key"] != "birth:" + fingerprint
        ):
            raise ValueError("External corpus birth fingerprint does not match inputs")
        record_ids.add(source_id)
    selected = _select(cases, split, case_ids)
    provenance = {
        "suite_id": SUITE_ID,
        "dataset_kind": DATASET_KIND,
        "source_commit": manifest.get("source_commit"),
        "source_manifest_sha256": sha256(manifest_data),
        "source_dataset_sha256": sha256(verified[manifest["cases_file"]]),
        "source_artifacts": files,
        "split_policy": manifest.get("split_policy"),
    }
    return _sealed(selected, split, provenance)


def _sealed(
    cases: list[dict[str, Any]], split: str, provenance: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "suite_id": SUITE_ID,
        "dataset_kind": DATASET_KIND,
        "split": split,
        "selection_kind": "frozen_single_split",
        "provenance": provenance,
        "cases": cases,
    }


def freeze_external_selection(document: dict[str, Any], output: Path) -> bytes:
    """Retain selected source excerpts/criteria; never copy the other split or raw corpus."""
    dataset = json_bytes(document)
    receipt = {
        "schema_version": 1,
        "suite_id": SUITE_ID,
        "split": document["split"],
        "selected_dataset_sha256": sha256(dataset),
        "selected_case_ids": [case["id"] for case in document["cases"]],
        "provenance": document["provenance"],
    }
    (output / "external-suite-receipt.json").write_bytes(json_bytes(receipt))
    return dataset


def load_frozen_selection(
    path: Path, split: str, case_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Rerun from the sealed preparation instead of the mutable upstream checkout."""
    data = path.read_bytes()
    document = _object(data, "frozen external dataset")
    receipt = _object(
        (path.parent / "external-suite-receipt.json").read_bytes(), "external receipt"
    )
    if (
        document.get("selection_kind") != "frozen_single_split"
        or document.get("suite_id") != SUITE_ID
    ):
        raise ValueError("External --cases-file must be a frozen suite selection")
    if document.get("dataset_kind") != DATASET_KIND or document.get("split") != split:
        raise ValueError("Frozen external dataset split or kind mismatch")
    cases = _cases(document)
    if any(case["split"] != split for case in cases):
        raise ValueError("Frozen external dataset mixes splits")
    if (
        receipt.get("selected_dataset_sha256") != sha256(data)
        or receipt.get("split") != split
    ):
        raise ValueError("Frozen external dataset integrity mismatch")
    if receipt.get("schema_version") != 1 or receipt.get("suite_id") != SUITE_ID:
        raise ValueError("Unsupported frozen external receipt")
    if receipt.get("selected_case_ids") != [
        case["id"] for case in cases
    ] or receipt.get("provenance") != document.get("provenance"):
        raise ValueError("Frozen external receipt disagrees with selection")
    return _sealed(_select(cases, split, case_ids), split, document["provenance"])


def evaluation_summary(
    document: dict[str, Any], records: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Keep selected, executed, mechanical and unreviewed semantic counts explicit."""
    records = records or []
    cases = document["cases"]
    selected = Counter(case["evaluation_layer"] for case in cases)
    by_id = {case["id"]: case for case in cases}
    executed = Counter(by_id[row["case"]]["evaluation_layer"] for row in records)
    passed = Counter(
        by_id[row["case"]]["evaluation_layer"]
        for row in records
        if row["mechanical_checks_passed"]
    )
    return {
        "suite_id": SUITE_ID,
        "dataset_kind": DATASET_KIND,
        "split": document["split"],
        "split_unit": "source_case_id_and_birth_identity",
        "selected_source_case_count": len({case["source_case_id"] for case in cases}),
        "independence": "Source-case split within a public competition; upstream content may exist in model training; no claim of pretraining-unseen data",
        "workspace_isolation": "Dataset, answers, review criteria and evaluation reports are excluded from the model workspace; filtering is not OS-level confidentiality from the same user account",
        "semantic_acceptance": "pending" if records else "not_run",
        "real_world_outcome_observations": 0,
        "source_provenance": document["provenance"],
        "layer_denominators": {
            layer: {
                "selected": selected[layer],
                "executed": executed[layer],
                "mechanical_passed": passed[layer],
                "semantic_reviewed": 0,
                "semantic_status": "pending",
            }
            for layer in LAYERS
        },
    }
