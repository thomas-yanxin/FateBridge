"""Independent native-PDF capture; no FateBridge imports or computed chart labels."""

import argparse
import hashlib
import importlib.metadata
import json
import re
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pdf", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
out = args.output
out.mkdir(parents=True, exist_ok=False)
(out / "captures").mkdir()
pdf = args.pdf
sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
assert sha == "b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847"
old = runpy.run_path(str(root / "scripts/fengshui/collect_fengshui_lower_clauses.py"))
compact = old["compact"]
document = pymupdf.open(pdf)
texts = []
spans = []
offset = 0
for page in range(284, 454):
    text = compact(document[page - 1].get_text())
    texts.append(text)
    spans.append((offset, offset + len(text), page))
    offset += len(text)
combined = "".join(texts)
headings = list(old["HEADING"].finditer(combined))
rows = []
pattern = re.compile(r"(山向|山|向)(?:均)?(生入|生出|克入|克出|比和)")
for i, heading in enumerate(headings):
    end = headings[i + 1].start() if i + 1 < len(headings) else offset
    chunk = combined[heading.end() : end]
    starts = list(re.finditer(r"[一二三四五六七八九]运挨星", chunk))
    for j, start in enumerate(starts):
        finish = starts[j + 1].start() if j + 1 < len(starts) else len(chunk)
        literal = chunk[start.start() : finish].split("则先谨按")[0]
        prefix = old["PREFIX"].match(literal) or old["SPLIT_PREFIX"].match(literal)
        assert prefix is not None, (heading.group(), literal)
        absolute = heading.end() + start.start()
        page = next(p for a, b, p in spans if a <= absolute < b)
        # Retain every native literal segment, including unparsed or repeated labels.
        parsed = [
            {"subject": m[1], "label": m[2], "offset": m.start()}
            for m in pattern.finditer(literal[len(prefix.group()) :])
        ]
        labels = {
            role: [p["label"] for p in parsed if p["subject"] in {role, "山向"}]
            for role in ("山", "向")
        }
        capture_pages = []
        for low, high, n in spans:
            if high <= absolute or low >= absolute + len(literal):
                continue
            page_text = compact(document[n - 1].get_text())
            left = max(absolute, low) - low
            right = min(absolute + len(literal), high) - low
            part = page_text[left:right]
            cursor = 0
            rects = []
            for block in document[n - 1].get_text("blocks"):
                if block[6] != 0:
                    continue
                limit = cursor + len(compact(block[4]))
                if cursor < right and limit > left:
                    rects.append(pymupdf.Rect(block[:4]))
                cursor = limit
            assert rects, (n, literal)
            rectangle = rects[0]
            for rect in rects[1:]:
                rectangle |= rect
            rectangle = (rectangle + (-5, -3, 5, 3)) & document[n - 1].rect
            name = (
                f'{heading[2]}-{heading[3]}-{old["DIGITS"].index(prefix[1])+1}-p{n}.png'
            )
            document[n - 1].get_pixmap(
                matrix=pymupdf.Matrix(2, 2), clip=rectangle
            ).save(out / "captures" / name)
            capture_pages.append(
                {
                    "file": "captures/" + name,
                    "page": n,
                    "rectangle": list(rectangle),
                    "native_part": part,
                }
            )
        rows.append(
            {
                "period": old["DIGITS"].index(prefix[1]) + 1,
                "sitting_mountain": heading[2],
                "facing_mountain": heading[3],
                "page": page,
                "literal_full_clause": literal,
                "literal_prefix": prefix.group(),
                "parsed_mentions": parsed,
                "labels": labels,
                "both_roles_unique": all(len(x) == 1 for x in labels.values()),
                "captures": capture_pages,
            }
        )
pages = {}
for number in (283, 453, 860, 901, 909, 910, 911):
    name = f"definition-p{number}.png"
    document[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(out / name)
    pages[str(number)] = {"file": name, "native_text": document[number - 1].get_text()}
elements = {
    "1": "水",
    "2": "土",
    "3": "木",
    "4": "木",
    "5": "土",
    "6": "金",
    "7": "金",
    "8": "土",
    "9": "火",
}
# Independently written reference table; rows are host, columns are guest.
# This is derived from the four named source operations, not 81 fortune clauses.
matrix = {
    "木": {"木": "比和", "火": "生出", "土": "克出", "金": "克入", "水": "生入"},
    "火": {"木": "生入", "火": "比和", "土": "生出", "金": "克出", "水": "克入"},
    "土": {"木": "克入", "火": "生入", "土": "比和", "金": "生出", "水": "克出"},
    "金": {"木": "克出", "火": "克入", "土": "生入", "金": "比和", "水": "生出"},
    "水": {"木": "生出", "火": "克出", "土": "克入", "金": "生入", "水": "比和"},
}
reference = {
    "reference_id": "shen_host_guest_native_recapture_v1",
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_pdf_sha256": sha,
    "source_pages": pages,
    "star_elements": elements,
    "fixed_earth_numbers": {
        "N": 1,
        "NE": 8,
        "E": 3,
        "SE": 4,
        "S": 9,
        "SW": 2,
        "W": 7,
        "NW": 6,
        "C": 5,
    },
    "capture_protocol_revision": 3,
    "derived_host_guest_matrix": matrix,
    "matrix_kind": "25 derived element cases from named operations, not literal 81 fortune cells",
    "role_policy": {
        "sitting_palace": {"host": "mountain", "guest": "facing"},
        "facing_palace": {"host": "facing", "guest": "mountain"},
        "earth_period": {"host": "earth", "guest": "period"},
        "period_mountain": {"host": "period", "guest": "mountain"},
        "period_facing": {"host": "period", "guest": "facing"},
        "other_six_palaces": "not_assigning_a_host_guest_under_this_source",
        "center": "not_covered",
    },
    "full_lower_clauses": rows,
    "required_lower_clauses": 216,
    "unparsed_or_repeated_labels": [r for r in rows if not r["both_roles_unique"]],
    "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "old_collector_sha256": hashlib.sha256(
        (root / "scripts/fengshui/collect_fengshui_lower_clauses.py").read_bytes()
    ).hexdigest(),
    "versions": {
        "Python": sys.version,
        "PyMuPDF": importlib.metadata.version("PyMuPDF"),
    },
    "source_fact_capture_before_new_implementation": False,
    "supersedes_frozen_reference": False,
    "independent_human_expert_review": False,
    "blind_assessment": False,
    "whole_book_conformity_established": False,
    "real_world_prediction_established": False,
}
assert (
    len(rows) == 216 and len({(r["period"], r["facing_mountain"]) for r in rows}) == 216
)
assert not any(n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules)
(out / "reference.json").write_text(
    json.dumps(reference, ensure_ascii=False, indent=2) + "\n"
)
hashes = {
    str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(out.rglob("*"))
    if p.is_file()
}
(out / "hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
print(
    json.dumps(
        {
            "rows": len(rows),
            "unparsed_or_repeated": len(reference["unparsed_or_repeated_labels"]),
            "files": len(hashes),
            "reference_sha256": hashes["reference.json"],
        },
        ensure_ascii=False,
    )
)
