"""Historical and modern charts publish the actual rotation TT argument policy."""

import asyncio
import json

import pytest

from fatebridge.core import astro_models as rotation
from fatebridge.core.astro import runtime
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize("year", [1800, 2024])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_historical_clock_policy_reaches_actual_rest_mcp_cli(
    year, zodiacal, rest, monkeypatch, tmp_path, capsys
):
    actual = rotation.iers2010_gast
    arguments = []

    def observed(ut1, tt, *args):
        arguments.append((ut1, tt))
        return actual(ut1, tt, *args)

    monkeypatch.setattr(rotation, "iers2010_gast", observed)
    spec = SPECS["astro_chart"]
    inputs = dict(
        birth_year=year,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=False,
        zodiacal=zodiacal,
    )
    fields = [
        "chart_profile.earth_rotation",
        "chart_profile.julian_day_tt",
        "chart_profile.julian_day_ut1",
    ]
    params = [("fields", p) for p in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http = rest.post(spec.rest_path, json=inputs, params=params)
    assert http.status_code == 200, http.text
    code, cli = call_cli(
        spec,
        inputs,
        tmp_path,
        capsys,
        [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert code == 0 and not protocol.is_error
    for value in [http.json(), cli, json.loads(protocol.content[0].text)]:
        spec.output_model.model_validate(value)
        profile = value["chart_profile"]
        policy = profile["earth_rotation"]
        assert policy["policy_id"] == "fatebridge_standard_rotation_v3"
        if year == 1800:
            assert policy["tt_argument_policy"] == (
                "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
            )
            assert any(
                abs(u - profile["julian_day_ut1"]) * 86400 <= 0.0002
                and abs(t - profile["julian_day_tt"]) * 86400 <= 0.0002
                for u, t in arguments
            )
        else:
            assert (
                policy["tt_argument_policy"] == "native_internal_sidereal_time_argument"
            )
    if year == 1800:
        assert arguments
        for ut1, tt in arguments:
            expected = ut1 + runtime.swe.deltat_ex(ut1, -1)
            assert abs(expected - tt) * 86400 <= 0.0002
