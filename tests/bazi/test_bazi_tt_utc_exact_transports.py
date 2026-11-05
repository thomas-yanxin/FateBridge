"""Actual calendar and timing clocks carry the same exact frozen-policy inversion."""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

import pytest

from fatebridge.core.astro.time_scales import leap_table
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import AS_OF, business, inputs
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls


def check_terms(value):
    """Find consumed selected roots, not a second ephemeris calculation."""
    found = 0
    if isinstance(value, dict):
        details = value.get("solar_model_details", {})
        jd = details.get("selected_crossing_jd_tt")
        parts = details.get("selected_crossing_tt_parts")
        civil = value.get("datetime_with_offset")
        if jd is not None and civil is not None:
            moment = datetime.fromisoformat(civil)
            with localcontext() as ctx:
                ctx.prec = 80
                # This test's selected inputs lie safely inside atomic-policy
                # intervals; the complete independent oracle covers transitions.
                entry = next(
                    e
                    for e in reversed(leap_table()["entries"])
                    if moment.date().isoformat() >= e["effective_date"]
                )
                offset = Decimal(entry["tai_minus_utc_seconds"]) + Decimal("32.184")
                # The selected epoch now has two components. The scalar is
                # explicitly a rounded display, not the calculation's input.
                # Keep the original exact-microsecond oracle and denominator.
                point = (
                    sum((Decimal.from_float(p) for p in parts), Decimal(0))
                    if parts is not None
                    else Decimal.from_float(jd)
                )
                expected_us = int(
                    (
                        ((point - Decimal("2440587.5")) * 86400 - offset) * 1_000_000
                    ).to_integral_value(rounding=ROUND_HALF_EVEN)
                )
            from datetime import timezone

            elapsed = moment.astimezone(timezone.utc) - datetime(
                1970, 1, 1, tzinfo=timezone.utc
            )
            actual_us = (
                elapsed.days * 86_400_000_000
                + elapsed.seconds * 1_000_000
                + elapsed.microseconds
            )
            assert actual_us == expected_us
            found += 1
        for child in value.values():
            found += check_terms(child)
    elif isinstance(value, list):
        for child in value:
            found += check_terms(child)
    return found


rest = _shared_rest


@pytest.mark.parametrize("key", ["bazi_birth", "timing_analysis", "dayun_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_same_correctly_converted_consumed_tt_roots_on_three_public_surfaces(
    key, project, surface_calls
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
    opts = {"response_char_limit": 0, "include_snapshot_text": False}
    flags = ["--response-char-limit", "0", "--include-snapshot-text", "false"]
    if project:
        field = (
            "bazi_birth.calendar_context" if key == "bazi_birth" else "calendar_context"
        )
        opts.update(fields=[field], strict_fields=True)
        flags += ["--fields", field, "--strict-fields", "true"]
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"as_of": AS_OF, **opts},
        options=opts,
        flags=flags,
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0, http.text
    outputs = [http.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    assert check_terms(outputs[0]) > 0
