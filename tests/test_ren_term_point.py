"""Consumed root receipts cannot contradict their exact TT/civil point."""

import asyncio
import copy
import hashlib
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import almanac
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.core.output_chinese import RenTermDependency
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_ren_anchors import assert_broken_on_three_ports
from tests.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_term_point_v1"
PIN = "135c9c197860fdf409cd0f71a7eeccd13fc896bd5d3863ad3d2e2d824433d77a"


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


@pytest.mark.parametrize("row", reference()["rows"], ids=lambda row: row["id"])
def test_independent_decimal_reference(row):
    parts = row["tt_parts"]
    point = (
        TTInstant.from_float(parts[0])
        if len(parts) == 1
        else TTInstant.from_parts(*parts)
    )
    assert datetime_from_tt_point(point).isoformat() == row["expected_utc"]


@pytest.fixture(params=["native", "analytic", "de440", "spk"])
def actual_term(request, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", request.param)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if request.param == "spk":
        pytest.importorskip("erfa")
        pytest.importorskip("jplephem")
        kernel = ROOT / "ephe/solar-de440.bsp"
        assert hashlib.sha256(kernel.read_bytes()).hexdigest() == (
            "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
        )
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(kernel))
    return almanac.get_solar_terms_for_year(2026, "UTC")[6]


def corrupt(term, fault):
    details = copy.deepcopy(term.solar_model_details)
    if fault == "civil_plus_second":
        return replace(term, moment=term.moment + timedelta(seconds=1))
    if fault == "missing_details":
        return replace(term, solar_model_details=None)
    if fault == "selected_plus_day":
        details["selected_crossing_jd_tt"] += 1
    elif fault == "reversed_bracket":
        details["root_bracket_tt"].reverse()
        if "root_bracket_tt_parts" in details:
            details["root_bracket_tt_parts"].reverse()
    elif fault == "negative_width":
        details["root_bracket_seconds"] = -1
    elif fault == "wrong_width":
        details["root_bracket_seconds"] += 1
    elif fault == "wrong_scale":
        details["root_time_scale"] = "UTC"
    elif fault == "unknown_representation":
        details["numerical_epoch_representation"] = "nominal_UTC_label"
    elif fault == "wrong_scalar_scope":
        details["scalar_jd_scope"] = "nominal_UTC_label"
    elif fault == "nonfinite_selected":
        details["selected_crossing_jd_tt"] = float("nan")
    elif fault == "bool_selected":
        details["selected_crossing_jd_tt"] = True
    elif fault == "missing_selected":
        del details["selected_crossing_jd_tt"]
    elif fault == "physical_accuracy_true":
        details["numerical_resolution_is_physical_accuracy"] = True
    else:
        raise AssertionError(fault)
    return replace(term, solar_model_details=details)


FAULTS = json.loads((CORPUS / "protocol.json").read_text())["faults"][:13]


def payload_for(key):
    if key == "sanshiunited":
        return dict(
            date="2026-04-04",
            time="21:18:37",
            zone="+08:00",
            qimen_options={"layout": "direct"},
            taiyi_options={"accNum": 0},
            use_true_solar_time=False,
            liureng_is_diurnal=False,
        )
    payload = dict(PAYLOAD)
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    return payload


@pytest.mark.parametrize("fault", FAULTS)
def test_runtime_refuses_contradictory_actual_root(actual_term, fault):
    # Missing independent-provider source identities already have their own
    # fail-closed path; this new gate preserves that earlier error identity.
    with pytest.raises((EphemerisSourceError, RuntimeError)):
        ren_calendar.require_ren_solar_term(corrupt(actual_term, fault))


def test_actual_valid_receipt_and_same_instant_other_offset(actual_term):
    ren_calendar.require_ren_solar_term(actual_term)
    ren_calendar.require_ren_solar_term(
        replace(
            actual_term,
            moment=actual_term.moment.astimezone(timezone(timedelta(hours=-4))),
        )
    )
    RenTermDependency.model_validate(
        dict(
            civil_moment=actual_term.moment.isoformat(),
            solar_model_details=actual_term.solar_model_details,
        )
    )


