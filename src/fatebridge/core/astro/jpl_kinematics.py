"""Analytic p/v/a of the selected direct-access DE441 source polynomial.

The numerical argument is the native caller's day, without a TT/TDB conversion.
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
from typing import Any, Dict, Sequence, Tuple

from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "de441_analytic_source_kinematics_v1"
RECORD_BYTES = 8144
FRAME_LINE = 2e-13
Vector = Tuple[float, ...]
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


def chebyshev_kinematics(coefficients: Sequence[float], x: float) -> Vector:
    """Differentiated Clenshaw, with full c0 and two analytic derivatives."""
    if (
        not coefficients
        or not -1 <= x <= 1
        or not all(math.isfinite(c) for c in coefficients)
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    b1 = b2 = d1 = d2 = a1 = a2 = 0.0
    for c in reversed(coefficients[1:]):
        b0 = math.fsum((c, 2 * x * b1, -b2))
        d0 = math.fsum((2 * b1, 2 * x * d1, -d2))
        a0 = math.fsum((4 * d1, 2 * x * a1, -a2))
        b2, b1, d2, d1, a2, a1 = b1, b0, d1, d0, a1, a0
    result = (
        math.fsum((coefficients[0], x * b1, -b2)),
        math.fsum((b1, x * d1, -d2)),
        math.fsum((2 * d1, x * a1, -a2)),
    )
    if not all(math.isfinite(v) for v in result):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    return result


def _signature(stat: os.stat_result) -> tuple:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def source_kinematics(
    path: Path, epoch: float, body: str
) -> Tuple[Vector, Dict[str, Any]]:
    """Read the actual selected record; never reuse a process-global file cache."""
    if (
        isinstance(epoch, bool)
        or not math.isfinite(epoch)
        or body not in {*GROUPS, "Earth", "Moon"}
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    info = jpl_header(path)
    try:
        with path.open("rb") as source:
            before = _signature(os.fstat(source.fileno()))
            if before != _signature(path.stat()):
                raise EphemerisSourceError("changed_during")
            if before[2] != info["bytes"]:
                raise EphemerisSourceError("changed_during")
            raw_header = source.read(RECORD_BYTES)
            if len(raw_header) != RECORD_BYTES:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            orders = [
                o
                for o in ("<", ">")
                if struct.unpack_from(o + "i", raw_header, 2840)[0] == 441
            ]
            if len(orders) != 1:
                raise EphemerisSourceError("jpl_kinematics_invalid")
            order = orders[0]
            begin, end, step = struct.unpack_from(order + "3d", raw_header, 2652)
            au, emrat = struct.unpack_from(order + "2d", raw_header, 2680)
            if (begin, end) != (
                info["start_julian_day_tdb"],
                info["end_julian_day_tdb"],
            ) or not begin <= epoch <= end:
                raise EphemerisSourceError("jpl_kinematics_outside_source")
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
            if (
                len(raw) != RECORD_BYTES
                or before != _signature(os.fstat(source.fileno()))
                or before != _signature(path.stat())
            ):
                raise EphemerisSourceError("changed_during")
    except OSError as error:
        raise EphemerisSourceError("unavailable_during") from error
    values = struct.unpack(order + "1018d", raw)
    if not all(math.isfinite(v) for v in values) or values[:2] != (
        begin + index * step,
        begin + (index + 1) * step,
    ):
        raise EphemerisSourceError("jpl_kinematics_invalid")
    cells: Dict[str, Any] = {}

    def group(number: int) -> Vector:
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
        width = step / parts
        subcell = min(int((epoch - values[0]) // width), parts - 1)
        if not 0 <= subcell < parts or not values[0] <= epoch <= values[1]:
            raise EphemerisSourceError("jpl_kinematics_outside_source")
        low = values[0] + subcell * width
        x = 2 * (epoch - low) / width - 1
        axes = []
        for axis in range(3):
            first = offset - 1 + (subcell * 3 + axis) * count
            axes.append(chebyshev_kinematics(values[first : first + count], x))
        cells[str(number)] = {
            "start": low,
            "end": low + width,
            "subcell_index": subcell,
            "coefficient_count": count,
            "at_left_boundary": epoch == low,
            "at_right_boundary": epoch == low + width,
        }
        return tuple(
            axes[axis][k] * (2 / width) ** k / au for k in range(3) for axis in range(3)
        )

    if body in {"Earth", "Moon"}:
        emb, moon = group(2), group(9)
        earth = tuple(b - m / (1 + emrat) for b, m in zip(emb, moon))
        state = earth if body == "Earth" else tuple(e + m for e, m in zip(earth, moon))
    else:
        state = group(GROUPS[body])
    return state, {
        "method_id": METHOD_ID,
        "filename": path.name,
        "epoch_native_argument_day": epoch,
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
) -> Tuple[Vector, Dict[str, Any]]:
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

    def dot(a: Sequence[float], b: Sequence[float]) -> float:
        return math.fsum(x * y for x, y in zip(a, b))

    def basis(p: Sequence[float], v: Sequence[float]) -> Tuple[Vector, ...]:
        size, speed = math.hypot(*p), math.hypot(*v)
        if size <= 0 or speed <= 0:
            raise EphemerisSourceError("jpl_kinematics_frame_mismatch")
        a = tuple(x / size for x in p)
        radial = dot(a, v)
        normal = tuple(x - radial * y for x, y in zip(v, a))
        radius = math.hypot(*normal)
        if radius / speed < 0.5:
            raise EphemerisSourceError("jpl_kinematics_frame_mismatch")
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
    return rotate(raw[6:9]), {
        "method_id": "checked_two_vector_fixed_rotation_v1",
        "matrix": [list(row) for row in matrix],
        "state_reproduction_errors_au_or_au_per_day": errors,
        "state_reproduction_line": FRAME_LINE,
        "frame_derivative_added": False,
    }
