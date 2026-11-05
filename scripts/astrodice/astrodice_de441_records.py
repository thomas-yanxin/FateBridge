"""Exact, maintenance-only geometric evaluation of original DE441 records.

No FateBridge, Swiss, NumPy or observational reference is imported. Coefficients
are the exact rational values of the original binary64 source words. Calendar
labels here are explicitly TDB; this does not supply a TT-to-TDB conversion.
"""

import hashlib
import math
import struct
from datetime import datetime
from fractions import Fraction as F

RECORD_BYTES = 8144
METHOD = "independent_exact_rational_de441_geometric_clenshaw_v1"


def calendar_jd_tdb(label):
    value = datetime.fromisoformat(label)
    if value.tzinfo is not None:
        raise ValueError("TDB labels must not carry a civil timezone")
    seconds = F(value.hour * 3600 + value.minute * 60 + value.second)
    seconds += F(value.microsecond, 1000000)
    return F(value.toordinal()) + F(3442849, 2) + seconds / 86400


def header(raw):
    if len(raw) != RECORD_BYTES:
        raise ValueError("Incomplete original DE441 header record")
    start, end, step = struct.unpack_from("<3d", raw, 2652)
    number = struct.unpack_from("<i", raw, 2840)[0]
    au, emrat = struct.unpack_from("<2d", raw, 2680)
    pointers = list(zip(*[iter(struct.unpack_from("<36i", raw, 2696))] * 3))
    libration = struct.unpack_from("<3i", raw, 2844)
    if (
        number != 441
        or step != 32
        or not start < end
        or (end - start) % step
        or au != 149597870.7
        or not 81 < emrat < 82
        or pointers[0] != (3, 14, 4)
        or pointers[1] != (171, 10, 2)
        or pointers[2] != (231, 13, 2)
        or pointers[9] != (441, 13, 8)
        or pointers[10] != (753, 11, 2)
        or libration != (899, 10, 4)
    ):
        raise ValueError("Unplanned original DE441 record layout")
    return {
        "start_jd_tdb": start,
        "end_jd_tdb": end,
        "step_days": step,
        "au_km": au,
        "earth_moon_mass_ratio": emrat,
        "pointers": pointers,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def clenshaw_with_derivative(coefficients, x):
    """Return p(x), dp/dx using exact rational differentiated Clenshaw."""
    x = F(x)
    if not coefficients or not -1 <= x <= 1:
        raise ValueError("Polynomial outside its source subinterval")
    b1 = b2 = d1 = d2 = F(0)
    for value in reversed(coefficients[1:]):
        b0 = F(value) + 2 * x * b1 - b2
        d0 = 2 * b1 + 2 * x * d1 - d2
        b2, b1, d2, d1 = b1, b0, d1, d0
    return F(coefficients[0]) + x * b1 - b2, b1 + x * d1 - d2


def group_state(metadata, record, epoch, group):
    if len(record) != RECORD_BYTES or type(group) is not int or not 0 <= group <= 10:
        raise ValueError("Invalid original position record/group")
    values = struct.unpack("<1018d", record)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Nonfinite source coefficient")
    begin, end = map(F, values[:2])
    epoch = F(epoch)
    if end - begin != 32 or not begin <= epoch < end:
        raise ValueError("Epoch outside the original record")
    offset, count, subdivisions = metadata["pointers"][group]
    width = (end - begin) / subdivisions
    part = int((epoch - begin) // width)
    x = 2 * (epoch - begin - part * width) / width - 1
    first = offset - 1 + part * 3 * count
    positions, velocities = [], []
    for axis in range(3):
        c = [F(v) for v in values[first + axis * count : first + (axis + 1) * count]]
        position, derivative = clenshaw_with_derivative(c, x)
        positions.append(position)
        velocities.append(derivative * 2 / width)
    return positions + velocities


def geometric_states(metadata, record, epoch):
    """Barycentric states in AU and AU/day; source Moon is geocentric."""
    au = F(metadata["au_km"])
    earth_moon = F(metadata["earth_moon_mass_ratio"])
    groups = {g: group_state(metadata, record, epoch, g) for g in (0, 1, 2, 9, 10)}
    earth = [b - m / (1 + earth_moon) for b, m in zip(groups[2], groups[9])]
    return {
        name: [v / au for v in state]
        for name, state in {
            "Mercury": groups[0],
            "Venus": groups[1],
            "Earth": earth,
            "Moon": [e + m for e, m in zip(earth, groups[9])],
            "Sun": groups[10],
        }.items()
    }


def mini_kernel(header_record, constant_record, records):
    """Copy consecutive coefficients; only header range/title are changed."""
    original = header(header_record)
    if len(constant_record) != RECORD_BYTES or not records:
        raise ValueError("Incomplete constants or record window")
    begin = None
    previous_end = None
    for record in records:
        if len(record) != RECORD_BYTES:
            raise ValueError("Incomplete original coefficient record")
        start, end = struct.unpack_from("<2d", record)
        if (
            end - start != original["step_days"]
            or (previous_end is not None and start != previous_end)
            or start < original["start_jd_tdb"]
            or end > original["end_jd_tdb"]
        ):
            raise ValueError("Nonconsecutive or invalid original record window")
        begin = start if begin is None else begin
        previous_end = end
    modified = bytearray(header_record)
    title = b"FateBridge DE441 diagnostic excerpt; original coefficient bytes retained"
    modified[:252] = title.ljust(252, b" ")
    struct.pack_into("<2d", modified, 2652, begin, previous_end)
    if any(
        a != b and not (i < 252 or 2652 <= i < 2668)
        for i, (a, b) in enumerate(zip(header_record, modified))
    ):
        raise ValueError("Unexpected source header modification")
    return bytes(modified) + constant_record + b"".join(records)
