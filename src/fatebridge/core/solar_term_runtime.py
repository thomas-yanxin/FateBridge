"""Private cache identity for the solar solver's selected data environment.

Native data identity uses filesystem metadata, not an atomic-read guarantee
or an accuracy claim. The loaded civil-clock profile uses a content hash.
The Sun/Earth calculation may consume planetary, lunar or selected JPL data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .ephemeris_paths import ephemeris_search_directories
from .ephemeris_runtime import effective_ephemeris_search_path
from .jpl_ephemeris import configured_jpl_file


def loaded_clock_profile_key() -> str:
    """Identify the tables actually consumed, including historical UTC drift.

    Reading their files again could fingerprint a new disk version while the
    conversion functions still hold older, cached contents. This key describes
    loaded data; it neither authenticates the source nor proves atomic reads.
    """
    from fatebridge.core.astro.utc_policy import leap_table

    from .astro.historical_utc import historical_utc_table, utc1960_table

    return hashlib.sha256(
        json.dumps(
            {
                "leap_seconds": leap_table(),
                "utc_1960": utc1960_table(),
                "utc_1961_1971": historical_utc_table(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def solar_term_cache_context(
    module: Any, *, year: int | None = None, native_only: bool = False
) -> tuple[Any, ...]:
    # Validate strict mode even when a prior default year is already cached.
    jpl_file = configured_jpl_file()
    from .solar_model_policy import solar_model_cache_key, solar_model_policy

    mode = "native" if native_only else solar_model_policy()
    if jpl_file is not None and mode in {
        "swiss",
        "analytic",
        "spk",
        "de440",
        "aa1996",
        "vsop2013",
    }:
        label = {"swiss": "Swiss", "vsop2013": "VSOP2013", "aa1996": "AA1996"}.get(
            mode, "analytic/SPK/DE440"
        )
        raise ValueError(
            f"Explicit {label} solar mode conflicts with strict JPL selection"
        )
    # An explicit native reobservation must not load an unrelated configured
    # analytic/SPK source merely to fingerprint its native data candidates.
    solar_model = (
        "native_observation_only"
        if native_only
        else (
            solar_model_cache_key(year=year)
            if year is not None
            else solar_model_cache_key()
        )
    )
    if jpl_file is not None and module is None:
        raise ImportError(
            "Swiss Ephemeris is required for explicitly selected JPL mode"
        )
    clock_profile = loaded_clock_profile_key()
    selected = effective_ephemeris_search_path()
    entries = []
    for directory in ephemeris_search_directories(selected or "."):
        path = directory.absolute()
        files: list[tuple[Any, ...]] = []
        try:
            candidates = {
                p for pattern in ("sepl*.se1", "semo*.se1") for p in path.glob(pattern)
            }
            candidates.update(
                path / name
                for name in ("swe_deltat.txt", "sedeltat.txt", "seleapsec.txt")
            )
            if jpl_file is not None:
                candidates.add(path / jpl_file)
            for candidate in sorted(candidates):
                try:
                    stat = candidate.stat()
                    files.append(
                        (
                            candidate.name,
                            stat.st_dev,
                            stat.st_ino,
                            stat.st_size,
                            stat.st_mtime_ns,
                            stat.st_ctime_ns,
                        )
                    )
                except FileNotFoundError:
                    continue
                except OSError as error:
                    files.append((candidate.name, "unreadable", error.errno))
        except OSError as error:
            files.append(("directory_unreadable", error.errno))
        entries.append((str(path), tuple(files)))
    return (
        id(module),
        str(getattr(module, "version", "unknown")),
        selected,
        tuple(entries),
        jpl_file,
        clock_profile,
        "all_numerical_solar_roots_explicit_tt_points_v3",
        solar_model,
    )
