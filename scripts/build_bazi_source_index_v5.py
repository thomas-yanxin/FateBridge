"""Append all frozen 清氣/濁氣 cases and separate forbidden-grade evidence."""

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fatebridge.validation.bazi_source_corpus import (
    case_strength_constraints,
    load_registry,
    source_cases,
    strength_annotation,
)

STUDY = ROOT / "docs/validation/bazi-source-bounds-v1"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v5.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    binding_path = STUDY / "index-generation-binding.json"
    assert sha(binding_path) == binding_path.with_suffix(".sha256").read_text().strip()
    plan = json.loads(binding_path.read_text())
    for name in ("parent_index", "reference", "registry", "protocol"):
        assert sha(ROOT / plan[name]) == plan[name + "_sha256"]
    registry = load_registry(ROOT, ROOT / plan["registry"])
    data = json.loads((ROOT / plan["parent_index"]).read_text())
    original = deepcopy(data["records"])
    document = json.loads((ROOT / plan["reference"]).read_text())
    group = next(k for k, p in registry["groups"].items() if p == plan["reference"])
    for case in source_cases(document):
        status, expected = strength_annotation(case)
        data["records"].append(
            {
                "reference_id": group + ":" + case["id"],
                "group": group,
                "case_id": case["id"],
                "pillars": case["pillars"],
                "retained_strength_annotation": expected,
                "annotation_status": status,
                "annotation_basis": case["reasoning"],
                "retained_anchor": case["source_anchor"],
                "retained_context": case["reasoning"],
                "source_reference": {
                    "title": document["title"],
                    "edition": document["edition"],
                    "url": document["source_url"],
                    "source_id": "ditian_ren_1947_qingqi_zhuoqi",
                    "pdf_pages": case["pages"],
                    "locator": case["unit"],
                    "registered_document": plan["reference"],
                    "registered_document_sha256": sha(ROOT / plan["reference"]),
                    "whole_pdf_sha256": document["whole_pdf_sha256"],
                    "identity_evidence": plan["reference"] + "#/whole_pdf_sha256",
                    "identity_evidence_sha256": sha(ROOT / plan["reference"]),
                },
                "independent_annotation_review": "not_certified",
            }
        )
    assert data["records"][: len(original)] == original
    assert len(data["records"]) == 367
    lookup = {(r["group"], r["case_id"]): r for r in data["records"]}
    assert len(lookup) == 367
    constraints = []
    for group, path in registry["groups"].items():
        document = json.loads((ROOT / path).read_text())
        annotations = []
        if isinstance(document, dict):
            annotations.extend(
                (f"/body_constraints/{i}", a)
                for i, a in enumerate(document.get("body_constraints", []))
            )
        for case in source_cases(document):
            annotations.extend(
                (f"case:{case['id']}/negative_constraints/{i}", a)
                for i, a in enumerate(case_strength_constraints(case))
            )
        for location, annotation in annotations:
            record = lookup[(group, annotation["case_id"])]
            forbidden = annotation["forbidden_strengths"]
            assert forbidden and all(v in {"强", "中和", "弱"} for v in forbidden)
            anchor = next(
                (
                    annotation[k]
                    for k in ("source_anchor", "anchor", "source_basis")
                    if annotation.get(k)
                ),
                None,
            )
            assert isinstance(anchor, str) and anchor
            constraints.append(
                {
                    "constraint_id": record["reference_id"] + "#" + location,
                    "reference_id": record["reference_id"],
                    "annotation_location": location,
                    "forbidden_strengths": forbidden,
                    "retained_anchor": anchor,
                    "retained_context": annotation.get(
                        "scope", record["retained_context"]
                    ),
                    "source_reference": record["source_reference"],
                    "original_annotation": deepcopy(annotation),
                    "does_not_assign_an_exact_source_label": True,
                }
            )
    assert len(constraints) == 3
    assert len({c["constraint_id"] for c in constraints}) == 3
    inputs = {tuple(r["pillars"]) for r in data["records"]}
    assert len(inputs) == 321
    data.update(
        method_id="registered_literal_source_annotations_with_bounds_v4",
        parent_index_sha256=sha(ROOT / plan["parent_index"]),
        registry_sha256=sha(ROOT / plan["registry"]),
        source_files=registry["source_sha256"],
        record_count=len(data["records"]),
        literal_input_count=len(inputs),
        generator_sha256=sha(Path(__file__)),
        extension_protocol_sha256=sha(ROOT / plan["protocol"]),
        strength_constraints=constraints,
        strength_constraint_count=len(constraints),
    )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = generate()
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if args.check or TARGET.exists():
        assert TARGET.read_bytes() == raw, "Preserve first v5 index; unexpected drift"
    else:
        TARGET.write_bytes(raw)
    print(
        json.dumps(
            {
                "records": data["record_count"],
                "constraints": data["strength_constraint_count"],
                "sha256": sha(TARGET),
            }
        )
    )


if __name__ == "__main__":
    main()
