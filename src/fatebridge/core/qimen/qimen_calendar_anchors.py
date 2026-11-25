"""The three source-validated civil anchors consumed by a Zhirun schedule."""

from __future__ import annotations

from fatebridge.core.almanac import (
    SolarTerm,
    _solar_term_source_year,
    _solar_terms_for_context_year,
)
from fatebridge.utils.errors import ParameterError


def zhirun_calendar_anchors(year: int, timezone_name: str) -> tuple[SolarTerm, ...]:
    """Keep each neighbor's own model, except its declared boundary allowance."""
    anchors = tuple(
        term
        for source_year, index in ((year - 1, 22), (year, 10), (year, 22))
        for term in _solar_terms_for_context_year(
            source_year,
            timezone_name,
            _solar_term_source_year(source_year, year),
            term_index=index,
        )
    )
    for term in anchors:
        if not term.has_defined_local_clock:
            raise ParameterError(
                f"unresolved local time：时区规则未定义奇门置闰锚点{term.name}的当地日序。",
                [{"path": "request", "code": "unresolved_timezone_offset"}],
            )
    return anchors
