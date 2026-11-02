"""Compare geocentric TT positions/events with the sealed external edge corpus."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.horary_events import native_planetary_events
from fatebridge.core.horary_motion import native_lunar_contacts

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path("tests/fixtures/western-tt-events-v1")


def validate_reference_identity(fixture: Path) -> None:
    """Alternate locations must contain the same canonically sealed corpus."""
    manifest = json.loads((ROOT / CORPUS / "manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        path = Path(relative)
        actual = (
            fixture / path.relative_to(CORPUS)
            if path.is_relative_to(CORPUS)
            else ROOT / path
        )
        if hashlib.sha256(actual.read_bytes()).hexdigest() != expected:
            raise ValueError("Sealed reference identity changed: " + relative)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / CORPUS)
    args = parser.parse_args()
    fixture = args.reference
    validate_reference_identity(fixture)
    protocol = json.loads((fixture / "protocol.json").read_text())
    reference = json.loads(
        gzip.decompress((fixture / "reference.json.gz").read_bytes())
    )
    assert reference["production_imports"] is False
    assert (
        reference["protocol_sha256"]
        == hashlib.sha256((fixture / "protocol.json").read_bytes()).hexdigest()
    )
    report = dict(
        protocol_id=protocol["protocol_id"],
        position_comparison_count=0,
        maximum_longitude_error_arcseconds=0.0,
        position_failures=[],
        event_comparisons=[],
        event_failures=[],
        planetary_histories=[],
        comparison_tolerance_arcseconds=protocol["comparison_tolerance_arcseconds"],
        comparison_tolerance_event_seconds=protocol[
            "comparison_tolerance_event_seconds"
        ],
        full_original_text_acceptance=False,
        real_world_outcomes=0,
    )

    def save():
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    for case in reference["cases"]:
        with use_ut1_source("iers_c04"):
            for planet, samples in case["samples"].items():
                for tt, longitude, _ in samples:
                    actual = _swisseph_planet_state(
                        planet, julian_day_tt=tt, correct_motion=False
                    )
                    if actual is None:
                        report["position_failures"].append(
                            dict(
                                case=case["case_id"],
                                planet=planet,
                                tt=tt,
                                reason="unavailable",
                            )
                        )
                        continue
                    error = (
                        abs((actual[0]["longitude"] - longitude + 180) % 360 - 180)
                        * 3600
                    )
                    report["position_comparison_count"] += 1
                    report["maximum_longitude_error_arcseconds"] = max(
                        report["maximum_longitude_error_arcseconds"], error
                    )
                    if error > protocol["comparison_tolerance_arcseconds"]:
                        report["position_failures"].append(
                            dict(
                                case=case["case_id"],
                                planet=planet,
                                tt=tt,
                                error_arcseconds=error,
                            )
                        )
            subject = SimpleNamespace(
                julian_day_tt=case["start_julian_day_tt"], zodiac_type="Tropic"
            )
            actual = native_lunar_contacts(subject)
            expected = case["expected"]
            comparison = dict(case=case["case_id"], actual=actual, expected=expected)
            report["event_comparisons"].append(comparison)
            if actual["status"] != "computed":
                report["event_failures"].append(
                    dict(case=case["case_id"], reason="lunar_unavailable")
                )
            else:
                if actual["void_of_course"] != expected["void_of_course"]:
                    report["event_failures"].append(
                        dict(case=case["case_id"], reason="void_of_course")
                    )
                delta = (
                    abs(
                        actual["sign_exit_julian_day_tt"]
                        - expected["sign_exit_julian_day_tt"]
                    )
                    * 86400
                )
                comparison["ingress_error_seconds"] = delta
                if delta > protocol["comparison_tolerance_event_seconds"]:
                    report["event_failures"].append(
                        dict(
                            case=case["case_id"], reason="ingress", error_seconds=delta
                        )
                    )
                akeys = [(e["other"], e["ray_degrees"]) for e in actual["contacts"]]
                ekeys = [(e["other"], e["ray_degrees"]) for e in expected["contacts"]]
                if akeys != ekeys:
                    report["event_failures"].append(
                        dict(
                            case=case["case_id"],
                            reason="contact_set_or_order",
                            actual=akeys,
                            expected=ekeys,
                        )
                    )
                else:
                    deltas = [
                        abs(a["julian_day_tt"] - e["julian_day_tt"]) * 86400
                        for a, e in zip(actual["contacts"], expected["contacts"])
                    ]
                    comparison["contact_errors_seconds"] = deltas
                    if any(
                        d > protocol["comparison_tolerance_event_seconds"]
                        for d in deltas
                    ):
                        report["event_failures"].append(
                            dict(
                                case=case["case_id"],
                                reason="contact_time",
                                errors_seconds=deltas,
                            )
                        )
            save()
            print(
                "Positions and lunar search:",
                case["case_id"],
                actual["status"],
                flush=True,
            )
            for zodiac in ("Tropic", "Sidereal"):
                subject.zodiac_type = zodiac
                history = native_planetary_events(subject)
                report["planetary_histories"].append(
                    dict(case=case["case_id"], zodiac=zodiac, actual=history)
                )
                if history["status"] != "computed":
                    report["event_failures"].append(
                        dict(
                            case=case["case_id"],
                            zodiac=zodiac,
                            reason="planetary_history_unavailable",
                            detail=history.get("unavailable_reason"),
                        )
                    )
                save()
                print(
                    "Planetary history:",
                    case["case_id"],
                    zodiac,
                    history["status"],
                    flush=True,
                )
    report["finite_corpus_comparison_passed"] = (
        not report["position_failures"] and not report["event_failures"]
    )
    save()
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in {
                    "event_comparisons",
                    "planetary_histories",
                    "position_failures",
                    "event_failures",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if report["finite_corpus_comparison_passed"] else 1)


if __name__ == "__main__":
    main()
