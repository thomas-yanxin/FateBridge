"""Pre-edit source controls and preservation of caller-owned native settings."""

import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core import compressed_ephemeris as context
from fatebridge.core import ephemeris_runtime as e
from fatebridge.utils.errors import EphemerisSourceError
from tests.unit_test.fixtures.jyotish_sources import restore_runtime  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/solar-common-window-reference-v1.json").read_text()
)


def test_original_sun_request_uses_frozen_common_window() -> None:
    for owned in (False, True):
        for row in REFERENCE["rows"]:
            e.configure_ephemeris_path(str(ROOT / "ephe"))
            e.swe.set_ephe_path(str(ROOT / "ephe"))
            e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
            if owned:
                with context.audit_compressed_endpoints():
                    values, flags = e.ephemeris_call(
                        "calc", row["epoch"], e.swe.SUN, row["requested_flags"]
                    )
                    receipt = context.coordinate_context_evidence()
            else:
                values, flags = e.ephemeris_call(
                    "calc", row["epoch"], e.swe.SUN, row["requested_flags"]
                )
                receipt = context.coordinate_context_evidence()
            assert flags == row["returned_flags"]
            assert values == pytest.approx(
                row["coherent"],
                abs=REFERENCE["comparison_absolute_tolerance"],
                rel=REFERENCE["comparison_relative_tolerance"],
            )
            assert receipt["private_native_cache_reset"] is owned
            assert receipt["input_julian_day"] == row["epoch"]
            assert receipt["physical_instant_shifted"] is False
            assert receipt["selected_native_state"] == list(values)
            assert [
                [w["filename"], w["start_jd_tt"], w["end_jd_tt"], w["de_number"]]
                for w in receipt["selected_windows"]
            ] == row["selected_windows"]
            path = receipt["solar_light_path"]
            assert path["requested_coordinate_flags"] == row["requested_flags"]
            assert len(path["retarded_epochs_jd_tt"]) == 2
            assert all(
                w["start_jd_tt"]
                <= min(path["retarded_epochs_jd_tt"])
                <= row["epoch"]
                <= w["end_jd_tt"]
                for w in path["selected_windows"]
            )


def test_actual_native_fallback_is_not_relabelled(tmp_path: Path) -> None:
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
    at = 2378496.500215332
    for index, files in enumerate(([], ["sepl_18.se1", "semo_18.se1"])):
        case_dir = tmp_path / f"case_{index}"
        case_dir.mkdir()
        for name in files:
            shutil.copy2(ROOT / "ephe" / name, case_dir / name)
        for operation in ("calc", "calc_ut"):
            e.configure_ephemeris_path(str(case_dir))
            e.swe.set_ephe_path(str(case_dir))
            expected = getattr(e.swe, operation)(at, e.swe.SUN, flags)
            assert expected[1] & 7 == e.swe.FLG_MOSEPH
            e.swe.set_ephe_path(str(case_dir))
            actual = e.ephemeris_call(operation, at, e.swe.SUN, flags)
            assert actual == expected
            assert context.coordinate_context_evidence() is None


def test_other_solar_definitions_keep_original_native_result() -> None:
    at = 2378496.500215332
    for flag in (16, 16384, 8, 32768, 128, 1048576):
        e.configure_ephemeris_path(str(ROOT / "ephe"))
        e.swe.set_ephe_path(str(ROOT / "ephe"))
        e.swe.set_topo(73.0, 40.0, 100.0)
        flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | flag
        expected = e.swe.calc(at, e.swe.SUN, flags)
        e.swe.set_ephe_path(str(ROOT / "ephe"))
        assert e.ephemeris_call("calc", at, e.swe.SUN, flags) == expected
        assert context.coordinate_context_evidence() is None


def test_external_rebuild_does_not_reset_native_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    e.ephemeris_call("deltat_ex", 2378496.5, e.swe.FLG_SWIEPH)
    e.swe.set_sid_mode(e.swe.SIDM_KRISHNAMURTI, 0, 0)
    e.swe.set_delta_t_userdef(0.000123)
    expected = e.swe.get_ayanamsa_ex(2378496.5, e.swe.FLG_SWIEPH)

    def forbidden(*args):
        raise AssertionError("Caller configuration was reset")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(e.swe, "set_ephe_path", forbidden)
            values, flags = e.ephemeris_call(
                "calc_ut",
                2378496.5,
                e.swe.SUN,
                e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL,
            )
            assert flags & 7 == e.swe.FLG_SWIEPH and len(values) == 6
            assert e.swe.deltat_ex(2378496.5, e.swe.FLG_SWIEPH) == 0.000123
            assert e.swe.get_ayanamsa_ex(2378496.5, e.swe.FLG_SWIEPH) == expected
            assert (
                context.coordinate_context_evidence()["private_native_cache_reset"]
                is False
            )
    finally:
        e.swe.set_delta_t_userdef(e.swe.DELTAT_AUTOMATIC)


def test_changed_dependency_window_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    original = context._solar_light_path

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result["selected_windows"] = [
            {**w, "end_jd_tt": w["end_jd_tt"] - 1.0} for w in result["selected_windows"]
        ]
        return result

    monkeypatch.setattr(context, "_solar_light_path", changed)
    with pytest.raises(EphemerisSourceError) as error:
        e.ephemeris_call(
            "calc", 2378496.500215332, e.swe.SUN, e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
        )
    assert error.value.reason == "dependency_source_window_incoherent"
