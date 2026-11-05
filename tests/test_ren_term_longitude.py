"""A coherent TT receipt must still describe the named Sun crossing."""

import asyncio
import copy
import hashlib
import json
import os
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import validate_output
from fatebridge.core import almanac
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.core.metaphysics.hko_term_dates import published_date_reference
from fatebridge.core.output_chinese import RenTermDependency
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.test_ren_anchors import assert_broken_on_three_ports
from tests.test_ren_term_point import payload_for

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_term_longitude_v1"
PIN = "5ac7cdfe4bb123f8aab1f4c592b819eb1cd5402fe560cb4c0f1b286e33700255"


def reference():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert set(p.name for p in CORPUS.iterdir()) == {
        "freeze.json",
        "reference.json",
        "protocol.json",
    }
    assert all(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() == h
        for n, h in frozen["files"].items()
    )
    return json.loads((CORPUS / "reference.json").read_text())


def test_all24_hko_definitions_are_literal_independent_facts():
    actual = dict(zip(almanac.SOLAR_TERM_NAMES, almanac.SOLAR_TERM_LONGITUDES))
    assert actual == {r["term"]: r["longitude_degrees"] for r in reference()["rows"]}


@pytest.mark.parametrize("fault", ["duplicate", "missing", "unknown"])
def test_root_auditor_cannot_replace_the_registered_inventory_with_easy_rows(fault):
    from scripts.audit_ren_term_longitude import validate_event_inventory

    protocol = dict(profiles=["native_swiss", "de440"], years=[1800, 2200])
    table = dict(rows=[dict(term="春分"), dict(term="冬至")])
    rows = [
        dict(profile=p, year=y, term=dict(name=n["term"]))
        for p in protocol["profiles"]
        for y in protocol["years"]
        for n in table["rows"]
    ]
    assert validate_event_inventory(rows, protocol, table) == 8
    if fault == "duplicate":
        rows[-1] = rows[0]
    elif fault == "missing":
        rows.pop()
    else:
        rows[-1]["year"] = 2026
    with pytest.raises(ValueError, match="inventory"):
        validate_event_inventory(rows, protocol, table)


def term_for(mode, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if mode == "spk":
        pytest.importorskip("erfa")
        pytest.importorskip("jplephem")
        kernel = ROOT / "ephe/solar-de440.bsp"
        assert (
            hashlib.sha256(kernel.read_bytes()).hexdigest()
            == "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
        )
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(kernel))
    return almanac.get_solar_terms_for_year(2026, "UTC")[6]


@pytest.fixture(params=["native", "analytic", "de440", "spk"])
def actual_term(request, monkeypatch):
    return term_for(request.param, monkeypatch)


def coherent_shift(term, *, wide=False):
    d = copy.deepcopy(term.solar_model_details)
    shift = 0.25 if wide else 1.0
    if "selected_crossing_tt_parts" in d:
        d["selected_crossing_tt_parts"][1] += shift
        for i, point in enumerate(d["root_bracket_tt_parts"]):
            point[1] += (-1 if i == 0 else 1) if wide else shift
        d["selected_crossing_jd_tt"] = sum(d["selected_crossing_tt_parts"])
        d["root_bracket_tt"] = [sum(p) for p in d["root_bracket_tt_parts"]]
        d["root_bracket_seconds"] = (
            d["root_bracket_tt_parts"][1][1] - d["root_bracket_tt_parts"][0][1]
        ) * 86400
        point = TTInstant.from_parts(*d["selected_crossing_tt_parts"])
    else:
        d["selected_crossing_jd_tt"] += shift
        d["root_bracket_tt"] = [
            v + ((-1 if i == 0 else 1) if wide else shift)
            for i, v in enumerate(d["root_bracket_tt"])
        ]
        d["root_bracket_seconds"] = (
            d["root_bracket_tt"][1] - d["root_bracket_tt"][0]
        ) * 86400
        point = TTInstant.from_float(d["selected_crossing_jd_tt"])
    return replace(term, moment=datetime_from_tt_point(point), solar_model_details=d)


@pytest.mark.parametrize(
    "fault", ["wrong_name", "unknown_name", "one_day", "wide_bracket"]
)
def test_numerically_coherent_wrong_crossing_is_rejected(actual_term, fault):
    if fault == "wrong_name":
        bad = replace(actual_term, name="立春")
    elif fault == "unknown_name":
        bad = replace(actual_term, name="未知节气")
    else:
        bad = coherent_shift(actual_term, wide=fault == "wide_bracket")
    from fatebridge.core.metaphysics.ren_term_point import validate_term_point

    validate_term_point(bad.solar_model_details, bad.moment, complete=True)
    with pytest.raises(EphemerisSourceError) as caught:
        ren_calendar.require_ren_solar_term(bad)
    assert caught.value.reason == "ren_solar_term_longitude_inconsistent"


def test_valid_actual_model_crossing_remains_accepted(actual_term):
    ren_calendar.require_ren_solar_term(actual_term)


