"""Independent interval and integer-RNE primitives, copied without execution.

Source: sealed R42 independent reference. No project/native imports.
"""
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_CEILING
from fractions import Fraction
import hashlib
import struct

class Uncertified(ArithmeticError):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail

def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def qtext(value):
    return str(value.numerator) + "/" + str(value.denominator)

def rational(value):
    return fmpq(value.numerator, value.denominator)

def ball(value):
    return arb(rational(value))

def endpoint(value):
    q = value.fmpq()
    return Fraction(int(q.p), int(q.q))

def bounds(value):
    if not value.is_finite():
        raise Uncertified("nonfinite Arb enclosure")
    return endpoint(value.lower()), endpoint(value.upper())

def sign(value):
    lower, upper = bounds(value)
    if lower > 0:
        return 1
    if upper < 0:
        return -1
    if lower == upper == 0:
        return 0
    raise Uncertified("interval does not certify a sign", [qtext(lower), qtext(upper)])

def decimal_bound(value, upper=False):
    with localcontext() as context:
        context.prec = 100
        context.rounding = ROUND_CEILING if upper else ROUND_FLOOR
        return str(Decimal(value.numerator) / Decimal(value.denominator))

def interval(lower, upper):
    return {"lower": qtext(lower), "upper": qtext(upper),
            "lower_decimal_outward": decimal_bound(lower),
            "upper_decimal_outward": decimal_bound(upper, True),
            "width": qtext(upper - lower)}

def encoded_rne(value):
    """Independent integer quotient/remainder encoder, including ties-even."""
    negative = value < 0
    n, d = abs(value.numerator), value.denominator
    if n == 0:
        return 0
    exponent = n.bit_length() - d.bit_length()
    if exponent >= 0:
        if n < d << exponent:
            exponent -= 1
    elif n << -exponent < d:
        exponent -= 1
    quantum = max(exponent - 52, -1074)
    if quantum >= 0:
        divisor, dividend = d << quantum, n
    else:
        divisor, dividend = d, n << -quantum
    m, remainder = divmod(dividend, divisor)
    if 2 * remainder > divisor or (2 * remainder == divisor and m & 1):
        m += 1
    if m == 0:
        encoded = 0
    elif quantum == -1074 and m < 1 << 52:
        encoded = m
    else:
        if m == 1 << 53:
            m >>= 1
            quantum += 1
        effective_exponent = quantum + 52
        if effective_exponent > 1023:
            encoded = 0x7ff0000000000000
        else:
            encoded = ((effective_exponent + 1023) << 52) | (m - (1 << 52))
    return encoded | (int(negative) << 63)

def bit_value(encoded):
    negative = encoded >> 63
    exponent = (encoded >> 52) & 0x7ff
    mantissa = encoded & ((1 << 52) - 1)
    if exponent == 0x7ff:
        raise Uncertified("nonfinite nearest binary64")
    power = -1074 if exponent == 0 else exponent - 1023 - 52
    mantissa += (1 << 52) if exponent else 0
    value = Fraction(mantissa << power) if power >= 0 else Fraction(mantissa, 1 << -power)
    return -value if negative else value

def bit_record(encoded):
    value = struct.unpack(">d", encoded.to_bytes(8, "big"))[0]
    return {"bits": f"0x{encoded:016x}", "hex": value.hex(), "value": value,
            "exact": qtext(bit_value(encoded))}

def nearest(lower, upper):
    first, last = encoded_rne(lower), encoded_rne(upper)
    if first != last:
        raise Uncertified("interval endpoints do not certify one RNE binary64",
                          {"lower_bits": f"0x{first:016x}", "upper_bits": f"0x{last:016x}"})
    return bit_record(first)

def phase_record(lower, upper):
    turn = lower // 360
    if upper // 360 != turn:
        raise Uncertified("phase wrap unresolved", interval(lower, upper))
    lower, upper = lower - 360 * turn, upper - 360 * turn
    first_house, last_house = lower // 30 + 1, upper // 30 + 1
    if first_house != last_house:
        raise Uncertified("half-open house unresolved", interval(lower, upper))
    pos_lower, pos_upper = lower / 30 + 1, upper / 30 + 1
    pos_rne = nearest(pos_lower, pos_upper)
    encoded = int(pos_rne["bits"], 16)
    # This is a separately labelled local delivery policy, never the RNE target.
    changed = bit_value(encoded) // 1 > first_house
    half_open = bit_record(encoded - 1 if changed else encoded)
    phase_rne = nearest(lower, upper)
    phase_bits = int(phase_rne["bits"], 16)
    circular_changed = bit_value(phase_bits) == 360
    return {"phase_degrees": interval(lower, upper), "phase_rne": phase_rne,
            "phase_circular_delivery": bit_record(phase_bits - 1 if circular_changed else phase_bits),
            "phase_circular_delivery_changed_rne": circular_changed,
            "house": first_house, "position": interval(pos_lower, pos_upper),
            "position_rne": pos_rne, "half_open_delivery": half_open,
            "half_open_delivery_changed_rne": changed}

def sincos(degrees):
    return arb.sin_cos_pi_fmpq(rational(degrees / 180))

def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), arb(0))
