"""Restore every frozen missing editorial annotation without changing a grade."""

import argparse
import json
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fatebridge.validation.bazi_source_corpus import (
    digest,
    load_registry,
    strength_annotation,
)

PROTOCOL = "docs/validation/bazi-editorial-annotation-projection-v1/protocol-first.json"
PROTOCOL_SHA256 = "509582ba1078ff185c1d111f1817a8e42f6a8d3a85ddb59f02c91275cd13fdc7"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v7.json"


def canonical_digest(value):
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def generate():
    if digest(ROOT / PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("Editorial projection protocol changed")
    plan = json.loads((ROOT / PROTOCOL).read_text())
    for key in ("parent_index", "registry", "prior_current_corpus"):
        if digest(ROOT / plan[key]) != plan[key + "_sha256"]:
            raise ValueError("Editorial projection preimage changed: " + key)
    registry = load_registry(ROOT, ROOT / plan["registry"])
    if registry["source_sha256"] != plan["all_raw_source_sha256"]:
        raise ValueError("Editorial projection source population changed")
    old = json.loads((ROOT / plan["parent_index"]).read_text())
    data = deepcopy(old)
    patches = {p["reference_id"]: p for p in plan["patches"]}
    if len(patches) != 149 or len(old["records"]) != 367:
        raise ValueError("Editorial projection record population changed")
    applied = set()
    for i, before in enumerate(old["records"]):
        if before["reference_id"] not in patches:
            continue
        patch = patches[before["reference_id"]]
        if before != patch["before"]:
            raise ValueError("Editorial projection record preimage changed")
        after = patch["after"]
        provenance = after["editorial_annotation_provenance"]
        document = json.loads((ROOT / provenance["registered_document"]).read_text())
        parts = provenance["source_field_pointer"].strip("/").split("/")
        source = document
        for part in parts[:-1]:
            source = source[int(part)] if isinstance(source, list) else source[part]
        if (
            source != patch["source_record"]
            or source["id"] != before["case_id"]
            or canonical_digest(source) != provenance["source_record_sha256"]
            or source[parts[-1]] != after["annotation_basis"]
            or after["retained_context"] != after["annotation_basis"]
            or strength_annotation(source)[1] != before["retained_strength_annotation"]
            or before["retained_strength_annotation"]
            != after["retained_strength_annotation"]
        ):
            raise ValueError(
                "Editorial note is not the original same-record annotation"
            )
        data["records"][i] = deepcopy(after)
        applied.add(before["reference_id"])
    if (
        applied != patches.keys()
        or data["strength_constraints"] != old["strength_constraints"]
    ):
        raise ValueError(
            "Editorial projection dropped a row or changed a bounded annotation"
        )
    data.update(
        parent_index_sha256=digest(ROOT / plan["parent_index"]),
        generator_sha256=digest(Path(__file__)),
        data_revision=plan["data_revision"],
        editorial_annotation_count=len(applied),
        editorial_annotation_projection_sha256=PROTOCOL_SHA256,
    )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(generate(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check or TARGET.exists():
        if TARGET.read_bytes() != raw:
            raise ValueError("Preserve first v7 index; unexpected generation drift")
    else:
        TARGET.open("xb").write(raw)
    print(json.dumps({"index_sha256": digest(TARGET), "editorial_notes": 149}))


if __name__ == "__main__":
    main()
