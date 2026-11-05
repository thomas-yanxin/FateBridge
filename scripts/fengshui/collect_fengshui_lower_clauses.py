"""Extract every lower-chart seed/flight clause from a fixed Shen PDF.

Run with pinned PyMuPDF in a separate source-research environment. This
collector never imports FateBridge or obtains expected values from its engine.
It preserves literal edition differences; it does not correct printed prose.
"""

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

import pymupdf

MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
DIGITS = "一二三四五六七八九"
HEADING = re.compile(rf"([天人地])元([{MOUNTAINS}])山([{MOUNTAINS}])向挨星图")
PREFIX = re.compile(
    rf"([{DIGITS}])运挨星[，,。]?([{DIGITS}])(?:天星)?到山[，,。]?"
    rf"([{DIGITS}])(?:天星)?到向[，,。]?飞星"
    r"(山向均[顺逆]|山[顺逆]向[顺逆])"
)
SPLIT_PREFIX = re.compile(
    rf"([{DIGITS}])运挨星，([{DIGITS}])到山，([顺逆])行，(?:犯下水，)?"
    rf"([{DIGITS}])到向，([顺逆])行"
)


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def collect(pdf: Path, protocol_path: Path, captures: Path) -> dict:
    protocol_raw = protocol_path.read_bytes()
    protocol = json.loads(protocol_raw)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != protocol["source"]["pdf_sha256"]:
        raise ValueError("Source PDF differs from the frozen protocol")
    captures.mkdir(parents=True, exist_ok=False)
    document = pymupdf.open(pdf)
    texts, spans = [], []
    offset = 0
    # Fixed volume boundaries, including the first heading on page 284.
    for page_number in range(284, 453):
        value = compact(document[page_number - 1].get_text())
        texts.append(value)
        spans.append((offset, offset + len(value), page_number))
        offset += len(value)
    combined = "".join(texts)
    headings = list(HEADING.finditer(combined))
    rows = []
    unparsed = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else offset
        chunk = combined[heading.end() : end]
        starts = list(re.finditer(rf"[{DIGITS}]运挨星", chunk))
        for start in starts:
            found = PREFIX.match(chunk, start.start())
            split_found = (
                SPLIT_PREFIX.match(chunk, start.start()) if found is None else None
            )
            if found is None:
                found = split_found
            if found is None:
                unparsed.append(
                    {
                        "heading": heading.group(),
                        "prefix": chunk[start.start() : start.start() + 70],
                    }
                )
                continue
            absolute = heading.end() + found.start()
            source_page = next(p for low, high, p in spans if low <= absolute < high)
            period = DIGITS.index(found[1]) + 1
            if split_found is not None:
                mountain_seed, facing_seed = found[2], found[4]
                mountain_flight, facing_flight = found[3], found[5]
            else:
                mountain_seed, facing_seed = found[2], found[3]
                flight = found[4]
                if flight.startswith("山向均"):
                    mountain_flight = facing_flight = flight[-1]
                else:
                    mountain_flight, facing_flight = flight[1], flight[3]
            literal = found.group()
            page = document[source_page - 1]
            blocks = [b for b in page.get_text("blocks") if b[6] == 0]
            block_text = "".join(compact(b[4]) for b in blocks)
            position = block_text.find(literal)
            if position < 0 or block_text.find(literal, position + 1) >= 0:
                raise ValueError("Clause cannot be uniquely located on its source page")
            cursor = 0
            rectangles = []
            for block in blocks:
                block_end = cursor + len(compact(block[4]))
                if cursor < position + len(literal) and block_end > position:
                    rectangles.append(pymupdf.Rect(block[:4]))
                cursor = block_end
            rectangle = rectangles[0]
            for other in rectangles[1:]:
                rectangle |= other
            rectangle = (rectangle + (-5, -3, 5, 3)) & page.rect
            name = f"p{source_page:03d}-{heading[2]}-{heading[3]}-{period}.png"
            image_path = captures / name
            page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rectangle).save(
                image_path
            )
            rows.append(
                {
                    "period": period,
                    "sitting_mountain": heading[2],
                    "facing_mountain": heading[3],
                    "yuan": heading[1],
                    "pdf_page": source_page,
                    "literal_prefix": literal,
                    "mountain_seed": DIGITS.index(mountain_seed) + 1,
                    "facing_seed": DIGITS.index(facing_seed) + 1,
                    "mountain_flight": (
                        "forward" if mountain_flight == "顺" else "reverse"
                    ),
                    "facing_flight": "forward" if facing_flight == "顺" else "reverse",
                    "capture": {
                        "file": name,
                        "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                        "pdf_rectangle": list(rectangle),
                        "render_scale": 2,
                    },
                }
            )
    required = {(p, m) for p in protocol["required_periods"] for m in MOUNTAINS}
    keys = [(r["period"], r["facing_mountain"]) for r in rows]
    coverage = {
        "heading_count": len(headings),
        "row_count": len(rows),
        "unique_pair_count": len(set(keys)),
        "missing_pairs": sorted(required - set(keys)),
        "unexpected_pairs": sorted(set(keys) - required),
        "duplicate_pair_count": len(keys) - len(set(keys)),
        "unparsed_clauses": unparsed,
    }
    if any(
        name == "fatebridge" or name.startswith("fatebridge.") for name in sys.modules
    ):
        raise RuntimeError("Production code was imported during source collection")
    return {
        "protocol": protocol,
        "protocol_sha256": hashlib.sha256(protocol_raw).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {"PyMuPDF": importlib.metadata.version("PyMuPDF")},
        "method": "Native PDF clause extraction and unmodified page-region rendering; no engine-derived correction",
        "fatebridge_imported": False,
        "coverage": coverage,
        "rows": rows,
        "independent_human_review_complete": False,
        "whole_book_conformity_established": False,
        "empirical_predictive_validity_established": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.pdf, args.protocol, args.captures)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["coverage"], ensure_ascii=False))
    coverage = result["coverage"]
    return int(
        coverage["heading_count"] != 24
        or coverage["unique_pair_count"] != 216
        or bool(coverage["missing_pairs"])
        or bool(coverage["unexpected_pairs"])
        or bool(coverage["duplicate_pair_count"])
        or bool(coverage["unparsed_clauses"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
