"""Bind public rendered observations to their original PDF and frozen inputs.

No calculation-engine imports. Missing planned rows are explicit; a partial
collection cannot be reported as full768-stratum acceptance. Source labels are
retained literally apart from whitespace normalization for PDF layout wrapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from build_human_design_cross_coverage import ORDER, source_utc
from read_human_design_official_pdf import LABELS, visible_properties

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-profile-coverage-plan.json"
PLAN_SHA256 = "ea4e0cd15bd228a3002bd055aaeaae28264b5edf0d51505af1828c29e78ce143"


def normalized(properties):
    return {k: " ".join(v.split()) for k, v in properties.items()}


def build(observations: Path, pdf_directory: Path, *, require_complete=False):
    plan_raw = PLAN_PATH.read_bytes()
    if hashlib.sha256(plan_raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Frozen pre-output plan changed")
    plan = json.loads(plan_raw)
    for name, expected in plan["preserved_cohorts_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Preserved cohort changed: {name}")
    samples = {r["id"]: r for r in plan["cases"]}
    raw = observations.read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) - set(samples):
        raise ValueError("Duplicated or unplanned observation IDs")
    missing = [identifier for identifier in samples if identifier not in ids]
    if require_complete and missing:
        raise ValueError(f"Incomplete collection: {len(missing)} planned rows missing")
    cases, changes, sources = [], [], []
    for row in rows:
        identifier = row["id"]
        if datetime.fromisoformat(row["collected_at_utc"]) <= datetime.fromisoformat(
            plan["declared_at_utc"]
        ):
            raise ValueError(f"Observation precedes frozen plan: {identifier}")
        facts, source = row["facts"], row["source"]
        properties = facts["properties"]
        if (
            set(properties) != set(LABELS)
            or properties["Name"] != f"FateBridge fictional {identifier}"
        ):
            raise ValueError(
                f"Incomplete properties or wrong rendered identity: {identifier}"
            )
        columns = facts["columns"]
        if set(columns) != {"design", "personality"} or any(
            len(v) != 13 for v in columns.values()
        ):
            raise ValueError(f"Incomplete activation columns: {identifier}")
        for values in columns.values():
            for value in values:
                gate, line = map(int, value.split("."))
                if not 1 <= gate <= 64 or not 1 <= line <= 6:
                    raise ValueError(f"Invalid rendered gate.line: {identifier}")
        pdf = pdf_directory / source["pdf_filename"]
        if pdf.parent.resolve() != pdf_directory.resolve():
            raise ValueError("PDF path escapes evidence directory")
        pdf_raw = pdf.read_bytes()
        if (
            len(pdf_raw) != source["pdf_bytes"]
            or hashlib.sha256(pdf_raw).hexdigest() != source["pdf_sha256"]
        ):
            raise ValueError(f"Original PDF changed: {identifier}")
        canonical = normalized(properties)
        if normalized(visible_properties(pdf)) != canonical:
            raise ValueError(f"Rendered/PDF properties differ: {identifier}")
        for key, value in properties.items():
            if value != canonical[key]:
                changes.append(
                    {
                        "id": identifier,
                        "property": key,
                        "raw": value,
                        "normalized": canonical[key],
                    }
                )
        cases.append(
            {
                "id": identifier,
                "birth_input": samples[identifier]["birth_input"],
                "displayed_birth_utc": source_utc(canonical["Date and Time (UTC)"]),
                "columns": columns,
                "properties": canonical,
                "defined_channel_render_ids": facts["defined_channel_render_ids"],
                "defined_centers": facts["defined_centers"],
                "pdf_sha256": source["pdf_sha256"],
                "pdf_filename": source["pdf_filename"],
            }
        )
        sources.append({"id": identifier, **source})
    return {
        "source": {
            "publisher": "Jovian Archive / Maia Mechanics public calculator",
            "url": plan["source_url"],
            "collected_at": max((r["collected_at_utc"] for r in rows), default=None),
            "plan_sha256": PLAN_SHA256,
            "observation_file_sha256": hashlib.sha256(raw).hexdigest(),
            "independent_pdf_properties_checked": len(cases),
            "pdf_diagram_independently_transcribed": False,
            "whitespace_changes": changes,
            "pdf_sources": sources,
        },
        "collection_status": "complete" if not missing else "incomplete",
        "planned_case_count": len(samples),
        "observed_case_count": len(cases),
        "missing_planned_ids": missing,
        "plan_reference": PLAN_PATH.name,
        "planet_order": ORDER,
        "cases": cases,
        "scope": "Predeclared synthetic1981 inputs; engine-informed, not blind. Planned64gates x12profiles. Only cases present here have observations; all missing IDs remain explicit. PDF text independently checks13properties;26gate.lines, centers and channels come from renderedSVG, not independent PDF diagram transcription. Literal cross-name failures, original19/193cohorts and original acceptance criteria remain unchanged. No complete line-prose, fixing, source-authentication, cycle-origin, full-calendar or real-world-prediction certification.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--pdf-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    value = build(
        args.observations, args.pdf_directory, require_complete=args.require_complete
    )
    with args.output.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: value[k]
                for k in (
                    "collection_status",
                    "planned_case_count",
                    "observed_case_count",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
