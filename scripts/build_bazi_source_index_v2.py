"""Supplement citation identity without changing any exposed source annotation."""

import argparse
import json
from copy import deepcopy

from build_bazi_source_index import ROOT
from build_bazi_source_index import generate as parent_generate
from build_bazi_source_index import sha

PROTOCOL = ROOT / "tests/fixtures/bazi_source_comparison_v1/citation-protocol-v2.json"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v2.json"


def generate():
    assert sha(PROTOCOL) == PROTOCOL.with_suffix(".sha256").read_text().strip()
    plan = json.loads(PROTOCOL.read_text())
    assert (
        sha(ROOT / "scripts/build_bazi_source_index.py")
        == plan["parent_generator_sha256"]
    )
    parent = ROOT / plan["parent_index"]
    assert sha(parent) == plan["parent_index_sha256"]
    data = parent_generate()
    assert json.loads(parent.read_text()) == data
    bindings = plan["group_bindings"]
    for binding in [*bindings.values(), *plan["books"].values()]:
        assert sha(ROOT / binding["evidence"]) == binding["evidence_sha256"]
    for binding in bindings.values():
        value = json.loads((ROOT / binding["evidence"]).read_text())
        for key in binding["pointer"].strip("/").split("/"):
            value = value[key]
        assert value == binding["whole_pdf_sha256"]
    old_records = deepcopy(data["records"])
    for record in data["records"]:
        citation = record["source_reference"]
        binding = bindings.get(record["group"])
        if binding is None and citation["source_id"] is not None:
            for digest, book in plan["books"].items():
                metadata = json.loads((ROOT / book["evidence"]).read_text())
                if metadata.get("source_id") == citation["source_id"]:
                    assert metadata["source_sha256"] == digest
                    binding = {
                        **book,
                        "whole_pdf_sha256": digest,
                        "pointer": "/source_sha256",
                    }
                    break
        if binding:
            book = plan["books"][binding["whole_pdf_sha256"]]
            for key in ("title", "edition", "url"):
                if citation[key] is None:
                    citation[key] = book[key]
            citation["whole_pdf_sha256"] = binding["whole_pdf_sha256"]
            citation["identity_evidence"] = (
                binding["evidence"] + "#" + binding["pointer"]
            )
            citation["identity_evidence_sha256"] = binding["evidence_sha256"]
        elif citation["title"] is None and record["group"] == "neutrality":
            document = json.loads((ROOT / citation["registered_document"]).read_text())
            citation["title"] = document["source_title"]
    for old, new in zip(old_records, data["records"]):
        assert {k: v for k, v in old.items() if k != "source_reference"} == {
            k: v for k, v in new.items() if k != "source_reference"
        }
        for key, value in old["source_reference"].items():
            if value is not None:
                assert new["source_reference"][key] == value
    data.update(
        method_id="registered_literal_source_annotations_v2",
        parent_index_sha256=plan["parent_index_sha256"],
        citation_protocol_sha256=sha(PROTOCOL),
        generator_sha256=sha(__file__),
    )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = generate()
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if args.check or TARGET.exists():
        assert TARGET.read_bytes() == raw, "Preserve first v2 index; unexpected drift"
    else:
        TARGET.write_bytes(raw)
    print(
        json.dumps(
            {
                "records": len(data["records"]),
                "index_sha256": sha(TARGET),
                "check": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()
