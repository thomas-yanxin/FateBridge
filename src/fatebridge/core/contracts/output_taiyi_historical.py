"""Projection-safe provenance for selected historical calendar observations."""

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiHistoricalReference(PartialOutput):
    case_id: str | None = None
    source_date: str | None = None
    western_source_date: str | None = None
    western_source_calendar: str | None = None
    normalized_gregorian_date: str | None = None
    calendar_table_title: str | None = None
    calendar_table_authors: str | None = None
    calendar_table_edition: str | None = None
    calendar_table_source: str | None = None
    calendar_table_printed_page: int | None = None
    source_day_ganzhi: str | None = None
    actual_day_ganzhi: str | None = None
    day_ganzhi_matches: bool | None = None
    source_accumulation: int | None = None
    actual_accumulation: int | None = None
    counter_matches: bool | None = None
    source_hour_branch: str | None = None
    actual_hour_branch: str | None = None
    hour_branch_matches: bool | None = None
    scope: str | None = None
