"""Publish six pinned image readings while preserving the complete old index."""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fatebridge.validation.bazi_source_corpus import (
    digest,
    load_registry,
    source_cases,
)
from fatebridge.validation.bazi_source_inputs import source_documents

PROTOCOL = "docs/validation/bazi-source-index-input-revision-v1/protocol-first.json"
PROTOCOL_SHA256 = "8308e3b1068c4fc9c7f96ab125a4ed2303893e2a42879b9d203d79f42c6f9a00"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v6.json"


def generate():
    if digest(ROOT / PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("Packaged source revision protocol changed")
    plan = json.loads((ROOT / PROTOCOL).read_text())
    for name in ("old_index", "source_input_plan", "current_registry"):
        if digest(ROOT / plan[name]) != plan[name + "_sha256"]:
            raise ValueError("Packaged source revision preimage changed: " + name)
    registry = load_registry(ROOT, ROOT / plan["current_registry"])
    documents, _, _ = source_documents(ROOT, registry)
    old = json.loads((ROOT / plan["old_index"]).read_text())
    data = deepcopy(old)
    patches = {p["reference_id"]: p for p in plan["patches"]}
    if len(patches) != 6 or len(data["records"]) != 367:
        raise ValueError("Packaged source revision population changed")
    applied = set()
    for index, record in enumerate(data["records"]):
        if record["reference_id"] not in patches:
            continue
        patch = patches[record["reference_id"]]
        if record != patch["before"]:
            raise ValueError("Packaged source record preimage changed")
        current = next(
            c
            for c in source_cases(documents[record["group"]])
            if c["id"] == record["case_id"]
        )
        after = deepcopy(patch["after"])
        if (
            after["pillars"] != current["pillars"]
            or after["annotation_basis"] != current["annotation"]
            or after["retained_strength_annotation"] is not None
            or current["expected_strength"] is not None
        ):
            raise ValueError("Packaged reading differs from reviewed source view")
        data["records"][index] = after
        applied.add(record["reference_id"])
    if applied != patches.keys():
        raise ValueError("Packaged source revision omitted a reviewed record")
    data.update(
        method_id=plan["new_method_id"],
        parent_index_sha256=digest(ROOT / plan["old_index"]),
        registry_sha256=digest(ROOT / plan["current_registry"]),
        generator_sha256=digest(Path(__file__)),
        input_reading_plan_sha256=PROTOCOL_SHA256,
        input_reading_revision_count=len(applied),
        literal_input_count=len({tuple(r["pillars"]) for r in data["records"]}),
        scope=plan["scope"],
    )
    if data["strength_constraints"] != old["strength_constraints"]:
        raise ValueError("Source input review cannot change bounded annotations")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(generate(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check or TARGET.exists():
        if TARGET.read_bytes() != raw:
            raise ValueError("Preserve first v6 index; unexpected regeneration drift")
    else:
        TARGET.open("xb").write(raw)
    print(json.dumps({"index_sha256": digest(TARGET), "revised_records": 6}))


if __name__ == "__main__":
    main()
