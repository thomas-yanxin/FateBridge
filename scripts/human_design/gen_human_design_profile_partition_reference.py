"""Freeze an engine-free rational oracle for the source's88degree partition.

Gate starts come from the unchanged independently transcribed2001 gate table;
line/foundation widths and profile lists come from the captured public glossary.
This does not resolve its29.1/29.2 printed line-table conflict or certify native
solar coordinates, roots, a whole original book or empirical interpretation.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / "tests/fixtures/human-design-profile-partition-source-facts.json"
GATES = ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a frozen reference")
    facts = json.loads(FACTS.read_text())
    gates = json.loads(GATES.read_text())["gates"]
    width, foundation = facts["line_arcseconds"], facts["foundation_arcseconds"]
    gate_width = 6 * width
    assert width == foundation + facts["transition_arcseconds"]
    starts = [(row["gate"], Fraction(str(row["start_longitude"]))) for row in gates]
    assert len(starts) == 64

    def point(lon):
        for gate, start in starts:
            offset = ((lon - start) % 360) * 3600
            if offset < gate_width:
                return gate, int(offset // width) + 1, offset % width
        raise AssertionError("Source gate interval gap")

    def ratio(value):
        return [value.numerator, value.denominator]

    cases = []
    for gate, start in starts:
        for line in range(1, 7):
            for boundary_name, offset in (
                ("line_start", 0),
                ("transition_start", foundation),
            ):
                cut = float((start + Fraction((line - 1) * width + offset, 3600)) % 360)
                for label, longitude in (
                    ("below", math.nextafter(cut, -math.inf)),
                    ("at", cut),
                    ("above", math.nextafter(cut, math.inf)),
                ):
                    p = Fraction(longitude) % 360
                    d = (p - facts["solar_arc_degrees"]) % 360
                    pg, pl, within = point(p)
                    dg, dl, _ = point(d)
                    profile = f"{pl}/{dl}"
                    category = "foundation" if within < foundation else "transition"
                    assert profile in facts[category + "_profiles"]
                    cases.append(
                        {
                            "id": f"g{gate:02}-l{line}-{boundary_name}-{label}",
                            "personality_longitude": longitude,
                            "personality_gate": pg,
                            "personality_line": pl,
                            "ideal_design_gate": dg,
                            "ideal_design_line": dl,
                            "ideal_profile": profile,
                            "angular_category": category,
                            "line_offset_arcseconds_ratio": ratio(within),
                            "ideal_design_longitude_degrees_ratio": ratio(d),
                        }
                    )
            for category, lo, hi in (
                ("foundation", 0, foundation),
                ("transition", foundation, width),
            ):
                longitude = float(
                    (
                        start
                        + Fraction((line - 1) * width, 3600)
                        + Fraction(lo + hi, 7200)
                    )
                    % 360
                )
                p = Fraction(longitude) % 360
                d = (p - facts["solar_arc_degrees"]) % 360
                pg, pl, within = point(p)
                dg, dl, _ = point(d)
                profile = f"{pl}/{dl}"
                assert profile in facts[category + "_profiles"]
                cases.append(
                    {
                        "id": f"g{gate:02}-l{line}-{category}-mid",
                        "personality_longitude": longitude,
                        "personality_gate": pg,
                        "personality_line": pl,
                        "ideal_design_gate": dg,
                        "ideal_design_line": dl,
                        "ideal_profile": profile,
                        "angular_category": category,
                        "line_offset_arcseconds_ratio": ratio(within),
                        "ideal_design_longitude_degrees_ratio": ratio(d),
                    }
                )
    assert len(cases) == 3072
    value = {
        "method_id": "human_design_independent_rational_profile_partition_reference_v1",
        "frozen_before_production_implementation_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "case_count": len(cases),
        "scope": "Exact arithmetic on supplied binary64 personality longitudes only.64gates x6lines x(two cuts x3neighboring floats +two interval midpoints). Ideal design is an exact88degree mathematical point, not a rounded native activation or physical truth. Negative subnormal wrap at0is retained. No tolerance or failed case removed.",
        "source_facts_sha256": hashlib.sha256(FACTS.read_bytes()).hexdigest(),
        "gate_reference_sha256": hashlib.sha256(GATES.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": len(cases),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
