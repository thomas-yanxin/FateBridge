"""Analytic p/v/a of the selected direct-access DE441 source polynomial.

The caller supplies the source day, without an internal TT/TDB conversion.
Exact rational days preserve fractions below a full Julian-day float's ULP.
Source words, the selected record and the fixed frame are separately checked;
this is neither an observational error bound nor an atomic read-set proof.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from fatebridge.core.astro.chebyshev import (
    ChebyshevKinematics,
    chebyshev_kinematics,
)
from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "de441_analytic_source_kinematics_v1"
RECORD_BYTES = 8144
FRAME_LINE = 2e-13
Vector = tuple[float, ...]
GROUPS = {
    "Mercury": 0,
    "Venus": 1,
    "Mars": 3,
    "Jupiter": 4,
    "Saturn": 5,
    "Uranus": 6,
    "Neptune": 7,
    "Pluto": 8,
    "Sun": 10,
}


def _signature(stat: os.stat_result) -> tuple:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def source_kinematics(
    path: Path, epoch: float | Fraction, body: str
) -> tuple[Vector, dict[str, Any]]:
    """Read the actual selected record; never reuse a process-global file cache."""
    if (
        isinstance(epoch, bool)
        or not math.isfinite(epoch)
        or body not in {*GROUPS, "Earth", "Moon"}
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    else:
        pass
    info = jpl_header(path)
    try:
        with path.open("rb") as source:
            before = _signature(os.fstat(source.fileno()))
            if before != _signature(path.stat()):
                raise EphemerisSourceError("changed_during")
            else:
                pass
            if before[2] != info["bytes"]:
                raise EphemerisSourceError("changed_during")
            else:
                pass
            raw_header = source.read(RECORD_BYTES)
            if len(raw_header) != RECORD_BYTES:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            else:
                pass
            orders = [
                o
                for o in ("<", ">")
                if struct.unpack_from(o + "i", raw_header, 2840)[0] == 441
            ]
            if len(orders) != 1:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            else:
                pass
            order = orders[0]
            begin, end, step = struct.unpack_from(order + "3d", raw_header, 2652)
            au, emrat = struct.unpack_from(order + "2d", raw_header, 2680)
            if (begin, end) != (
                info["start_julian_day_tdb"],
                info["end_julian_day_tdb"],
            ) or not begin <= epoch <= end:
                raise EphemerisSourceError("jpl_kinematics_outside_source")
            else:
                pass
            # Wide subtraction can discard an epoch ULP before a record edge.
            # Select with the exact stored binary64 words, before any rounding.
            index = min(
                int((Fraction(epoch) - Fraction(begin)) // Fraction(step)),
                int((end - begin) / step) - 1,
            )
            source.seek((index + 2) * RECORD_BYTES)
            raw = source.read(RECORD_BYTES)
            if step != 32 or au != 149597870.7 or not 81 < emrat < 82:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            else:
                pass
            if (
                len(raw) != RECORD_BYTES
                or before != _signature(os.fstat(source.fileno()))
                or before != _signature(path.stat())
            ):
                raise EphemerisSourceError("changed_during")
            else:
                pass
    except OSError as error:
        raise EphemerisSourceError("unavailable_during") from error
    values = struct.unpack(order + "1018d", raw)
    if not all(math.isfinite(v) for v in values) or values[:2] != (
        begin + index * step,
        begin + (index + 1) * step,
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    else:
        pass
    cells: dict[str, Any] = {}

    def group(
        number: int,
    ) -> tuple[ChebyshevKinematics, ChebyshevKinematics, ChebyshevKinematics]:
        offset, count, parts = struct.unpack_from(
            order + "3i", raw_header, 2696 + 12 * number
        )
        if not (
            1 <= count <= 41
            and parts in {1, 2, 4, 8, 16}
            and 3 <= offset
            and offset + 3 * count * parts - 1 <= 1018
        ):
            raise EphemerisSourceError("jpl_kinematics_invalid")
        else:
            pass
        width = step / parts
        subcell = min(
            int((Fraction(epoch) - Fraction(values[0])) // Fraction(width)), parts - 1
        )
        if not 0 <= subcell < parts or not values[0] <= epoch <= values[1]:
            raise EphemerisSourceError("jpl_kinematics_outside_source")
        else:
            pass
        low = values[0] + subcell * width
        x = 2 * (Fraction(epoch) - Fraction(low)) / Fraction(width) - 1
        axes = []
        for axis in range(3):
            first = offset - 1 + (subcell * 3 + axis) * count
            axes.append(
                chebyshev_kinematics(values[first : first + count], x).in_units(
                    2 / width, au
                )
            )
        cells[str(number)] = {
            "start": low,
            "end": low + width,
            "subcell_index": subcell,
            "coefficient_count": count,
            "at_left_boundary": epoch == low,
            "at_right_boundary": epoch == low + width,
        }
        return axes[0], axes[1], axes[2]

    if body in {"Earth", "Moon"}:
        emb, moon = group(2), group(9)
        resolved = tuple(e.minus(m, 1 + emrat) for e, m in zip(emb, moon))
        if body == "Moon":
            resolved = tuple(e.plus(m) for e, m in zip(resolved, moon))
        else:
            pass
    else:
        resolved = group(GROUPS[body])
    vectors = [axis.rounded() for axis in resolved]
    state = tuple(vectors[axis][k] for k in range(3) for axis in range(3))
    return state, {
        "method_id": METHOD_ID,
        "filename": path.name,
        "epoch_native_argument_day": float(epoch),
        "header_sha256": hashlib.sha256(raw_header).hexdigest(),
        "record_sha256": hashlib.sha256(raw).hexdigest(),
        "record_index": index,
        "record_start": values[0],
        "record_end": values[1],
        "group_cells": cells,
        "source_time_scale": "TDB",
        "argument_policy": "same_native_numeric_day_no_TT_conversion",
        "tt_tdb_conversion_applied": False,
        "unit": "AU, AU/source_day, AU/source_day2",
        "source_boundary_policy": "right-hand cell except final source endpoint; no global unique acceleration assertion",
        "atomic_file_read_proven": False,
        "observational_accuracy_certified": False,
    }


def checked_fixed_acceleration(
    raw: Sequence[float], native: Sequence[float]
) -> tuple[Vector, dict[str, Any]]:
    """Recover a proper *fixed* rotation from two noncollinear state vectors.

    Geometry, lengths and dot products control eligibility, never expected
    angular rates. Both p and v must reproduce before acceleration is rotated.
    No derivative of the reconstructed rotation is taken.
    """
    if (
        len(raw) != 9
        or len(native) != 6
        or not all(math.isfinite(v) for v in (*raw, *native))
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    else:
        pass

    def dot(a: Sequence[float], b: Sequence[float]) -> float:
        return math.fsum(x * y for x, y in zip(a, b))

    def basis(p: Sequence[float], v: Sequence[float]) -> tuple[Vector, ...]:
        size, speed = math.hypot(*p), math.hypot(*v)
        if size <= 0 or speed <= 0:
            raise EphemerisSourceError("jpl_kinematics_frame_mismatch")
        else:
            pass
        a = tuple(x / size for x in p)
        radial = dot(a, v)
        normal = tuple(x - radial * y for x, y in zip(v, a))
        radius = math.hypot(*normal)
        if radius / speed < 0.5:
            raise EphemerisSourceError("jpl_kinematics_frame_mismatch")
        else:
            pass
        b = tuple(x / radius for x in normal)
        return (
            a,
            b,
            (
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            ),
        )

    a, b = basis(raw[:3], raw[3:6]), basis(native[:3], native[3:6])
    matrix = tuple(
        tuple(math.fsum(b[k][i] * a[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )

    def rotate(v: Sequence[float]) -> Vector:
        return tuple(dot(row, v) for row in matrix)

    errors = [
        math.dist(rotate(raw[:3]), native[:3]),
        math.dist(rotate(raw[3:6]), native[3:6]),
    ]
    if max(errors) > FRAME_LINE:
        raise EphemerisSourceError("jpl_kinematics_frame_mismatch")
    else:
        pass
    return rotate(raw[6:9]), {
        "method_id": "checked_two_vector_fixed_rotation_v1",
        "matrix": [list(row) for row in matrix],
        "state_reproduction_errors_au_or_au_per_day": errors,
        "state_reproduction_line": FRAME_LINE,
        "frame_derivative_added": False,
    }
