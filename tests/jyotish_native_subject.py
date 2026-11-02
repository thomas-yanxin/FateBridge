import json
import os
import sys
from contextlib import nullcontext
from pathlib import Path

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.utils.errors import EphemerisSourceError

mode = sys.argv[1]
root = Path(sys.argv[2])
empty = root / "empty"
custom = root / "custom"
for p in [empty, custom]:
    p.mkdir(parents=True)
for k in ["SE_EPHE_PATH", "FATEBRIDGE_JPL_FILE"]:
    os.environ.pop(k, None)
value = 63.9 if mode in {"file", "alias", "stale_small", "manual_small"} else 400.0
(custom / ("sedeltat.txt" if mode == "alias" else "swe_deltat.txt")).write_text(
    "\n".join(f"{y} {value}" for y in range(1990, 2011)) + "\n"
)
if mode.startswith("stale"):
    e.configure_ephemeris_path(str(custom))
    e.ephemeris_call("deltat_ex", 2451545.0, e.swe.FLG_SWIEPH)
e.configure_ephemeris_path(str(custom if mode in {"file", "alias"} else empty))
if mode in {"manual", "manual_small"}:
    e.swe.set_delta_t_userdef(value / 86400)
real = runtime.ephemeris_call
fault = {"transient_geometry": "houses_ex", "transient_events": "rise_trans"}.get(mode)


def transient(operation, *args, **kwargs):
    if operation == fault:
        e.swe.set_delta_t_userdef(400 / 86400)
        try:
            return real(operation, *args, **kwargs)
        finally:
            e.swe.set_delta_t_userdef(e.swe.DELTAT_AUTOMATIC)
    return real(operation, *args, **kwargs)


if fault:
    runtime.ephemeris_call = transient
birth = build_astro_birth_info(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_longitude=0,
    birth_latitude=0,
    birth_timezone="UTC",
    preserve_instant=True,
)
try:
    with e.preserve_ephemeris_path() if mode == "stale_under_lock" else nullcontext():
        result = build_india(birth, divisions=[])
except EphemerisSourceError as error:
    out = {"reason": error.reason, "envelope": error.as_result()}
else:
    out = {
        "status": result["status"],
        "ascendant": result["charts"]["D1"]["ascendant"]["longitude"],
        "delta_t_seconds": (
            result["profile"]["julian_day_tt"] - result["profile"]["julian_day_ut"]
        )
        * 86400,
        "sun_longitude": result["charts"]["D1"]["planets"][0]["longitude"],
        "solar_events": result["strengths"]["kala_bala"]["solar_events"]["events"],
    }
print(json.dumps(out))
