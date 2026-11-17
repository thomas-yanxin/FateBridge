"""Controlled event sequences for consumer clock and interval tests."""

from fatebridge.core.astro.solar_events import SolarEvent


def solar_event(ut1, *, rising, model="swieph"):
    return SolarEvent(
        ut1,
        ut1 + 70 / 86400,
        model,
        4 if model == "moshier" else 2,
        "hindu_geometric_center",
        (ut1, ut1),
        0,
        0,
        1,
        rising,
    )


def fixed_crossings(rises, sets):
    events = sorted(
        [solar_event(t, rising=True) for t in rises]
        + [solar_event(t, rising=False) for t in sets],
        key=lambda event: event.julian_day_ut1,
    )

    def crossings(start, end, **kwargs):
        return [event for event in events if start <= event.julian_day_ut1 <= end]

    return crossings
