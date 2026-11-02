"""Explicit, strict DE441 selection for managed native ephemeris calls.

The operator supplies a basename in the ordinary Swiss search path. Native
fallback is an error in this opt-in mode. The default compressed path is
unchanged. File identity and structural checks do not certify astronomical
accuracy or prove an atomic read set.
"""

from __future__ import annotations

import math
import os
import re
import struct
from pathlib import Path
from typing import Any, Dict, Tuple

from fatebridge.utils.errors import EphemerisSourceError


def configured_jpl_file() -> str | None:
    name = os.environ.get("FATEBRIDGE_JPL_FILE")
    if not name:
        return None
    # swe_set_jpl_file discards directory components and truncates long input.
    # Require an unambiguous basename; SE_EPHE_PATH owns directory selection.
    if len(name.encode()) >= 256 or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise EphemerisSourceError("jpl_filename_invalid")
    if name in {".", ".."}:
        raise EphemerisSourceError("jpl_filename_invalid")
    return name


def jpl_header(path: Path) -> Dict[str, Any]:
    """Read both byte orders of the original direct-access DE441 format."""
    try:
        with path.open("rb") as source:
            data = source.read(2856)
        size = path.stat().st_size
        if len(data) != 2856:
            raise ValueError("short header")
        for order in ("<", ">"):
            start, end, step = struct.unpack_from(order + "3d", data, 2652)
            de = struct.unpack_from(order + "i", data, 2840)[0]
            if de != 441:
                continue
            au, emrat = struct.unpack_from(order + "2d", data, 2680)
            pointers = struct.unpack_from(order + "36i", data, 2696)
            libration = struct.unpack_from(order + "3i", data, 2844)
            triples = list(zip(*[iter(pointers + libration)] * 3))
            coefficients = max(
                offset + count * segments * (2 if i == 11 else 3) - 1
                for i, (offset, count, segments) in enumerate(triples)
            )
            records = (end - start) / step if step > 0 else math.nan
            record_bytes = coefficients * 8
            expected = (records + 2) * record_bytes
            if not (
                all(math.isfinite(x) for x in (start, end, step, records))
                and start < end
                and step == 32
                and records == int(records)
                and au == 149597870.7
                and 81 < emrat < 82
                and coefficients == 1018
                and size in {expected, expected + record_bytes}
            ):
                raise ValueError("invalid DE441 layout")
            return {
                "time_scale": "TDB",
                "start_julian_day_tdb": start,
                "end_julian_day_tdb": end,
                # Retained for existing provenance consumers. These values
                # came from the raw header; no TDB-to-TT conversion occurred.
                "start_julian_day_tt": start,
                "end_julian_day_tt": end,
                "legacy_tt_range_fields": "Compatibility aliases for raw TDB header values; not converted TT bounds",
                "de_number": de,
                "bytes": size,
            }
    except (OSError, ValueError, struct.error, OverflowError) as error:
        raise EphemerisSourceError("jpl_kernel_invalid") from error
    raise EphemerisSourceError("jpl_kernel_invalid")


def prepare_jpl_call(
    module: Any,
    name: str,
    operation: str,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Tuple[Tuple[Any, ...], Dict[str, Any], bool]:
    """Restore the selected kernel and replace supported ephemeris flags."""
    module.set_jpl_file(name)
    filename = module.get_current_file_data(0)[0]
    if not filename or Path(filename).name != name or not Path(filename).is_file():
        raise EphemerisSourceError("jpl_file_unavailable")
    jpl_header(Path(filename))
    # These are the flagged functions used by managed chart calculations.
    # Unflagged native helpers (e.g. time_equ) retain their own documented
    # algorithms; this mode does not relabel them as JPL-vector calculations.
    flag_arguments = {
        "calc": (2, "flags", module.FLG_SWIEPH | module.FLG_SPEED),
        "calc_ut": (2, "flags", module.FLG_SWIEPH | module.FLG_SPEED),
        "get_ayanamsa_ex": (1, "flags", module.FLG_SWIEPH),
        "get_ayanamsa_ex_ut": (1, "flags", module.FLG_SWIEPH),
        "deltat_ex": (1, "flag", -1),
        "rise_trans": (6, "flags", module.FLG_SWIEPH),
        "fixstar2": (2, "flags", module.FLG_SWIEPH),
    }
    if operation not in flag_arguments:
        return args, kwargs, False
    index, key, default = flag_arguments[operation]
    flags = args[index] if len(args) > index else kwargs.get(key, default)
    # The negative Delta-T flag has a separate historical calibration meaning.
    if flags < 0:
        return args, kwargs, False
    if flags & module.FLG_MOSEPH:
        raise EphemerisSourceError("jpl_mixed_request")
    flags = (flags & ~module.FLG_SWIEPH) | module.FLG_JPLEPH
    if len(args) > index:
        updated = list(args)
        updated[index] = flags
        args = tuple(updated)
    else:
        kwargs = {**kwargs, key: flags}
    return args, kwargs, operation in {"calc", "calc_ut", "fixstar2"}


def check_jpl_result(module: Any, result: Any, operation: str = "calc") -> None:
    flags = result[2] if operation == "fixstar2" else result[1]
    if flags < 0 or not flags & module.FLG_JPLEPH:
        raise EphemerisSourceError("jpl_native_fallback")
