"""Create an explicit corrected view while retaining every original case object."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-census-pillar-consistency-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def apply_corrections(inventory, corrections, root):
    records = copy.deepcopy(inventory["records"])
    positions = {r["case"]["case_id"]: r for r in records}
    if len(positions) != len(records):
        raise ValueError("Duplicate source-case IDs")
    seen = set()
    for edit in corrections["records"]:
        if set(edit) != {
            "case_id",
            "before_case_object_sha256",
            "before_literal_pillars",
            "after_literal_pillars",
            "before_anchor",
            "after_anchor",
            "evidence",
            "source_reading_reason",
        }:
            raise ValueError(
                "Correction cannot edit grades, actors, kinds or source claims"
            )
        identity = edit["case_id"]
        if identity not in positions or identity in seen:
            raise ValueError("Absent or repeated case correction")
        seen.add(identity)
        record = positions[identity]
        case = record["case"]
        if (
            object_digest(case) != record["case_object_sha256"]
            or record["case_object_sha256"] != edit["before_case_object_sha256"]
            or case["literal_pillars"] != edit["before_literal_pillars"]
            or case["anchor"] != edit["before_anchor"]
        ):
            raise ValueError("Correction lost its exact first case value")
        after = edit["after_literal_pillars"]
        if (
            set(after) != {"year", "month", "day", "hour"}
            or after == case["literal_pillars"]
            or any(not isinstance(v, str) or len(v) != 2 for v in after.values())
        ):
            raise ValueError("Correction must retain four explicit source-read pillars")
        old_flat = "".join(
            case["literal_pillars"][n] or "" for n in ["year", "month", "day", "hour"]
        )
        new_flat = "".join(after[n] for n in ["year", "month", "day", "hour"])
        expected_anchor = new_flat if case["anchor"] == old_flat else case["anchor"]
        if edit["after_anchor"] != expected_anchor:
            raise ValueError(
                "Only the mechanically aligned literal-pillar caption may change"
            )
        if not edit["evidence"] or not edit["source_reading_reason"].strip():
            raise ValueError("Source-reading evidence is required")
        if not any(
            e["path"] == record["page_image"]
            and e["sha256"] == record["page_image_sha256"]
            for e in edit["evidence"]
        ):
            raise ValueError("Correction omitted its full original page")
        for evidence in edit["evidence"]:
            path = (root / evidence["path"]).resolve()
            if (
                not path.is_relative_to(root.resolve())
                or evidence["pdf_page"] != record["pdf_page"]
                or digest(path) != evidence["sha256"]
            ):
                raise ValueError("Correction image escaped or lost page/hash binding")
        record["case_first_value_retained"] = copy.deepcopy(case)
        record["case_first_value_sha256"] = record["case_object_sha256"]
        case["literal_pillars"] = copy.deepcopy(after)
        case["anchor"] = edit["after_anchor"]
        record["case_object_sha256"] = object_digest(case)
        record["transcription_correction"] = copy.deepcopy(edit)
        record["source_claim_alignment_review"] = "pending_before_any_force_comparison"
    return {**copy.deepcopy(inventory), "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    study, output = args.study.resolve(), args.output_directory.resolve()
    if output.exists():
        raise FileExistsError("Refuse to replace a corrected-view directory")
    protocol_path = study / "correction-protocol-first.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Correction protocol changed")
    protocol = json.loads(protocol_path.read_text())
    if digest(study / "cases-first.json") != protocol["cases_sha256"]:
        raise ValueError("Original complete case inventory changed")
    edits_path = study / "case-input-corrections-first.json"
    if digest(edits_path) != edits_path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Correction records changed")
    edits = json.loads(edits_path.read_text())
    if edits["correction_protocol_sha256"] != digest(protocol_path):
        raise ValueError("Corrections lost prospective protocol binding")
    if [e["case_id"] for e in edits["records"]] != protocol["corrected_case_ids"]:
        raise ValueError("Correction scope changed")
    for edit in edits["records"]:
        planned = protocol["after_literals_frozen_before_resolver_execution"][
            edit["case_id"]
        ]
        if [
            edit["after_literal_pillars"][n] for n in ["year", "month", "day", "hour"]
        ] != planned:
            raise ValueError(
                "Source-read correction changed after the prospective freeze"
            )
    parent_protocol = study / "protocol-first.json"
    if digest(parent_protocol) != protocol["parent_protocol_sha256"]:
        raise ValueError("Original inventory protocol changed")
    parent_source = json.loads(parent_protocol.read_text())
    if (
        edits["source_pdf_sha256"] != parent_source["source_pdf_sha256"]
        or digest(
            ROOT / "docs/validation/bazi-controller-root-load-v1/source-whole.pdf"
        )
        != parent_source["source_pdf_sha256"]
    ):
        raise ValueError("Corrections lost the exact source PDF binding")
    source = json.loads((study / "cases-first.json").read_text())
    resolved = apply_corrections(source, edits, ROOT)
    output.mkdir()
    destination = output / "cases-first.json"
    destination.write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n")
    parent = json.loads((study / "protocol-first.json").read_text())
    next_protocol = {
        **parent,
        "scope": "Separate full558 corrected transcription view, not a replacement or rescoring of original gates",
        "parent_inventory_protocol_sha256": digest(study / "protocol-first.json"),
        "correction_protocol_sha256": digest(protocol_path),
        "correction_document_sha256": digest(edits_path),
        "cases_sha256": digest(destination),
        "original_case_objects_retained": True,
        "source_claim_alignment_review_complete": False,
        "force_comparison_allowed": False,
    }
    p = output / "protocol-first.json"
    p.write_text(json.dumps(next_protocol, ensure_ascii=False, indent=2) + "\n")
    p.with_suffix(".sha256").write_text(digest(p) + "\n")
    for name in ["reference-first.json", "reference-first.sha256"]:
        (output / name).write_bytes((study / name).read_bytes())
    print(
        json.dumps(
            {
                "records": len(resolved["records"]),
                "corrections": len(edits["records"]),
                "all_original_cases_retained": True,
                "force_comparison_allowed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
