"""Independent integer unpacking, Decimal rotation and Clenshaw SWE replay.

No native library or first decoder is imported. This is a source-recipe
cross-check, not a certificate for the unknown pre-compression coefficients.
"""

import math
import struct
import zlib
from decimal import Decimal as D
from decimal import localcontext
from fractions import Fraction as Q

PI = D(
    "3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117067982148086513282306647"
)


def exact(value):
    q = Q(value)
    return D(q.numerator) / D(q.denominator)


def sincos(x):
    x %= 2 * PI
    if x > PI:
        x -= 2 * PI
    ss, cc, s, c = x, D(1), x, D(1)
    for k in range(1, 150):
        ss *= -(x * x) / ((2 * k) * (2 * k + 1))
        cc *= -(x * x) / ((2 * k - 1) * (2 * k))
        s += ss
        c += cc
    return s, c


def reflected_crc(raw):
    def reverse(n, bits):
        return int(f"{n:0{bits}b}"[::-1], 2)

    return reverse(zlib.crc32(bytes(reverse(b, 8) for b in raw)), 32)


def unpack(path, epoch, wanted):
    raw = path.read_bytes()
    first = raw.split(b"\r\n", 3)
    if len(first) != 4 or first[1].decode().strip().lower() != path.name.lower():
        raise ValueError("Independent SWE header/filename mismatch")
    base = sum(len(s) + 2 for s in first[:3])
    marker = raw[base : base + 4]
    endian = {b"cba\0": "<", b"\0abc": ">"}[marker]
    order = "little" if endian == "<" else "big"
    cursor = base + 4

    def read(fmt):
        nonlocal cursor
        n = struct.calcsize(endian + fmt)
        result = struct.unpack_from(endian + fmt, raw, cursor)
        cursor += n
        return result

    length, edition, _, _, number = read("ii2dh")
    if length != len(raw) or edition != 441:
        raise ValueError("Independent SWE edition/length mismatch")
    ids = read(("i" if number > 256 else "h") * (number % 256))
    crc_at = cursor
    if read("I")[0] != reflected_crc(raw[:crc_at]):
        raise ValueError("Independent reflected-CRC header check failed")
    read("5d")
    descriptor = None
    for body in ids:
        pointer, flags, size, radius = read("iBBi")
        parameters = read("10d")
        reference = read(str(2 * size) + "d") if flags & 4 else None
        if body == wanted:
            descriptor = pointer, flags, size, radius, parameters, reference
    if descriptor is None:
        raise ValueError("Independent SWE target absent")
    pointer, flags, size, radius, params, reference = descriptor
    start, stop, span, origin, node, dnode, inclination, dinclination, peri, dperi = (
        params
    )
    if not start <= epoch < stop:
        raise ValueError("Independent SWE epoch out of range")
    segment = math.floor((epoch - start) / span)
    at = pointer + 3 * segment
    cursor = int.from_bytes(raw[at : at + 3], order)
    axes, formats = [], []
    for _ in range(3):
        header = read("2B")
        if header[0] >= 128:
            header = (header[1], *read("2B"))
        counts = [int(bit, 16) for bit in bytes(header).hex()]
        if sum(counts) > size:
            raise ValueError("Independent SWE coefficient count overflow")
        coefficients = []
        for group, count in enumerate(counts):
            width = 32 - 8 * group if group < 4 else 4 if group == 4 else 2
            length = (width * count + 7) // 8
            block = raw[cursor : cursor + length]
            if len(block) != length:
                raise ValueError("Independent truncated SWE block")
            cursor += length
            if group < 4:
                words = [
                    int.from_bytes(block[k : k + width // 8], order)
                    for k in range(0, length, width // 8)
                ]
            else:
                bits = "".join(f"{byte:08b}" for byte in block)
                words = [
                    int(bits[k * width : (k + 1) * width], 2) for k in range(count)
                ]
            for word in words:
                signed = -(int((word + 1) % (1 << 32)) // 2) if word % 2 else word // 2
                coefficients.append(Q(signed * radius, 2000000000000))
        axes.append(coefficients + [Q()] * (size - len(coefficients)))
        formats.append(counts)
    segment_start = start + segment * span
    with localcontext() as ctx:
        ctx.prec = 110
        rotated = [[exact(x) for x in axis] for axis in axes]
        last = size - 1
        if flags & 2:
            # Re-evaluate the real-valued source recipe at its binary64
            # descriptor. Do not imitate each rounding operation of decoder 1.
            dt = (exact(segment_start) + exact(span) / 2 - exact(origin)) / 365250
            p = exact(node) + dt * exact(dnode)
            q = exact(inclination) + dt * exact(dinclination)
            if wanted == 1:
                sine, cosine = sincos(p)
                q, p = q * cosine, q * sine
            f = 1 / (1 + q * q + p * p)
            basis = (
                ((1 + q * q - p * p) * f, 2 * q * p * f, -2 * p * f),
                (2 * q * p * f, (1 - q * q + p * p) * f, 2 * q * f),
                (2 * p * f, -2 * q * f, (1 - q * q - p * p) * f),
            )
            if flags & 4:
                sine, cosine = sincos(exact(peri) + dt * exact(dperi))
                for k in range(size):
                    rx, ry = exact(reference[k]), exact(reference[k + size])
                    rotated[0][k] += cosine * rx - sine * ry
                    rotated[1][k] += cosine * ry + sine * rx
            output = [[], [], []]
            last = None
            for k in range(size):
                v = [
                    sum(rotated[j][k] * basis[j][i] for j in range(3)) for i in range(3)
                ]
                if sum(map(abs, v)) >= D("1e-14"):
                    last = k
                if wanted == 1:
                    ce, se = exact(0.91748206215761929), exact(0.39777715572793088)
                    v[1], v[2] = ce * v[1] - se * v[2], se * v[1] + ce * v[2]
                for axis in range(3):
                    output[axis].append(v[axis])
            if last is None:
                raise ValueError("Independent no-significant-coefficient case")
            rotated = output
        return {
            "body": wanted,
            "flags": flags,
            "ncoef": size,
            "last_significant_index": last,
            "segment_start": segment_start,
            "span": span,
            "segment_index": segment,
            "packed_sizes": formats,
            "decoded_exact_coefficients": axes,
            "rotated_decimal_coefficients": rotated,
        }


def evaluate(segment, epoch, profile):
    with localcontext() as ctx:
        ctx.prec = 110
        count = segment["ncoef"]
        if segment["flags"] & 2 and profile != "all_coefficients":
            count = segment["last_significant_index"] + (profile == "index_plus_one")
        x = (
            2
            * (exact(epoch) - exact(segment["segment_start"]))
            / exact(segment["span"])
            - 1
        )
        positions, velocities = [], []
        for axis in segment["rotated_decimal_coefficients"]:
            coefficients = axis[:count]
            b1 = b2 = d1 = d2 = D(0)
            for coefficient in reversed(coefficients[1:]):
                b0 = coefficient + 2 * x * b1 - b2
                d0 = 2 * b1 + 2 * x * d1 - d2
                b2, b1, d2, d1 = b1, b0, d1, d0
            positions.append((coefficients[0] / 2 if count else 0) + x * b1 - b2)
            velocities.append((b1 + x * d1 - d2) * 2 / exact(segment["span"]))
        return positions + velocities


def geometric(planet, moon, epoch, body, profile):
    with localcontext() as ctx:
        ctx.prec = 110
        m = evaluate(unpack(moon, epoch, 1), epoch, profile)
        if body == "Moon":
            return m
        emb = evaluate(unpack(planet, epoch, 0), epoch, profile)
        solar_segment = unpack(planet, epoch, 10)
        s = evaluate(solar_segment, epoch, profile)
        if solar_segment["flags"] & 8:
            s = [x - y for x, y in zip(emb, s)]
        target = unpack(planet, epoch, {"Mercury": 2, "Venus": 3}[body])
        values = evaluate(target, epoch, profile)
        if target["flags"] & 1:
            values = [x + y for x, y in zip(values, s)]
        ratio = exact((1 / 0.0123000383) + 1)
        return [x - e + mm / ratio for x, e, mm in zip(values, emb, m)]
