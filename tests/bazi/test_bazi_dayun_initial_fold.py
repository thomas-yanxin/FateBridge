"""Initial calendar offsets respect a confirmed physical birth instant."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.timezones import parse_timezone_name
from tests.evaluation.test_agentic_nested_outputs import SPECS, business, native
from tests.evaluation.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/data/bazi/dayun-fold-magnitudes.json").read_text()
)


@pytest.mark.parametrize("row", REFERENCE, ids=lambda row: row["zone"])
@pytest.mark.parametrize("fold", [0, 1])
@pytest.mark.parametrize("step", [0, 1, 2])
def test_all_registered_fold_magnitudes_with_nonnegative_calendar_offsets(
    row, fold, step, monkeypatch
):
    # Offsets are artificial calendar-policy controls. Birth instants and all
    # 111 rollback magnitudes come from the existing independently compiled
    # IANA reference, not from the candidate solver.
    selected = row["expected"][fold]
    birth_utc = datetime.fromisoformat(selected["utc"])
    birth = birth_utc.astimezone(parse_timezone_name(row["zone"]))
    assert birth.fold == fold
    seconds = [0, 1, min(60, abs(row["shift_seconds"]) // 4)][step]
    elapsed = seconds / 120
    details = {
        "elapsed_seconds": elapsed,
        "start_age_unrounded": elapsed / 86400 / 3,
        "year_stem": "甲",
    }
    monkeypatch.setattr(
        TimingAnalysis,
        "calculate_dayun_start_details",
        staticmethod(lambda *args: details),
    )
    current = TimingAnalysis.calculate_dayun_timeline(
        birth, "女", ("丙", "寅"), row["zone"], periods=3
    )
    expected = birth_utc + timedelta(seconds=seconds)
    assert (
        datetime.fromisoformat(current["start_at"]).astimezone(timezone.utc) == expected
    )
    assert current["periods"][0]["start_at"] == current["start_at"]
    for period in current["periods"]:
        assert datetime.fromisoformat(period["end_at"]).astimezone(
            timezone.utc
        ) > datetime.fromisoformat(period["start_at"]).astimezone(timezone.utc)
    assert current["dst_policy"] == (
        "fold_0_gap_forward_initial_not_before_birth" if fold else "fold_0_gap_forward"
    )


def test_actual_havana_positive_interval_no_longer_starts_before_birth():
    birth = datetime(
        1972, 10, 7, 23, 41, 46, tzinfo=parse_timezone_name("America/Havana"), fold=1
    )
    value = TimingAnalysis.calculate_dayun_timeline(
        birth, "女", ("庚", "戌"), "America/Havana", periods=2
    )
    assert 0 < value["start_details"]["elapsed_seconds"] < 2
    start = datetime.fromisoformat(value["start_at"])
    assert start.utcoffset() == timedelta(hours=-5)
    assert start.astimezone(timezone.utc) > birth.astimezone(timezone.utc)


@lru_cache(maxsize=1)
def public_rows():
    return json.loads((ROOT / "tests/data/bazi/dayun-consumers.json").read_text())


@lru_cache(maxsize=4)
def current_dayun_control(index):
    row = public_rows()[index]
    assert row["tool"] == "dayun_analysis"
    spec = SPECS[row["tool"]]
    complete = execute_tool(
        spec,
        spec.request_model(**row["arguments"]),
        options=ExecutionOptions(as_of=row["as_of"]),
        include_metadata=False,
    )
    return complete


@pytest.mark.parametrize("index", range(41))
def test_complete_business_results_match_rest_native_mcp_and_cli(
    index, rest, tmp_path, capsys
):
    row = public_rows()[index]
    spec = SPECS[row["tool"]]
    payload = row["arguments"]
    protocol = asyncio.run(
        native(
            spec,
            payload,
            as_of=row["as_of"],
            include_snapshot_text=True,
            response_char_limit=0,
        )
    )
    # The common CLI helper uses a fixed as_of; preserve that helper and pass
    # the actual clock explicitly through the CLI entry for this fixture.
    from fatebridge.cli import run

    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload, ensure_ascii=False))
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(subject),
            "--as-of",
            row["as_of"],
            "--response-char-limit",
            "0",
            "--include-snapshot-text",
        ]
    )
    local = json.loads(capsys.readouterr().out)
    assert code == 0 and not protocol.is_error
    complete = business(local)
    assert complete == business(protocol.structured_content)
    # Every consumer must use the same current timeline and confirmed birth clock.
    control_index = 12 if index < 13 else 25 if index < 26 else 38 if index < 39 else 40
    control = current_dayun_control(control_index)
    if spec.key == "analyze_destiny":
        # This natal-only envelope has no dayun selection. Its complete birth
        # calendar, including the confirmed UTC/fold and reference term, is
        # the input consumed by the independently hash-pinned dayun control.
        assert complete["calendar_context"] == control["calendar_context"]
        assert complete["person_info"]["birth_timezone"] == (
            control["timing_context"]["timeline"]["timezone"]
        )
    elif spec.key == "dayun_analysis":
        assert complete == control
    elif spec.key == "timing_analysis":
        assert complete["dayun_analysis"]["timing_context"] == control["timing_context"]
        if control["dayun_info"]["current_dayun"] is not None:
            for key, value in control["dayun_info"].items():
                assert complete["dayun_analysis"][key] == value
        else:
            assert (
                complete["dayun_analysis"]["status"] == control["dayun_info"]["status"]
            )
            assert complete["dayun_analysis"]["error"] == control["summary"]
    elif spec.key == "bazi_birth":
        dayun = complete["bazi_birth"]["timing_overview"]["dayun"]
        expected = control["dayun_info"]
        for key in dayun.keys() - {"pillar", "summary"}:
            assert dayun[key] == expected[key]
        assert dayun["pillar"] == expected["current_dayun"]
    elif spec.key.startswith("bazi_"):
        context = complete[spec.key.removeprefix("bazi_") + "_analysis"][
            "timing_context"
        ]
        expected = control["dayun_info"]
        for key in ("dayun_age", "selection_basis", "start_at", "end_at"):
            name = key if key == "dayun_age" else "dayun_" + key
            assert context[name] == expected[key]
        assert context["dayun_pillar"] == expected["current_dayun"]
    else:
        pytest.fail("Unreviewed initial-fold consumer: " + spec.key)
    if spec.rest_path is not None:
        http = rest.post(
            spec.rest_path,
            json=payload,
            params={
                "as_of": row["as_of"],
                "response_char_limit": 0,
                "include_snapshot_text": True,
            },
        )
        assert http.status_code == 200
        assert business(http.json()) == complete
