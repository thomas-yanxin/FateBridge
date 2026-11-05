"""Frozen Ren boundary cohorts, clock attribution and actual protocol parity."""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from scripts.ren.audit_ren_boundary_decisions import (
    FIXTURE,
    ROOT,
    expectations,
    expected_state,
    reference,
    sha,
)
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)


@pytest.fixture(scope="module")
def frozen():
    return reference()


def test_protocol_keeps_full_denominators_and_original_acceptance_rules(frozen):
    protocol = frozen["protocol"]
    assert len(frozen["roots"]) == 4872
    assert len(frozen["probes"]) == 9744
    assert protocol["criteria"]["tt_seconds"] == 1.0
    assert protocol["criteria"]["published_hko_date"] == "exact_original_date_equality"
    assert protocol["cohorts"]["hko_dates"] == 4800
    assert len(protocol["arms"]) == 4
    assert protocol["full_goal_complete"] is False
    assert protocol["new_real_world_samples"] == 0
    assert protocol["model_processes"] == 0


@pytest.mark.parametrize("change", ["inventory", "protocol", "manifest"])
def test_audit_refuses_modified_frozen_protocol_before_computation(change, tmp_path):
    target = tmp_path / "fixture"
    shutil.copytree(FIXTURE, target)
    if change == "inventory":
        (target / "extra.json").write_text("{}")
    elif change == "protocol":
        (target / "protocol.json").write_text("{}")
    else:
        (target / "freeze.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        reference(target)


def test_term_year_month_and_zhongqi_changes_are_distinct(frozen):
    calendar = json.loads(
        (ROOT / "tests/fixtures/ren_calendar_v1/reference.json").read_text()
    )
    roots = frozen["roots"]
    general_map = frozen["protocol"]["reference_maps"]["general_by_last_term"]
    changes = dict(term=0, year=0, month=0, general=0)
    for row in [v for v in roots if v["year"] == 1900]:
        before = expected_state(roots, row["jd_tt"] - 1e-6, calendar["month_starts"])
        exact = expected_state(roots, row["jd_tt"], calendar["month_starts"])
        assert exact["last_term"] == row["name"]
        changes["term"] += before["last_term"] != exact["last_term"]
        changes["year"] += before["bazi_year"] != exact["bazi_year"]
        changes["month"] += before["month_branch"] != exact["month_branch"]
        changes["general"] += (
            general_map[before["last_term"]] != general_map[exact["last_term"]]
        )
    assert changes == dict(term=24, year=1, month=12, general=12)
    unavailable = expected_state(roots, roots[0]["jd_tt"] - 1, calendar["month_starts"])
    assert unavailable == dict(last_term=None, bazi_year=None, month_branch=None)


@pytest.fixture
def native_files(monkeypatch):
    previous = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    try:
        yield
    finally:
        configure_ephemeris_path(previous)


@pytest.mark.parametrize(
    "year,prefix",
    [
        (1959, "pre_1972_swiss_UT1"),
        (1960, "SOFA_1960"),
        (1969, "IERS_1961_1971"),
        (2026, "IERS_UTC"),
        (2084, "IERS_UTC"),
    ],
)
def test_actual_ren_dependency_clock_method_and_scope_agree(year, prefix, native_files):
    from fatebridge.services.metaphysics import calculate_jinkou_analysis

    result = calculate_jinkou_analysis(
        analysis_year=year,
        analysis_month=6,
        analysis_day=15,
        analysis_hour=12,
        analysis_timezone="UTC",
        use_true_solar_time=False,
        di_fen="酉",
        is_diurnal=True,
    )
    assert "error" not in result
    policy = result["jinkou"]["calendar_policy"]
    assert "1960年前采用历史UT1" in policy["scope"]
    assert "1960年用SOFA历史UTC偏移与日漂移" in policy["scope"]
    assert "1961年前采用历史UT1" not in policy["scope"]
    assert len(policy["solar_term_dependencies"]) == 5
    for dependency in policy["solar_term_dependencies"]:
        assert dependency["civil_time_method"].startswith(prefix)
        assert dependency["solver_time_scale"] == "TT"
        assert dependency["future_leap_seconds_assumed_unchanged"] is (year == 2084)


# Each case uses the original frozen minute label, never an offset fitted to
# a particular model. The actual-clock comparison is conditional propagation.
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
@pytest.mark.parametrize(
    "mode,identifier",
    [
        ("native", "1960-雨水-floor"),
        ("spk", "2022-小暑-floor"),
        ("spk", "1918-小雪-floor"),
        ("spk", "1936-雨水-next_minute"),
    ],
)
def test_ren_boundary_facts_and_clock_attribution_agree_on_three_protocols(
    key, mode, identifier, frozen, monkeypatch, rest, tmp_path, capsys
):
    previous = configured_ephemeris_path()
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    if mode == "spk":
        pytest.importorskip("erfa")
        pytest.importorskip("jplephem")
        kernel = ROOT / "ephe/solar-de440.bsp"
        if not kernel.exists():
            pytest.skip("Explicit external DE440 kernel unavailable")
        assert sha(kernel) == frozen["protocol"]["kernel_sha256"]
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setenv("SE_EPHE_PATH", str(empty))
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(kernel))
    else:
        monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    try:
        probe = next(v for v in frozen["probes"] if v["id"] == identifier)
        moment = datetime.fromisoformat(probe["civil_utc"])
        cal = json.loads(
            (ROOT / "tests/fixtures/ren_calendar_v1/reference.json").read_text()
        )
        rules = json.loads(
            (ROOT / "tests/fixtures/ren_classical_v1/rules.json").read_text()
        )
        expected = expectations(
            expected_state(
                frozen["roots"], ephemeris_time(moment).jd_tt, cal["month_starts"]
            ),
            moment,
            frozen["protocol"],
            cal,
            rules,
        )
        payload = dict(
            analysis_year=moment.year,
            analysis_month=moment.month,
            analysis_day=moment.day,
            analysis_hour=moment.hour,
            analysis_minute=moment.minute,
            analysis_timezone="UTC",
            use_true_solar_time=False,
            is_diurnal=True,
        )
        if key == "jinkou":
            payload["di_fen"] = "酉"
        spec = SPECS[key]
        fields = ["four_pillars", "liureng.month_general", "liureng.calendar_policy"]
        if key == "jinkou":
            fields += [
                "jinkou.rows",
                "jinkou.overview.use_position",
                "jinkou.calendar_policy",
            ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
        http = rest.post(
            spec.rest_path,
            json=payload,
            params=[
                *[("fields", field) for field in fields],
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
                ("response_char_limit", "0"),
            ],
        )
        code, cli = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=[
                "--response-char-limit",
                "0",
                "--strict-fields",
                "true",
                "--include-snapshot-text",
                "false",
                "--fields",
                *fields,
            ],
        )
        mcp = asyncio.run(native(spec, payload, **options))
        assert http.status_code == 200 and code == 0 and not mcp.is_error
        outputs = [http.json(), cli, mcp.structured_content]
        assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
        for value in outputs:
            Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
            assert value["four_pillars"]["year"] == dict(
                stem=expected["year"][0], branch=expected["year"][1]
            )
            assert value["four_pillars"]["month"] == dict(
                stem=expected["month"][0], branch=expected["month"][1]
            )
            assert (
                value["liureng"]["month_general"]["branch"] == expected["month_general"]
            )
            policy = value["liureng"]["calendar_policy"]
            assert "1960年用SOFA" in policy["scope"]
            for dep in policy["solar_term_dependencies"]:
                assert dep["provider"] == ("jpl_spk" if mode == "spk" else "swisseph")
                if mode == "spk":
                    assert (
                        dep["solar_model_details"]["kernel_sha256"]
                        == frozen["protocol"]["kernel_sha256"]
                    )
                    assert dep["ephemeris_retflags"] == []
                elif moment.year == 1960:
                    assert dep["civil_time_method"].startswith("SOFA_1960")
            if key == "jinkou":
                board = value["jinkou"]
                assert [r["content"] for r in board["rows"]] == expected["positions"]
                assert [r["seasonal_power"] for r in board["rows"]] == expected[
                    "seasonal_powers"
                ]
                assert board["overview"]["use_position"] == expected["polarity_use"]
                assert board["calendar_policy"] == policy
    finally:
        configure_ephemeris_path(previous)
