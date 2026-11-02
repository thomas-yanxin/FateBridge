"""Independent JPL regression values; never call FateBridge's solar formula."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def expected_solar_clock(civil: datetime, zone: str, longitude: float) -> datetime:
    fixture = json.loads(
        (Path(__file__).parent / "bazi-solar-regression-jpl-v1.json").read_text()
    )
    instant = civil.replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    case = next(row for row in fixture["rows"] if row["instant"] == instant.isoformat())
    return instant.replace(tzinfo=None) + timedelta(
        minutes=4 * longitude + case["equation_of_time_minutes"]
    )
