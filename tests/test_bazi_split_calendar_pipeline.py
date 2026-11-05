"""Actual default solar/timing consumers must use their two-part TT epoch."""

import asyncio
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.astro.time_scales import (
    datetime_from_tt_point,
    ephemeris_time,
    leap_table,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.services.tool_catalog import CATALOG
from tests.test_agentic_nested_outputs import (
    AS_OF,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest


def check_actual_parts(value):
    found = 0
    if isinstance(value, dict):
        details = value.get("solar_model_details", {})
        parts = details.get("selected_crossing_tt_parts")
        text = value.get("datetime_with_offset")
        if parts is not None and text is not None:
            assert details["numerical_epoch_representation"] == "explicit_two_part_tt"
            assert details["scalar_jd_scope"] == "rounded_display_of_selected_tt_parts"
            exact = sum((Fraction(v) for v in parts), Fraction(0))
            assert float(exact) == details["selected_crossing_jd_tt"]
            moment = datetime.fromisoformat(text).astimezone(timezone.utc)
            assert moment.year >= 1972  # chosen transport controls only
            entry = next(
                e
                for e in reversed(leap_table()["entries"])
                if moment.date().isoformat() >= e["effective_date"]
            )
            with localcontext() as context:
                context.prec = 80
                point = sum((Decimal.from_float(v) for v in parts), Decimal(0))
                expected = int(
                    (
                        (
                            (point - Decimal("2440587.5")) * 86400
                            - Decimal(entry["tai_minus_utc_seconds"])
                            - Decimal("32.184")
                        )
                        * 1_000_000
                    ).to_integral_value(rounding=ROUND_HALF_EVEN)
                )
            elapsed = moment - datetime(1970, 1, 1, tzinfo=timezone.utc)
            assert (
                expected
                == elapsed.days * 86_400_000_000
                + elapsed.seconds * 1_000_000
                + elapsed.microseconds
            )
            low, high = (
                sum((Fraction(v) for v in p), Fraction(0))
                for p in details["root_bracket_tt_parts"]
            )
            assert low <= exact <= high
            assert details["numerical_resolution_is_physical_accuracy"] is False
            found += 1
        for child in value.values():
            found += check_actual_parts(child)
    elif isinstance(value, list):
        for child in value:
            found += check_actual_parts(child)
    return found


rest = _shared_rest


@pytest.mark.parametrize("key", ["bazi_birth", "timing_analysis", "dayun_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_parts_and_same_business_result_on_rest_mcp_cli(
    key, project, rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        **inputs(spec),
        "birth_year": 2001,
        "birth_month": 6,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_second": 21,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
    }
    opts = dict(include_snapshot_text=False, response_char_limit=0)
    flags = [
        "--as-of",
        AS_OF,
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    if project:
        field = (
            "bazi_birth.calendar_context" if key == "bazi_birth" else "calendar_context"
        )
        opts.update(fields=[field], strict_fields=True)
        flags += [
            "--fields",
            field,
            "--strict-fields",
            "true",
        ]
    http = rest.post(spec.rest_path, json=payload, params={"as_of": AS_OF, **opts})
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags)
    assert http.status_code == 200 and not mcp.is_error and code == 0, http.text
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    assert check_actual_parts(http.json()) > 0


@pytest.mark.parametrize(
    "year", [1800, 1899, 1959, 1960, 1961, 1968, 1971, 1972, 2000, 2101, 2200]
)
def test_default_calendar_keeps_all24terms_across_each_clock_regime(year):
    terms = get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term in terms:
        details = term.solar_model_details
        assert details is not None
        point = TTInstant.from_parts(*details["selected_crossing_tt_parts"])
        assert datetime_from_tt_point(point) == term.moment
        assert (
            abs(ephemeris_time(term.moment).jd_tt - point.as_float()) * 86400 <= 0.0002
        )
