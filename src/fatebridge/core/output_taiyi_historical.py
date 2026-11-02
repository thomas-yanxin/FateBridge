"""Projection-safe provenance for selected historical calendar observations."""

from typing import Optional

from .output_base import PartialOutput


class TaiyiHistoricalReference(PartialOutput):
    case_id: Optional[str] = None
    source_date: Optional[str] = None
    western_source_date: Optional[str] = None
    western_source_calendar: Optional[str] = None
    normalized_gregorian_date: Optional[str] = None
    calendar_table_title: Optional[str] = None
    calendar_table_authors: Optional[str] = None
    calendar_table_edition: Optional[str] = None
    calendar_table_source: Optional[str] = None
    calendar_table_printed_page: Optional[int] = None
    source_day_ganzhi: Optional[str] = None
    actual_day_ganzhi: Optional[str] = None
    day_ganzhi_matches: Optional[bool] = None
    source_accumulation: Optional[int] = None
    actual_accumulation: Optional[int] = None
    counter_matches: Optional[bool] = None
    source_hour_branch: Optional[str] = None
    actual_hour_branch: Optional[str] = None
    hour_branch_matches: Optional[bool] = None
    scope: Optional[str] = None
