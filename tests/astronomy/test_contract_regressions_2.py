"""Related contract regressions with shared imports; original cases retained."""

import inspect
from dataclasses import replace
from datetime import datetime

import pytest
from jsonschema import Draft202012Validator

import fatebridge.services.bazi as bazi
from fatebridge.core import almanac, solar_model_policy
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    calculate_solar_time_adjustment,
)
from tests.ren.test_ren_transports import PAYLOAD
from tests.support.transports import (
    SPECS,
    business,
    inputs,
    native,
    rest,
    surface_calls,
)


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_named_solar_model_in_ren_calendar_all_transports(
    key, project, tmp_path, monkeypatch, surface_calls
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    root = "jinkou" if key == "jinkou" else "liureng"
    fields = [f"{root}.calendar_policy"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", field) for field in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, payload, params=params, options=options, flags=flags
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        policy = body[root]["calendar_policy"]
        assert policy["solar_longitude_definition"]["astronomical_model"] == MODEL_ID
        assert (
            policy["solar_longitude_definition"]["horizons_frame_equivalence_certified"]
            is False
        )
        assert len(policy["solar_term_dependencies"]) == 5
        for term in policy["solar_term_dependencies"]:
            assert term["provider"] == "fatebridge_analytic"
            assert term["ephemeris_model"] == MODEL_ID
            assert term["ephemeris_retflags"] == []
            assert term["solar_model_details"]["native_choice_probe_model"] == "moshier"
            assert term["solar_model_details"]["accuracy_certified"] is False
            assert term["solver_time_scale"] == "TT"
        assert body["run_metadata"]["engine_is_approximate"] is True
        assert not body.get("projection_warnings")


@pytest.mark.parametrize("fault", ["native_flags", "wrong_model", "missing_details"])
def test_ren_rejects_borrowed_flags_and_incomplete_analytic_identity(
    fault, tmp_path, monkeypatch
):
    from fatebridge.core.metaphysics import ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    seed = _build_analysis_seed(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    current, following = ren_calendar.get_adjacent_solar_terms(
        seed.input_datetime, seed.timezone
    )
    assert current.ephemeris_model == MODEL_ID
    changes = {
        "native_flags": dict(ephemeris_retflags=(4,)),
        "wrong_model": dict(ephemeris_model="unknown"),
        "missing_details": dict(solar_model_details=None),
    }[fault]
    monkeypatch.setattr(
        ren_calendar,
        "get_adjacent_solar_terms",
        lambda *args: (replace(current, **changes), following),
    )
    with pytest.raises(RuntimeError):
        ren_calendar.require_ren_calendar(seed)


@pytest.mark.parametrize("project", [False, True])
def test_named_analytic_solar_source_matches_three_protocols(
    project, tmp_path, monkeypatch, surface_calls
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["sixyao"]
    payload = {
        **inputs(spec),
        "date": "2000-01-07",
        "time": "12:00:00",
        "gua_code": "111111",
    }
    fields = [
        "calendar_context.current_solar_term",
        "calendar_context.next_solar_term",
        "calendar_context.bazi_month_boundary",
        "liuyao_evidence.calendar_conventions",
    ]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response, mcp, code, cli = surface_calls(
        spec, payload, params=params, options=options, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        term = result["calendar_context"]["current_solar_term"]
        assert term["resolution_provider"] == "fatebridge_analytic"
        assert term["ephemeris_model"] == MODEL_ID
        details = term["solar_model_details"]
        assert details["native_choice_probe_model"] == "moshier"
        assert details["accuracy_certified"] is False
        assert details["root_time_scale"] == "TT"
        assert details["civil_time_method"]
        assert result["run_metadata"]["engine_is_approximate"] is True
        assert (
            result["run_metadata"]["runtime"]["solar_term_policy"]["mode"] == "analytic"
        )
        assert MODEL_ID in result["run_metadata"]["provenance"]["ephemeris_model"]
        assert not result.get("projection_warnings")


@pytest.mark.parametrize(
    "mode,expected", [("auto", "fatebridge_de440_solar_v1"), ("native", "moshier")]
)
def test_captured_year_source_is_not_reselected_by_a_transient_environment_read(
    mode, expected, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    original = solar_model_policy.solar_model_policy
    injected = False

    def transient():
        nonlocal injected
        caller = inspect.currentframe().f_back
        if (
            not injected
            and caller.f_code.co_name == "de440_selected"
            and caller.f_back.f_code.co_name == "_calculate_solar_terms_for_year"
        ):
            injected = True
            monkeypatch.setenv(
                "FATEBRIDGE_SOLAR_TERM_MODEL", "native" if mode == "auto" else "auto"
            )
            selected = original()
            monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
            return selected
        return original()

    almanac.get_solar_terms_for_year.cache_clear()
    monkeypatch.setattr(solar_model_policy, "solar_model_policy", transient)
    for _ in range(2):
        terms = almanac.get_solar_terms_for_year(2026, "UTC")
        assert len(terms) == 24
        assert {term.ephemeris_model for term in terms} == {expected}
        assert all(almanac.is_calculated_solar_term(term) for term in terms)


def test_longitude_only_strategy_sign_matches_physics() -> None:
    """At Shanghai's +08 meridian (120°E), 130°E sits 10° east; true solar
    time must run AHEAD of the wall clock. The longitude-only strategy
    used to flip this, pushing eastern longitudes backward."""
    moment = datetime(2024, 6, 21, 14, 30)
    tz = "Asia/Shanghai"

    east = calculate_solar_time_adjustment(
        moment, tz, 130.0, strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    west = calculate_solar_time_adjustment(
        moment, tz, 100.0, strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    same_east = calculate_solar_time_adjustment(
        moment, tz, 130.0, strategy=SOLAR_TIME_STRATEGY_APPARENT
    )

    # 4 minutes per degree: 10° * 4 = 40 min.
    assert east["total_correction_minutes"] == 40.0
    assert west["total_correction_minutes"] == -80.0
    # Both strategies must agree in sign (apparent adds the equation-of-time
    # term, so magnitudes differ by a few minutes but direction must match).
    assert (east["total_correction_minutes"] > 0) == (
        same_east["total_correction_minutes"] > 0
    )


def test_longitude_only_true_solar_matches_explicit_timezone():
    """A western longitude without a timezone must not use Asia/Shanghai's meridian."""
    implicit = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "未提供",
        birth_longitude=-74.0,
        use_true_solar_time=True,
    )
    explicit = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "未提供",
        birth_longitude=-74.0,
        birth_timezone="America/New_York",
        use_true_solar_time=True,
    )
    pi = bazi.calculate_bazi_birth(implicit)["bazi_birth"]["four_pillars"]
    pe = bazi.calculate_bazi_birth(explicit)["bazi_birth"]["four_pillars"]
    assert pi["day"] == pe["day"]
    assert pi["hour"] == pe["hour"]


def test_china_longitude_keeps_expected_day_pillar():
    p = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "北京",
        birth_longitude=116.4,
        use_true_solar_time=True,
    )
    day = bazi.calculate_bazi_birth(p)["bazi_birth"]["four_pillars"]["day"]
    assert day == {"stem": "乙", "branch": "酉"}
