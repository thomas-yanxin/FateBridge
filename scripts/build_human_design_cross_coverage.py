"""Build the new official cohort from frozen rendered facts and original PDFs.

No calculation engine imports. The plan supplies inputs only. Observed expected
activations, graph and properties come from the separate page observations.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from read_human_design_official_pdf import visible_properties

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
PLAN = FIXTURES / "human-design-cross-coverage-plan.json"
OBSERVATIONS = FIXTURES / "human-design-cross-coverage-observations.json"
OBSERVATION_SHA256 = "46d801f0c468f1b87096ac6951cd2352cddf440af25cc57875f70a631f5da22c"
ORDER = [
    "Sun",
    "Earth",
    "Moon",
    "NorthNode",
    "SouthNode",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
]
MONTHS = {
    name: i
    for i, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}


def source_utc(label):
    date, year, clock = label.split(", ")
    month, day = date.split()
    return f"{int(year):04}-{MONTHS[month]:02}-{int(day):02}T{clock}:00+00:00"


def build(pdf_directory):
    raw = OBSERVATIONS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OBSERVATION_SHA256:
        raise ValueError(
            "Frozen rendered observations changed; review before rebuilding"
        )
    observed = json.loads(raw)
    plan = json.loads(PLAN.read_bytes())
    if hashlib.sha256(PLAN.read_bytes()).hexdigest() != observed["plan_sha256"]:
        raise ValueError("The pre-output selection plan changed")
    samples = {r["id"]: r for r in plan["cases"]}
    facts = {r["id"]: r["facts"] for r in observed["observations"]}
    sources = {r["id"]: r for r in observed["sources"]}
    if (
        len(samples) != 193
        or set(samples) != set(facts)
        or set(samples) != set(sources)
    ):
        raise ValueError("Missing, extra or duplicated planned source observations")
    cases = []
    for sample in plan["cases"]:
        identifier = sample["id"]
        row = facts[identifier]
        source = sources[identifier]
        pdf = pdf_directory / source["pdf_filename"]
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != source["pdf_sha256"]:
            raise ValueError(f"Original PDF changed: {identifier}")
        if visible_properties(pdf) != row["properties"]:
            raise ValueError(f"Rendered/PDF properties differ: {identifier}")
        if any(len(row["columns"][s]) != 13 for s in ("design", "personality")):
            raise ValueError("Incomplete rendered activation column")
        cases.append(
            {
                "id": identifier,
                "birth_input": sample["birth_input"],
                "displayed_birth_utc": source_utc(
                    row["properties"]["Date and Time (UTC)"]
                ),
                "columns": row["columns"],
                "properties": row["properties"],
                "defined_channel_render_ids": row["defined_channel_render_ids"],
                "defined_centers": row["defined_centers"],
                "pdf_sha256": source["pdf_sha256"],
                "pdf_filename": source["pdf_filename"],
            }
        )
    return {
        "source": {
            "publisher": "Jovian Archive / Maia Mechanics",
            "url": observed["source_url"],
            "collection": observed["scope"],
            "collected_at": observed["collected_at_utc"],
            "observation_fixture_sha256": OBSERVATION_SHA256,
            "plan_sha256": observed["plan_sha256"],
            "transcription_crosscheck": observed["transcription_crosscheck"],
        },
        "plan_reference": PLAN.name,
        "planet_order": ORDER,
        "cases": cases,
        "scope": "All64 Personality Sun gates at each of3 angles in193 synthetic, engine-selected inputs from1980; all192 gate/angle strata plus one extra quadruple definition. Inputs fixed before new official outputs. Earlier19 cases unchanged and separate. No aliases, birth-record authentication, population frequency, full calendar-range, line-prose or prediction certification.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--catalog-output", type=Path)
    args = parser.parse_args()
    cohort = build(args.pdf_directory)
    text = json.dumps(cohort, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(text)
    if args.catalog_output:
        rows = []
        angles = {
            "Right Angle": "right",
            "Juxtaposition": "juxtaposition",
            "Left Angle": "left",
        }
        for c in cohort["cases"]:
            match = re.fullmatch(
                r"(Right Angle|Left Angle|Juxtaposition) Cross of (.+?)\s+\((\d+)/(\d+) \| (\d+)/(\d+)\)",
                c["properties"]["Incarnation Cross"],
            )
            if match is None:
                raise ValueError("Unknown visible source cross label")
            gates = list(map(int, match.groups()[2:]))
            columns = c["columns"]
            if gates != [
                int(columns[s][i].split(".")[0])
                for s, i in (
                    ("personality", 0),
                    ("personality", 1),
                    ("design", 0),
                    ("design", 1),
                )
            ]:
                raise ValueError(
                    "Visible cross gate quartet differs from visible Sun/Earth columns"
                )
            rows.append(
                {
                    "case_id": c["id"],
                    "gates": gates,
                    "angle": angles[match[1]],
                    "display_name": match[2],
                    "profile": c["properties"]["Profile"],
                    "definition": c["properties"]["Definition"],
                    "pdf_sha256": c["pdf_sha256"],
                }
            )
        course = FIXTURES / "human-design-course-cross-disagreement.json"
        value = {
            "method_id": "human_design_expanded_official_cross_observation_v1",
            "source": cohort["source"],
            "scope": cohort["scope"],
            "cohort_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "observations": rows,
            "course_list_disagreement": json.loads(course.read_text()),
            "course_disagreement_fixture_sha256": hashlib.sha256(
                course.read_bytes()
            ).hexdigest(),
        }
        args.catalog_output.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        json.dumps(
            {"source_charts": 193, "activation_slots": 5018, "output": str(args.output)}
        )
    )


if __name__ == "__main__":
    main()
