"""Verify the two-frame reference from original external bytes, without importing the engine.

Run with isolated pyerfa==2.0.1.5/numpy==2.5.4. Saved NASA bytes replace
transport; every parsed position and both moving-frame rates must match the independent reference.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.astrodice import gen_astrodice_lunar_chain_reference
from scripts.astrodice.gen_astrodice_apparent_reference import (
    julian_day_tt,
    project_motion,
)
from scripts.astronomy.gen_moshier_frame_reference import project_lahiri_motion
from scripts.guolao.gen_guolao_motion_reference import validate_header

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SHA256 = "7500bb8ad80313e886b461882ab81386110e87a933181df3ec67fec1cc625675"
REFERENCE_SHA256 = "3441dca5cb939edbfef37171da87b7c44a0a56bb0a6800c2e126784030fda78b"


def verify(
    protocol_path: Path, reference_path: Path
) -> dict[str, str | int | bool | list[str]]:
    protocol_bytes = protocol_path.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Frozen protocol identity changed")
    else:
        pass
    reference_bytes = reference_path.read_bytes()
    if hashlib.sha256(reference_bytes).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Frozen reference identity changed")
    else:
        pass
    protocol = json.loads(protocol_bytes)
    reference = json.loads(reference_bytes)
    if reference["protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("Reference protocol provenance changed")
    else:
        pass
    for package, expected in protocol["versions"].items():
        if importlib.metadata.version(package) != expected:
            raise ValueError("Independent reference dependency changed")
        else:
            pass
    if {body["body"] for body in reference["references"]} != set(protocol["targets"]):
        raise ValueError("Reference target coverage changed")
    else:
        pass
    positions = epochs = 0
    with tempfile.TemporaryDirectory(prefix="fatebridge-frame-offline-") as temporary:
        for target in reference["references"]:
            expected = protocol["targets"][target["body"]]
            if target["target_id"] != expected:
                raise ValueError("Reference target identity changed")
            else:
                pass
            if [row["date_tt"] for row in target["rows"]] != protocol["dates_tt"]:
                raise ValueError("Reference epoch coverage changed")
            else:
                pass
            points = {}
            for index, batch in enumerate(target["batches"]):
                raw = batch["raw_response_utf8"]
                if (
                    "error" in batch
                    or hashlib.sha256(raw.encode()).hexdigest()
                    != batch["raw_response_sha256"]
                ):
                    raise ValueError("Missing or changed raw response")
                else:
                    pass
                dates = [row["date_tt"] for row in batch["rows"]]
                with patch.object(
                    gen_astrodice_lunar_chain_reference, "subprocess"
                ) as transport:
                    transport.check_output.return_value = raw.encode()
                    rebuilt = gen_astrodice_lunar_chain_reference.fetch(
                        dates,
                        {"reference_parameters": batch["parameters"]},
                        Path(temporary),
                        str(index),
                    )
                    transport.check_output.assert_called_once_with(
                        [
                            "curl",
                            "--fail",
                            "--silent",
                            "--show-error",
                            "--max-time",
                            "45",
                            batch["request_url"],
                        ]
                    )
                validate_header(rebuilt, expected, protocol["target_id_aliases"])
                if any(
                    rebuilt[key] != batch[key]
                    for key in ("request_url", "parameters", "rows")
                ):
                    raise ValueError("Raw response parsing changed")
                else:
                    pass
                positions += len(rebuilt["rows"])
                points.update(
                    {
                        row["date_tt"]: row["icrf_unit_direction"]
                        for row in rebuilt["rows"]
                    }
                )
            for row in target["rows"]:
                if (
                    row["jd_tt"] != julian_day_tt(row["date_tt"])
                    or row["icrf_unit_direction"] != points[row["date_tt"]]
                ):
                    raise ValueError("Reference center or TT epoch changed")
                else:
                    pass
                rates = {
                    str(step): gen_astrodice_lunar_chain_reference.seven_point(
                        points, datetime.fromisoformat(row["date_tt"]), step
                    )
                    for step in protocol["seven_point_steps_seconds"]
                }
                if rates != row["seven_point_derivatives"]:
                    raise ValueError("Frozen directional derivative changed")
                else:
                    pass
                if (
                    math.degrees(math.dist(*rates.values())) * 3600
                    != row["stencil_difference_arcsec_per_day"]
                ):
                    raise ValueError("Reference stencil uncertainty changed")
                else:
                    pass
                arguments = (
                    row["jd_tt"],
                    points[row["date_tt"]],
                    rates[str(protocol["chosen_step_seconds"])],
                    protocol["frame_derivative_step_days"],
                )
                if project_motion(*arguments) != row["erfa_display_frame"]:
                    raise ValueError("Tropical frame projection changed")
                else:
                    pass
                if project_lahiri_motion(*arguments) != row["erfa_lahiri_frame"]:
                    raise ValueError("Lahiri frame projection changed")
                else:
                    pass
                half_arguments = (*arguments[:-1], arguments[-1] / 2)
                for project, key, uncertainty in (
                    (
                        project_motion,
                        "erfa_display_frame",
                        "frame_step_difference_arcsec_per_day",
                    ),
                    (
                        project_lahiri_motion,
                        "erfa_lahiri_frame",
                        "lahiri_frame_step_difference_arcsec_per_day",
                    ),
                ):
                    difference = (
                        abs(
                            project(*half_arguments)["longitude_speed_degrees_per_day"]
                            - row[key]["longitude_speed_degrees_per_day"]
                        )
                        * 3600
                    )
                    if difference != row[uncertainty]:
                        raise ValueError("Moving-frame uncertainty changed")
                    else:
                        pass
                epochs += 1
    forbidden = [
        name
        for name in sys.modules
        if name == "swisseph" or name == "fatebridge" or name.startswith("fatebridge.")
    ]
    if forbidden:
        raise RuntimeError(
            "Independent reference verification imported the production engine"
        )
    else:
        pass
    return {
        "scope": "Current offline verification of original external bytes and independently projected moving-frame rates; not physical trajectory, original-page or human-outcome certification.",
        "protocol_sha256": PROTOCOL_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "source_position_rows_verified": positions,
        "central_epochs_verified": epochs,
        "derived_frame_rates_verified": 2 * epochs,
        "all_stencil_and_moving_frame_uncertainties_verified": True,
        "network_requests": 0,
        "forbidden_engine_imports": forbidden,
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "tests/data/astro/moshier_frames/protocol.json",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "tests/data/astro/moshier_frames/reference.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refuse to replace an earlier verification result")
    else:
        pass
    result = verify(args.protocol, args.reference)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
else:
    pass
