"""Loaded UTC coefficients must govern both cached roots and their receipts."""

import asyncio
import copy
import importlib.util
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import almanac
from fatebridge.core.astro import historical_utc, time_scales, utc_policy
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.services.metaphysics import calculate_liureng_gods
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
MOD = importlib.util.spec_from_file_location(
    "clock_profile_audit", ROOT / "scripts/ren/audit_ren_clock_profiles.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()


@pytest.fixture(autouse=True)
def clear_clock_caches():
    AUDIT.reset()
    yield
    AUDIT.reset()


def test_all_four_predeclared_faults_and_hand_declared_arithmetic():
    result = AUDIT.run()
    assert result["engineering_checks_passed"]
    assert result["historical_faults_fixed"] == result["receipt_faults_fixed"] == 2
    assert result["source_tables_modified"] is False
    assert result["new_reference_events"] == 0 and result["goal_complete"] is False


@pytest.mark.parametrize("change", ["edit", "missing", "extra", "prune"])
def test_frozen_protocol_cannot_change_to_make_a_fault_disappear(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.F, target)
    if change in {"edit", "prune"}:
        p = target / "protocol.json"
        value = json.loads(p.read_text())
        if change == "edit":
            value["historical_cases"][0]["expected_context_changes"] = False
        else:
            value["historical_cases"].pop()
        p.write_text(json.dumps(value))
    elif change == "missing":
        (target / "source-links.json").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen clock-profile"):
        AUDIT.reference(target)


@pytest.mark.parametrize(
    "owner,name",
    [
        (utc_policy, "leap_table"),
        (historical_utc, "utc1960_table"),
        (historical_utc, "historical_utc_table"),
    ],
)
def test_all_three_loaded_profiles_change_the_key_and_restore_it(
    owner, name, monkeypatch
):
    value = copy.deepcopy(getattr(owner, name)())
    monkeypatch.setattr(owner, name, lambda: value)
    before = solar_term_cache_context(almanac.swe)
    value["source_url"] += "#hypothetical-reload"
    assert solar_term_cache_context(almanac.swe) != before
    value["source_url"] = value["source_url"].removesuffix("#hypothetical-reload")
    assert solar_term_cache_context(almanac.swe) == before


@pytest.mark.parametrize("case", REFERENCE["historical_cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("tool", ["liureng_gods", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_reloaded_historical_profile_reaches_three_ports_without_manual_cache_clear(
    case, tool, project, rest, tmp_path, capsys, monkeypatch
):
    name = "utc1960_table" if case["table"] == "utc1960" else "historical_utc_table"
    table = copy.deepcopy(getattr(historical_utc, name)())
    monkeypatch.setattr(historical_utc, name, lambda: table)
    old = next(
        t
        for t in almanac.get_solar_terms_for_year(case["year"], "UTC")
        if t.name == "雨水"
    )
    moment = (old.moment - timedelta(seconds=1)).replace(microsecond=0)
    payload = AUDIT.payload(moment)
    payload["selected_sections"] = ["起盘信息"]
    before = calculate_liureng_gods(**payload)
    assert before["liureng"]["month_general"]["branch"] == "子"
    entry = next(
        e for e in table["entries"] if e["effective_date"] == case["entry_effective"]
    )
    entry["offset_seconds"] += case["offset_increment_seconds"]
    spec = SPECS[tool]
    fields = ["four_pillars", "liureng.month_general", "liureng.calendar_policy"]
    if tool == "jinkou":
        fields += ["jinkou.overview.month_general", "jinkou.calendar_policy"]
    params, flags, options = (
        [("as_of", AS_OF), ("response_char_limit", "0")],
        ["--response-char-limit", "0"],
        {},
    )
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
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        assert body["liureng"]["month_general"]["branch"] == "亥"
        if tool == "jinkou":
            assert body["jinkou"]["overview"]["month_general"]["branch"] == "亥"


def test_mid_receipt_profile_change_is_retried_before_publishing_mixed_metadata(
    monkeypatch,
):
    table = copy.deepcopy(utc_policy.leap_table())
    monkeypatch.setattr(utc_policy, "leap_table", lambda: table)
    real = time_scales.ephemeris_time
    calls = []

    def changing(moment):
        epoch = real(moment)
        calls.append(moment)
        if len(calls) == 1:
            table["expires_at"] = "2026-01-01T00:00:00+00:00"
        return epoch

    monkeypatch.setattr(time_scales, "ephemeris_time", changing)
    result = ren_calendar._term_time_scale(
        datetime.fromisoformat("2026-06-01T00:00:00+00:00")
    )
    assert len(calls) == 2
    assert result["future_leap_seconds_assumed_unchanged"] is True
    assert result["leap_table_expires_at"] == table["expires_at"]


def test_persistently_changing_receipt_profile_fails_instead_of_caching_mixed_data(
    monkeypatch,
):
    table = copy.deepcopy(utc_policy.leap_table())
    monkeypatch.setattr(utc_policy, "leap_table", lambda: table)
    real = time_scales.ephemeris_time
    calls = []

    def changing(moment):
        epoch = real(moment)
        calls.append(moment)
        table["source_url"] += "#changed"
        return epoch

    monkeypatch.setattr(time_scales, "ephemeris_time", changing)
    with pytest.raises(RuntimeError, match="profile changed"):
        ren_calendar._term_time_scale(
            datetime.fromisoformat("2026-06-01T00:00:00+00:00")
        )
    assert len(calls) == 3
