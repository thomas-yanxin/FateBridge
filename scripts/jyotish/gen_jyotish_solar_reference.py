"""Independent DE421/Skyfield Hindu solar events; no FateBridge or Swiss.

Run only in an isolated, pinned reference environment. Numerical UT1 inputs,
builtin Earth-rotation data and the apparent geocentric Sun are explicit.
This is a software reference, not a terrain-horizon observation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path


def main() -> None:
    import numpy as np
    from skyfield import framelib
    from skyfield.api import load, load_file

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    versions = {
        key: importlib.metadata.version(key)
        for key in ("skyfield", "skyfield-data", "jplephem", "numpy")
    }
    assert versions["skyfield"] == "1.54"
    assert versions["skyfield-data"] == "6.0.0"
    assert versions["jplephem"] == "2.23"
    spec = importlib.util.find_spec("skyfield_data")
    assert spec is not None and spec.origin is not None
    kernel_path = Path(spec.origin).parent / "data/de421.bsp"
    kernel_sha = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
    assert (
        kernel_sha == "a20a7139da04cbc462454634918e9a9ca69127044e2cc9d4f9c16e238d2deedc"
    )
    kernel = load_file(str(kernel_path))
    earth, sun = kernel["earth"], kernel["sun"]
    ts = load.timescale(builtin=True)

    def sine_altitude(jd_ut1, longitude, latitude):
        t = ts.ut1_jd(jd_ut1)
        apparent = earth.at(t).observe(sun).apparent()
        _, lon, _ = apparent.frame_latlon(framelib.ecliptic_frame)
        # Hindu definition: solar ecliptic latitude is set to zero. Use the
        # same true equinox/obliquity frame as the apparent ecliptic longitude.
        _, nutation_obliquity = t._nutation_angles_radians
        epsilon = t._mean_obliquity_radians + nutation_obliquity
        ra = np.arctan2(np.sin(lon.radians) * np.cos(epsilon), np.cos(lon.radians))
        dec = np.arcsin(np.sin(lon.radians) * np.sin(epsilon))
        hour_angle = np.deg2rad(t.gast * 15 + longitude) - ra
        phi = np.deg2rad(latitude)
        return np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(
            hour_angle
        )

    cases = []
    windows = [(2026, 3, 17), (2026, 9, 20)]
    for year, month, day in windows:
        start = float(ts.ut1(year, month, day).ut1)
        end = start + 8
        grid = start + np.arange(193) / 24
        for longitude, latitude in [(91, 30), (-91, -30), (0, 0), (90, 60)]:
            heights = sine_altitude(grid, longitude, latitude)
            assert not np.any(
                heights == 0
            ), "An exact scan-boundary root needs explicit handling"
            events = []
            for index in np.flatnonzero(heights[:-1] * heights[1:] < 0):
                left, right = float(grid[index]), float(grid[index + 1])
                rising = bool(heights[index] < heights[index + 1])
                left_height = float(heights[index])
                while (right - left) * 86400 > 0.001:
                    mid = (left + right) / 2
                    height = float(sine_altitude(mid, longitude, latitude))
                    if left_height * height <= 0:
                        right = mid
                    else:
                        left, left_height = mid, height
                event = (left + right) / 2
                t = ts.ut1_jd(event)
                events.append(
                    {
                        "kind": "rise" if rising else "set",
                        "julian_day_ut1": event,
                        "julian_day_tt": float(t.tt),
                        "delta_t_seconds": float(t.delta_t),
                        "residual_sine_altitude": float(
                            sine_altitude(event, longitude, latitude)
                        ),
                        "root_bracket_width_seconds": (right - left) * 86400,
                    }
                )
            cases.append(
                {
                    "start_jd_ut1": start,
                    "end_jd_ut1": end,
                    "longitude": longitude,
                    "latitude": latitude,
                    "events": events,
                }
            )
    skyfield_spec = importlib.util.find_spec("skyfield")
    assert skyfield_spec is not None and skyfield_spec.origin is not None
    package = Path(skyfield_spec.origin).parent
    fingerprints = {}
    for rel in [
        "framelib.py",
        "timelib.py",
        "positionlib.py",
        "data/iers.npz",
        "data/nutation.npz",
    ]:
        fingerprints[rel] = hashlib.sha256((package / rel).read_bytes()).hexdigest()
    result = {
        "reference": "Independent apparent-geocentric DE421 + Skyfield1.54 Hindu solar events",
        "versions": versions,
        "kernel_sha256": kernel_sha,
        "skyfield_files_sha256": fingerprints,
        "definition": "Geocentric apparent solar centre; solar ecliptic latitude forced to zero; true equinox and obliquity of date; GAST and explicit UT1; no refraction or terrain",
        "time_scale": "Skyfield1.54 builtin timescale and delta-T; no Swiss time conversion",
        "generation": "One-hour altitude sign scan followed by0.001-second bisection; no production event seeds",
        "matching_tolerance_seconds": 1.0,
        "cases": cases,
        "cases_are_known_development_windows": True,
        "real_event_cases": 0,
        "heldout_cases": 0,
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        f"Saved {len(cases)} windows and {sum(len(c['events']) for c in cases)} events"
    )


if __name__ == "__main__":
    main()
