import json
import os
import sys
from pathlib import Path

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.birth_clock import solar_wall_clock
from fatebridge.core.jyotish import build_india
from fatebridge.services.jyotish import calculate_vimshottari

mode = sys.argv[1]
root = Path(sys.argv[2])
empty = root / "empty"
custom = root / "custom"
for p in [empty, custom]:
    p.mkdir(parents=True)
os.environ.pop("SE_EPHE_PATH", None)
os.environ.pop("FATEBRIDGE_JPL_FILE", None)
(custom / "swe_deltat.txt").write_text(
    "\n".join(f"{y} 400" for y in range(1990, 2011)) + "\n"
)
if mode == "stale":
    e.configure_ephemeris_path(str(custom))
    e.ephemeris_call("deltat_ex", 2451545.0, e.swe.FLG_SWIEPH)
e.configure_ephemeris_path(str(empty))
if mode == "manual":
    e.swe.set_delta_t_userdef(400 / 86400)
args = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=34,
    birth_second=56,
    birth_microsecond=123456,
    birth_timezone="UTC",
    birth_longitude=10,
    birth_latitude=0,
    use_true_solar_time=True,
)
birth = build_astro_birth_info(**args, preserve_instant=True)
result = build_india(birth, divisions=[])
service = calculate_vimshottari(**args, analysis_year=2026, divisions=[])
out = {
    "mode": mode,
    "birth_utc": birth.utc_datetime.isoformat(),
    "prebuilt_display": birth.solar_datetime.replace(tzinfo=None).isoformat(),
    "SDK_display": result["profile"]["clock_context"],
    "service_display": service["india"]["profile"]["clock_context"],
    "ascendant": result["charts"]["D1"]["ascendant"]["longitude"],
    "delta_t_seconds": (
        result["profile"]["julian_day_tt"] - result["profile"]["julian_day_ut"]
    )
    * 86400,
}
if mode == "clean":
    out["shared_physical_LAT"] = solar_wall_clock(
        birth.utc_datetime, birth.longitude, "local_apparent_solar"
    ).isoformat()
print(json.dumps(out))
