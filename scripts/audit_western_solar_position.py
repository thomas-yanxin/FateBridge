"""Keep failed default positions separate from solar-convention diagnostics."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.output_charts import ApparentPositionPolicy

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SHA256 = "064ebd6f554cd94b2a3c3471a1f82d7afc4edf4abeabf1e76d2aac180e516973"
REFERENCE_SHA256 = "de2a112a588aad555916969edd49849a31ba7e8ae829926ef86861bd54e2ea6f"


def separation(first, second):
    ra, dec, other, lat = map(math.radians, (*first, *second))
    h = (
        math.sin((dec - lat) / 2) ** 2
        + math.cos(dec) * math.cos(lat) * math.sin((ra - other) / 2) ** 2
    )
    return math.degrees(2 * math.asin(min(1, math.sqrt(max(0, h)))))


def independent_domain(body, sun):
    """JPL astrometry, solar angular diameter and finite target range only."""
    angle = math.radians(
        separation(body["astrometric_ra_dec"], sun["astrometric_ra_dec"])
    )
    # Q13 is the apparent angular diameter; this diagnostic uses its model
    # sphere with astrometric center directions. No optical contact is solved.
    radius = sun["range_au"] * math.sin(
        math.radians(sun["angular_diameter_arcseconds"] / 7200)
    )
    impact = sun["range_au"] * math.sin(angle) / radius
    along = sun["range_au"] * math.cos(angle)
    if along <= 0:
        return "sun_behind_observer", impact
    if impact >= 1:
        return "outside_solar_disc", impact
    chord = radius * math.sqrt(1 - impact * impact)
    gap = body["range_au"] - along
    return (
        "behind_solar_disc"
        if gap > chord
        else (
            "foreground_of_solar_disc" if gap < -chord else "target_inside_model_sphere"
        )
    ), impact


def audit():
    protocol = ROOT / "tests/fixtures/western-solar-position-protocol.json"
    reference = ROOT / "tests/fixtures/western-solar-position-horizons.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == REFERENCE_SHA256
    plan, oracle = json.loads(protocol.read_text()), json.loads(reference.read_text())
    assert oracle["protocol_sha256"] == PROTOCOL_SHA256
    assert oracle["production_imports"] is oracle["swiss_imports"] is False
    prior = ROOT / "tests/fixtures/western-event-reference-points-horizons.json"
    failure = ROOT / "docs/validation/western-event-paths-evidence.json"
    assert (
        hashlib.sha256(prior.read_bytes()).hexdigest() == plan["prior_reference_sha256"]
    )
    assert (
        hashlib.sha256(failure.read_bytes()).hexdigest()
        == plan["prior_failed_evidence_sha256"]
    )
    rows = []
    swe = runtime.swe
    flags = swe.FLG_SWIEPH | swe.FLG_J2000 | swe.FLG_ICRS | swe.FLG_EQUATORIAL
    trace = PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        for panel in oracle["panels"]:
            for key in ("body_reference", "sun_reference"):
                receipt = panel[key]["receipt"]
                assert (
                    hashlib.sha256(receipt["raw_response_utf8"].encode()).hexdigest()
                    == receipt["response_sha256"]
                )
            for body, sun in zip(
                panel["body_reference"]["rows"],
                panel["sun_reference"]["rows"],
                strict=True,
            ):
                epoch = body["julian_day_tt"]
                assert epoch == sun["julian_day_tt"]
                body_id = getattr(swe, panel["body"].upper())
                native, returned = runtime.ephemeris_call("calc", epoch, body_id, flags)
                model = runtime.ephemeris_model_from_retflag(returned)
                assert (
                    model == "swieph"
                ), "This fixed numerical audit requires the disclosed Swiss files"
                policy = apparent_position_policy(epoch, {panel["body"]: model}, trace)
                ApparentPositionPolicy.model_validate(policy)
                assert (
                    runtime.ephemeris_call("calc", epoch, body_id, flags)[0] == native
                )
                bare, _ = runtime.ephemeris_call(
                    "calc", epoch, body_id, flags | swe.FLG_NOGDEFL
                )
                astrometric, _ = runtime.ephemeris_call(
                    "calc", epoch, body_id, flags | swe.FLG_NOGDEFL | swe.FLG_NOABERR
                )
                independent, impact = independent_domain(body, sun)
                geometry = policy["bodies"][panel["body"]]
                rows.append(
                    dict(
                        panel=panel["id"],
                        body=panel["body"],
                        epoch_jd_tt=epoch,
                        independent_domain=independent,
                        native_domain=geometry["unbent_ray_domain"],
                        independent_impact_fraction=impact,
                        native_geometry=geometry,
                        native_apparent_error_arcseconds=3600
                        * separation(native[:2], body["apparent_ra_dec"]),
                        no_deflection_control_error_arcseconds=3600
                        * separation(bare[:2], body["apparent_ra_dec"]),
                        astrometric_error_arcseconds=3600
                        * separation(astrometric[:2], body["astrometric_ra_dec"]),
                    )
                )
    assert len(rows) == plan["expected_physical_body_epochs"]
    line = plan["position_line_arcseconds"]
    domains = sorted(set(r["independent_domain"] for r in rows))
    return dict(
        protocol_sha256=PROTOCOL_SHA256,
        reference_sha256=REFERENCE_SHA256,
        independent_body_epochs=len(rows),
        solar_reference_epochs=len(rows),
        default_position_line_arcseconds=line,
        default_native_apparent_positions_passed=all(
            r["native_apparent_error_arcseconds"] <= line for r in rows
        ),
        astrometric_diagnostic_passed=all(
            r["astrometric_error_arcseconds"] <= line for r in rows
        ),
        all_finite_ray_classifications_match=all(
            r["independent_domain"] == r["native_domain"] for r in rows
        ),
        source=trace.finish(),
        domains={
            d: dict(
                count=sum(r["independent_domain"] == d for r in rows),
                maximum_default_apparent_error_arcseconds=max(
                    r["native_apparent_error_arcseconds"]
                    for r in rows
                    if r["independent_domain"] == d
                ),
                maximum_no_deflection_control_error_arcseconds=max(
                    r["no_deflection_control_error_arcseconds"]
                    for r in rows
                    if r["independent_domain"] == d
                ),
                maximum_astrometric_error_arcseconds=max(
                    r["astrometric_error_arcseconds"]
                    for r in rows
                    if r["independent_domain"] == d
                ),
            )
            for d in domains
        },
        domain_counts=dict(Counter(r["independent_domain"] for r in rows)),
        native_coordinates_unchanged_after_receipt=True,
        no_deflection_is_diagnostic_only=True,
        omitted_cases=0,
        rows=rows,
        full_original_text_acceptance=False,
        real_world_prediction_established=False,
        all_four_full_marks_established=False,
        scope="Development solar-convention diagnostic. Every default comparison retained, including failures. Finite unbent-ray classification is not a visibility, optical-lensing or limb-contact proof. The no-deflection control never replaces production positions or its failed score.",
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"rows", "source"}}))
    return 0 if result["default_native_apparent_positions_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
