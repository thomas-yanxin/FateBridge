"""Explicit TZif transition instants, without extrapolating footer rules."""

import struct


def explicit_transition_seconds(data: bytes) -> tuple[int, ...] | None:
    """Read the complete explicit section, or decline this optimization.

    RFC9636 sections3.1–3.2 specify the two headers and signed transition
    arrays. Version2+ must use its64-bit section. Leap-bearing files and
    unknown versions remain on the existing loaded-clock scan path.
    Offsets are deliberately obtained from the actual ZoneInfo object later.
    """
    if (
        len(data) < 44
        or data[:4] != b"TZif"
        or data[4:5] not in {b"\0", b"2", b"3", b"4"}
    ):
        return None

    def header(at: int) -> tuple[int, ...]:
        if data[at : at + 4] != b"TZif" or len(data) < at + 44:
            raise ValueError("Incomplete TZif header")
        counts = struct.unpack_from(">6I", data, at + 20)
        if counts[2] or not counts[4] or counts[4] > 256:
            raise ValueError("Unsupported TZif counts")
        return counts

    try:
        counts = header(0)
        at, size, code = 44, 4, "l"
        if data[4:5] != b"\0":
            isut, isstd, leaps, times, types, chars = counts
            at += times * 5 + types * 6 + chars + leaps * 8 + isstd + isut
            counts = header(at)
            at, size, code = at + 44, 8, "q"
        isut, isstd, leaps, times, types, chars = counts
        end = at + times * (size + 1) + types * 6 + chars + isstd + isut
        if end > len(data):
            return None
        values = struct.unpack_from(f">{times}{code}", data, at)
        if any(a >= b for a, b in zip(values, values[1:])):
            return None
        return values
    except (ValueError, struct.error):
        return None
