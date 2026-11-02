"""Shoushi nominal book-year versus preceding winter-year labels.

The Xin-si 1281 reference labels a calendar whose Tianzheng winter is in
Geng-chen 1280. This ordinal bridge supplies neither a Gregorian date nor
an astronomical epoch, civil timezone, midnight convention or UTC instant.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_historical import shoushi_winter_cycle

DATA = Path(__file__).resolve().parents[1] / "data/guolao/shoushi-year-labels-v1.json"
REFERENCE_YEAR = 1281


def _integer_year(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("原历标年须为明确整数，不接收浮点、布尔、日期或隐式距算")


def _ganzhi_label(year: int) -> str:
    return STEMS[(year - 4) % 10] + BRANCHES[(year - 4) % 12]


def shoushi_year_context(
    *, source_year: int | None = None, winter_year: int | None = None
) -> dict[str, Any]:
    """Require one explicit nominal year kind, with no guessed present year.

    CE numbers identify the named source's historical year labels only. They
    do not establish Jan 1, LiChun, lunar New Year or a civil-date interval.
    The shared lower-reckoning arithmetic still rejects upward reckoning.
    """
    if (source_year is None) == (winter_year is None):
        raise ValueError("须且只能明确选择历书标年source_year或岁前冬至年winter_year")
    if source_year is not None:
        _integer_year(source_year)
        nominal_year = source_year
        input_kind = "source_calendar_nominal_year_label"
    else:
        assert winter_year is not None
        _integer_year(winter_year)
        nominal_year = winter_year + 1
        input_kind = "preceding_winter_nominal_year_label"
    cycle = shoushi_winter_cycle(nominal_year - REFERENCE_YEAR)
    blob = DATA.read_bytes()
    source = json.loads(blob)
    if (
        source["reference_nominal_year_ce"] != REFERENCE_YEAR
        or source["reference_winter_year_ce"] != REFERENCE_YEAR - 1
    ):
        raise ValueError("具名历元资料与1281年标年规则不一致，不能改元以凑合算例")
    return {
        "model_id": source["model_id"],
        "source_data_sha256": hashlib.sha256(blob).hexdigest(),
        "sources": source["sources"],
        "input_kind": input_kind,
        "source_year_label_ce": nominal_year,
        "source_year_sexagenary_label": _ganzhi_label(nominal_year),
        "preceding_winter_year_label_ce": nominal_year - 1,
        "preceding_winter_year_sexagenary_label": _ganzhi_label(nominal_year - 1),
        "reference_nominal_year_ce": REFERENCE_YEAR,
        "reference_winter_year_ce": REFERENCE_YEAR - 1,
        "elapsed_years": cycle.elapsed_years,
        "inclusive_count_from_reference": cycle.elapsed_years + 1,
        "effective_year_days_exact": str(cycle.effective_year_days),
        "zhongji_days_exact": str(cycle.zhongji_days),
        "winter_cycle_days_exact": str(cycle.winter_cycle_days),
        "winter_sexagenary_day": cycle.winter_sexagenary_day,
        "winter_fraction_of_day_exact": str(cycle.winter_fraction_of_day),
        "year_boundary_policy": "named_book_year_label_only_no_modern_calendar_boundary",
        "modern_calendar_date_assigned": False,
        "modern_epoch_calibrated": False,
        "physical_julian_day": None,
        "timezone": None,
        "gujin58_header_variants_resolved": False,
        "used_in_native_birth_chart": False,
    }
