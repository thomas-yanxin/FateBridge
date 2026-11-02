"""Actual native-selected roots, error closure and truthful source metadata."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac, solar_term_clock
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-native-solar-point-v1"


def read(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    raw = (
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )
    return json.loads(raw)


def test_all6391_requested_inputs_and_actual_selected_roots_are_retained():
    before = read("native-control-before-first.json.gz")
    after = read("native-control-after-second.json.gz")
    reference = read("selected-reference-first.json.gz")
    assert len(before["rows"]) == len(after["rows"]) == len(reference["rows"]) == 6391
    counts = {
        "normal": 0,
        "unrepresentable_utc_label": 0,
        "pre_atomic_policy_unadjudicated": 0,
    }
    for old, new, expected in zip(
        before["rows"], after["rows"], reference["rows"], strict=True
    ):
        assert (
            old["original_reference"]
            == new["original_reference"]
            == expected["original_reference"]
        )
        assert (
            old["actual_selected_jd_tt"]
            == new["actual_selected_jd_tt"]
            == expected["actual_selected_jd_tt"]
        )
        counts[expected["selected_point_status"]] += 1
        if expected["selected_point_status"] == "normal":
            assert new["actual_datetime_utc"] == expected["expected_datetime_utc"]
            details = new["provenance"]["solar_model_details"]
            assert (
                details["selected_crossing_jd_tt"] == expected["actual_selected_jd_tt"]
            )
            assert details["ephemeris_model"] == "moshier"
            assert details["ephemeris_retflags"] == [4]
            assert details["accuracy_certified"] is False
        elif expected["selected_point_status"] == "unrepresentable_utc_label":
            assert new["structured_error"]["issues"] == [
                {
                    "path": "runtime.solar_term_clock",
                    "code": "solar_root_civil_unrepresentable",
                }
            ]
            assert new["structured_error"]["status_code"] == 503
    assert counts == {
        "normal": 3931,
        "unrepresentable_utc_label": 242,
        "pre_atomic_policy_unadjudicated": 2218,
    }
    assert (
        before["root_equals_requested_count"]
        == after["root_equals_requested_count"]
        == 5644
    )
    assert after["none_outcomes"] == 0


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("private-label-and-path"), "solar_root_civil_unrepresentable"),
        (OverflowError("private-overflow"), "solar_root_civil_unrepresentable"),
        (ImportError("private-dependency-path"), "solar_root_clock_unavailable"),
        (RuntimeError("private-clock-failure"), "solar_root_clock_unavailable"),
    ],
)
def test_known_root_clock_failure_is_bounded_and_cannot_return_none(
    error, reason, monkeypatch
):
    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    result = caught.value.as_result()
    assert result["issues"] == [{"path": "runtime.solar_term_clock", "code": reason}]
    assert "private" not in json.dumps(result)
    assert result["retryable"] is False


def test_original_strict_source_error_is_preserved_not_wrapped(monkeypatch):
    error = EphemerisSourceError("solar_spk_changed")

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(EphemerisSourceError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    assert caught.value is error


def test_all_actual_events_and_native_probe_changes_match_declared_clock_policy():
    result = read("actual-assessment-first.json")
    assert result["counts"]["actual_TT_points_checked"] == 576
    assert result["counts"]["before_point_mismatch"] == 48
    assert result["counts"]["after_point_mismatch"] == 0
    assert result["counts"]["public_native_labels_changed"] == 48
    assert result["counts"]["analytic_native_probe_labels_changed"] == 48
    assert result["counts"]["unchanged_full_auto"] == 144
    assert result["counts"]["unchanged_full_spk"] == 144
    assert result["counts"]["same_run_private_native_receipts_checked"] == 288
    assert not result["unexpected_delta_ids"]
    assert not result["physical_clock_accuracy_certified"]


def test_no_native_engine_and_no_crossing_keep_their_original_unverified_fallback(
    monkeypatch,
):
    anchor = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with monkeypatch.context() as context:
        context.setattr(almanac, "swe", None)
        assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None
    original = almanac.ephemeris_call

    def no_crossing(method, *args, **kwargs):
        if method == "calc":
            return ((120.0, 0, 1, 0, 0, 0), almanac.swe.FLG_MOSEPH)
        return original(method, *args, **kwargs)

    monkeypatch.setattr(almanac, "ephemeris_call", no_crossing)
    assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None


@pytest.mark.parametrize(
    "error", [ValueError("private-time"), ImportError("private-package")]
)
def test_known_native_root_clock_failure_never_becomes_a_linear_year(
    error, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError):
        almanac._calculate_solar_terms_for_year(2000, "UTC")
