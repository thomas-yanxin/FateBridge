"""Primary counters, complete month cohorts and faithful adapter-year receipts."""

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_month import (
    DEFAULT_MONTH_PROFILE,
    jinjing_month_origin,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_lunation_chain import (
    CORPUS,
    ROOT,
    audit,
    serial_lunations,
    verify_sources,
)
from tests.test_taiyi_month_nominal_year import (
    with_prior_default_origin_in_current_runtime,
)

SOFTWARE = ROOT / "tests/fixtures/taiyi_month_origin_v32"
SOFTWARE_FREEZE = "39b415121a9aa8c5f90b779f8f8efe3d13cf46d3521a3850d7328107d0698ae7"
BASELINE = json.loads((SOFTWARE / "before-production.json").read_text())


@pytest.fixture(scope="module")
def report():
    return audit()


def test_primary_source_and_software_preservation_are_different_frozen_objects():
    source = verify_sources()
    assert len(source["files"]) == 7 and len(source["prior_sources"]) == 37
    assert source["production_comparisons_before_freeze"] == 0
    assert not source["blinded"] and not source["source_expectations_from_production"]
    assert (
        hashlib.sha256((SOFTWARE / "freeze.json").read_bytes()).hexdigest()
        == SOFTWARE_FREEZE
    )
    frozen = json.loads((SOFTWARE / "freeze.json").read_text())
    assert frozen["captured_before_origin_receipt_edits"] and frozen["cases"] == 26
    for name, digest in frozen["files"].items():
        assert hashlib.sha256((SOFTWARE / name).read_bytes()).hexdigest() == digest
    assert all(
        row["calendar_rules"].get("month_origin") is None
        for row in BASELINE["rows"]
        if row["input"]["month_profile"] == DEFAULT_MONTH_PROFILE
    )


@pytest.mark.parametrize("rewrite_manifest", [False, True])
def test_cannot_erase_the_652_transcription_by_editing_frozen_readings(
    tmp_path, rewrite_manifest
):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "readings.json"
    reading = json.loads(path.read_text())
    reading["wujing"]["initial_online_transcription_chapter_years"] = 657
    path.write_text(json.dumps(reading))
    if rewrite_manifest:
        frozen = json.loads((corpus / "freeze.json").read_text())
        frozen["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="V32"):
        verify_sources(corpus)


def test_native_constant_corroboration_does_not_replace_primary_siku_values(report):
    assert report["online_transcription_variant"] == {
        "initial_online": 652,
        "native": 657,
        "old_file_overwritten": False,
    }
    editions = report["wujing_constants_against_two_jinjing_editions"]
    assert [r["edition"] for r in editions] == ["ncl_ming", "siku"]
    assert [sum(o["matches"] for o in r["observations"]) for r in editions] == [4, 2]
    assert all(len(r["observations"]) == 4 for r in editions)
    assert all(r["matches"] for r in report["given_annual_anchor_checks"])
    assert (
        report["fuying_month_formula"]["literal_subtract_one_before_multiply_stated"]
        is False
    )
    assert report["fuying_month_formula"]["source_epoch_reused_as_jinjing"] is False


def test_all_rival_year_readings_and_profiles_survive_when_one_happens_to_match(report):
    rows = report["month_case_rival_readings"]
    assert len(rows) == 4
    assert [r["cycle360"] for r in rows] == [241, 241, 253, 253]
    assert [r["all_listed_fields_match"] for r in rows] == [True, True, False, False]
    assert all(len(r["observations"]) == 3 for r in rows)
    assert not report["year_label_reading_selected_by_match"]
    assert not report["mean_lunation_counter_is_public_jie_counter"]


def test_complete_month_cohorts_keep_the_remaining_failures(report):
    rows = report["full_lunation_cohort_hypotheses"]
    assert len(rows) == 8
    assert {
        (r["edition"], r["year_shift"], r["extra_preceding_lunation"]) for r in rows
    } == {(e, y, m) for e in ("ncl_ming", "siku") for y in (0, -1) for m in (0, 1)}
    assert all(
        len(r["records"]) == r["required_month_first_anchors"] == 13
        and r["required_month_lengths"] == 12
        for r in rows
    )
    assert all(len(record["day_labels"]) == 2 for r in rows for record in r["records"])
    assert all(not r["june8_matches_original_accumulation"] for r in rows)
    ncl = [r for r in rows if r["edition"] == "ncl_ming"]
    assert [r["june8_candidate_accumulation"] for r in ncl] == [
        707501413,
        707501443,
        707501059,
        707501089,
    ]
    near = next(
        r for r in ncl if r["year_shift"] == -1 and r["extra_preceding_lunation"] == 0
    )
    assert near["matching_month_lengths"] == 10
    assert near["matching_first_labels_by_origin"] == {"0": 12, "1": 0}
    assert [
        r["month"] for r in near["records"] if not r["day_labels"][0]["matches"]
    ] == [3]
    assert [
        r["month"] for r in near["records"] if r["month_length_matches"] is False
    ] == [2, 3]


@pytest.mark.parametrize("edition,per49", [("ncl_ming", 1447), ("siku", 1457)])
def test_every_small_remainder_survives_49_serial_steps_without_rounding(
    edition, per49
):
    reading = json.loads((CORPUS / "readings.json").read_text())
    profile = reading["jinjing_serial_month_rules"][edition]
    rows = serial_lunations(profile, 1937060, months=50)
    assert len({r["small_remainder"] for r in rows[:49]}) == 49
    assert rows[49]["small_remainder"] == rows[0]["small_remainder"]
    assert rows[49]["day_accumulation"] - rows[0]["day_accumulation"] == per49
    assert {r["next_month_days"] for r in rows} == {29, 30}
    if edition == "ncl_ming":
        assert all(r["direct_minus_serial"] == 0 for r in rows)
    else:
        assert rows[49]["direct_minus_serial"] == 990


@pytest.mark.parametrize(
    "year,offset", [(0, 0), (True, 0), (10000, 0), (2026, -1), (2026, 12), (2026, True)]
)
def test_origin_requires_explicit_year_and_month_units(year, offset):
    with pytest.raises(ValueError, match="金镜节月"):
        jinjing_month_origin(year, offset)


@pytest.mark.parametrize(
    "row",
    BASELINE["rows"],
    ids=lambda r: f"{r['input']['analysis_year']}-{r['input']['analysis_month']}-{r['input']['month_profile']}",
)
def test_nominal_year_migrates_default_counter_and_preserves_key_profile(
    row, monkeypatch
):
    result = calculate_taiyi_analysis(**row["input"])
    board = result["taiyi"]
    if row["input"]["month_profile"] == DEFAULT_MONTH_PROFILE:
        receipt = board["calendar_rules"]["month_origin"]
        assert receipt["accumulation"] == board["core_board"]["accumulation"]
        assert (
            receipt["counted_year"]
            == receipt["cycle_year"] + 1
            == board["calendar_rules"]["cycle_year"] + 1
        )
        # The old frozen software payloads remain unchanged as history.
        # V39 corrects the nominal-year defect, adding12 before all dependent
        # chart layers are recomputed; it does not rewrite their old values.
        assert (
            board["core_board"]["accumulation"]
            == row["core_board"]["accumulation"] + 12
        )
        assert board["core_board"]["jishen"] == row["core_board"]["jishen"]
        assert receipt["counted_year_basis"] == "nominal_year_after_tianzheng11"
        assert receipt["counter_unit"] == "twelve_jie_months"
        assert (
            receipt["mean_lunation_counter"] is False
            and receipt["source_year_label_adjudicated"] is False
        )
        assert receipt["scope"] in board["calendar_summary"]["convention"]
        assert receipt["year_label_policy"] in result["snapshot_text"]
        assert f"本盘年标{receipt['counted_year']}" in result["snapshot_text"]
        assert "弘治17年截数" not in result["snapshot_text"]
        assert board["ruleset"]["version"] == "1.2.0"
    else:
        # Keep the old full hash in the frozen file and historical audit.
        # The live solar provider now has new precision metadata/roots; use
        # identical current astronomy for this patch's causal comparison.
        assert board["core_board"] == row["core_board"]
        actual_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
        controlled = with_prior_default_origin_in_current_runtime(
            row["input"], monkeypatch
        )
        assert actual_json == json.dumps(controlled, ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "year,month,cycle_year",
    [(2026, 1, 2025), (2026, 12, 2026), (1043, 12, 1043), (1561, 5, 1560)],
)
def test_default_month_receipt_is_identical_on_rest_mcp_cli(
    monkeypatch, capsys, key, year, month, cycle_year
):
    payload = (
        {
            "analysis_year": year,
            "analysis_month": month,
            "analysis_day": 15,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "calculation_mode": "month",
        }
        if key == "taiyi"
        else {
            "date": f"{year:04d}-{month:02d}-15",
            "time": "12:00:00",
            "zone": "+08:00",
            "taiyi_options": {"calculation_mode": "month"},
        }
    )
    payload["use_true_solar_time"] = False
    spec = next(s for s in CATALOG if s.key == key)
    fields = suggested_fields(
        spec, view="clock_basis" if key == "taiyi" else "taiyi_depth"
    )
    opts = {
        "fields": fields,
        "strict_fields": True,
        "response_char_limit": 0,
        "include_snapshot_text": False,
        "as_of": "2026-10-23T12:00:00+08:00",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    rest = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key, {**payload, **opts}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    mcp = asyncio.run(invoke())
    argv = [key]
    for name, value in payload.items():
        argv.extend(
            [
                "--" + name.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
        )
    argv.extend(
        [
            "--as-of",
            opts["as_of"],
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in (rest.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    receipt = bodies[0]["taiyi"]["calendar_rules"]["month_origin"]
    assert receipt["counted_year"] == receipt["cycle_year"] + 1 == cycle_year + 1
    if (year, month) == (1561, 5):
        assert receipt["accumulation"] == 23257410
    elif (year, month) == (1043, 12):
        assert (receipt["accumulation"] - 1) % 360 + 1 == 241
    assert receipt["source_year_label_adjudicated"] is False


def test_unresolved_calendar_audit_keeps_failure_exit_and_whole_scope(tmp_path):
    path = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_taiyi_lunation_chain.py"),
            "--output",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1 and not result.stderr
    report = json.loads(path.read_text())
    assert len(report["full_lunation_cohort_hypotheses"]) == 8
    assert report["new_complete_dated_classical_cases_passed"] == 0
    assert not report["production_numeric_formula_changed"]
    assert not report["whole_goal_complete"]
