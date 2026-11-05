"""Maintenance-only SWI3 packed coefficient decoding and retention diagnostics.

No native library, production service or external ephemeris is imported. File
selection is supplied from observed native source contexts, never residuals.
This replays the pinned binary64 rotation recipe and independently evaluates
Chebyshev values/derivatives; it is not a physical-accuracy certificate.
"""

import hashlib
import math
import struct

PROFILES = ("rebuilt_original", "index_plus_one", "all_coefficients")


def crc32_msb(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = (
                (value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)
            ) & 0xFFFFFFFF
    return (~value) & 0xFFFFFFFF


class PackedFile:
    def __init__(self, path):
        self.path = path
        self.raw = path.read_bytes()
        self.cursor = 0
        headers = []
        for _ in range(3):
            end = self.raw.index(b"\r\n", self.cursor)
            headers.append(self.raw[self.cursor : end].decode("ascii"))
            self.cursor = end + 2
        if (
            not headers[0].startswith("SWISSEPH")
            or headers[1].strip().lower() != path.name.lower()
        ):
            raise ValueError("SWI3 identity/header mismatch")
        marker = self.take(4)
        if marker == bytes.fromhex("63626100"):
            self.order, self.byteorder = "<", "little"
        elif marker == bytes.fromhex("00616263"):
            self.order, self.byteorder = ">", "big"
        else:
            raise ValueError("Unrecognized packed-source byte order")
        length, de = self.unpack("2i")
        if length != len(self.raw) or de != 441:
            raise ValueError("Packed source length/edition mismatch")
        begin, end = self.unpack("2d")
        count = self.unpack("h")[0]
        width = 4 if count > 256 else 2
        count %= 256
        if not 1 <= count <= 20:
            raise ValueError("Invalid packed source object count")
        ids = [int.from_bytes(self.take(width), self.byteorder) for _ in range(count)]
        crc_end = self.cursor
        declared_crc = self.unpack("I")[0]
        if crc32_msb(self.raw[:crc_end]) != declared_crc:
            raise ValueError("Packed-source header CRC mismatch")
        constants = self.unpack("5d")
        self.objects = {}
        for body in ids:
            index = self.unpack("i")[0]
            flags, ncoef = self.take(2)
            rmax = self.unpack("i")[0] / 1000.0
            values = self.unpack("10d")
            if not 0 < ncoef <= 41 or values[2] <= 0:
                raise ValueError("Invalid packed polynomial descriptor")
            ref = self.unpack(str(2 * ncoef) + "d") if flags & 4 else None
            self.objects[body] = {
                "index": index,
                "flags": flags,
                "ncoef": ncoef,
                "rmax": rmax,
                "parameters": values,
                "reference": ref,
            }
        self.identity = {
            "filename": path.name,
            "bytes": len(self.raw),
            "sha256": hashlib.sha256(self.raw).hexdigest(),
            "de_number": de,
            "file_start": begin,
            "file_end": end,
            "header_crc_verified": True,
            "general_constants_not_used_by_native_recipe": constants,
        }

    def take(self, size):
        result = self.raw[self.cursor : self.cursor + size]
        if len(result) != size:
            raise ValueError("Truncated packed source")
        self.cursor += size
        return result

    def unpack(self, format):
        return struct.unpack(
            self.order + format, self.take(struct.calcsize(self.order + format))
        )

    def segment(self, epoch, body):
        item = self.objects[body]
        start, end, span, telem, prot, dprot, qrot, dqrot, peri, dperi = item[
            "parameters"
        ]
        if not start <= epoch < end:
            raise ValueError("Diagnostic epoch outside selected packed source")
        index = int((epoch - start) / span)
        pointer = item["index"] + index * 3
        self.cursor = pointer
        location = int.from_bytes(self.take(3), self.byteorder)
        if not 0 < location < len(self.raw):
            raise ValueError("Invalid packed segment pointer")
        self.cursor = location
        ncoef, radius = item["ncoef"], item["rmax"]
        coefficients, packing = [], []
        for axis in range(3):
            a, b = self.take(2)
            if a & 128:
                c, d = self.take(2)
                sizes = [b // 16, b % 16, c // 16, c % 16, d // 16, d % 16]
            else:
                sizes = [a // 16, a % 16, b // 16, b % 16]
            if sum(sizes) > ncoef:
                raise ValueError("Too many packed coefficients")
            values = []
            for group, count in enumerate(sizes):
                if group < 4:
                    words = [
                        int.from_bytes(self.take(4 - group), self.byteorder)
                        for _ in range(count)
                    ]
                else:
                    bits = 4 if group == 4 else 2
                    packed = self.take((count * bits + 7) // 8)
                    words = [
                        (packed[k * bits // 8] >> (8 - bits - (k * bits) % 8))
                        & ((1 << bits) - 1)
                        for k in range(count)
                    ]
                for word in words:
                    # Reproduce the inspected uint32 +1 convention, including
                    # its wrap if that word ever occurs. No word is discarded.
                    magnitude = (
                        ((word + 1) & 0xFFFFFFFF) // 2 if word & 1 else word // 2
                    )
                    value = (
                        magnitude / 1e9 * radius / 2
                        if group < 4
                        else magnitude * radius / 2 / 1e9
                    )
                    values.append(-value if word & 1 else value)
            values.extend([0.0] * (ncoef - len(values)))
            coefficients.append(values)
            packing.append(sizes)
        segment_start = start + index * span
        rotated = list(map(list, coefficients))
        last = ncoef - 1
        if item["flags"] & 2:
            dt = (segment_start + span / 2 - telem) / 365250.0
            if body == 1:
                dn = prot + dt * dprot
                dn -= int(dn / math.tau) * math.tau
                q, p = (
                    (qrot + dt * dqrot) * math.cos(dn),
                    (qrot + dt * dqrot) * math.sin(dn),
                )
            else:
                q, p = qrot + dt * dqrot, prot + dt * dprot
            x = [list(row) for row in zip(*coefficients)]
            if item["flags"] & 4:
                phase = peri + dt * dperi
                phase -= int(phase / math.tau) * math.tau
                c, s = math.cos(phase), math.sin(phase)
                rx, ry = item["reference"][:ncoef], item["reference"][ncoef:]
                for k in range(ncoef):
                    x[k][0] = coefficients[0][k] + c * rx[k] - s * ry[k]
                    x[k][1] = coefficients[1][k] + c * ry[k] + s * rx[k]
            f = 1 / (1 + q * q + p * p)
            ux = ((1 + q * q - p * p) * f, 2 * q * p * f, -2 * p * f)
            uy = (2 * q * p * f, (1 - q * q + p * p) * f, 2 * q * f)
            uz = (2 * p * f, -2 * q * f, (1 - q * q - p * p) * f)
            rows = []
            last = None
            for k, (a, b, c) in enumerate(x):
                xr, yr, zr = [a * ux[j] + b * uy[j] + c * uz[j] for j in range(3)]
                if abs(xr) + abs(yr) + abs(zr) >= 1e-14:
                    last = k
                if body == 1:
                    yr, zr = (
                        0.91748206215761929 * yr - 0.39777715572793088 * zr,
                        0.39777715572793088 * yr + 0.91748206215761929 * zr,
                    )
                rows.append((xr, yr, zr))
            rotated = list(map(list, zip(*rows)))
            if last is None:
                raise ValueError(
                    "No significant coefficient; native stale-count behavior unqualified"
                )
        return {
            "body": body,
            "file": self.identity,
            "flags": item["flags"],
            "ncoef": ncoef,
            "segment_index": index,
            "segment_start": segment_start,
            "span": span,
            "byte_offset": location,
            "packed_sizes": packing,
            "decoded_coefficients": coefficients,
            "rotated_coefficients": rotated,
            "last_significant_index": last,
        }


def evaluate(segment, epoch, profile):
    if profile not in PROFILES:
        raise ValueError("Unplanned coefficient-retention profile")
    count = segment["ncoef"]
    if segment["flags"] & 2 and profile != "all_coefficients":
        count = segment["last_significant_index"] + int(profile == "index_plus_one")
    t = 2 * ((epoch - segment["segment_start"]) / segment["span"]) - 1
    basis, derivatives = [1.0, t], [0.0, 1.0]
    for k in range(2, segment["ncoef"]):
        derivatives.append(2 * basis[-1] + 2 * t * derivatives[-1] - derivatives[-2])
        basis.append(2 * t * basis[-1] - basis[-2])
    position = []
    velocity = []
    for coefficients in segment["rotated_coefficients"]:
        position.append(
            math.fsum(
                c * (b / 2 if k == 0 else b)
                for k, (c, b) in enumerate(zip(coefficients[:count], basis))
            )
        )
        velocity.append(
            math.fsum(c * d for c, d in zip(coefficients[:count], derivatives))
            * 2
            / segment["span"]
        )
    return position + velocity


def geometric(planet_file, moon_file, epoch, body, profile):
    moon_segment = moon_file.segment(epoch, 1)
    moon = evaluate(moon_segment, epoch, profile)
    if body == "Moon":
        return moon, [moon_segment]
    emb_segment = planet_file.segment(epoch, 0)
    sun_segment = planet_file.segment(epoch, 10)
    target_segment = planet_file.segment(epoch, {"Mercury": 2, "Venus": 3}[body])
    emb = evaluate(emb_segment, epoch, profile)
    solar = evaluate(sun_segment, epoch, profile)
    sun = [a - b for a, b in zip(emb, solar)] if sun_segment["flags"] & 8 else solar
    earth = [e - m / ((1 / 0.0123000383) + 1) for e, m in zip(emb, moon)]
    target = evaluate(target_segment, epoch, profile)
    if target_segment["flags"] & 1:
        target = [x + y for x, y in zip(target, sun)]
    return [x - y for x, y in zip(target, earth)], [
        moon_segment,
        emb_segment,
        sun_segment,
        target_segment,
    ]
