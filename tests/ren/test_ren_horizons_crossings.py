"""Independent solar events, missing historical EOP and explicit frame identity."""

import asyncio
import importlib.util
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_fault,
)
from tests.ren.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ren_horizons_crossing_audit", ROOT / "scripts/ren/audit_ren_horizons_crossings.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_raw_jpl_probes_reconstruct_the_complete_frozen_diagnostic_cohort():
    frozen = AUDIT.reference()
    cases = frozen["reference"]["cases"]
    assert len(cases) == 113
    assert sum(c["dut1_seconds"] is None for c in cases) == 33
    assert {
        (c["year"], c["term"])
        for c in cases
        if not c["within_original_printed_minute_criterion"]
    } == {(2011, "夏至"), (2014, "寒露"), (2025, "春分")}
    assert frozen["prior"]["original_full_failure_count"] == 21
    assert not frozen["reference"]["physical_accuracy_certified"]
    assert not frozen["reference"]["goal_complete"]


def test_actual_audit_retains_both_frames_and_original_thresholds():
    report = AUDIT.audit()
    assert report["expected_count"] == report["compared_count"] == 113
    assert not report["calculation_errors"]
    assert not report["implementation_changed_during_audit"]
    assert report["criteria"]["existing_printed_minute_absolute_seconds"] == 30
    assert report["criteria"]["existing_coordinate_absolute_arcseconds"] == 0.1
    assert report["pmo_minute_failure_count"] == sum(
        not row["within_original_printed_minute_criterion"]
        for row in report["comparisons"]
    )
    assert report["cross_frame_coordinate_failure_count"] == sum(
        max(
            abs(row["longitude_error_same_label_arcseconds"]),
            abs(row["latitude_error_same_label_arcseconds"]),
        )
        > 0.1
        for row in report["comparisons"]
    )
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["classical_acceptance_passed"] and not report["goal_complete"]


def test_complete_solver_failure_keeps_all_113_errors(monkeypatch):
    from fatebridge.core import almanac

    monkeypatch.setattr(almanac, "get_solar_terms_for_year", lambda *a, **kw: [])
    report = AUDIT.audit()
    assert report["expected_count"] == 113 and report["compared_count"] == 0
    assert len(report["calculation_errors"]) == 113
    assert not report["all_performed_comparisons_passed"]


def test_stale_native_file_receipt_preserves_all_errors_without_crashing(
    monkeypatch, tmp_path
):
    from fatebridge.core import almanac
    from fatebridge.core.ephemeris_runtime import swe

    monkeypatch.setattr(almanac, "get_solar_terms_for_year", lambda *a, **kw: [])
    missing = tmp_path / "no-longer-present.se1"
    monkeypatch.setattr(
        swe, "get_current_file_data", lambda *a: (str(missing), 1.0, 2.0, 431)
    )
    report = AUDIT.audit()
    assert len(report["calculation_errors"]) == 113
    assert report["native_file_receipt_error"]["error_type"] == "FileNotFoundError"
    assert report["planet_file"]["sha256"] is None
    assert not report["all_performed_comparisons_passed"]


def test_frozen_source_tampering_is_rejected(tmp_path):
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    path = corpus / "collection/initial-post-short/batch-00.response.json"
    path.write_text(path.read_text() + "modified")
    with pytest.raises(ValueError, match="Frozen JPL source changed"):
        AUDIT.reference(corpus)


def test_opposite_side_wrap_and_unbracketed_probes_cannot_become_crossings():
    samples = [
        {"timestamp_label": "2000-01-01 12:00:00", "ObsEcLon": 179.999},
        {"timestamp_label": "2000-01-01 12:01:00", "ObsEcLon": 180.001},
    ]
    with pytest.raises(ValueError, match="monotonically"):
        AUDIT.interpolate(samples, 0)
    with pytest.raises(ValueError, match="exactly one crossing"):
        AUDIT.interpolate(samples, 90)
    samples[0]["ObsEcLon"], samples[1]["ObsEcLon"] = 359.999, 0.001
    crossing, _ = AUDIT.interpolate(samples, 0)
    assert crossing.isoformat() == "2000-01-01T12:00:30"


@pytest.mark.parametrize("flags", [(), (32770,), (34,), (18,)])
def test_unverified_geometry_cannot_receive_the_default_definition(flags, monkeypatch):
    from fatebridge.core.metaphysics import ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    original = ren_calendar.get_adjacent_solar_terms

    def different_geometry(*args, **kwargs):
        return tuple(
            replace(term, ephemeris_retflags=flags)
            for term in original(*args, **kwargs)
        )

    monkeypatch.setattr(ren_calendar, "get_adjacent_solar_terms", different_geometry)
    seed = _build_analysis_seed(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    with pytest.raises(RuntimeError, match="黄经选项未知"):
        ren_calendar.require_ren_calendar(seed)


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("mode", ["native", "de440"])
def test_actual_coordinate_definition_survives_all_surfaces(
    key, project, mode, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    spec = SPECS[key]
    payload = {**PAYLOAD}
    if key == "jinkou":
        payload["di_fen"] = "酉"
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    root = "jinkou" if key == "jinkou" else "liureng"
    field = f"{root}.calendar_policy.solar_longitude_definition"
    params = [("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [
            ("fields", field),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            field,
        ]
        options = dict(fields=[field], strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        definition = body[root]["calendar_policy"]["solar_longitude_definition"]
        assert definition["origin"] == "geocentric"
        assert definition["position"] == "apparent"
        assert definition["plane"] == "ecliptic_of_date"
        assert definition["equinox"] == "true_of_date"
        assert definition["horizons_frame_equivalence_certified"] is False
        if mode == "native":
            assert definition["source_section"].startswith("3.3.5")
            assert "IAU76/80" in definition["scope"]
        else:
            assert "DE440" in definition["source_section"]
            assert "IAU2006/P03 and IAU2000B" in definition["source_section"]
            assert "原始内核来源不等于运行时加载了完整SPK" in definition["scope"]


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize(
    "fault", [{"horizons_frame_equivalence_certified": True}, {"origin": "topocentric"}]
)
def test_wrong_reference_frame_claim_is_rejected_before_projection(
    key, fault, rest, monkeypatch, tmp_path, capsys
):
    root = "jinkou" if key == "jinkou" else "liureng"
    payload = {root: {"calendar_policy": {"solar_longitude_definition": fault}}}
    reject_fault(key, payload, rest, monkeypatch, tmp_path, capsys)
