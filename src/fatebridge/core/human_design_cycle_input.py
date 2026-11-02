"""Isolate native time ordering during Human Design request validation."""

from typing import Any

from fatebridge.core.astro import native_execution
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design_birth_clock import resolve_birth_clock
from fatebridge.core.human_design_reference_order import reference_ordering

ENTRY = "fatebridge.core.human_design_cycle_input.validate_cycle_reference"


def validate_cycle_reference(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_timezone: str,
    cycle_reference_datetime: str,
    birth_second: int = 0,
) -> None:
    """Compare source-defined continuous TT; never use caller native settings.

    Request validation has its own short-lived process. The full calculation
    subsequently checks the reference again in its existing operation worker.
    Neither input acceptance nor this boundary authenticates a civil clock.
    """
    arguments: dict[str, Any] = dict(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        birth_timezone=birth_timezone,
    )
    active = native_execution.in_native_worker()
    with source_session(restore_native_path=active):
        if not active:
            native_execution.calculate(
                ENTRY,
                (),
                {**arguments, "cycle_reference_datetime": cycle_reference_datetime},
            )
            return
        from fatebridge.core.human_design_cycles import reference_epoch

        clock = resolve_birth_clock(**arguments)
        label, reference_tt = reference_epoch(cycle_reference_datetime)
        birth_tt = (
            clock.jd_tt if clock.leap_second else ephemeris_time(clock.utc_anchor).jd_tt
        )
        if (
            birth_tt is None
            or reference_ordering(clock.utc_label, birth_tt, label, reference_tt)[
                "relation"
            ]
            == "before"
        ):
            raise ValueError("周期评估时刻不能早于出生瞬间")
