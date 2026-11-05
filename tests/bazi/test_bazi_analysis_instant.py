"""Current means the frozen instant, including offset, fold and subminute time."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.execution_context import call_clock
from fatebridge.core.output_timing import AnalysisReference
from fatebridge.core.reproducibility import BAZI_ANALYSIS_CLOCK_TOOLS
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.timing_clock import DATE_FIELDS, resolve_analysis_moment

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_analysis_instant_v1"


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
def test_all_absent_components_keep_one_complete_execution_instant(tool):
    with call_clock("2025-02-04T04:37:49.123456Z") as clock:
        selected = resolve_analysis_moment(tool, "Asia/Shanghai")
        assert selected.moment.isoformat() == "2025-02-04T12:37:49.123456+08:00"
        assert selected.reference["utc_datetime"] == "2025-02-04T04:37:49.123456+00:00"
        assert selected.reference["basis"] == "implicit_execution_clock"
        assert selected.reference["defaulted_from_clock"] == list(DATE_FIELDS)
        assert selected.reference["fixed_defaults"] == {}
        assert clock.reads == ["Asia/Shanghai"]


@pytest.mark.parametrize(
    "tool,expected,clock_fields",
    [
        ("timing_analysis", "2028-04-01T00:00:00", []),
        ("dayun_analysis", "2028-04-01T00:00:00", []),
        ("liuyue_analysis", "2028-04-15T00:00:00", []),
        ("liuri_analysis", "2028-04-20T00:00:00", ["analysis_day"]),
        ("liushi_analysis", "2028-04-20T12:00:00", ["analysis_day", "analysis_hour"]),
    ],
)
def test_explicit_partial_inputs_keep_their_declared_completion_policy(
    tool, expected, clock_fields
):
    with call_clock("2025-03-20T04:37:49Z") as clock:
        selected = resolve_analysis_moment(
            tool, "Asia/Shanghai", analysis_year=2028, analysis_month=4
        )
        assert selected.moment.isoformat() == expected
        assert selected.reference["defaulted_from_clock"] == clock_fields
        assert selected.reference["basis"] == "declared_partial_components"
        assert bool(clock.reads) is bool(clock_fields)


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
def test_explicit_zero_hour_and_minute_are_not_replaced_by_now(tool):
    with call_clock("2025-03-20T04:37:49Z") as clock:
        selected = resolve_analysis_moment(
            tool,
            "Asia/Shanghai",
            analysis_year=2025,
            analysis_month=3,
            analysis_day=20,
            analysis_hour=0,
            analysis_minute=0,
        )
        assert selected.moment == datetime(2025, 3, 20)
        assert selected.reference["basis"] == "explicit_components"
        assert selected.reference["provided_fields"] == list(DATE_FIELDS)
        assert clock.reads == []


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
@pytest.mark.parametrize(
    "month,day,hour,token", [(3, 9, 2, "nonexistent"), (11, 2, 1, "ambiguous")]
)
def test_explicit_analysis_clock_never_silently_picks_a_fold_or_gap(
    tool, month, day, hour, token
):
    with pytest.raises(ValueError, match=token):
        resolve_analysis_moment(
            tool,
            "America/New_York",
            analysis_year=2025,
            analysis_month=month,
            analysis_day=day,
            analysis_hour=hour,
            analysis_minute=30,
        )


def test_known_as_of_instants_keep_both_folds_and_distinct_cached_month_day_windows():
    moments = []
    for stamp in ["2025-11-02T05:30:00Z", "2025-11-02T06:30:00Z"]:
        with call_clock(stamp):
            selected = resolve_analysis_moment("timing_analysis", "America/New_York")
        moments.append(selected.moment)
    assert [m.fold for m in moments] == [0, 1]
    assert [m.isoformat() for m in moments] == [
        "2025-11-02T01:30:00-04:00",
        "2025-11-02T01:30:00-05:00",
    ]
    assert moments[1].astimezone(timezone.utc) - moments[0].astimezone(
        timezone.utc
    ) == timedelta(hours=1)
    # Python same-zone datetime keys compare equal across these folds.
    assert moments[0] == moments[1]
    for kind in ("month", "day"):
        results = [
            (
                TimingAnalysis.calculate_liuyue(2025, 11, 2, "America/New_York", moment)
                if kind == "month"
                else TimingAnalysis.calculate_liuri(moment, "America/New_York")
            )
            for moment in moments
        ]
        first, second = [r["solar_term_window"]["days_since_start"] for r in results]
        assert second - first == pytest.approx(1 / 24, abs=0.0001)
        assert results[0]["pillar"] == results[1]["pillar"]


def test_clock_contract_stays_projectable_and_fold_bounds_are_validated():
    AnalysisReference.model_validate({"basis": "implicit_execution_clock"})
    AnalysisReference.model_validate({"utc_datetime": "2025-02-04T04:37:49+00:00"})
    with pytest.raises(ValidationError):
        AnalysisReference.model_validate({"fold": 2})


def test_supplemental_day_and_term_witnesses_keep_their_original_source_hashes():
    path = FIXTURE / "date-side-witnesses.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    witnesses = json.loads(path.read_text())
    for ref in witnesses["sources"].values():
        assert (
            hashlib.sha256((ROOT / ref["path"]).read_bytes()).hexdigest()
            == ref["sha256"]
        )
    assert witnesses["sources"]["day_reference"]["row"]["literal"] == "初三庚午"
