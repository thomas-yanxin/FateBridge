"""Observe visible triangles in unchanged official PDFs, without engine imports.

Requires operator-installed Poppler pdfimages. Neither OCR nor chart calculation
is used. Blank cells remain unobserved fixing states, not unfixed ground truth.
The detection plan was frozen before comparison with the production engine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
COHORTS = (
    (
        "human-design-official-charts.json",
        "77e5e322dd87230a307a1e8413f4e38b1890d3f27da0b6a71c3a612d146d3225",
    ),
    (
        "human-design-official-authority-charts.json",
        "552d68813be5b40076981aa07f4e34c2965c5ecc6444537a539ffec06df6ecc7",
    ),
)
PLAN_SHA = "db7b67310c74752c5b50a860b3e9ec59f33e23563ee3e9a366d9ac1ed56f3998"


def ppm(path: Path):
    raw = path.read_bytes()
    pos, tokens = 0, []
    for _ in range(4):
        while True:
            while pos < len(raw) and raw[pos : pos + 1].isspace():
                pos += 1
            if raw[pos : pos + 1] != b"#":
                break
            pos = raw.index(b"\n", pos) + 1
        start = pos
        while pos < len(raw) and not raw[pos : pos + 1].isspace():
            pos += 1
        tokens.append(raw[start:pos])
    if tokens[0] != b"P6" or tokens[3] != b"255":
        return None
    # Consume the header delimiter, never strip whitespace-valued raster bytes.
    pos += 2 if raw[pos : pos + 2] == b"\r\n" else 1
    width, height = map(int, tokens[1:3])
    pixels = raw[pos:]
    if len(pixels) != width * height * 3:
        raise ValueError("Incomplete PPM raster")
    return width, height, pixels


def markers(path: Path):
    raw = ppm(path)
    if raw is None or raw[:2] != (200, 800):
        raise ValueError("Expected the original 200 by 800 activation column")
    width, height, pixels = raw
    points = {
        (i % width, i // width)
        for i in range(width * height)
        if pixels[3 * i : 3 * i + 3] == b"\x7c\x7c\x7c"
    }
    found, rejected = [], []
    while points:
        queue, component = [points.pop()], []
        while queue:
            x, y = queue.pop()
            component.append((x, y))
            for dx, dy in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
                (-1, -1),
                (1, 1),
                (-1, 1),
                (1, -1),
            ):
                point = x + dx, y + dy
                if point in points:
                    points.remove(point)
                    queue.append(point)
        if len(component) < 8:
            continue
        box = [
            min(x for x, y in component),
            min(y for x, y in component),
            max(x for x, y in component),
            max(y for x, y in component),
        ]
        mean = sum(y for x, y in component) / len(component)
        row = round((mean - 90) / 56)
        offset = mean - (box[1] + box[3]) / 2
        record = {"pixels": len(component), "bbox": box, "centroid_y": mean, "row": row}
        if not (
            5 <= box[2] - box[0] + 1 <= 14
            and 5 <= box[3] - box[1] + 1 <= 14
            and len(component) >= 20
            and 0 <= row < 13
            and abs(mean - (90 + 56 * row)) < 8
            and abs(offset) > 0.1
        ):
            rejected.append(record)
            continue
        record["visible_marker"] = "exaltation" if offset > 0 else "detriment"
        found.append(record)
    if rejected or len({r["row"] for r in found}) != len(found):
        raise ValueError(
            f"Unrecognized or duplicate marker components: {found}, {rejected}"
        )
    return sorted(found, key=lambda r: r["row"])


def extract(folders: tuple[Path, Path]) -> dict:
    plan_path = ROOT / "tests/fixtures/human-design-fixing-observation-plan.json"
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != PLAN_SHA:
        raise ValueError("Detection plan changed after comparison")
    observations, sources = [], []
    for (filename, sha), folder in zip(COHORTS, folders):
        path = ROOT / "tests/fixtures" / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("Original chart cohort changed")
        cohort = json.loads(path.read_text())
        sources.append(
            {
                "fixture": filename,
                "sha256": sha,
                "source": cohort["source"],
                "selection_scope": cohort["scope"],
            }
        )
        for case in cohort["cases"]:
            pdf = folder / case["pdf_filename"]
            if hashlib.sha256(pdf.read_bytes()).hexdigest() != case["pdf_sha256"]:
                raise ValueError("Original PDF changed: " + case["id"])
            with TemporaryDirectory(prefix="hd-fixing-observations-") as temp:
                subprocess.run(
                    ["pdfimages", str(pdf), str(Path(temp) / "image")],
                    check=True,
                    capture_output=True,
                )
                columns = []
                for image in sorted(Path(temp).glob("*.ppm")):
                    image_data = ppm(image)
                    if image_data is not None and image_data[:2] == (200, 800):
                        columns.append(image)
                if len(columns) != 2:
                    raise ValueError("Expected original design and personality columns")
                rows = []
                for side, column in zip(("design", "personality"), columns):
                    by_row = {r["row"]: r for r in markers(column)}
                    for index, body in enumerate(cohort["planet_order"]):
                        component = by_row.get(index)
                        rows.append(
                            {
                                "side": side,
                                "body": body,
                                "gate_line": case["columns"][side][index],
                                "visible_marker": (
                                    component["visible_marker"]
                                    if component
                                    else "no_visible_marker"
                                ),
                                "component": component,
                            }
                        )
                observations.append(
                    {
                        "case_id": case["id"],
                        "pdf_sha256": case["pdf_sha256"],
                        "cohort_sha256": sha,
                        "observations": rows,
                    }
                )
    return {
        "catalogue_id": "official_visible_natal_fixing_markers_2026_v1",
        "plan_sha256": PLAN_SHA,
        "plan": json.loads(plan_path.read_text()),
        "cohort_sources": sources,
        "scope": "All 19 original PDFs and 494 activation slots, no selection after comparison. Gate.lines are the unchanged printed cohort observations. Raster triangle polarity is observed independently of FateBridge. Not an independent birth-clock or astronomy reference.",
        "rendering_limit": "Public widget references a combined fixing symbol but its fixing asset object only defines exalted and detriment. No visible marker does not identify unfixed versus juxtaposition or other hidden states. The 356 blank slots cannot certify full fixing states.",
        "node_agency_source": {
            "url": "https://humandesignsystem.com/archive/newsletters/0402.pdf",
            "author": "Martin Grassinger",
            "article": "Raise the Titanic",
            "pdf_page_one_based": 2,
            "date": "1997-06-30",
            "scope": "Nodes do not fix other lines; this is donor agency, not a prohibition on receiving planetary fixing.",
        },
        "fixing_rule_source": {
            "url": "https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition",
            "author": "Ryan Hanna",
            "date": "2026-06-09",
            "scope": "Current official public explanation, not claimed to be the 2001 primary text.",
        },
        "complete_fixing_statuses_certified": False,
        "full_384_line_meaning_acceptance": False,
        "cases": observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar-pdfs", type=Path, required=True)
    parser.add_argument("--authority-pdfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract((args.calendar_pdfs, args.authority_pdfs))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Observed {len(result['cases'])} original PDFs")


if __name__ == "__main__":
    main()
