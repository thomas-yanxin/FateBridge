"""Apply a pinned image-reading revision without rewriting frozen source records."""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from fatebridge.validation.bazi_source_corpus import (
    digest,
    source_cases,
    strength_annotation,
)

PLAN_PATH = "docs/validation/bazi-corpus-input-revision-v1/plan-first.json"
PLAN_SHA256 = "27d510e8ede34d3d4a456604b2ee908b149bea2467b4ae4b648d9324fb25a2ff"


def canonical_digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def source_documents(
    root: Path, registry: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Return current documents, untouched originals, and a non-scoring receipt."""
    originals = {}
    for group, relative in registry["groups"].items():
        path = root / relative
        if digest(path) != registry["source_sha256"][relative]:
            raise ValueError("Original source preimage changed: " + relative)
        originals[group] = json.loads(path.read_text())
    documents = deepcopy(originals)
    if "input_view" not in registry:
        return documents, originals, None
    if (
        registry["input_view"]
        != {
            "plan_path": PLAN_PATH,
            "plan_sha256": PLAN_SHA256,
        }
        or digest(root / PLAN_PATH) != PLAN_SHA256
    ):
        raise ValueError("Input revision does not match the pinned source review")
    plan = json.loads((root / PLAN_PATH).read_text())
    if digest(root / plan["parent_registry"]) != plan["parent_registry_sha256"]:
        raise ValueError("Parent source registry changed")
    parent = json.loads((root / plan["parent_registry"]).read_text())
    if any(registry[k] != parent[k] for k in ("groups", "source_sha256")):
        raise ValueError("Input revision changed the registered source population")
    if canonical_digest(originals) != plan["original_documents_canonical_sha256"]:
        raise ValueError("Full original source document preimage changed")
    for relative, expected in plan["evidence_sha256"].items():
        if digest(root / relative) != expected:
            raise ValueError("Input reading evidence changed: " + relative)
    count = sum(len(source_cases(d)) for d in originals.values())
    if len(originals) != 27 or count != 367 or len(plan["patches"]) != 6:
        raise ValueError("Input revision population changed")
    changes = []
    seen = set()
    for patch in plan["patches"]:
        identity = (patch["group"], patch["id"])
        if identity in seen:
            raise ValueError("Input revision repeats a source record")
        seen.add(identity)
        cases = source_cases(documents[identity[0]])
        positions = [i for i, c in enumerate(cases) if c["id"] == identity[1]]
        if len(positions) != 1 or cases[positions[0]] != patch["before"]:
            raise ValueError("Input revision source record preimage changed")
        before, after = patch["before"], patch["after"]
        if (
            before["id"] != after["id"]
            or strength_annotation(before) != strength_annotation(after)
            or strength_annotation(after)[1] is not None
        ):
            raise ValueError("Input review cannot relabel a strength observation")
        # source_cases concatenates lists, so replace the actual document entry.
        document = documents[identity[0]]
        lists = (
            [document]
            if isinstance(document, list)
            else [document["cases"], document.get("additional_cases", [])]
        )
        for entries in lists:
            for index, case in enumerate(entries):
                if case["id"] == identity[1]:
                    entries[index] = deepcopy(after)
        changes.append(
            {
                "group": identity[0],
                "id": identity[1],
                "original_source_record": deepcopy(before),
                "current_source_record": deepcopy(after),
                "source_strength_label_assigned": False,
            }
        )
    return (
        documents,
        originals,
        {
            "plan_path": PLAN_PATH,
            "plan_sha256": PLAN_SHA256,
            "record_count": count,
            "changed_source_records": changes,
            "original_records_and_derived_metadata_retained": True,
            "new_independent_validation_credit": 0,
            "source_strength_labels_changed": False,
            "real_world_efficacy": "not_tested",
        },
    )
