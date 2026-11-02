"""Projection-safe record of the Key's hour-count calendar adapter."""

from typing import Optional

from .output_base import PartialOutput


class TaiyiHourOrigin(PartialOutput):
    source: Optional[str] = None
    winter_clock: Optional[str] = None
    winter_anchor_utc: Optional[str] = None
    winter_anchor_provider: Optional[str] = None
    winter_effective_date: Optional[str] = None
    winter_day_ganzhi: Optional[str] = None
    origin_effective_date: Optional[str] = None
    origin_day_ganzhi: Optional[str] = None
    origin_clock: Optional[str] = None
    origin_day_selection: Optional[str] = None
    target_effective_date: Optional[str] = None
    target_day_ganzhi: Optional[str] = None
    day_number: Optional[int] = None
    hour_number: Optional[int] = None
    accumulation: Optional[int] = None
    gate_cycle_counter: Optional[int] = None
    day_boundary: Optional[str] = None
    scope: Optional[str] = None
