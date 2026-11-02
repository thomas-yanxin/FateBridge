"""Keep measured cloud amount distinct from a rainfall-only sky-state proxy.

This descriptive data audit neither labels ancient 晴 nor supplies prior weather
to a cast. Monthly retrospective files do not establish historical availability.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .meihua_weather_study import RainObservation

_TITLE = "Daily Mean Amount of Cloud (%) at the Hong Kong Observatory"
_HEADER = [
    "年/Year",
    "月/Month",
    "日/Day",
    "數值/Value",
    "數據完整性/data Completeness",
]


@dataclass(frozen=True)
class CloudObservation:
    day: date
    raw_value: str
    completeness: str
    status: str
    cloud_percent: Decimal | None = None

    def complete_percent(self) -> Decimal | None:
        if self.status != "complete_numeric":
            return None
        amount = self.cloud_percent
        if (
            self.completeness != "C"
            or amount is None
            or not amount.is_finite()
            or not 0 <= amount <= 100
        ):
            raise ValueError("Complete cloud amount requires a finite0..100 C value")
        return amount


def parse_hko_cloud(
    raw: bytes, *, start: date, end: date
) -> dict[date, CloudObservation]:
    """Read the declared station/percentage dataset, keeping unknowns explicit."""
    if start >= end:
        raise ValueError("Cloud observation period must be ordered")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if len(rows) < 4 or rows[1] != [_TITLE] or rows[2] != _HEADER:
        raise ValueError("Not the declared HKO station cloud percentage dataset")
    observations = {}
    for row in rows[3:]:
        if not row or not any(s.strip() for s in row):
            continue
        if not re.fullmatch(r"\d{4}", row[0].strip()):
            if len(row) == 1 and any(
                phrase in row[0].casefold()
                for phrase in ["unavailable", "data incomplete", "data complete"]
            ):
                continue
            raise ValueError("Unrecognized cloud source row")
        year = int(row[0])
        if not start.year <= year <= end.year:
            continue
        if len(row) != 5:
            raise ValueError("Incomplete cloud source row")
        day = date(year, int(row[1]), int(row[2]))
        if not start <= day < end:
            continue
        if day in observations:
            raise ValueError("Duplicate cloud dates cannot be selected by value")
        value, flag = row[3].strip(), row[4].strip()
        if flag not in {"C", "#"}:
            raise ValueError("Undocumented cloud data completeness flag")
        amount = None
        if value == "***":
            status = "unavailable"
        else:
            try:
                amount = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError("Invalid cloud percentage") from exc
            if not amount.is_finite() or not 0 <= amount <= 100:
                raise ValueError("Cloud percentage must be finite and in0..100")
            status = "complete_numeric" if flag == "C" else "incomplete"
        observations[day] = CloudObservation(day, value, flag, status, amount)
    return observations


def audit_rainfall_cloud_mapping(
    cohort: list[str],
    rainfall: dict[date, RainObservation],
    clouds: dict[date, CloudObservation],
    *,
    rain_threshold_mm: Decimal = Decimal("0.1"),
) -> dict[str, Any]:
    """Describe all locked days, without producing a sunny label or skill score."""
    days = [date.fromisoformat(s) for s in cohort]
    if not days or [d.isoformat() for d in days] != cohort or days != sorted(set(days)):
        raise ValueError("Mapping cohort must retain unique ordered ISO civil dates")
    if not rain_threshold_mm.is_finite() or rain_threshold_mm <= 0:
        raise ValueError("Rain threshold must be finite and positive")
    paired = dry = coincident = reported100 = 0
    cloud_values: Counter[str] = Counter()
    below_threshold_cloud_values: Counter[str] = Counter()
    records = []
    for day in days:
        rain, cloud = rainfall.get(day), clouds.get(day)
        if (rain and rain.day != day) or (cloud and cloud.day != day):
            raise ValueError("Observation day differs from its cohort key")
        occurred = rain.occurred(rain_threshold_mm) if rain else None
        percent = cloud.complete_percent() if cloud else None
        complete = occurred is not None and percent is not None
        # 100 is a reported measurement, not a fitted sky-state threshold.
        dry_and_100 = complete and occurred is False and percent == 100
        reported100 += percent == 100
        if percent is not None:
            cloud_values[str(percent)] += 1
            if occurred is False:
                below_threshold_cloud_values[str(percent)] += 1
        paired += complete
        dry += complete and occurred is False
        coincident += dry_and_100
        records.append(
            {
                "date": day.isoformat(),
                "rainfall_status": rain.status if rain else "absent",
                "rainfall_raw_value": rain.raw_value if rain else None,
                "rainfall_completeness": rain.completeness if rain else None,
                "rain_at_threshold": occurred,
                "cloud_status": cloud.status if cloud else "absent",
                "cloud_raw_value": cloud.raw_value if cloud else None,
                "cloud_completeness": cloud.completeness if cloud else None,
                "complete_cloud_percent": str(percent) if percent is not None else None,
                "paired_complete": complete,
                "below_rain_threshold_and_reported100percent_cloud": dry_and_100,
            }
        )
    return {
        "kind": "descriptive_observation_mapping_diagnostic",
        "cohort_days": len(days),
        "paired_complete_days": paired,
        "days_with_unknown_rain_or_cloud": len(days) - paired,
        "below_rain_threshold_paired_days": dry,
        "below_rain_threshold_and_reported100percent_cloud_days": coincident,
        "reported100percent_cloud_days_including_unknown_rain": reported100,
        "complete_cloud_percent_histogram": dict(sorted(cloud_values.items())),
        "below_rain_threshold_cloud_percent_histogram": dict(
            sorted(below_threshold_cloud_values.items())
        ),
        "rain_threshold_mm": str(rain_threshold_mm),
        "reported_cloud_percent_probe": "100",
        "station": "Hong Kong Observatory",
        "daily_means_do_not_locate_clear_or_rainy_dayparts": True,
        "ancient_clear_sky_equivalence_adjudicated": False,
        "sunny_labels_generated": 0,
        "prior_condition_inputs_generated": 0,
        "historical_as_of_availability_established": False,
        "forecast_skill_evaluated": False,
        "prediction_efficacy_established": False,
        "records": records,
    }
