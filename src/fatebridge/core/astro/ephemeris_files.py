"""Planet/Moon segment planning from Swiss Ephemeris documentation 2.1.1.

Public civil dates use CE 1..9999. Neighbouring years cover candidate segment
changes around civil/TT/UT and historical calendar year boundaries; a file
plan does not certify file integrity, loaded model or astronomical accuracy.
"""

from __future__ import annotations

from typing import Sequence, Tuple


def ephemeris_files_for_years(years: Sequence[int]) -> Tuple[str, ...]:
    if not years:
        raise ValueError("At least one CE year is required")
    segments: set[int] = set()
    for year in years:
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError(
                "Ephemeris file planning requires CE integer years 1..9999"
            )
        segments.update(
            (candidate // 600) * 6 for candidate in (year - 1, year, year + 1)
        )
    return tuple(
        f"{prefix}_{segment:02d}.se1"
        for segment in sorted(segments)
        for prefix in ("sepl", "semo")
    )