@pytest.mark.parametrize(
    "fault",
    [
        "civil_plus_second",
        "selected_plus_day",
        "reversed_bracket",
        "wrong_width",
        "nonfinite_selected",
        "physical_accuracy_true",
    ],
)
def test_present_output_receipt_refuses_spliced_numerical_evidence(actual_term, fault):
    term = corrupt(actual_term, fault)
    with pytest.raises(ValidationError):
        RenTermDependency.model_validate(
            dict(
                civil_moment=term.moment.isoformat(),
                solar_model_details=term.solar_model_details,
            )
        )


def test_legacy_and_sparse_output_does_not_invent_missing_evidence():
    RenTermDependency.model_validate(dict(civil_moment="2026-04-05T00:00:00Z"))
    RenTermDependency.model_validate(
        dict(solar_model_details={"selected_crossing_jd_tt": 2461135.0})
    )


@pytest.mark.parametrize(
    "fault",
    [
        "split_outside_bracket",
        "split_display_mismatch",
        "split_bracket_display_mismatch",
    ],
)
def test_split_exact_inputs_are_checked_before_rounded_display(fault, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    term = almanac.get_solar_terms_for_year(2026, "UTC")[6]
    d = copy.deepcopy(term.solar_model_details)
    assert d["numerical_epoch_representation"] == "explicit_two_part_tt"
    if fault == "split_outside_bracket":
        base, upper = d["root_bracket_tt_parts"][1]
        outside = math.nextafter(upper, math.inf)
        # All displayed scalar JDs can agree even though the exact TT point
        # lies outside the exact bracket. A scalar-only check misses this.
        assert base + outside == d["selected_crossing_jd_tt"]
        d["selected_crossing_tt_parts"] = [base, outside]
    elif fault == "split_display_mismatch":
        d["selected_crossing_jd_tt"] += 1
    else:
        d["root_bracket_tt"][1] += 1
    with pytest.raises(EphemerisSourceError):
        ren_calendar.require_ren_solar_term(replace(term, solar_model_details=d))
    with pytest.raises(ValidationError):
        RenTermDependency.model_validate(
            dict(civil_moment=term.moment.isoformat(), solar_model_details=d)
        )


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
def test_valid_actual_provider_agrees_on_three_ports(
    actual_term, key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = payload_for(key)
    params = {"response_char_limit": 0, "include_snapshot_text": "false"}
    http = rest.post(spec.rest_path, json=payload, params=params)
    mcp = asyncio.run(
        native(spec, payload, response_char_limit=0, include_snapshot_text=False)
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--response-char-limit", "0", "--include-snapshot-text", "false"],
    )
    assert http.status_code == 200 and not mcp.is_error and code == 0, http.text
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    holder = (
        http.json()["subresults"]["liureng_gods"]
        if key == "sanshiunited"
        else http.json()
    )
    board = holder["jinkou"] if key == "jinkou" else holder["liureng"]
    assert {
        r["provider"] for r in board["calendar_policy"]["solar_term_dependencies"]
    } == {actual_term.resolution_provider}


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_bad_consumed_clock_fails_before_projection_on_three_ports(
    key, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    original = ren_calendar.get_adjacent_solar_terms
    monkeypatch.setattr(
        ren_calendar,
        "get_adjacent_solar_terms",
        lambda *a, **kw: tuple(
            corrupt(t, "civil_plus_second") for t in original(*a, **kw)
        ),
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
        assert "ren_solar_term_point_inconsistent" in str(body["issues"])
        assert not any(k in body for k in ("jinkou", "liureng", "subresults"))


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_bad_output_point_is_an_output_failure_before_projection(
    key, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    spec = SPECS[key]
    request = spec.request_model.model_validate(payload_for(key))
    fn, args, kw = spec.bind(request)
    bad = fn(*args, **kw)
    holder = bad["subresults"]["liureng_gods"] if key == "sanshiunited" else bad
    board = holder["jinkou"] if key == "jinkou" else holder["liureng"]
    board["calendar_policy"]["solar_term_dependencies"][0]["solar_model_details"][
        "selected_crossing_jd_tt"
    ] += 1
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    assert_broken_on_three_ports(
        spec, bad, project, rest, monkeypatch, tmp_path, capsys
    )
