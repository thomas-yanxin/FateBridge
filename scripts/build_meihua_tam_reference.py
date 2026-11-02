"""Extract printed TAM 1900 date cells without any lunar-calendar calculator.

Reference-only dependency: run with uv --with pymupdf==1.26.7. Existing frozen
files are checked by default; --write creates them only when they do not exist.
"""

import argparse
import bisect
import calendar
import hashlib
import json
import unicodedata
from pathlib import Path

PDF_SHA256 = "e6bc3affa9264fd377e5b91d50047d2c99fa5a9f44fc6f15f9f7e956dc10f649"


def extract(directory: Path) -> dict[str, str]:
    import fitz

    path = directory / "sources/tam-1900.pdf"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError("The fixed primary PDF changed; adjudicate before extraction")
    document = fitz.open(path)
    page = document[0]
    words = [
        (fitz.Rect(w[:4]) * page.rotation_matrix, w[4]) for w in page.get_text("words")
    ]
    # Header labels define Gregorian day columns; the left-hand month labels
    # define row bands. Coordinates are in the displayed, rotated page frame.
    headers = {}
    months = {}
    for rect, text in words:
        if text.isdigit() and 128 <= rect.y0 <= 130 and 1 <= int(text) <= 31:
            headers[int(text)] = (rect.x0 + rect.x1) / 2
        if (
            text.isdigit()
            and 70 <= rect.x0 <= 90
            and 142 <= rect.y0 <= 486
            and 1 <= int(text) <= 12
        ):
            month_word = next(
                r
                for r, t in words
                if t == "月" and 70 <= r.x0 <= 90 and 0 < r.y0 - rect.y0 < 20
            )
            months[int(text)] = (rect.y0 + month_word.y1) / 2
    if set(headers) != set(range(1, 32)) or set(months) != set(range(1, 13)):
        raise ValueError("The fixed PDF must retain all 31 columns and 12 month rows")
    column_step = (headers[31] - headers[1]) / 30
    x_edges = [headers[1] - column_step / 2 + i * column_step for i in range(32)]
    centers = [months[i] for i in range(1, 13)]
    y_edges = [centers[0] - (centers[1] - centers[0]) / 2]
    y_edges += [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    y_edges += [centers[-1] + (centers[-1] - centers[-2]) / 2]
    grouped = {}
    for rect, text in words:
        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
        column, row = bisect.bisect_right(x_edges, cx), bisect.bisect_right(y_edges, cy)
        if 1 <= column <= 31 and 1 <= row <= 12:
            grouped.setdefault((row, column), []).append(
                {"text": text, "bbox": [round(n, 4) for n in rect]}
            )
    cells = []
    for month in range(1, 13):
        valid_days = calendar.monthrange(1900, month)[1]
        for day in range(1, 32):
            tokens = sorted(
                grouped.get((month, day), []),
                key=lambda w: (w["bbox"][1], w["bbox"][0]),
            )
            if day > valid_days:
                if tokens:
                    raise ValueError(
                        "The primary table has text in an invalid Gregorian date cell"
                    )
                continue
            label = unicodedata.normalize(
                "NFKC", "".join(t["text"] for t in tokens)
            ).replace(" ", "")
            if not label:
                raise ValueError("An actual Gregorian date has no printed lunar label")
            cells.append(
                {
                    "date": f"1900-{month:02d}-{day:02d}",
                    "printed_label": label,
                    "source_page": 0,
                    "gregorian_month_row": month,
                    "gregorian_day_column": day,
                    "tokens": tokens,
                }
            )
    if len(cells) != 365:
        raise ValueError("Extraction must retain every civil date in 1900")
    metadata = {
        "source_pdf_sha256": PDF_SHA256,
        "pymupdf_version": fitz.VersionBind,
        "page_count": len(document),
        "page_rotation": page.rotation,
        "display_page_size": [page.rect.width, page.rect.height],
        "column_centers": headers,
        "month_row_centers": months,
        "normalization": "display rotation, geometric cell grouping, top-to-bottom token order, Unicode NFKC and space removal",
        "calendar_calculators_used": [],
        "date_count": 365,
    }
    return {
        "cells.json": json.dumps(
            {
                "kind": "primary_printed_table_cells_not_production_answers",
                "cells": cells,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "extraction.json": json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--references",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/meihua_calendar_v2",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    files = extract(args.references)
    for name, content in files.items():
        path = args.references / name
        if args.write:
            if path.exists():
                raise FileExistsError(
                    "Frozen reference exists; use the default check instead"
                )
            path.write_text(content, encoding="utf-8")
        elif path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Extracted primary cells drifted: {name}")
    print(
        "365 primary cells "
        + ("created" if args.write else "reproduced identically")
        + "; no lunar calculator used"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
