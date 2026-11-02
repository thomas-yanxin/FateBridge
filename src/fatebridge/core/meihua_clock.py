"""Meihua civil-clock evidence uses the shared, verified instant resolver."""

from datetime import datetime
from typing import Any

from fatebridge.core.meihua_clock_input import clock_input_receipt
from fatebridge.core.meihua_clock_resolution import (
    resolve_meihua_civil_clock as resolve_civil_clock,
)
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    utc_instant,
)
from fatebridge.utils.timezones import timezone_rules_metadata


def resolve_meihua_clock(
    wall: datetime,
    timezone_name: str,
    explicit_offset: str | None,
    *,
    seconds_supplied: bool = False,
    minute_supplied: bool = True,
    component_provenance: str = "direct_datetime_components",
) -> tuple[datetime, dict[str, Any]]:
    """An offset selects a valid named-zone instant; it never creates a clock."""
    resolved = resolve_civil_clock(wall, timezone_name, explicit_offset)
    offset = resolved.utcoffset()
    assert offset is not None
    evidence: dict[str, Any] = {
        "ruleset_id": "meihua_civil_clock_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "method": (
            "explicit_offset_verified_against_timezone"
            if explicit_offset is not None
            else "unambiguous_timezone_clock"
        ),
        "timezone": timezone_name,
        "input_utc_offset": explicit_offset,
        "resolved_utc_offset": format_utc_offset(offset),
        "local_datetime": resolved.isoformat(),
        "instant_utc": utc_instant(resolved).isoformat(),
        "fold": resolved.fold,
        "timezone_rules": timezone_rules_metadata(timezone_name),
        "calendar_zone_replaced_by_offset": False,
        "clock_label_precision": (
            "supplied_civil_second; historical_offset_seconds_preserved"
            if seconds_supplied and minute_supplied
            else (
                "supplied_civil_minute; historical_offset_seconds_preserved"
                if minute_supplied
                else (
                    "hour_and_second_supplied; minute_00_calculation_default; historical_offset_seconds_preserved"
                    if seconds_supplied
                    else "supplied_civil_hour; minute_and_second_00_calculation_defaults; historical_offset_seconds_preserved"
                )
            )
        ),
        **(
            {
                "input_second": {
                    "ruleset_id": "meihua_civil_second_input_v1",
                    "version": "1.0.0",
                    "rule_kind": "software_convention",
                    "value": wall.second,
                    "seconds_enter_cast_seed": False,
                    "input_precision_certifies_accuracy": False,
                    "original_text_uniquely_prescribes_seconds": False,
                }
            }
            if seconds_supplied
            else {}
        ),
        "original_text_uniquely_prescribes_IANA_or_fold": False,
    }
    supplied = ["year", "month", "day", "hour"]
    if minute_supplied:
        supplied.append("minute")
    if seconds_supplied:
        supplied.append("second")
    evidence["input_components"] = clock_input_receipt(
        resolved, evidence["instant_utc"], supplied, component_provenance
    )
    return resolved, evidence
