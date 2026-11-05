"""Freeze JPL astrometric/apparent solar-disc controls, without project imports."""

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def acquire(panel, target, epochs, plan, archive):
    parameters = {
        **plan["reference_parameters"],
        "format": "json",
        "COMMAND": f"'{target}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'JD{epochs[0]:.12f}'",
        "STOP_TIME": f"'JD{epochs[-1]:.12f}'",
        "STEP_SIZE": "'1h'",
    }
    name = f"{panel}-{target}.json"
    path = archive / name
    if path.exists():
        raw = path.read_bytes()
    else:
        raw = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--retry",
                "3",
                "--max-time",
                "45",
                URL + "?" + urlencode(parameters),
            ]
        )
        path.write_bytes(raw)
    response = json.loads(raw)
    assert "error" not in response, response.get("error")
    source = response["result"]
    assert all(
        s in source for s in ("ICRF-a-app", "Ang-diam", "delta", "R.A.___(ICRF)")
    )
    assert f"({target})" in source.split("Target body name:", 1)[1].splitlines()[0]
    rows = []
    for epoch, row in zip(
        epochs,
        csv.reader(io.StringIO(source.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])),
        strict=True,
    ):
        ra, dec, diameter, distance, radial, app_ra, app_dec = map(float, row[3:10])
        printed = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        printed_tt = (
            2440587.5 + (printed - datetime(1970, 1, 1)).total_seconds() / 86400
        )
        assert abs(printed_tt - epoch) < 1e-9
        assert all(
            math.isfinite(x)
            for x in (ra, dec, diameter, distance, radial, app_ra, app_dec)
        )
        rows.append(
            dict(
                julian_day_tt=epoch,
                astrometric_ra_dec=[ra, dec],
                angular_diameter_arcseconds=diameter,
                range_au=distance,
                range_rate_km_per_second=radial,
                apparent_ra_dec=[app_ra, app_dec],
            )
        )
    return dict(
        rows=rows,
        receipt=dict(
            parameters=parameters,
            response_sha256=hashlib.sha256(raw).hexdigest(),
            raw_file=name,
            raw_response_utf8=raw.decode(),
        ),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ("protocol", "archive", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "References are append-only"
    plan = json.loads(args.protocol.read_text())
    args.archive.mkdir(parents=True, exist_ok=True)
    panels = []
    for panel in plan["panels"]:
        epochs = [panel["center_jd_tt"] + h / 24 for h in plan["offset_hours"]]
        panels.append(
            {
                **panel,
                "body_reference": acquire(
                    panel["id"], panel["target"], epochs, plan, args.archive
                ),
                "sun_reference": acquire(
                    panel["id"], plan["sun_target"], epochs, plan, args.archive
                ),
            }
        )
    result = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=URL,
        protocol_sha256=hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        production_imports=False,
        swiss_imports=False,
        panels=panels,
        independent_body_epochs=sum(len(p["body_reference"]["rows"]) for p in panels),
    )
    assert result["independent_body_epochs"] == plan["expected_physical_body_epochs"]
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("protocol_sha256", "independent_body_epochs")}
        )
    )


if __name__ == "__main__":
    main()
