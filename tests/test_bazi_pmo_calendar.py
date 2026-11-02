"""Complete printed-date conformance does not certify all birth clocks."""

import ast
import asyncio
import gzip
import json
import subprocess
import sys
import tarfile
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.core import almanac
from scripts.audit_bazi_pmo_calendar import hko_parser
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_pmo_calendar_v1"
FIRST = ROOT / "docs/validation/bazi-pmo-calendar-first-v1.json.gz"
REFERENCE = json.loads(
    gzip.decompress((FIXTURE / "expected-calendar.json.gz").read_bytes())
)
RESULT = json.loads(gzip.decompress(FIRST.read_bytes()))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


def test_every_source_day_and_full_first_result_are_bound_without_range_reduction():
    protocol = frozen("protocol.json")
    freeze = frozen("reference-freeze.json")
    assert freeze["protocol_sha256"] == digest(FIXTURE / "protocol.json")
    assert digest(FIRST) == FIRST.with_suffix(".gz.sha256").read_text().strip()
    for name, wanted in freeze["files"].items():
        assert digest(FIXTURE / name) == wanted
    assert freeze["candidate_comparisons_before_freeze"] == 0
    assert freeze["old_references_and_unknown_fields_unchanged"]
    assert protocol["expected_source_date_count"] == len(REFERENCE["rows"]) == 46021
    assert [r["solar"] for r in REFERENCE["rows"]] == [
        (date(1900, 1, 1) + timedelta(days=i)).isoformat() for i in range(46021)
    ]
    assert set(r["source_pdf_page"] for r in REFERENCE["rows"]) == set(range(3, 381))
    assert (
        RESULT["pmo"]["rows"]
        == RESULT["pmo"]["lunar_matches"]
        == RESULT["pmo"]["day_ganzhi_matches"]
        == 46021
    )
    assert RESULT["pmo"]["mismatches"] == []
    assert RESULT["source_drift"] == []
    assert RESULT["new_independent_observation_credit"] == 0
    assert not RESULT["production_changed"] and not RESULT["whole_goal_complete"]
    assert RESULT["overall_score"] is None
    assert RESULT["reality_prediction_efficacy"] == "not_tested"


@pytest.mark.filterwarnings(
    "ignore:(from|to)SolarDate is deprecated.*:DeprecationWarning"
)
@pytest.mark.filterwarnings("ignore:use is_leap_month:DeprecationWarning")
def test_current_shared_date_components_match_every_frozen_literal_not_only_first_run():
    differences = []
    for row in REFERENCE["rows"]:
        solar = date.fromisoformat(row["solar"])
        actual = almanac._lunar_date_from_solar(solar)
        got = (actual.year, actual.month, actual.day, actual.isLeapMonth)
        expected = (row["year"], row["month"], row["day"], row["is_leap_month"])
        ganzhi = almanac.get_day_ganzhi(solar.year, solar.month, solar.day)
        if got != expected or ganzhi != row["day_ganzhi"]:
            differences.append((row["solar"], got, expected, ganzhi, row["day_ganzhi"]))
    assert differences == []


def test_raw_extraction_and_repeated_heading_rejection_remain_recoverable():
    raw = json.loads(
        gzip.decompress((FIXTURE / "source-cells-first.json.gz").read_bytes())
    )
    assert len(raw["rows"]) == 46021 and not raw["collection_errors"]
    assert raw["source_consistency_flags"] == []
    assert raw["candidate_calculators_imported"] is False
    assert raw["collector_sha256"] == digest(FIXTURE / "first-collector.py.txt")

    # Black formatting must not silently replace the actual first collector.
    def functions(path):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    assert functions(FIXTURE / "first-collector.py.txt") == functions(
        ROOT / "scripts/collect_bazi_pmo_calendar.py"
    )
    notes = frozen("source-semantic-check.json")
    assert notes["candidate_comparisons"] == 0
    assert (
        notes["printed_year_hint_month_blocks_checked"]
        == len(notes["printed_year_hints"])
        == 1512
    )
    repeated = [r for r in notes["printed_year_hints"] if r["normalization"] != "none"]
    assert {r["source_pdf_page"] for r in repeated} == {60, 312, 369}
    assert all(
        len(r["literal_components"]) == 2 and len(r["semantic_year_sequence"]) == 1
        for r in repeated
    )
    first_failure = json.loads(
        (FIXTURE / "source-semantic-initial-failure.json").read_text()
    )
    assert first_failure["exception_type"] == "AssertionError"
    assert first_failure["candidate_comparisons"] == 0
    assert (
        "AssertionError" in (FIXTURE / "source-semantic-first-replay.log").read_text()
    )


