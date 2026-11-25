"""Explicit solar sources retain the independently adjudicated month phases."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

import erfa
import pytest

import fatebridge.core.analytic_solar as solar
from fatebridge.core.de441_solar import MODEL_ID as DE441_MODEL
from fatebridge.core.liuyao.liuyao_calendar_models import SCOPE
from fatebridge.core.local_techniques.sixyao import build_sixyao_result

CASES = json.loads(
    (Path(__file__).parents[1] / "data/liuyao/model_boundary_inputs.json").read_bytes()
)["cases"]

SOURCE = json.loads(
    (
        Path(__file__).parents[1] / "data/liuyao/model_boundary_de440_source.json"
    ).read_bytes()
)
SOURCE_CASES = {row["id"]: row for row in SOURCE["cases"]}

ROOT = "liuyao_evidence.calendar_conventions.month_model_comparison"
pytestmark = pytest.mark.usefixtures("analytic_environment")


@pytest.fixture
def analytic_environment(monkeypatch, tmp_path_factory):
    empty = tmp_path_factory.getbasetemp() / "model-boundary-empty-ephe"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def comparison(result):
    return result["liuyao_evidence"]["calendar_conventions"]["month_model_comparison"]


def assert_analytic_month(result, case):
    value = comparison(result)
    assert value["status"] == "not_compared_incomplete_native_probes"
    assert value["coverage_complete"] is False
    assert value["compared_month_boundaries"] == 0
    assert value["calculation_month_branch"] == (
        SOURCE_CASES[case["id"]]["current_month_branch_from_reference"]
    )
    assert value["native_models"] == []
    assert value["selected_models"] == ["fatebridge_analytic_solar_v1"]
    assert len(value["missing_native_probes"]) == 36
    assert value["active_boundary_differences"] == []
    assert "month_changed" not in value and "native_month_branch" not in value
    assert value["scope"] == SCOPE


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_explicit_analytic_month_matches_the_independent_source_phase(case) -> None:
    result = build_sixyao_result(**case["input"])
    assert_analytic_month(result, case)
    assert "同次交气比较未完成，不能认定月令路径一致。" in result["snapshot_text"]


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["id"])
def test_explicit_native_month_matches_source_without_starting_analytic(
    case, monkeypatch: pytest.MonkeyPatch
) -> None:

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")

    def unexpected(*args, **kwargs):
        raise AssertionError("Native result must not manufacture another model")

    monkeypatch.setattr(solar, "solar_longitude", unexpected)
    result = build_sixyao_result(**case["input"])
    assert (
        "month_model_comparison"
        not in result["liuyao_evidence"]["calendar_conventions"]
    )
    assert (
        result["liuyao_evidence"]["calendar_conventions"]["month_branch"]
        == SOURCE_CASES[case["id"]]["current_month_branch_from_reference"]
    )
    assert (
        result["calendar_context"]["current_solar_term"]["ephemeris_model"]
        == DE441_MODEL
    )


@pytest.mark.local_data
@pytest.mark.parametrize("case", CASES, ids=lambda row: row["id"])
def test_original_inputs_and_stock_counterexamples_keep_independent_de440_phase(
    case,
) -> None:
    source = SOURCE_CASES[case["id"]]
    assert source["input"] == case["input"]
    assert source["stock_native_month_branch"] == case["native_month_branch"]
    assert source["stock_month_changed"] is case["month_changed"]
    reference_path = Path(__file__).parents[2] / SOURCE["reference_path"]
    raw = reference_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE["reference_original_bytes_sha256"]
    packet = json.loads(gzip.decompress(raw))
    original = next(
        row
        for row in packet["rows"]
        if row["year"] == 1972 and row["index"] == case["term_index"]
    )
    assert source["original_reference_row"] == original
    clock = datetime.fromisoformat(case["input"]["date"] + "T" + case["input"]["time"])
    utc = erfa.dtf2d(
        "UTC",
        clock.year,
        clock.month,
        clock.day,
        clock.hour,
        clock.minute,
        clock.second + clock.microsecond / 1e6,
    )
    expected_tai_minus_utc = 11 if clock.month >= 7 else 10
    assert erfa.dat(clock.year, clock.month, clock.day, 0) == expected_tai_minus_utc
    assert source["tt_minus_utc_seconds"] == expected_tai_minus_utc + 32.184
    tt1, tt2 = erfa.taitt(*erfa.utctai(*utc))
    delta = float(((tt1 - original["jd_tt"]) + tt2) * 86400)
    assert delta == pytest.approx(source["input_minus_reference_seconds"], abs=1e-9)
    assert (delta >= 0) is source["reference_has_passed"]
    expected_month = (
        source["month_branch_after"] if delta >= 0 else source["month_branch_before"]
    )
    assert expected_month == source["current_month_branch_from_reference"]
    assert source["stock_month_matches_reference"] is (case["id"] == "1972-07")