@pytest.mark.parametrize(
    "mode,field", [("analytic", "coefficient_sha256"), ("spk", "kernel_sha256")]
)
def test_angular_observation_must_use_its_own_loaded_source(mode, field, monkeypatch):
    term = term_for(mode, monkeypatch)
    d = {**term.solar_model_details, field: "0" * 64}
    with pytest.raises(EphemerisSourceError):
        ren_calendar.require_ren_solar_term(replace(term, solar_model_details=d))


def dependency(term):
    return dict(
        name=term.name,
        provider=term.resolution_provider,
        ephemeris_model=term.ephemeris_model,
        ephemeris_retflags=list(term.ephemeris_retflags),
        ephemeris_library_version=term.ephemeris_library_version,
        solar_model_details=term.solar_model_details,
        civil_moment=term.moment.isoformat(),
        published_date_reference=published_date_reference(term.name, term.moment),
    )


def test_false_name_with_coherent_official_date_receipt_is_not_enough(actual_term):
    bad = dependency(replace(actual_term, name="立春"))
    assert bad["published_date_reference"]["dates_equal"] is False
    with pytest.raises(ValidationError):
        RenTermDependency.model_validate(bad)


def test_native_moshier_receipt_uses_moshier_when_swiss_files_are_available(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    term = term_for("native", monkeypatch)
    from fatebridge.core.moshier_solar import MODEL_ID

    assert term.ephemeris_model == MODEL_ID
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    ren_calendar.require_ren_solar_term(term)


def test_unrelated_missing_spk_does_not_block_explicit_native_reobservation(
    monkeypatch,
):
    term = term_for("native", monkeypatch)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "spk")
    monkeypatch.setenv(
        "FATEBRIDGE_SOLAR_SPK_FILE", "/nonexistent/not-the-native-source.bsp"
    )
    ren_calendar.require_ren_solar_term(term)


def test_sparse_outputs_remain_unverified_not_invented():
    RenTermDependency.model_validate(dict(name="清明"))
    RenTermDependency.model_validate(
        dict(
            name="清明",
            solar_model_details={
                "numerical_epoch_representation": "explicit_two_part_tt"
            },
        )
    )


def test_native_returned_model_must_match_the_declared_observation(monkeypatch):
    from fatebridge.core.metaphysics import ren_term_longitude as angular

    term = term_for("native", monkeypatch)
    wrong_flag = 4 if term.ephemeris_model == "swieph" else 2
    monkeypatch.setattr(
        angular, "ephemeris_call", lambda *a: ([15.0, 0, 0, 0, 0, 0], wrong_flag)
    )
    with pytest.raises(EphemerisSourceError):
        ren_calendar.require_ren_solar_term(term)


def test_native_source_cannot_claim_physical_certification(monkeypatch):
    term = term_for("native", monkeypatch)
    d = {**term.solar_model_details, "accuracy_certified": True}
    with pytest.raises(EphemerisSourceError):
        ren_calendar.require_ren_solar_term(replace(term, solar_model_details=d))


def test_spk_selection_cannot_change_during_a_two_endpoint_observation(
    monkeypatch, tmp_path
):
    from fatebridge.core import spk_solar

    term_for("spk", monkeypatch)
    other = tmp_path / "same-bytes-other-source.bsp"
    shutil.copyfile(ROOT / "ephe/solar-de440.bsp", other)
    original = spk_solar._KernelSun.longitude

    def change_selection(self, epoch):
        value = original(self, epoch)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(other))
        return value

    monkeypatch.setattr(spk_solar._KernelSun, "longitude", change_selection)
    with pytest.raises(EphemerisSourceError) as caught:
        spk_solar.solar_longitudes_tt([2461135.0, 2461136.0])
    assert caught.value.reason == "solar_configuration_changed"


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_wrong_named_actual_boundary_fails_before_projection_on_all_ports(
    key, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    original = ren_calendar.get_adjacent_solar_terms
    monkeypatch.setattr(
        ren_calendar,
        "get_adjacent_solar_terms",
        lambda *a, **kw: tuple(replace(t, name="立春") for t in original(*a, **kw)),
    )
    spec = SPECS[key]
    payload = payload_for(key)
    params, options, flags = {}, {}, []
    if project:
        params = {"fields": "analysis_type", "strict_fields": "true"}
        options = {"fields": ["analysis_type"], "strict_fields": True}
        flags = ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=payload, params=params)
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 503 and mcp.is_error and code != 0
    for body in (http.json(), mcp.structured_content, cli):
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert "ren_solar_term_longitude_inconsistent" in str(body["issues"])


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_coherent_false_output_name_is_rejected_before_projection(
    key, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    spec = SPECS[key]
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload_for(key)))
    bad = fn(*args, **kw)
    holder = bad["subresults"]["liureng_gods"] if key == "sanshiunited" else bad
    board = holder["jinkou"] if key == "jinkou" else holder["liureng"]
    row = board["calendar_policy"]["solar_term_dependencies"][0]
    row["name"] = "立春"
    row["published_date_reference"] = published_date_reference(
        "立春", datetime.fromisoformat(row["civil_moment"])
    )
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    assert_broken_on_three_ports(
        spec, bad, project, rest, monkeypatch, tmp_path, capsys
    )
