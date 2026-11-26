"""Validate and seal external evaluation inputs without exposing the other split.

These are public competition cases, not independently verified outcomes. Runtime
checks and semantic review are separate denominators; neither is prediction proof.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import JsonValue

SUITE_ID: Literal["mingli-bench-v2"] = "mingli-bench-v2"
DATASET_KIND: Literal["public_competition"] = "public_competition"
SPLITS = ("development", "holdout")
LAYERS = ("input_quality", "interpretation_fidelity", "consultation_boundary")


class ExternalSelection(TypedDict):
    schema_version: Literal[1]
    suite_id: Literal["mingli-bench-v2"]
    dataset_kind: Literal["public_competition"]
    split: str
    selection_kind: Literal["frozen_single_split"]
    provenance: dict[str, JsonValue]
    cases: list[dict[str, JsonValue]]


class ExternalReceipt(TypedDict):
    schema_version: Literal[1]
    suite_id: Literal["mingli-bench-v2"]
    split: str
    selected_dataset_sha256: str
    selected_case_ids: list[JsonValue]
    provenance: dict[str, JsonValue]


def json_bytes(value: JsonValue | ExternalSelection | ExternalReceipt) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(data: bytes, description: str) -> dict[str, JsonValue]:
    value: object = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {description}: expected an object")
    else:
        pass
    return value


def _safe_file(root: Path, relative: str) -> Path:
    if not relative:
        raise ValueError("External manifest file path must be nonempty")
    else:
        pass
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(
        root.resolve()
    ):
        raise ValueError("External manifest path escapes the suite")
    else:
        pass
    if not path.is_file() or path.is_symlink():
        raise ValueError("External manifest file missing or symlinked: " + relative)
    else:
        pass
    return path


def _cases(document: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("External suite must contain cases")
    else:
        pass
    ids: set[str] = set()
    source_splits: dict[str, str] = {}
    identity_splits: dict[str, str] = {}
    validated: list[dict[str, JsonValue]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Invalid external case")
        else:
            pass
        name = case.get("id")
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("External case IDs must be nonempty and unique")
        else:
            pass
        if name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError("Unsafe external case ID")
        else:
            pass
        ids.add(name)
        split = case.get("split")
        if (
            not isinstance(split, str)
            or split not in SPLITS
            or case.get("evaluation_layer") not in LAYERS
        ):
            raise ValueError("Unknown external split or evaluation layer")
        else:
            pass
        for field, seen in (
            ("source_case_id", source_splits),
            ("identity_key", identity_splits),
        ):
            identity = case.get(field)
            if not isinstance(identity, str) or not identity:
                raise ValueError("Missing external case " + field)
            else:
                pass
            if identity in seen and seen[identity] != split:
                raise ValueError("External birth identity leaks across splits")
            else:
                pass
            seen[identity] = split
        prompt = case.get("prompt")
        review = case.get("manual_review")
        source = case.get("source")
        if (
            not isinstance(prompt, str)
            or not prompt
            or not isinstance(review, list)
            or not review
            or not all(isinstance(criterion, str) for criterion in review)
            or not isinstance(source, dict)
            or not source
        ):
            raise ValueError(
                "External case lacks prompt, review criteria or provenance"
            )
        else:
            pass
        reference = case.get("reference_request")
        if reference and case.get("no_calculation"):
            raise ValueError("No-calculation cases cannot have reference calculations")
        else:
            pass
        if reference is not None and (
            not isinstance(reference, dict)
            or not isinstance(reference.get("tool"), str)
            or not isinstance(reference.get("arguments"), dict)
        ):
            raise ValueError("Invalid external case reference request")
        else:
            pass
        if not isinstance(case.get("birth_fingerprint"), str):
            raise ValueError("Missing external case birth_fingerprint")
        else:
            pass
        validated.append(case)
    return validated


def _select(
    cases: list[dict[str, JsonValue]], split: str, case_ids: Iterable[str] | None
) -> list[dict[str, JsonValue]]:
    if split not in SPLITS:
        raise ValueError("Unknown external split")
    else:
        pass
    available = {case["id"] for case in cases if case["split"] == split}
    requested = list(case_ids or [])
    if len(requested) != len(set(requested)):
        raise ValueError("Duplicate requested external case IDs")
    else:
        pass
    if set(requested) - available:
        raise ValueError(
            "Unknown case or case outside selected split: "
            + ", ".join(sorted(set(requested) - available))
        )
    else:
        pass
    selected = [
        case
        for case in cases
        if case["split"] == split and (not requested or case["id"] in requested)
    ]
    if not selected:
        raise ValueError("Selected external split is empty")
    else:
        pass
    return selected


def load_external_suite(
    root: Path, split: str = "development", case_ids: Iterable[str] | None = None
) -> ExternalSelection:
    """Verify the full source corpus before selecting a single immutable split."""
    manifest_data = (root / "manifest.json").read_bytes()
    manifest = _object(manifest_data, "external manifest")
    if manifest.get("schema_version") != 1 or manifest.get("suite_id") != SUITE_ID:
        raise ValueError("Unsupported external suite manifest")
    else:
        pass
    if manifest.get("dataset_kind", manifest.get("dataset_type")) != DATASET_KIND:
        raise ValueError("External suite must be labelled public_competition")
    else:
        pass
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("External manifest must freeze all corpus artifacts")
    else:
        pass
    verified: dict[str, bytes] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Invalid external manifest file record")
        else:
            pass
        name, expected_sha, expected_bytes = (
            entry.get("path"),
            entry.get("sha256"),
            entry.get("bytes"),
        )
        if (
            not isinstance(name, str)
            or not isinstance(expected_sha, str)
            or type(expected_bytes) is not int
        ):
            raise ValueError("Invalid external manifest file record")
        else:
            pass
        if name in verified:
            raise ValueError("Duplicate external manifest file")
        else:
            pass
        data = _safe_file(root, name).read_bytes()
        if sha256(data) != expected_sha or len(data) != expected_bytes:
            raise ValueError("External artifact integrity mismatch: " + name)
        else:
            pass
        verified[name] = data
    required: list[str] = []
    for field in ("cases_file", "corpus_file", "split_manifest_file"):
        filename = manifest.get(field)
        if not isinstance(filename, str) or filename not in verified:
            raise ValueError("External manifest does not hash all required artifacts")
        else:
            pass
        required.append(filename)
    cases_file, corpus_file, split_file = required
    document = _object(verified[cases_file], "external cases")
    cases = _cases(document)
    if (
        document.get("suite_id") != SUITE_ID
        or document.get("dataset_kind", document.get("dataset_type")) != DATASET_KIND
    ):
        raise ValueError("External case document kind or suite mismatch")
    else:
        pass
    assignments = _object(verified[split_file], "external split manifest")
    identities = assignments.get("identities")
    if not isinstance(identities, list) or not identities:
        raise ValueError("External split manifest needs birth identities")
    else:
        pass
    sources: dict[str, dict[str, JsonValue]] = {}
    seen_identity: dict[str, str] = {}
    for row in identities:
        if not isinstance(row, dict):
            raise ValueError("Invalid external source identity")
        else:
            pass
        source_id = row.get("source_case_id")
        split_name = row.get("split")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in sources
            or not isinstance(split_name, str)
            or split_name not in SPLITS
        ):
            raise ValueError("Duplicate source case or unknown source split")
        else:
            pass
        for field in ("identity_key", "birth_fingerprint"):
            key = row.get(field)
            if not isinstance(key, str) or not key:
                raise ValueError("Missing source birth identity")
            else:
                pass
            identity = field + ":" + key
            if identity in seen_identity and seen_identity[identity] != split_name:
                raise ValueError("External birth identity leaks across source splits")
            else:
                pass
            seen_identity[identity] = split_name
        sources[source_id] = row
    for split_name in SPLITS:
        listed = assignments.get(split_name)
        expected = {key for key, row in sources.items() if row["split"] == split_name}
        if (
            not isinstance(listed, list)
            or not all(isinstance(source_id, str) for source_id in listed)
            or len(listed) != len(set(listed))
            or set(listed) != expected
        ):
            raise ValueError(
                "External split membership disagrees with source identities"
            )
        else:
            pass
    for case in cases:
        source_case_id = case["source_case_id"]
        assert isinstance(source_case_id, str)
        source = sources.get(source_case_id)
        if source is None or any(
            case[key] != source[key]
            for key in ("identity_key", "birth_fingerprint", "split")
        ):
            raise ValueError("External case disagrees with source split identity")
        else:
            pass
        case_source = case["source"]
        assert isinstance(case_source, dict)
        if case_source.get("commit") != manifest.get("source_commit"):
            raise ValueError("External case source revision disagrees with manifest")
        else:
            pass
        raw_file = case_source.get("raw_file")
        if raw_file and (not isinstance(raw_file, str) or raw_file not in verified):
            raise ValueError("External case source artifact lacks an integrity hash")
        else:
            pass
    corpus = _object(verified[corpus_file], "external corpus")
    records = corpus.get("records")
    if not isinstance(records, list) or len(records) != len(sources):
        raise ValueError("External corpus and source identity coverage disagree")
    else:
        pass
    record_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid external corpus record")
        else:
            pass
        source_id = record.get("source_case_id")
        if not isinstance(source_id, str):
            raise ValueError("Invalid external corpus source ID")
        else:
            pass
        source = sources.get(source_id)
        if (
            source_id in record_ids
            or source is None
            or any(
                record.get(key) != source[key]
                for key in ("identity_key", "birth_fingerprint", "split")
            )
        ):
            raise ValueError("External corpus disagrees with source split identity")
        else:
            pass
        normalized = record.get("normalized_input")
        if not isinstance(normalized, dict):
            raise ValueError("External corpus needs normalized birth identity inputs")
        else:
            pass
        identity_fields = ("gender", "year", "month", "day", "time_expression")
        if not all(field in normalized for field in identity_fields):
            raise ValueError("External corpus needs normalized birth identity inputs")
        else:
            pass
        identity_inputs = {field: normalized[field] for field in identity_fields}
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
        else:
            pass
        record_ids.add(source_id)
    selected = _select(cases, split, case_ids)
    provenance: dict[str, JsonValue] = {
        "suite_id": SUITE_ID,
        "dataset_kind": DATASET_KIND,
        "source_commit": manifest.get("source_commit"),
        "source_manifest_sha256": sha256(manifest_data),
        "source_dataset_sha256": sha256(verified[cases_file]),
        "source_artifacts": files,
        "split_policy": manifest.get("split_policy"),
    }
    return _sealed(selected, split, provenance)


def _sealed(
    cases: list[dict[str, JsonValue]], split: str, provenance: dict[str, JsonValue]
) -> ExternalSelection:
    return {
        "schema_version": 1,
        "suite_id": SUITE_ID,
        "dataset_kind": DATASET_KIND,
        "split": split,
        "selection_kind": "frozen_single_split",
        "provenance": provenance,
        "cases": cases,
    }


def freeze_external_selection(document: ExternalSelection, output: Path) -> bytes:
    """Retain selected source excerpts/criteria; never copy the other split or raw corpus."""
    dataset = json_bytes(document)
    receipt: ExternalReceipt = {
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
) -> ExternalSelection:
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
    else:
        pass
    if document.get("dataset_kind") != DATASET_KIND or document.get("split") != split:
        raise ValueError("Frozen external dataset split or kind mismatch")
    else:
        pass
    cases = _cases(document)
    if any(case["split"] != split for case in cases):
        raise ValueError("Frozen external dataset mixes splits")
    else:
        pass
    if (
        receipt.get("selected_dataset_sha256") != sha256(data)
        or receipt.get("split") != split
    ):
        raise ValueError("Frozen external dataset integrity mismatch")
    else:
        pass
    if receipt.get("schema_version") != 1 or receipt.get("suite_id") != SUITE_ID:
        raise ValueError("Unsupported frozen external receipt")
    else:
        pass
    if receipt.get("selected_case_ids") != [
        case["id"] for case in cases
    ] or receipt.get("provenance") != document.get("provenance"):
        raise ValueError("Frozen external receipt disagrees with selection")
    else:
        pass
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Frozen external dataset lacks source provenance")
    else:
        pass
    return _sealed(_select(cases, split, case_ids), split, provenance)


def evaluation_summary(
    document: ExternalSelection, records: list[dict[str, JsonValue]] | None = None
) -> dict[str, JsonValue]:
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
