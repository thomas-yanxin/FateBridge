"""Audit all printed Witte1924 comparative rows using independent integer minutes.

Returns1 for retained numerical discrepancies,2 for invalid source material.
This does not calculate a natal chart, apply event claims or call FateBridge.
"""

import argparse
import hashlib
import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/uranian-witte1924-comparative.json"
)
FIXTURE_SHA256 = "a493e9f5534aa2357ca7da69273234974ebc8e868b507431c51bdde1b06da6ea"
FULL = 360 * 60


def minutes(position):
    sign, degree, minute = position
    if any(type(v) is not int for v in position) or not (
        0 <= sign < 12 and 0 <= degree < 30 and 0 <= minute < 60
    ):
        raise ValueError("Invalid manually transcribed zodiac coordinate")
    return (sign * 30 + degree) * 60 + minute


def audit(path=FIXTURE):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        raise ValueError("Frozen original transcription digest mismatch")
    data = json.loads(raw)
    natal = {
        name: minutes(position)
        for name, position in data["natal_table_page138"].items()
    }
    rows = []
    for frame, table in data["printed_tables_page139"].items():
        anchor = table["anchor"]
        target = table["target_tropical_longitude"] * 60
        for name, printed in table["positions"].items():
            observed = minutes(printed)
            calculated = (natal[name] - natal[anchor] + target) % FULL
            residual = (observed - calculated + FULL // 2) % FULL - FULL // 2
            # The same printed anchor cancels itself; other coordinates have
            # two printed operands plus one printed output interval.
            radius = 0.5 if name == anchor else 1.5
            rows.append(
                {
                    "frame": frame,
                    "factor": name,
                    "anchor": anchor,
                    "printed_arcminutes": observed,
                    "calculated_arcminutes": calculated,
                    "printed_minus_calculated_arcminutes": residual,
                    "nearest_arcminute_interval_allowance": radius,
                    "compatible_under_declared_rounding_assumption": abs(residual)
                    <= radius,
                    "implied_natal_operand_arcminutes": (
                        observed + natal[anchor] - target
                    )
                    % FULL,
                }
            )
    example = data["mirror_example_page138"]
    original = minutes(example["input"])
    reflected = (180 * 60 - original) % FULL
    reflection_opposition = (-original) % FULL
    mirrors = {
        "printed_reflection_matches": reflected
        == minutes(example["solstitial_reflection"]),
        "printed_reflection_of_opposition_matches": reflection_opposition
        == minutes(example["reflection_of_opposition"]),
        "coordinates_arcminutes": [
            original,
            (original + FULL // 2) % FULL,
            reflected,
            reflection_opposition,
        ],
    }
    failed = [r for r in rows if not r["compatible_under_declared_rounding_assumption"]]
    return {
        "scope": "Exploratory source arithmetic audit, not a blind original-book or real prediction validation",
        "source": data["source"],
        "fixture_sha256": FIXTURE_SHA256,
        "printed_rotation_rows": len(rows),
        "compatible_rows": len(rows) - len(failed),
        "uncoordinated_rows": failed,
        "all_rows": rows,
        "mirror_example": mirrors,
        "original_printing_policy_authenticated": False,
        "source_house_labels": data["raw_northern_earth_house_labels_page138"],
        "source_inputs_rewritten_or_fitted": False,
        "original_method_fully_accepted": False,
        "real_world_efficacy": "not_tested",
        "authority_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", default=FIXTURE, type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.fixture)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "source_integrity_failed", "error": str(exc)}))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(
        json.dumps(
            {
                "compatible_rows": result["compatible_rows"],
                "uncoordinated_rows": len(result["uncoordinated_rows"]),
                "authority_certified": False,
            }
        )
    )
    return 1 if result["uncoordinated_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
