"""Generate exposed literal-source annotations; never generate strength labels."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fatebridge.validation.bazi_source_corpus import (
    load_registry,
    pillar_values,
    source_cases,
    strength_annotation,
)

PROTOCOL = ROOT / "tests/fixtures/bazi_source_comparison_v1/protocol.json"
TARGET = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def string(value):
    return value if isinstance(value, str) else None


def generate():
    assert sha(PROTOCOL) == PROTOCOL.with_suffix(".sha256").read_text().strip()
    protocol = json.loads(PROTOCOL.read_text())
    registry_path = ROOT / protocol["registry"]["path"]
    assert sha(registry_path) == protocol["registry"]["sha256"]
    registry = load_registry(ROOT, registry_path)
    profile_path = ROOT / "tests/fixtures/bazi_classical_v1/profile.json"
    profile = json.loads(profile_path.read_text())
    records = []
    for group, relative in registry["groups"].items():
        assert sha(ROOT / relative) == protocol["source_files"][relative]
        document = json.loads((ROOT / relative).read_text())
        meta = document if isinstance(document, dict) else {}
        doc_source = meta.get("source", {})
        doc_source = doc_source if isinstance(doc_source, dict) else {}
        for case in source_cases(document):
            annotation_status, expected = strength_annotation(case)
            source = case.get("source", {})
            source = source if isinstance(source, dict) else {}
            linked = profile if source.get("source_id") == profile["source_id"] else {}
            adjudication = case.get("adjudication", {})
            fields = [
                case.get(k)
                for k in [
                    "pages",
                    "source_pdf_pages",
                    "pdf_pages",
                    "source_pdf_page",
                    "pdf_page",
                ]
            ]
            fields += [source.get("pdf_pages")]
            pages = next(
                (
                    ([p] if isinstance(p, int) else p)
                    for p in fields
                    if isinstance(p, int)
                    or (isinstance(p, list) and all(isinstance(n, int) for n in p))
                ),
                None,
            )
            reasoning = case.get("reasoning")
            if isinstance(reasoning, list):
                reasoning = "；".join(p for p in reasoning if isinstance(p, str))
            basis = next(
                (
                    s
                    for p in [
                        adjudication.get("strength_basis"),
                        case.get("source_basis"),
                        case.get("strength_basis"),
                        case.get("source_label"),
                        case.get("raw_body_term"),
                    ]
                    if (s := string(p))
                ),
                None,
            )
            anchor = string(case.get("source_anchor")) or string(
                source.get("verified_excerpt_no_punctuation")
            )
            source_url = (
                string(case.get("source_url"))
                or string(source.get("url"))
                or string(source.get("source_url"))
                or string(meta.get("source_url"))
                or string(doc_source.get("url"))
                or string(linked.get("source_url"))
            )
            edition = (
                string(meta.get("edition"))
                or string(source.get("edition"))
                or string(linked.get("edition"))
            )
            title = (
                string(meta.get("title"))
                or string(doc_source.get("title"))
                or string(source.get("title"))
            )
            records.append(
                {
                    "reference_id": group + ":" + case["id"],
                    "group": group,
                    "case_id": case["id"],
                    "pillars": pillar_values(case),
                    "retained_strength_annotation": expected,
                    "annotation_status": annotation_status,
                    "annotation_basis": basis,
                    "retained_anchor": anchor,
                    "retained_context": string(reasoning),
                    "source_reference": {
                        "title": title,
                        "edition": edition,
                        "url": source_url,
                        "source_id": string(source.get("source_id")),
                        "pdf_pages": pages,
                        "locator": string(source.get("locator")),
                        "registered_document": relative,
                        "registered_document_sha256": sha(ROOT / relative),
                    },
                    "independent_annotation_review": "not_certified",
                }
            )
    assert len(records) == 349 and len({tuple(r["pillars"]) for r in records}) == 303
    assert len({r["reference_id"] for r in records}) == len(records)
    return {
        "schema_version": 1,
        "method_id": "registered_literal_source_annotations_v1",
        "registry_sha256": sha(registry_path),
        "protocol_sha256": sha(PROTOCOL),
        "generator_sha256": sha(__file__),
        "source_files": registry["source_sha256"],
        "records": records,
        "record_count": len(records),
        "literal_input_count": 303,
        "all_records_exposed": True,
        "scope": "Exactliteral registered annotations only. No inventedbirthdate, source label, independentreview, predictionorweightchange. Sourcegrade equivalence and historicalcalendar provenance notcertified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(generate(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        assert TARGET.read_bytes() == payload, "Generated source index drift"
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        if TARGET.exists():
            assert (
                TARGET.read_bytes() == payload
            ), "Preserve first source-index bytes; explicit version needed"
        else:
            TARGET.write_bytes(payload)
    print(
        json.dumps(
            {
                "records": 349,
                "literal_inputs": 303,
                "index_sha256": hashlib.sha256(payload).hexdigest(),
                "check": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()
