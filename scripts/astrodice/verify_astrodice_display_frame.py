"""Independent 288-bit derivative and expanded nutation-frame source replay.

No display producer, production, native library or its algebra is imported.
Primary ERFA tables independently bind pole and 77-term numeric coefficients;
the source-specific full fundamental arguments remain explicitly distinguished.
"""

import json
import math
import re
from fractions import Fraction as Q

from scripts.astrodice.verify_astrodice_observer_clock import (
    add,
    divide,
    independent_pi,
    mul,
    neg,
    rounded,
    sub,
)
from scripts.astrodice.verify_astrodice_taylor_remainder import (
    R,
    dot,
    normalize,
    vector_product,
)


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def table(text, name):
    text = strip_comments(text)
    begin = re.search(r"\b" + name + r"\s*\[[^;=]*=\s*\{", text)
    if begin is None:
        raise ValueError("Independent missing primary array: " + name)
    end = text.index("};", begin.end())
    return re.findall(
        r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", text[begin.end() : end]
    )


def reshape(values, rows, columns):
    if len(values) != rows * columns:
        raise ValueError("Independent primary array shape mismatch")
    return [values[i : i + columns] for i in range(0, len(values), columns)]


def data_from_primary(run):
    native = (run / "authority/swephlib.c").read_text()
    tables = {}
    for name, rows, columns in (
        ("pepol", 4, 2),
        ("peper", 5, 10),
        ("pqpol", 4, 2),
        ("pqper", 5, 8),
        ("xypol", 4, 2),
        ("xyper", 5, 14),
    ):
        tables[name] = reshape(table(native, name), rows, columns)
    for prefix, source, count in (("pq", "ltpecl.c", 8), ("xy", "ltpequ.c", 14)):
        raw = (run / "authority" / source).read_text()
        polynomial = list(map(list, zip(*reshape(table(raw, prefix + "pol"), 2, 4))))
        periodic = list(map(list, zip(*reshape(table(raw, prefix + "per"), count, 5))))
        for actual, expected in (
            (tables[prefix + "pol"], polynomial),
            (tables[prefix + "per"], periodic),
        ):
            if [[Q(v) for v in row] for row in actual] != [
                [Q(v) for v in row] for row in expected
            ]:
                raise ValueError(
                    "Native corrected pole table differs from primary ERFA"
                )
    raw = (run / "authority/swenut2000a.h").read_text()
    n = reshape(table(raw, "nls"), 678, 5)
    c = reshape(table(raw, "cls"), 678, 6)
    terms = [a + b for a, b in zip(n[:77], c[:77])]
    primary = reshape(table((run / "authority/nut00b.c").read_text(), "x"), 77, 11)
    if [[Q(v) for v in row] for row in terms] != [
        [Q(v) for v in row] for row in primary
    ]:
        raise ValueError("77-term coefficients differ from primary ERFA")
    function = strip_comments(native.split("static int calc_nutation_iau2000ab", 1)[1])
    fundamental = []
    for name in ("M", "SM", "F", "D", "OM"):
        expr = re.search(
            r"\b" + name + r"\s*=\s*swe_degnorm\((.*?)\)\s*\*\s*DEGTORAD",
            function,
            re.S,
        )[1]
        tokens = re.findall(
            r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?",
            re.sub(r"([+-])\s+(\d)", r"\1\2", expr),
        )
        if len(tokens) != 6 or Q(tokens[-1]) != 3600:
            raise ValueError("Native full fundamental polynomial shape changed")
        fundamental.append(tokens[:-1])
    block = native.split("if (bias_model == SEMOD_BIAS_IAU2006)", 1)[1].split(
        "} else", 1
    )[0]
    bias = [[None] * 3 for _ in range(3)]
    for column, row, value in re.findall(
        r"rb\[(\d)\]\[(\d)\]\s*=\s*([+\-\d.]+)", block
    ):
        bias[int(row)][int(column)] = value
    stored = json.loads((run / "frame-coefficients-before-evaluation.json").read_text())
    result = {
        "tables": tables,
        "nutation77": terms,
        "fundamental": fundamental,
        "bias": bias,
        "GM_sun_hex": float(1.32712440017987e20).hex(),
        "solar_radius_radians_hex": float((959.63 / 3600) * (math.pi / 180)).hex(),
    }
    # Numeric equality tolerates only spelling differences such as +1 and 1.0.
    for key in ("tables", "nutation77", "fundamental", "bias"):

        def rationals(value):
            if isinstance(value, dict):
                return {k: rationals(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rationals(v) for v in value]
            return Q(value)

        if rationals(stored[key]) != rationals(result[key]):
            raise ValueError("Saved reference coefficient detached from primary source")
    if any(stored[k] != result[k] for k in ("GM_sun_hex", "solar_radius_radians_hex")):
        raise ValueError("Declared source constants changed")
    return result


def sc(x):
    if len(x.v) != 2:
        raise ValueError("Only first analytic derivative planned")
    pi = rounded(*independent_pi())
    low, high = x.v[0]
    turn = round((low + high) / (2 * (pi[0] + pi[1])))
    a = sub(x.v[0], mul(rounded(2 * turn), pi))
    if max(map(abs, a)) > 4:
        raise ValueError("Independent reduced trigonometric support too wide")
    square_negative = neg(mul(a, a))
    st, ct, s, c = a, rounded(1), rounded(0), rounded(0)
    for k in range(90):
        if k:
            st = divide(mul(st, square_negative), rounded((2 * k) * (2 * k + 1)))
            ct = divide(mul(ct, square_negative), rounded((2 * k - 1) * (2 * k)))
        s, c = add(s, st), add(c, ct)
    tail_s = Q(4) ** 181 / math.factorial(181)
    tail_c = Q(4) ** 180 / math.factorial(180)
    s, c = add(s, rounded(-tail_s, tail_s)), add(c, rounded(-tail_c, tail_c))
    return R([s, mul(c, x.v[1])]), R([c, neg(mul(s, x.v[1]))])


def constant(value):
    return R([rounded(value), rounded(0)])


def pair(t, data, poly, periodic):
    table = data["tables"]
    factor = constant(1) * R([rounded(*independent_pi()), rounded(0)]) / 648000
    values = []
    for axis in range(2):
        value = constant(0)
        for row in reversed(table[poly]):
            value = value * t + Q(float(row[axis]))
        for index, period in enumerate(table[periodic][0]):
            s, c = sc(t * (2 * 648000) * factor / Q(float(period)))
            value += c * Q(float(table[periodic][1 + axis][index])) + s * Q(
                float(table[periodic][3 + axis][index])
            )
        values.append(value * factor)
    return values


def mm(a, b):
    return [
        [sum((x * y for x, y in zip(row, col)), constant(0)) for col in zip(*b)]
        for row in a
    ]


def rx(angle):
    s, c = sc(angle)
    zero, one = constant(0), constant(1)
    return [[one, zero, zero], [zero, c, s], [zero, -s, c]]


def rz(angle):
    s, c = sc(angle)
    zero, one = constant(0), constant(1)
    return [[c, -s, zero], [s, c, zero], [zero, zero, one]]


def frame_state(epoch, data):
    t = R([rounded((Q(epoch) - 2451545) / 36525), rounded(Q(1, 36525))])
    factor = R([rounded(*independent_pi()), rounded(0)]) / 648000
    p, q = pair(t, data, "pqpol", "pqper")
    z = (1 - p * p - q * q).sqrt()
    s, c = sc(constant(Q(float("84381.406"))) * factor)
    ecliptic = [p, -q * c - z * s, -q * s + z * c]
    x, y = pair(t, data, "xypol", "xyper")
    equator = [x, y, (1 - x * x - y * y).sqrt()]
    equinox = normalize(vector_product(equator, ecliptic))
    precession = [equinox, vector_product(equator, equinox), equator]
    _, eps = pair(t, data, "pepol", "peper")
    angles = []
    for polynomial in data["fundamental"]:
        value = constant(0)
        for coefficient in reversed(polynomial):
            value = value * t + Q(float(coefficient))
        angles.append(value * factor)
    psi, deps = constant(0), constant(0)
    for row in data["nutation77"]:
        s, c = sc(sum((p * int(n) for n, p in zip(row[:5], angles)), constant(0)))
        a, b, c0, d, e, f = map(lambda v: Q(float(v)), row[5:])
        psi += (a + b * t) * s + c0 * c
        deps += (d + e * t) * c + f * s
    psi, deps = psi * factor / 10000000, deps * factor / 10000000
    # Expanded chain independently checks cancellation of deps and its rate.
    nut = mm(mm(rx(-eps - deps), rz(psi)), rx(eps))
    true = mm(mm(rx(eps + deps), nut), precession)
    return {"mean": mm(rx(eps), precession), "true": true, "psi": psi, "deps": deps}


def project(frame, direction, data):
    biased = [
        sum((Q(float(a)) * b for a, b in zip(row, direction)), constant(0))
        for row in data["bias"]
    ]
    return [dot(row, biased) for row in frame["true"]]
