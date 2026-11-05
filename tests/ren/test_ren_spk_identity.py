"""SPK boundaries cannot borrow native Swiss calculation return flags."""

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.services.metaphysics import _build_analysis_seed

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/ren_spk_identity_v1"
FREEZE_SHA = "f5d7c56917e80db0d7c89c2cf48fefdaa6ba57f8c5aec08391845341c535d64e"


def reference(folder=FIXTURE):
    assert (
        hashlib.sha256((folder / "freeze.json").read_bytes()).hexdigest() == FREEZE_SHA
    )
    manifest = json.loads((folder / "freeze.json").read_text())
    assert set(p.name for p in folder.iterdir()) == {"protocol.json", "freeze.json"}
    assert manifest["files"] == {
        "protocol.json": hashlib.sha256(
            (folder / "protocol.json").read_bytes()
        ).hexdigest()
    }
    return json.loads((folder / "protocol.json").read_text())


PROTOCOL = reference()


def test_identity_fault_protocol_is_frozen(tmp_path):
    assert len(PROTOCOL["cases"]) == 3
    assert PROTOCOL["new_astronomical_events"] == 0
    assert PROTOCOL["new_model_processes"] == 0
    assert PROTOCOL["full_goal_complete"] is False
    target = tmp_path / "corpus"
    shutil.copytree(FIXTURE, target)
    (target / "extra.json").write_text("{}")
    with pytest.raises(AssertionError):
        reference(target)


@pytest.fixture
def actual_spk(monkeypatch, tmp_path):
    pytest.importorskip("erfa")
    pytest.importorskip("jplephem")
    kernel = ROOT / "ephe/solar-de440.bsp"
    if not kernel.exists():
        pytest.skip("Explicit external DE440 kernel unavailable")
    assert hashlib.sha256(kernel.read_bytes()).hexdigest() == (
        "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
    )
    previous = configured_ephemeris_path()
    try:
        with monkeypatch.context() as environment:
            environment.setenv("SE_EPHE_PATH", str(tmp_path))
            environment.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "spk")
            environment.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(kernel))
            environment.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            yield _build_analysis_seed(
                analysis_year=2026,
                analysis_month=4,
                analysis_day=4,
                analysis_hour=12,
                analysis_timezone="UTC",
                use_true_solar_time=False,
            )
    finally:
        configure_ephemeris_path(previous)


def test_valid_actual_spk_dependencies_keep_empty_native_flags(actual_spk):
    policy = ren_calendar.require_ren_calendar(actual_spk)
    assert all(
        v["provider"] == "jpl_spk" and v["ephemeris_retflags"] == []
        for v in policy["solar_term_dependencies"]
    )


@pytest.mark.parametrize("case", PROTOCOL["cases"], ids=lambda c: c["id"])
def test_spk_cannot_borrow_native_return_flags(case, actual_spk, monkeypatch):
    original = ren_calendar.get_adjacent_solar_terms

    def wrong_receipt(*args, **kwargs):
        return tuple(
            replace(term, ephemeris_retflags=tuple(case["flags"]))
            for term in original(*args, **kwargs)
        )

    monkeypatch.setattr(ren_calendar, "get_adjacent_solar_terms", wrong_receipt)
    with pytest.raises(RuntimeError, match="原生星历返回标志"):
        ren_calendar.require_ren_calendar(actual_spk)
