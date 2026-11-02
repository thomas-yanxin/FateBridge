"""Initial calendar offsets respect a confirmed physical birth instant."""

import asyncio
import gzip
import hashlib
import json
import tarfile
import types
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest

from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.timezones import parse_timezone_name
from tests.test_agentic_nested_outputs import SPECS, business, native
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_dayun_initial_fold_v1"
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/bazi_birth_fold_v1/coupled-reference.json").read_bytes()
)["magnitude_rows"]


@lru_cache(maxsize=1)
def legacy():
    with tarfile.open(FIXTURE / "before-runtime-source.tar.gz") as archive:
        source = archive.extractfile("src/fatebridge/core/timing.py").read()
    module = types.ModuleType("fatebridge.core._initial_fold_before")
    module.__package__ = "fatebridge.core"
    exec(compile(source, "initial_fold_before.py", "exec"), module.__dict__)
    return module.TimingAnalysis


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
    for cls in [TimingAnalysis, legacy()]:
        monkeypatch.setattr(
            cls, "calculate_dayun_start_details", staticmethod(lambda *args: details)
        )
    current, previous = [
        cls.calculate_dayun_timeline(birth, "女", ("丙", "寅"), row["zone"], periods=3)
        for cls in [TimingAnalysis, legacy()]
    ]
    expected = birth_utc + timedelta(seconds=seconds)
    assert (
        datetime.fromisoformat(current["start_at"]).astimezone(timezone.utc) == expected
    )
    assert current["periods"][0]["start_at"] == current["start_at"]
    assert current["calendar_offset"] == previous["calendar_offset"]
    assert current["start_details"] == previous["start_details"]
    assert current["periods"][1:] == previous["periods"][1:]
    assert current["periods"][0]["end_at"] == previous["periods"][0]["end_at"]
    if fold == 0:
        assert current == previous
    else:
        assert (
            datetime.fromisoformat(previous["start_at"]).astimezone(timezone.utc)
            < birth_utc
        )
        assert current["dst_policy"] == "fold_0_gap_forward_initial_not_before_birth"


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
    previous = legacy().calculate_dayun_timeline(
        birth, "女", ("庚", "戌"), "America/Havana", periods=2
    )
    assert start.astimezone(timezone.utc) - datetime.fromisoformat(
        previous["start_at"]
    ).astimezone(timezone.utc) == timedelta(hours=1)
    assert value["periods"][1:] == previous["periods"][1:]


@lru_cache(maxsize=1)
def public_rows():
    original = (FIXTURE / "public-after-final.json.gz").read_bytes()
    assert (
        hashlib.sha256(original).hexdigest()
        == "fa553058dab89d7ce41dc72b31403ca4e6d7a33afe1231fd07ee4b5a52e1cb73"
    )
    packed = (
        ROOT / "tests/fixtures/architecture_refactor_v1/dayun41-before-manifest.json"
    ).read_bytes()
    assert (
        hashlib.sha256(packed).hexdigest()
        == "b624e085126650de90412c73d57809c2ddccbebcf5055a2c3c518ff3b86dbde1"
    )
    before = json.loads(packed)["rows"]
    historical = json.loads(gzip.decompress(original))["rows"]
    assert len(before) == len(historical) == 41
    for old, current in zip(historical, before):
        assert all(old[key] == current[key] for key in ("tool", "arguments", "as_of"))
    return before


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
    # No numeric rounding: compare every business leaf to the same-input,
    # same-host result captured from the complete source before this repair.
    encoded = json.dumps(
        complete,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == row["business_sha256"]
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
