"""Annual Zi Bai overlay, never a house natal chart."""

from typing import Any, Dict

from .calendar import year_context
from .directions import rule_data, wrap9
from .models import AnnualRequest


def annual_stars(req: AnnualRequest) -> Dict[str, Any]:
    time = year_context(req.effective_year, req.query_at, req.timezone_name)
    year = time["effective_year"]
    if time.get("effective_year_status") == "requires_confirmation":
        return {
            "status": "partial",
            "time_context": time,
            "palaces": {},
            "missing_inputs": [
                "annual_stars.confirmed_effective_year_due_to_boundary_precision"
            ],
        }
    if year is None:
        return {
            "status": "partial",
            "time_context": time,
            "palaces": {},
            "missing_inputs": ["annual_stars.query_at_or_effective_year"],
        }
    center = wrap9(1 - (year - 1864))
    directions = rule_data("directions")
    stars = rule_data("annual_stars")
    palaces = {}
    for index, direction in enumerate(rule_data("flight_path")):
        number = wrap9(center + index)
        palaces[direction] = {
            **directions.get(
                direction,
                {
                    "direction": "C",
                    "label": "中",
                    "palace_number": 5,
                    "trigram": None,
                    "element": "土",
                },
            ),
            "annual_star_number": number,
            "annual_star": stars[str(number)],
            "method": "annual_stars",
            "rule_id": "annual_zibai_lichun_v1.forward_flight",
            "source_ids": ["S4", "S6"],
        }
    period_index = (year - 1864) // 20
    period_start = 1864 + period_index * 20
    return {
        "status": "complete",
        "effective_year": year,
        "time_context": time,
        "center_star_number": center,
        "palaces": palaces,
        "flight_path": rule_data("flight_path"),
        "current_period": {
            "number": period_index % 9 + 1,
            "start_year": period_start,
            "end_year": period_start + 19,
            "basis": "current_calendar_period_not_house_period",
            "rule_id": "annual_zibai_lichun_v1.twenty_year_period",
            "source_ids": ["S4"],
        },
        "missing_inputs": [],
        "trace": {
            "epoch_year": 1864,
            "year_center_direction": "descending",
            "within_year_flight": "ascending",
        },
        "interpretation_scope": "annual_star_positions_only_no_house_verdict",
    }
