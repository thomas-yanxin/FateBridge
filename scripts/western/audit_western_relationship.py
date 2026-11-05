"""Reproduce bounded geographic, native-frame and relationship-recipe evidence."""

import argparse
import hashlib
import json
import math
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.relationship_geometry import (
    geographic_midpoint,
    unique_midpoint,
)
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.services.astrology import calculate_relative_chart_analysis

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/western-geographiclib-midpoints.json"
METHODS = ROOT / "tests/fixtures/western-relationship-methods.json"


def audit():
    reference = json.loads(REFERENCE.read_text())
    geography = []
    for row in reference["cases"]:
        longitude, latitude = geographic_midpoint(
            *row["input_longitudes_latitudes"], spherical=True
        )
        longitude_error = abs((longitude - row["expected_longitude"] + 180) % 360 - 180)
        if abs(row["expected_latitude"]) == 90:
            longitude_error = 0.0  # meridian is undefined at the pole
        error = max(longitude_error, abs(latitude - row["expected_latitude"]))
        geography.append(
            {
                "reference": row,
                "longitude": longitude,
                "latitude": latitude,
                "error_degrees": error,
                "passed": error <= reference["tolerance_degrees"],
            }
        )
    first = dict(
        name="甲",
        birth_year=1990,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="UTC",
        birth_longitude=179,
        birth_latitude=10,
    )
    second = dict(
        name="乙",
        birth_year=1992,
        birth_month=3,
        birth_day=2,
        birth_hour=8,
        birth_minute=18,
        birth_timezone="UTC",
        birth_longitude=-179,
        birth_latitude=20,
    )
    variants = []
    previous = configured_ephemeris_path()
    try:
        with tempfile.TemporaryDirectory(
            prefix="fatebridge-relationship-audit-"
        ) as empty:
            configure_ephemeris_path(empty)
            for variant in ("uncorrected", "corrected", "spherical"):
                for mode in ("TimeSpace", "Marks"):
                    result = calculate_relative_chart_analysis(
                        inner_payload=first,
                        outer_payload=second,
                        relative_mode=mode,
                        davison_variant=variant,
                        hsys=0,
                        zodiacal=1,
                    )
                    if "error" in result:
                        raise RuntimeError(result["error"])
                    charts = result.get("marks_charts", {"pair": result["chart"]})
                    variants.append(
                        {
                            "mode": mode,
                            "variant": variant,
                            "profile": result["relationship_profile"],
                            "charts": {
                                key: {
                                    "person_info": value["person_info"],
                                    "chart_profile": value["chart_profile"],
                                }
                                for key, value in charts.items()
                            },
                            "passed": all(
                                value["chart_profile"]["derivation_policy"][
                                    "positions_from_single_instant"
                                ]
                                and value["chart_profile"]["derivation_policy"][
                                    "variant"
                                ]
                                == variant
                                for value in charts.values()
                            ),
                        }
                    )
    finally:
        configure_ephemeris_path(previous)
    files = [
        "src/fatebridge/core/astro/relationship_geometry.py",
        "src/fatebridge/core/astro/relationship_charts.py",
        "src/fatebridge/core/astro/relationship.py",
        "src/fatebridge/core/astro/layout.py",
        "src/fatebridge/core/astro/aspects.py",
        "src/fatebridge/core/requests/astrology.py",
        "src/fatebridge/services/catalog/astro_bindings.py",
        "src/fatebridge/services/catalog/astrology.py",
        "src/fatebridge/services/astrology.py",
        "src/fatebridge/core/output_charts.py",
        "src/fatebridge/core/response_models.py",
        "tests/western/test_western_relationship_geometry.py",
        "tests/western/test_western_relationship_transports.py",
        "tests/western/test_predictive_dates_and_runtime.py",
        "src/fatebridge/core/ephemeris_runtime.py",
        "scripts/western/audit_western_relationship.py",
        "scripts/western/gen_western_relationship_reference.py",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system() + "-" + platform.machine(),
        "geographic_reference": {
            "source": reference["source_url"],
            "oracle": reference["oracle"],
            "sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        },
        "spherical_midpoints": {
            "count": len(geography),
            "passed": sum(row["passed"] for row in geography),
            "tolerance_degrees": reference["tolerance_degrees"],
            "maximum_error_degrees": max(row["error_degrees"] for row in geography),
            "cases": geography,
        },
        "dateline_coordinate_mean": geographic_midpoint(179, 10, -179, 10),
        "representable_near_antipode": unique_midpoint(0, math.nextafter(180.0, 0)),
        "variants_and_marks_recipe": variants,
        "source_annotations": json.loads(METHODS.read_text()),
        "source_annotation_sha256": hashlib.sha256(METHODS.read_bytes()).hexdigest(),
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in files
        },
        "validation_limits": {
            "all_geographic_pairs_validated": False,
            "original_davison_book_collated": False,
            "marks_mirror_verified_against_original": False,
            "independent_expert_review": False,
            "score_is_probability": False,
            "real_model_dialogue_evaluated": False,
            "all_three_full_marks_established": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
        print(
            json.dumps(
                {
                    "geography": report["spherical_midpoints"]["passed"],
                    "maximum_error_degrees": report["spherical_midpoints"][
                        "maximum_error_degrees"
                    ],
                    "variant_recipe_cases": len(report["variants_and_marks_recipe"]),
                }
            )
        )
    else:
        print(encoded, end="")
    if not all(
        row["passed"]
        for row in [
            *report["spherical_midpoints"]["cases"],
            *report["variants_and_marks_recipe"],
        ]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
