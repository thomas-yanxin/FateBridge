"""Verify unchanged selected scan pages; this does not prove manual readings."""

import argparse
import hashlib
import json
from pathlib import Path

from fatebridge.validation.meihua_scans import reference_bundle


def main() -> int:
    import fitz

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests/fixtures/meihua_scan_v1",
    )
    parser.add_argument(
        "--original",
        type=Path,
        help="Optional complete GGZBCK415 PDF; never needed by the runtime tool",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reference_bundle(args.references)
    selection = json.loads(
        (args.references / "sources/dejutang-selection.json").read_text()
    )
    selected = fitz.open(args.references / "sources/dejutang-selected.pdf")
    original = None
    if args.original:
        if (
            hashlib.sha256(args.original.read_bytes()).hexdigest()
            != selection["original_sha256"]
        ):
            raise ValueError("The complete original scan changed")
        original = fitz.open(args.original)
    checks = []
    for row in selection["pages"]:
        p = selected[row["selected_pdf_index"]].get_pixmap(matrix=fitz.Matrix(2, 2))
        assert [p.width, p.height] == row["render_size"]
        assert hashlib.sha256(p.samples).hexdigest() == row["render_rgb_sha256"]
        if original is not None:
            q = original[row["original_pdf_index"]].get_pixmap(matrix=fitz.Matrix(2, 2))
            assert p.samples == q.samples
        checks.append(
            {
                "original_pdf_index": row["original_pdf_index"],
                "selected_pixels_match_frozen_original": True,
            }
        )
    collation = json.loads((args.references / "collation.json").read_text())
    nlc = fitz.open(args.references / "sources/nlc-1925.pdf")
    assert len(nlc) == 232 and len(selected) == 5
    mapping = {
        r["selected_pdf_index"]: r["original_pdf_index"] for r in selection["pages"]
    }
    for reading in collation["readings"]:
        for location in reading["locations"]:
            if location["edition"] == "nlc-1925":
                assert 0 <= location["pdf_index"] < len(nlc)
            else:
                assert mapping[location["pdf_index"]] == location["original_pdf_index"]
    record = {
        "status": "passed",
        "pymupdf_version": fitz.VersionBind,
        "complete_original_reverified": original is not None,
        "page_checks": checks,
        "manual_transcription_truth_automatically_proved": False,
        "scope": "Frozen byte integrity, original-to-selection image identity and valid locators only",
    }
    content = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