def test_original_hko_unknown19_are_not_relabelled_as_full_matches():
    hko = RESULT["hko"]
    assert hko["full_source_cells"] == hko["matched_full"] == 73030
    assert hko["partial_source_cells"] == hko["matched_year_day_only"] == 19
    assert hko["mismatches"] == []
    old_partial = [r for r in hko["all_rows"] if not r["source_full_date"]]
    assert len(old_partial) == 19
    assert all(set(r["known_source_fields"]) == {"year", "day"} for r in old_partial)
    cross = RESULT["cross_source"]
    assert cross["overlapping_date_labels"] == 45656
    assert cross["overlapping_full_date_labels"] == 45637
    assert cross["different_dates"] == []
    assert cross["union_complete_source_dates"] == 73414
    assert cross["not_summed_as_independent_samples"]
    assert cross["existing_ziwei_TAM_join_already_exposed_the_HKO_prefix"]
    recovered = cross["old_unknown_hko19_new_pmo_fields"]
    assert len(recovered) == 19
    assert all(
        r["original_hko_unknown_fields_not_changed"] and r["not_new_independent_credit"]
        for r in recovered
    )
    assert recovered[0]["new_pmo_fields"] == {
        "year": 1900,
        "month": 11,
        "day": 11,
        "is_leap_month": False,
    }
    parser = hko_parser()
    source = ROOT / "tests/fixtures/ziwei_independent/hko/T1901c.txt"
    rows = parser(source.read_text(encoding="utf-8-sig"), 1901)
    assert len([r for r in rows if r["month"] is None]) == 19


def test_supplemental_parser_binding_keeps_its_after_first_timing_explicit():
    binding = frozen("comparison-inputs-v2.json")
    assert binding["first_comparison_already_completed"] is True
    assert "cannot retroactively certify" in binding["first_comparison_limit"]
    for name, wanted in binding["files"].items():
        assert digest(FIXTURE / name) == wanted
    assert binding["new_independent_credit"] == 0 and binding["first_result_unchanged"]


def extract_candidate(destination):
    with tarfile.open(FIXTURE / "candidate-source.tar.gz") as archive:
        for member in archive.getmembers():
            assert member.isfile() and not Path(member.name).is_absolute()
            assert ".." not in Path(member.name).parts
        archive.extractall(destination, filter="data")


def replay(candidate, output):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_pmo_calendar.py"),
            "--candidate-root",
            str(candidate),
            "--environment",
            str(FIXTURE / "environment-before-comparison.json"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_portable_candidate_replay_reproduces_all_first_fields_except_declared_metadata(
    tmp_path,
):
    candidate = tmp_path / "candidate"
    extract_candidate(candidate)
    output = tmp_path / "replay.json.gz"
    process = replay(candidate, output)
    assert process.returncode == 0, process.stderr
    current = json.loads(gzip.decompress(output.read_bytes()))
    assert set(current) == set(RESULT) | {
        "supplemental_input_binding_sha256",
        "first_comparison_binding_limit",
    }
    for key, value in RESULT.items():
        if key not in {
            "recorded_at_utc",
            "actual_candidate_root",
            "actual_almanac_file",
            "runner_sha256",
        }:
            assert current[key] == value, key
    assert current["supplemental_input_binding_sha256"] == digest(
        FIXTURE / "comparison-inputs-v2.json"
    )
    again = replay(candidate, output)
    assert again.returncode != 0 and "Keep all first comparison outputs" in again.stderr


def test_unregistered_candidate_source_file_cannot_pass_frozen_replay(tmp_path):
    candidate = tmp_path / "candidate"
    extract_candidate(candidate)
    (candidate / "src/fatebridge/unregistered_source.py").write_text(
        "raise RuntimeError('never import a source outside the manifest')\n"
    )
    output = tmp_path / "rejected.json.gz"
    process = replay(candidate, output)
    assert process.returncode != 0 and "file inventory changed" in process.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "case", frozen("edge-clock-regressions.json")["cases"], ids=lambda c: c["id"]
)
def test_accepted_birth_edges_do_not_fake_lunar_fields_outside_corrected_date_range(
    case, rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    payload = {
        k: v
        for k, v in case.items()
        if k.startswith("birth_") or k == "use_true_solar_time"
    }
    payload.update(
        gender="男",
        analysis_year=case["birth_year"],
        analysis_month=case["birth_month"],
        analysis_day=case["birth_day"],
    )
    fields = ["bazi_birth.calendar_context"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    params = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
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
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for result in (http.json(), protocol.structured_content, cli):
        context = result["bazi_birth"]["calendar_context"]
        assert context["solar_datetime"][:10] == case["expected_corrected_solar_date"]
        assert context["lunar_calendar"] is None
        assert context["lunar_calendar_support"]["supported"] is False
        assert context["lunar_calendar_support"]["supported_range"] == {
            "start": "1900-01-01",
            "end": "2100-12-31",
        }
        assert (
            context["bazi_month_boundary"]["comparison_datetime"][:10]
            == f"{case['birth_year']:04}-{case['birth_month']:02}-{case['birth_day']:02}"
        )
