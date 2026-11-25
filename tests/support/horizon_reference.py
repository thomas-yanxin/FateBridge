"""Independent vector-plane control over exact supplied binary64 angles.

The local east/up axes follow the USNO equatorial-to-horizon convention:
https://aa.usno.navy.mil/faq/alt_az
This checks a numerical angle model; it does not validate TT, EOP or sites.
"""

from typing import TypedDict

from mpmath import mp


class HorizonReference(TypedDict):
    ascendant: float
    cusps: dict[str, list[float]]


def horizon_vector_reference(
    latitude: float, armc: float, obliquity: float
) -> HorizonReference:
    context = mp.clone()
    context.dps = 100
    phi, theta, epsilon = [
        context.mpf(value) * context.pi / 180 for value in (latitude, armc, obliquity)
    ]
    cp, sp = context.cos(phi), context.sin(phi)
    ct, st = context.cos(theta), context.sin(theta)
    ce, se = context.cos(epsilon), context.sin(epsilon)
    up = (cp * ct, cp * st, sp)
    east = (-st, ct, context.mpf(0))
    ecliptic_pole = (context.mpf(0), -se, ce)
    cusps = {}
    for code in ("R", "C"):
        values = []
        for index in range(12):
            phase = index * context.pi / 6
            cosine, sine = context.cos(phase), context.sin(phase)
            factor = cp if code == "R" else context.mpf(1)
            normal = tuple(u * cosine + factor * e * sine for u, e in zip(up, east))
            a, b = ecliptic_pole, normal
            point = (
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            )
            eastward = context.fsum(a * b for a, b in zip(point, east))
            altitude = context.fsum(a * b for a, b in zip(point, up))
            orientation = factor * eastward * cosine - altitude * sine
            if orientation < 0:
                point = tuple(-value for value in point)
            else:
                pass
            longitude = context.atan2(point[1] * ce + point[2] * se, point[0])
            values.append(float(longitude * 180 / context.pi % 360) % 360)
        cusps[code] = values
    return {"ascendant": cusps["C"][0], "cusps": cusps}
