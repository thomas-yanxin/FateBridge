"""Explicit UTC transition seconds and the POSIX footer of loaded TZif data."""

import re
import struct
from bisect import bisect_right
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone

from fatebridge.utils.civil_time import UTCCalendar, gregorian_ordinal, utc_calendar

EPOCH = utc_calendar(datetime(1970, 1, 1, tzinfo=timezone.utc))
DAY_SECONDS = 86_400
_SECOND_MICROSECONDS = 1_000_000
NAME = rb"(?:[A-Za-z]{3,}|<[A-Za-z0-9+-]{3,}>)"
MINUTE_SECOND = rb"(?::[0-5][0-9](?::[0-5][0-9])?)?"
OFFSET = rb"[+-]?[0-9]{1,2}" + MINUTE_SECOND
# The locked month rules and their signed clock shifts stay in their rule
# year. Keep January and December rules on the loaded-clock fallback.
MONTH_RULE = (
    rb"M(?:[2-9]|10|11)\.[1-5]\.[0-6]"
    rb"(?:/[+-]?(?:[0-9]{1,2}|1[0-5][0-9]|16[0-7])" + MINUTE_SECOND + rb")?"
)
FOOTER = re.compile(
    rb"\n" + NAME + rb"(?P<standard>" + OFFSET + rb")"
    rb"(?:" + NAME + rb"(?P<daylight>" + OFFSET + rb")?,"
    rb"(?P<start>" + MONTH_RULE + rb"),(?P<end>" + MONTH_RULE + rb"))?\n"
)


def _signed_seconds(text: bytes) -> int:
    parts = text.lstrip(b"+-").split(b":")
    magnitude = sum(int(part) * scale for part, scale in zip(parts, (3600, 60, 1)))
    return -magnitude if text.startswith(b"-") else magnitude


@dataclass(frozen=True)
class _MonthRule:
    month: int
    week: int
    weekday: int
    utc_shift: int

    @classmethod
    def parse(cls, rule: bytes, offset_before: int) -> "_MonthRule":
        label, _, clock = rule.partition(b"/")
        month, week, weekday = map(int, label[1:].split(b"."))
        # POSIX defaults to 02:00 on the wall clock before the transition.
        local_seconds = _signed_seconds(clock) if clock else 7200
        return cls(month, week, weekday, local_seconds - offset_before)

    def utc_second(self, year: int) -> int:
        first_weekday, length = monthrange(year, self.month)
        # POSIX numbers Sunday as zero. Week five means the last occurrence.
        day = 1 + (self.weekday - first_weekday - 1) % 7 + (self.week - 1) * 7
        if day > length:
            day -= 7
        ordinal = gregorian_ordinal(year, self.month, day)
        return (ordinal - EPOCH.ordinal) * DAY_SECONDS + self.utc_shift


@dataclass(frozen=True)
class TZifTransitions:
    seconds: tuple[int, ...]
    fixed_tail: bool
    recurring: tuple[_MonthRule, _MonthRule] | None = None

    def between(
        self, lower: UTCCalendar, upper: UTCCalendar
    ) -> tuple[UTCCalendar, ...] | None:
        """Return UTC candidates in (lower, upper] when the index covers it."""
        first = (lower.ordinal - EPOCH.ordinal) * DAY_SECONDS + (
            lower.microseconds_of_day // _SECOND_MICROSECONDS
        )
        last = (upper.ordinal - EPOCH.ordinal) * DAY_SECONDS + (
            upper.microseconds_of_day // _SECOND_MICROSECONDS
        )
        last_microsecond = upper.microseconds_of_day % _SECOND_MICROSECONDS
        beyond = not self.seconds or (last, last_microsecond) > (self.seconds[-1], 0)
        if beyond and not self.fixed_tail and self.recurring is None:
            return None
        left, right = bisect_right(self.seconds, first), bisect_right(
            self.seconds, last
        )
        seconds = self.seconds[left:right]
        if beyond and (rules := self.recurring) is not None:
            floor = max(first, self.seconds[-1]) if self.seconds else first
            origin_year, _, _ = UTCCalendar(
                EPOCH.ordinal + floor // DAY_SECONDS, 0
            ).date_parts
            last_year, _, _ = upper.date_parts
            seconds += tuple(
                second
                for year in range(origin_year, last_year + 1)
                for second in sorted(rule.utc_second(year) for rule in rules)
                if floor < second <= last
            )
        return tuple(
            UTCCalendar(
                EPOCH.ordinal + second // DAY_SECONDS,
                second % DAY_SECONDS * _SECOND_MICROSECONDS,
            )
            for second in seconds
        )


def read_tzif_transitions(data: bytes) -> TZifTransitions | None:
    """Index explicit and supported footer candidates from loaded TZif bytes.

    RFC 9636 sections 3.1–3.2 specify the headers and signed arrays.
    Section 3.3 extends the final table with a POSIX TZ string. Read actual
    offsets and designations from ZoneInfo.
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
        footer = FOOTER.fullmatch(data[end:]) if size == 8 else None
        if footer is None:
            return TZifTransitions(values, False)
        if (start := footer["start"]) is None:
            return TZifTransitions(values, True)
        # POSIX offset signs map local time to UTC. End rules use the
        # daylight offset even in places where that offset is smaller.
        standard = -_signed_seconds(footer["standard"])
        daylight = (
            -_signed_seconds(offset)
            if (offset := footer["daylight"]) is not None
            else standard + 3600
        )
        return TZifTransitions(
            values,
            False,
            (
                _MonthRule.parse(start, standard),
                _MonthRule.parse(footer["end"], daylight),
            ),
        )
    except (ValueError, struct.error):
        return None
