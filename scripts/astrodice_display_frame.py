"""Outward analytic tropical frame for a pinned, explicitly named source model.

No native or production import. The Swiss 77-term/full-Simon-angle variant is
not silently identified with the ERFA00B linear-angle/fixed-offset variant.
"""

import hashlib
import json
import math
import re
import sys
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, cross, dot, norm, scale
from scripts.astrodice_tt_models import pi_interval, sine

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.historical_source_identity import HistoricalSources

PLAN_SHA = "8ea36f1fe01f04e38f4f741f7de53250350d8da539e4a3c02b4c25a5d3e2b07d"
INPUT_SHA = "8f80c3a9654b182ee5a423083ecfc9c0b95e34fd3219fc0a2808694acb9adef4"
FUNDAMENTAL = (
    ("485868.249036", "1717915923.2178", "31.8792", "0.051635", "-0.00024470"),
    ("1287104.79305", "129596581.0481", "-0.5532", "0.000136", "-0.00001149"),
    ("335779.526232", "1739527262.8478", "-12.7512", "-0.001037", "0.00000417"),
    ("1072260.70369", "1602961601.2090", "-6.3706", "0.006593", "-0.00003169"),
    ("450160.398036", "-6962890.5431", "7.4722", "0.007702", "-0.00005939"),
)
BIAS = (
    ("0.99999999999999412", "-0.00000007078368961", "0.00000008056213978"),
    ("0.00000007078368695", "0.99999999999999700", "0.00000003306428553"),
    ("-0.00000008056214212", "-0.00000003306427981", "0.99999999999999634"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(run):
    if (
        sha(run / "plan-before-evaluation.json") != PLAN_SHA
        or sha(run / "inputs-before-development.json") != INPUT_SHA
    ):
        raise ValueError("Frozen full-display plan/input manifest changed")
    bindings = json.loads((run / "inputs-before-development.json").read_text())
    sources = HistoricalSources(Path(__file__).resolve().parents[1])
    for name, digest in bindings.items():
        # A causally reviewed production patch is allowed after development;
        # reference helpers, raw data and the original source copy stay fixed.
        if name.startswith("src/"):
            continue
        if not sources.matches(Path(name), digest):
            raise ValueError("Frozen display reference input changed: " + name)
    return json.loads((run / "plan-before-evaluation.json").read_text())


def clean(raw):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", raw, flags=re.S)


def array(raw, name):
    match = re.search(r"\b" + name + r"\s*\[[^;=]*=\s*\{(.*?)\};", clean(raw), re.S)
    if match is None:
        raise ValueError("Source array absent: " + name)
    return re.findall(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", match[1])


def source_coefficients(run):
    raw = (run / "authority/swephlib.c").read_text()
    tables = {}
    for name, rows, cols in (
        ("pepol", 4, 2),
        ("peper", 5, 10),
        ("pqpol", 4, 2),
        ("pqper", 5, 8),
        ("xypol", 4, 2),
        ("xyper", 5, 14),
    ):
        values = array(raw, name)
        if len(values) != rows * cols:
            raise ValueError("Incomplete frame table: " + name)
        tables[name] = [values[i : i + cols] for i in range(0, len(values), cols)]
    nu = (run / "authority/swenut2000a.h").read_text()
    angles, coefficients = array(nu, "nls"), array(nu, "cls")
    if len(angles) != 678 * 5 or len(coefficients) != 678 * 6:
        raise ValueError("Incomplete native nutation table")
    terms = [
        angles[i * 5 : (i + 1) * 5] + coefficients[i * 6 : (i + 1) * 6]
        for i in range(77)
    ]
    return {
        "tables": tables,
        "nutation77": terms,
        "fundamental": FUNDAMENTAL,
        "bias": BIAS,
        "GM_sun_hex": float(1.32712440017987e20).hex(),
        "solar_radius_radians_hex": float((959.63 / 3600) * (math.pi / 180)).hex(),
    }


def sc(angle):
    angle = A.cast(angle)
    s, c = sine(angle.v), sine(angle.v + pi_interval() / 2)
    return A(s, c * angle.d), A(c, -s * angle.d)


def pair(t, tables, poly, periodic):
    values = []
    factor = pi_interval() / 648000
    for axis in (0, 1):
        value, power = A(), A(1)
        for row in tables[poly]:
            value += Q(float(row[axis])) * power
            power *= t
        periodic_table = tables[periodic]
        for index, period in enumerate(periodic_table[0]):
            s, c = sc(t * (2 * pi_interval()) / Q(float(period)))
            value += (
                Q(float(periodic_table[1 + axis][index])) * c
                + Q(float(periodic_table[3 + axis][index])) * s
            )
        values.append(value * factor)
    return values


def nutation(t, data, *, erfa_variant=False):
    radians = pi_interval() / 648000
    phases = []
    for polynomial in data["fundamental"]:
        value = A()
        for coefficient in reversed(polynomial[:2] if erfa_variant else polynomial):
            value = value * t + Q(float(coefficient))
        phases.append(value * radians)
    psi, eps = A(), A()
    for row in reversed(data["nutation77"]):
        n = [int(v) for v in row[:5]]
        a, b, c, d, e, f = [Q(float(v)) for v in row[5:]]
        s, cs = sc(sum((k * p for k, p in zip(n, phases)), A()))
        psi += (a + b * t) * s + c * cs
        eps += (d + e * t) * cs + f * s
    psi, eps = psi * radians / 10000000, eps * radians / 10000000
    if erfa_variant:
        psi -= Q("0.000135") * radians
        eps += Q("0.000388") * radians
    return psi, eps


def mean_frame(epoch, data):
    t = A((Q(epoch) - 2451545) / 36525, Q(1, 36525))
    p, q = pair(t, data["tables"], "pqpol", "pqper")
    z = (1 - p * p - q * q).sqrt()
    s0, c0 = sc(A(Q(float("84381.406"))) * (pi_interval() / 648000))
    ecliptic = [p, -q * c0 - z * s0, -q * s0 + z * c0]
    x, y = pair(t, data["tables"], "xypol", "xyper")
    equator = [x, y, (1 - x * x - y * y).sqrt()]
    eqx = cross(equator, ecliptic)
    eqx = scale(eqx, 1 / norm(eqx))
    middle = cross(equator, eqx)
    _, epsilon = pair(t, data["tables"], "pepol", "peper")
    se, ce = sc(epsilon)
    mean = [
        eqx,
        [ce * m + se * e for m, e in zip(middle, equator)],
        [-se * m + ce * e for m, e in zip(middle, equator)],
    ]
    return mean, nutation(t, data), nutation(t, data, erfa_variant=True)


def frame_state(epoch, data):
    mean, (psi, eps), standard = mean_frame(epoch, data)
    s, c = sc(psi)
    true = [
        [c * x - s * y for x, y in zip(mean[0], mean[1])],
        [s * x + c * y for x, y in zip(mean[0], mean[1])],
        mean[2],
    ]
    return {
        "mean": mean,
        "true": true,
        "psi": psi,
        "deps": eps,
        "erfa00b_psi": standard[0],
        "erfa00b_deps": standard[1],
    }


def project(state, direction, data):
    biased = [
        sum((Q(float(a)) * b for a, b in zip(row, direction)), A())
        for row in data["bias"]
    ]
    return [dot(row, biased) for row in state["true"]]


def record(v):
    return {
        "value": list(map(str, v.v.bounds())),
        "derivative": list(map(str, v.d.bounds())),
    }


def vector_record(v):
    return [record(x) for x in v]
