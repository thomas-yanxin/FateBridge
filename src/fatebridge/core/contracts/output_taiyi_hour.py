"""Projection-safe record of the Key's hour-count calendar adapter."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiHourOrigin(PartialOutput):
    source: str | None = None
    winter_clock: str | None = None
    winter_anchor_utc: str | None = None
    winter_anchor_provider: str | None = None
    winter_effective_date: str | None = None
    winter_day_ganzhi: str | None = None
    origin_effective_date: str | None = None
    origin_day_ganzhi: str | None = None
    origin_clock: str | None = None
    origin_day_selection: str | None = None
    target_effective_date: str | None = None
    target_day_ganzhi: str | None = None
    day_number: int | None = None
    hour_number: int | None = None
    accumulation: int | None = None
    gate_cycle_counter: int | None = None
    day_boundary: str | None = None
    scope: str | None = None
