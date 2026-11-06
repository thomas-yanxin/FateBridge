"""Independent Decimal angular reference with fixed thresholds and precision."""

from decimal import Decimal, localcontext

ANGLES = [
    ("conjunction", 0),
    ("sextile", 60),
    ("square", 90),
    ("trine", 120),
    ("opposition", 180),
]
RADII = {
    "Sun": 10.0,
    "Moon": 10.0,
    "Mercury": 7.0,
    "Venus": 7.0,
    "Mars": 7.5,
    "Jupiter": 9.0,
    "Saturn": 9.0,
    "Uranus": 5.0,
    "Neptune": 5.0,
    "Pluto": 5.0,
}


def dec(value):
    return Decimal.from_float(value) if isinstance(value, float) else Decimal(value)


def wrap(value):
    return (value % 360 + 360) % 360


def gap(a, b):
    diff = wrap(dec(a) - dec(b))
    return min(diff, 360 - diff)


def reference_match(a, b, radius, pair=None):
    with localcontext() as ctx:
        ctx.prec = 2048
        separation = gap(a, b)
        matches = []
        for name, angle in ANGLES:
            limit = radius
            if pair:
                limit = (RADII[pair[0]] + RADII[pair[1]]) / 2
                if name in {"sextile", "square"}:
                    limit *= 0.8
            distance = abs(separation - angle)
            if distance <= dec(limit):
                matches.append((distance, name))
        if not matches:
            return None
        distance, name = min(matches, key=lambda row: row[0])
        return {"aspect": name, "delta": float(distance)}


def reference_midpoints(a, b):
    a, b = wrap(dec(a)), wrap(dec(b))
    forward = wrap(b - a)
    if forward == 180:
        axis = ((a + b) / 2) % 180
        return (axis, axis + 180)
    if forward > 180:
        forward -= 360
    return (wrap(a + forward / 2),)


def reference_phase(a, va, b, vb, angle):
    if va is None or vb is None:
        return "unavailable"
    with localcontext() as ctx:
        ctx.prec = 2048
        current = wrap(dec(b) - dec(a))
        distance = min(current, 360 - current)
        current_gap = abs(distance - dec(angle))
        if current_gap == 0:
            return "exact"
        velocity = dec(vb) - dec(va)
        if velocity == 0:
            return "stationary"
        future = wrap(current + velocity * Decimal("1e-1200"))
        future_gap = abs(min(future, 360 - future) - dec(angle))
        assert future_gap != current_gap
        return "applying" if future_gap < current_gap else "separating"
