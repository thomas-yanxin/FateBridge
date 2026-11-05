"""Three-way absolute comparisons and separate paired deflection diagnostics.

This never replaces an original reference or passes its failed calendar row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.gen_human_design_calendar_horizons import (
    ROOT,
    parameters,
    parse_response,
    plan,
)

EVIDENCE = ROOT / "tests/data/human_design/calendar_horizons/evidence"
BINDINGS = {
    "horizons-attempt1/reference.json": "a96f2658c3ec33a3a4c6ad4801cde92f2f4699ae55d4a92a78b8ca910bf32ea3",
    "de440-reference.json": "1fb6e869926ab8b4c74fd5dbe56e6459ce0ac6b90bc03fce41b88d559dfb3824",
    "de440-no-deflection.json": "fa6279f8137f344344077a7a73c561a9c305ffaf057d465f2c3a58bf8a8f256f",
}


def references() -> dict:
    result = {}
    for name, expected in BINDINGS.items():
        raw = (EVIDENCE / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Fixed independent reference changed: " + name)
        result[name] = json.loads(raw)
    horizons = result["horizons-attempt1/reference.json"]
    for row in horizons["records"]:
        raw = (EVIDENCE / f"horizons-attempt1/{row['body']}.response.json").read_bytes()
        request = json.loads(
            (EVIDENCE / f"horizons-attempt1/{row['body']}.request.json").read_bytes()
        )
        if request["parameters"] != parameters(row["body"]):
            raise ValueError(
                "Captured NASA query differs from fixed target/TT/coordinate request"
            )
        if parse_response(raw, row["body"]) != row:
            raise ValueError("Saved coordinates detached from their raw NASA response")
    fixed = plan()
    for value in result.values():
        if [r["body"] for r in value["records"]] != list(fixed["bodies"]):
            raise ValueError("Reference target omitted or replaced")
        for record in value["records"]:
            if record["target_id"] != fixed["bodies"][record["body"]] or [
                (r["id"], r["jd_tt"]) for r in record["rows"]
            ] != [(r["id"], r["jd_tt"]) for r in fixed["epochs"]]:
                raise ValueError("Reference target or physical TT rebound")
    return result


def capture() -> dict:
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design import positions_at_tt
    from fatebridge.core.human_design_mechanics import BODY_IDS
    from fatebridge.core.human_design_natal_sources import guard_natal_sources

    @guard_natal_sources
    def observe() -> dict:
        if runtime.swe is None:
            raise RuntimeError("Swiss Ephemeris unavailable")
        rows = []
        for epoch in plan()["epochs"]:
            positions = positions_at_tt(
                epoch["jd_tt"], "true", require_swiss_files=True
            )
            for body in plan()["bodies"]:
                controls = {}
                for label, extra in [
                    ("default", 0),
                    ("no_gravitational_deflection", runtime.swe.FLG_NOGDEFL),
                ]:
                    flags = runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED | extra
                    coords, returned = runtime.ephemeris_call(
                        "calc", epoch["jd_tt"], BODY_IDS[body], flags
                    )
                    if returned != flags or not all(math.isfinite(x) for x in coords):
                        raise ValueError(
                            "Diagnostic native flags or coordinates changed"
                        )
                    controls[label] = {
                        "requested_flags": flags,
                        "return_flags": returned,
                        "native_coordinates": list(coords),
                    }
                original = positions[body]
                raw = controls["default"]
                if (
                    raw["native_coordinates"][0] % 360,
                    raw["native_coordinates"][3],
                    raw["return_flags"],
                ) != (
                    original["longitude"],
                    original["longitude_speed"],
                    original["return_flags"],
                ):
                    raise ValueError(
                        "Diagnostic default differs from the actual producer"
                    )
                rows.append(
                    {**epoch, "body": body, "position": original, "controls": controls}
                )
        return {
            "rows": rows,
            "scope": "Actual current positions_at_tt plus separate counterfactual flags in this new Python process. Existing source observer covers production calls; direct diagnostic controls retain raw coordinates/flags but are not a separate native-source or physical-execution certificate.",
        }

    return observe()


def signed_arcseconds(a: float, b: float) -> float:
    return ((a - b + 180) % 360 - 180) * 3600


def compare(production: dict, sources: dict) -> dict:
    from fatebridge.core.human_design import longitude_activation

    fixed = plan()
    identities = [
        (r["id"], body, r["jd_tt"]) for r in fixed["epochs"] for body in fixed["bodies"]
    ]
    if [(r["id"], r["body"], r["jd_tt"]) for r in production["rows"]] != identities:
        raise ValueError("Production cohort omitted, duplicated or rebound")
    actual = {(r["body"], r["id"]): r for r in production["rows"]}
    references_by_source = {
        name: {
            (record["body"], r["id"]): r
            for record in value["records"]
            for r in record["rows"]
        }
        for name, value in sources.items()
    }
    rows = []
    for epoch in fixed["epochs"]:
        for body in fixed["bodies"]:
            key = body, epoch["id"]
            native = actual[key]
            if (
                native["position"]["ephemeris_model"] != "swieph"
                or native["position"]["return_flags"] != 258
            ):
                raise ValueError("Current baseline did not use requested Swiss data")
            default = native["controls"]["default"]
            disabled = native["controls"]["no_gravitational_deflection"]
            if (
                default["requested_flags"] != 258
                or default["return_flags"] != 258
                or disabled["requested_flags"] != 770
                or disabled["return_flags"] != 770
            ):
                raise ValueError("Counterfactual or baseline flags changed")
            if (
                default["native_coordinates"][0] % 360,
                default["native_coordinates"][3],
            ) != (
                native["position"]["longitude"],
                native["position"]["longitude_speed"],
            ):
                raise ValueError("Producer detached from default raw coordinates")
            values = {
                "swiss_default": native["position"]["longitude"],
                "swiss_no_deflection": native["controls"][
                    "no_gravitational_deflection"
                ]["native_coordinates"][0],
                "horizons": references_by_source["horizons-attempt1/reference.json"][
                    key
                ]["longitude"],
                "de440_skyfield": references_by_source["de440-reference.json"][key][
                    "longitude"
                ],
                "de440_no_deflection": references_by_source["de440-no-deflection.json"][
                    key
                ]["longitude"],
            }
            if not all(math.isfinite(x) and 0 <= x < 360 for x in values.values()):
                raise ValueError("Nonfinite or out-of-range comparison position")
            differences = {
                name: signed_arcseconds(values[a], values[b])
                for name, a, b in [
                    ("swiss_minus_original_de440", "swiss_default", "de440_skyfield"),
                    ("horizons_minus_original_de440", "horizons", "de440_skyfield"),
                    ("horizons_minus_swiss", "horizons", "swiss_default"),
                    ("swiss_deflection_effect", "swiss_default", "swiss_no_deflection"),
                    (
                        "skyfield_deflection_effect",
                        "de440_skyfield",
                        "de440_no_deflection",
                    ),
                    (
                        "no_deflection_swiss_minus_de440",
                        "swiss_no_deflection",
                        "de440_no_deflection",
                    ),
                ]
            }
            mappings = {
                name: {
                    k: longitude_activation(v)[k]
                    for k in ("gate", "line", "color", "tone", "base")
                }
                for name, v in values.items()
            }
            rows.append(
                {
                    **epoch,
                    "body": body,
                    "longitudes": values,
                    "signed_differences_arcseconds": differences,
                    "absolute_comparisons_with_original2arcsec_threshold": {
                        name: abs(differences[name])
                        <= fixed["comparison_tolerance_arcseconds"]
                        for name in [
                            "swiss_minus_original_de440",
                            "horizons_minus_original_de440",
                            "horizons_minus_swiss",
                        ]
                    },
                    "subdivisions_using_current_mapping_not_independent_oracle": mappings,
                    "production_longitude_replaced": False,
                }
            )
    by_key = {(r["body"], r["id"]): r for r in rows}
    for epoch in fixed["epochs"]:
        target, sun = by_key["Uranus", epoch["id"]], by_key["Sun", epoch["id"]]
        target["paired_sun_relative_diagnostic_arcseconds"] = {
            k: v - sun["signed_differences_arcseconds"][k]
            for k, v in target["signed_differences_arcseconds"].items()
        }
    center = by_key["Uranus", "offset_+0d"]
    original = fixed["original_failed_row"]
    if center["longitudes"]["de440_skyfield"] != original["reference_longitude"]:
        raise ValueError("Original independent reference replaced")
    comparison_keys = list(
        center["absolute_comparisons_with_original2arcsec_threshold"]
    )
    counts = {
        key: {
            "positions": len(rows),
            "within_original_threshold": sum(
                r["absolute_comparisons_with_original2arcsec_threshold"][key]
                for r in rows
            ),
            "failed": sum(
                not r["absolute_comparisons_with_original2arcsec_threshold"][key]
                for r in rows
            ),
        }
        for key in comparison_keys
    }
    failed = any(r["failed"] for r in counts.values())
    original_passed = center["absolute_comparisons_with_original2arcsec_threshold"][
        "swiss_minus_original_de440"
    ]
    return {
        "method_id": "human_design_near_conjunction_three_way_diagnostics_v1",
        "status": "disagreements_remain" if failed else "bounded_absolute_agreement",
        "position_count": len(rows),
        "comparison_counts": counts,
        "rows": rows,
        "original_failed_row_passed": original_passed,
        "original_historical_failed_row": original,
        "original_calendar_status": (
            "failed_current_original_case"
            if not original_passed
            else "full_original_cohort_requires_rerun"
        ),
        "original_tolerances_changed": False,
        "complete_calendar_acceptance": False,
        "subdivision_accuracy_certified": False,
        "physical_occultation_certified": False,
        "original_human_design_software_convention_certified": False,
        "scope": "34 investigative same-TT targets. Paired Sun-relative and no-deflection rows are additional causal diagnostics, never replacements for absolute longitudes, original failed rows or the complete prior cohort. Mapping uses current arithmetic, not independent semantic acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.capture.exists():
        raise FileExistsError("Never overwrite a numerical capture or report")
    sources = references()  # Verify independent artifacts before producer calls.
    production = capture()
    args.capture.write_text(json.dumps(production, indent=2) + "\n")
    result = compare(production, sources)
    result["production_capture_sha256"] = hashlib.sha256(
        args.capture.read_bytes()
    ).hexdigest()
    result["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["reference_bindings"] = BINDINGS
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    center = next(
        r for r in result["rows"] if r["body"] == "Uranus" and r["offset_days"] == 0
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(result["rows"]),
                "center_diagnostics": center["signed_differences_arcseconds"],
            }
        )
    )
    return int(result["status"] == "disagreements_remain")


if __name__ == "__main__":
    raise SystemExit(main())
