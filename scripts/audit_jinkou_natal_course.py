"""京本本命另课: literal clause, manual symbolic cases, and scope limits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_natal_course_v1"
PIN = "d17d459dc6cd8b88982456828a1f0169e304361f81b72fe741a67b7f15790717"


def reference() -> dict[str, Any]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != PIN:
        raise ValueError("Frozen natal-course reference changed")
    files = json.loads((CORPUS / "freeze.json").read_text())
    if {p.name for p in CORPUS.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Natal-course source inventory changed")
    for name, digest in files.items():
        if hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Natal-course source changed")
    return json.loads((CORPUS / "reference.json").read_text())


TABLES = reference()["literal_tables"]


def literal_positions(
    stem: str, hour: str, general: str, natal: str, diurnal: bool
) -> list[str]:
    """Independent small table expansion, not production's position builder."""
    tables = TABLES
    branches, stems = tables["branches"], tables["day_stems"]
    i, n = stems.index(stem), branches.index(natal)
    start = tables["noble_day" if diurnal else "noble_night"][i]
    direction = -1 if start in tables["reverse_starts"] else 1
    god_index = ((n - branches.index(start)) * direction) % 12
    return [
        stems[(stems.index(tables["wuzi_start"][i]) + n) % 10],
        tables["god_inherent_branches"][god_index],
        branches[(branches.index(general) + n - branches.index(hour)) % 12],
        natal,
    ]


def observe(case: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.metaphysics.jinkou_natal_course import build_natal_course
    from scripts.audit_ren_classical import make_seed

    return build_natal_course(
        make_seed(case),
        {"month_general": {"branch": case["general"]}},
        birth_year_ganzhi=None,
        natal_branch=case["natal"],
        gender="未知",
        is_diurnal=case["diurnal"],
    )


def audit() -> dict[str, Any]:
    ref = reference()
    rows = []
    for case in ref["cases"]:
        value = observe(case)
        actual = [r["content"] for r in value["course"]["rows"]]
        rows.append(
            dict(
                id=case["id"],
                actual=actual,
                expected=case["expected"],
                matched=actual == case["expected"],
            )
        )
    return dict(
        source_sha256=ref["source_sha256"],
        source_pages=ref["original_pdf_pages"],
        manual_symbolic_cases=rows,
        matched=sum(r["matched"] for r in rows),
        printed_historical_cases=0,
        selected_reading=ref["reading"],
        six_unresolved_predicates_preserved=True,
        whole_book_conformance=False,
        new_independent_model_processes=0,
        goal_complete=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    value = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(value)
    print(value)
    raise SystemExit(0 if result["matched"] == 6 else 1)
