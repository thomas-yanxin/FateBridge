"""Preserve real source transitions and reject unrequested lunation frames."""

import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import classical, runtime
from fatebridge.utils.errors import EphemerisSourceError
from tests.native_syzygy_witness import NativeSourceWitness
from tests.syzygy_source_profiles import PROTOCOL as PROFILE_PROTOCOL
from tests.syzygy_source_profiles import (  # noqa: F401
    syzygy_profile_directories,
    syzygy_source_profile,
)

FIXTURE = Path(__file__).parent / "fixtures/western-syzygy-source-v1"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
BEFORE = json.loads((FIXTURE / "before.json").read_text())["rows"]


@pytest.fixture(scope="module")
def prior_classical():
    # Compare a change within one native runtime. The initial cross-platform
    # bitwise comparisons and their four failures remain in the audit report.
    path = FIXTURE / "classical-before.py.txt"
    receipt = json.loads((FIXTURE / "replay-reference.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["old_source_sha256"]
    loader = importlib.machinery.SourceFileLoader("prior_lunation_source", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("row", BEFORE)
@pytest.mark.parametrize(
    "syzygy_source_profile", ["recorded5", "full37", "empty0"], indirect=True
)
def test_valid_numeric_results_remain_exactly_equal_to_before(
    row, prior_classical, syzygy_source_profile
):
    with runtime.preserve_ephemeris_path():
        previous = prior_classical._prenatal_syzygy(
            row["jd_ut1"], julian_day_tt=row["jd_tt"], sidereal=row["sidereal"]
        )
    with runtime.preserve_ephemeris_path():
        result = classical._prenatal_syzygy(
            row["jd_ut1"], julian_day_tt=row["jd_tt"], sidereal=row["sidereal"]
        )
    if result is not None:
        result = {
            k: v
            for k, v in result.items()
            if k not in {"ephemeris_source", "utc_representation"}
        }
    assert result == previous


@pytest.mark.parametrize("row", [r for r in BEFORE if r["result"] is not None])
def test_search_receipt_preserves_all_actual_observed_models(
    row, syzygy_source_profile
):
    result = classical._prenatal_syzygy(
        row["jd_ut1"], julian_day_tt=row["jd_tt"], sidereal=row["sidereal"]
    )
    receipt = result["ephemeris_source"]
    expected = {
        body: sorted({c["model"] for c in row["calls"] if c["body"] == body})
        for body in ["Sun", "Moon"]
    }
    assert receipt["models_by_body"] == expected
    assert receipt["models_stable"] == all(len(v) == 1 for v in expected.values())
    assert receipt["absolute_accuracy_certified"] is False
    assert sum(c["sample_count"] for c in receipt["sample_contexts"]) == len(
        row["calls"]
    )
    if row["date"] == [1800, 1, 10]:
        assert not receipt["models_stable"]
        assert expected == {"Sun": ["moshier", "swieph"], "Moon": ["moshier", "swieph"]}
    for context in receipt["sample_contexts"]:
        assert context["minimum_jd_tt"] <= context["maximum_jd_tt"]
        if context["model"] == "moshier":
            assert context["file_ids"] == []  # Do not borrow stale Swiss slots.


@pytest.mark.parametrize("index", range(len(BEFORE)))
@pytest.mark.parametrize(
    "syzygy_source_profile", ["recorded5", "full37", "empty0"], indirect=True
)
def test_every_source_context_matches_the_actual_native_call(
    index, syzygy_source_profile
):
    row = BEFORE[index]
    expected = next(
        r
        for r in PROFILE_PROTOCOL["case_outcomes"]
        if (r["profile"], r["kind"], r["index"])
        == (syzygy_source_profile, "source", index)
    )
    witness = NativeSourceWitness(runtime)
    with witness.observe():
        result = classical._prenatal_syzygy(
            row["jd_ut1"], julian_day_tt=row["jd_tt"], sidereal=row["sidereal"]
        )
    assert (result is None) == (expected["status"] == "no_result")
    if result is not None:
        witness.assert_matches(result)
        assert (
            result["ephemeris_source"]["models_by_body"] == expected["models_by_body"]
        )
    assert len(witness.entries) == expected["native_call_count"]


@pytest.mark.parametrize("body", ["SUN", "MOON"])
@pytest.mark.parametrize("flag_name", PROTOCOL["frame_fault_names"])
def test_lunation_helper_rejects_unrequested_frames(body, flag_name, monkeypatch):
    original = runtime.ephemeris_call

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        return values, flags | getattr(runtime.swe, flag_name)

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError, match="coordinate frame"):
        classical._luminary_lon_speed(2461045.0, getattr(runtime.swe, body))


@pytest.mark.parametrize("body", ["SUN", "MOON"])
@pytest.mark.parametrize("fault", PROTOCOL["motion_faults"])
def test_lunation_helper_rejects_missing_or_invalid_motion(body, fault, monkeypatch):
    original = runtime.ephemeris_call

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        values = list(values)
        if fault == "missing_speed_flag":
            flags &= ~runtime.swe.FLG_SPEED
        elif fault == "truncated_coordinates":
            values = values[:3]
        else:
            values[3] = float("nan" if fault == "nan_speed" else "inf")
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError):
        classical._luminary_lon_speed(2461045.0, getattr(runtime.swe, body))


@pytest.mark.parametrize("reason", ["coordinate_contract_changed", "changed_during"])
def test_optional_lunation_never_hides_a_source_integrity_error(reason, monkeypatch):
    def broken(*args, **kwargs):
        raise EphemerisSourceError(reason)

    monkeypatch.setattr(runtime, "ephemeris_call", broken)
    with pytest.raises(EphemerisSourceError) as error:
        classical._prenatal_syzygy(2461045.0, julian_day_tt=2461045.0)
    assert error.value.reason == reason


def test_lahiri_event_display_rejects_a_different_native_frame(monkeypatch):
    original = runtime.ephemeris_call
    changed = []

    def fault(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[2] & runtime.swe.FLG_SIDEREAL:
            changed.append(args[0])
            return result[0], result[1] | runtime.swe.FLG_EQUATORIAL
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", fault)
    with pytest.raises(EphemerisSourceError) as error:
        classical._prenatal_syzygy(2461045.0, julian_day_tt=2461045.0, sidereal=True)
    assert error.value.reason == "coordinate_contract_changed" and changed
