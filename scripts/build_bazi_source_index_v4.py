"""Append three complete units, preserving all previous annotations byte for value."""

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fatebridge.validation.bazi_source_corpus import load_registry, strength_annotation

STUDY = ROOT / "docs/validation/bazi-capacity-caid-fenyu-enyuan-v1"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v4.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    protocol_path = STUDY / "index-extension-protocol.json"
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    plan = json.loads(protocol_path.read_text())
    parent, reference, registry_path = (
        ROOT / plan[name] for name in ("parent_index", "reference", "registry")
    )
    for name, path in (
        ("parent_index", parent),
        ("reference", reference),
        ("registry", registry_path),
    ):
        assert sha(path) == plan[name + "_sha256"]
    registry = load_registry(ROOT, registry_path)
    data = json.loads(parent.read_text())
    original = deepcopy(data["records"])
    document = json.loads(reference.read_text())
    group = next(k for k, v in registry["groups"].items() if v == plan["reference"])
    for case in document["cases"]:
        status, expected = strength_annotation(case)
        data["records"].append(
            {
                "reference_id": group + ":" + case["id"],
                "group": group,
                "case_id": case["id"],
                "pillars": case["pillars"],
                "retained_strength_annotation": expected,
                "annotation_status": status,
                "annotation_basis": case["label_reason"],
                "retained_anchor": case["source_anchor"],
                "retained_context": case["label_reason"],
                "source_reference": {
                    "title": document["title"],
                    "edition": document["edition"],
                    "url": document["source_url"],
                    "source_id": "ditian_ren_1947_caid_fenyu_enyuan",
                    "pdf_pages": case["source_pdf_pages"],
                    "locator": case["chapter"],
                    "registered_document": plan["reference"],
                    "registered_document_sha256": sha(reference),
                    "whole_pdf_sha256": document["source_pdf_sha256"],
                    "identity_evidence": plan["reference"] + "#/source_pdf_sha256",
                    "identity_evidence_sha256": sha(reference),
                },
                "independent_annotation_review": "not_certified",
            }
        )
    assert data["records"][: len(original)] == original
    assert len(data["records"]) == 361
    inputs = {tuple(r["pillars"]) for r in data["records"]}
    assert len(inputs) == 315
    assert len({r["reference_id"] for r in data["records"]}) == 361
    data.update(
        parent_index_sha256=sha(parent),
        registry_sha256=sha(registry_path),
        source_files=registry["source_sha256"],
        record_count=len(data["records"]),
        literal_input_count=len(inputs),
        generator_sha256=sha(Path(__file__)),
        extension_protocol_sha256=sha(protocol_path),
    )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(generate(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check or TARGET.exists():
        assert TARGET.read_bytes() == raw, "Preserve first v4 index; unexpected drift"
    else:
        TARGET.write_bytes(raw)
    print(json.dumps({"records": 361, "literal_inputs": 315, "sha256": sha(TARGET)}))


if __name__ == "__main__":
    main()
