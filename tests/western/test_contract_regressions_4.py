"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.core import astro_models as rotation
from fatebridge.core.astro import runtime
from fatebridge.core.astro_models import POLICY_ID
from fatebridge.utils.errors import EphemerisSourceError
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.support.ephemeris_case_runtime import native_ephemeris_files
from tests.western.test_western_accuracy import BIRTH
from tests.western.test_western_horary import QUESTION
from tests.western.test_western_natal_reference_points import INPUT
from tests.western.test_western_origin_preflight import directories, selected
from tests.western.test_western_source_errors import inject


@pytest.mark.parametrize("variant", ["chart", "hellen_chart", "chart13"])
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("project", [False, True])
def test_actual_point_receipts_survive_all_protocols(
    variant, zodiacal, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["astro_chart"]
    inputs = dict(INPUT, chart_variant=variant, zodiacal=zodiacal)
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        fields = ["chart_profile.ephemeris_reference_points", "summary"]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=inputs, params=params)
    assert http.status_code == 200, http.text
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags)
    protocol = asyncio.run(native(spec, inputs, **kwargs))
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    expected = values[0]["chart_profile"]["ephemeris_reference_points"]
    for value in values:
        spec.output_model.model_validate(value)
        p = value["chart_profile"]["ephemeris_reference_points"]
        assert p == expected
        assert p["center_body_correction_applied"] is False
        assert {"Mars", "Jupiter", "Saturn"} <= set(p["system_barycenters"])
        assert not p["approximate_points"] and not p["unresolved_points"]
        assert p["note_zh"] in value["summary"]
        if project:
            assert "planets" not in value
        else:
            assert p["note_zh"] in value["snapshot_text"]


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_wrong_native_point_is_not_published_as_a_normal_horary(
    zodiac, monkeypatch, rest, tmp_path, capsys
):
    original = runtime.ephemeris_call
    swe = runtime.swe
    calls = []

    def changed(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == swe.SATURN:
            values, flags = result
            calls.append(flags)
            return values, flags | 1048576
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    spec = SPECS["astro_horary"]
    payload = dict(
        question_year=2026,
        question_month=9,
        question_day=19,
        question_hour=0,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
        zodiac_type=zodiac,
        category="career",
    )
    http = rest.post(spec.rest_path, json=payload)
    assert http.status_code == 503
    expected = http.json()
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert code == 1 and protocol.is_error
    mcp = json.loads(protocol.content[0].text)
    assert len(calls) >= 3
    for value in [expected, cli, mcp]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == expected["issues"]
        assert "coordinate_contract_changed" in json.dumps(value["issues"])
        assert "horary" not in value


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_terms_and_faithful_interpretation_across_real_local_protocols(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "classical.ptolemy.ruleset_id",
        "classical.ptolemy.planets.Sun",
        "classical.ptolemy.term_policy",
        "classical.ptolemy.term_source_url",
        "classical.ptolemy.term_transcription_note",
        "classical.sect",
        "interpretation.original_text_terms",
        "interpretation_evidence.original_text_terms",
    ]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    response = rest.post(spec.rest_path, json=BIRTH, params=query)
    code, local = call_cli(
        spec,
        BIRTH,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, BIRTH, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        assert "snapshot_text" not in result
        layer = result["classical"]["ptolemy"]
        assert layer["ruleset_id"].endswith("bounded_v4")
        assert set(layer["planets"]["Sun"]["terms"]) == {
            "egyptian",
            "chaldaean",
            "ptolemaic",
        }
        assert (
            "printed" in layer["term_policy"]
            and "Libra" in layer["term_transcription_note"]
        )
        assert (
            result["interpretation_evidence"]["original_text_terms"]["policy_id"]
            == "ptolemy_robbins_printed_terms_v1"
        )
        assert "纸本表" in result["interpretation"]["original_text_terms"]


@pytest.mark.parametrize(
    "key",
    [
        "astro_chart",
        "astro_hellen",
        "astro_chart13",
        "astro_germany",
        "astro_horary",
        "astro_election",
        "profection",
        "astro_harmonic",
    ],
)
@pytest.mark.parametrize("mode", ["empty", "planet_only", "full"])
def test_actual_public_adapters_share_explicit_source_policy(
    key, mode, selected, rest, tmp_path, capsys
):
    spec = SPECS[key]
    selected(mode)
    payload = {**inputs(spec), "ephemeris_policy": "require_data_files"}
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, ["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    if mode == "full":
        assert http.status_code == 200 and code == 0 and not protocol.is_error
        for value in values:
            receipt = value["ephemeris_data_policy"]
            assert receipt["requested"] == "require_data_files"
            assert receipt["physical_calls_by_model"]["swieph"] > 0
            assert receipt["accuracy_certified"] is False
        assert (
            values[0]["ephemeris_data_policy"]
            == values[1]["ephemeris_data_policy"]
            == values[2]["ephemeris_data_policy"]
        )
    else:
        assert http.status_code == 503 and code == 1 and protocol.is_error
        for value in values:
            assert value["error_code"] == "ephemeris_source_inconsistent"
            assert value["issues"][0]["code"] == (
                "required_data_files_fallback"
                if mode == "empty"
                else "swiss_dependency_unavailable"
            )
            assert value["retryable"] is False
            assert "ephemeris_data_policy" not in value and "score" not in value
    for index, value in enumerate(values):
        (tmp_path / f"{key}-{mode}-{index}.json").write_text(json.dumps(value))


def test_policy_evidence_view_projects_the_same_receipt_on_all_adapters(
    selected, rest, tmp_path, capsys
):
    from fatebridge.application.examples import suggested_fields

    selected("full")
    spec = SPECS["astro_chart"]
    payload = {**inputs(spec), "ephemeris_policy": "require_data_files"}
    fields = suggested_fields(spec, view="data_files")
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": fields,
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            "ephemeris_data_policy",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert (
        values[0]["ephemeris_data_policy"]
        == values[1]["ephemeris_data_policy"]
        == values[2]["ephemeris_data_policy"]
    )
    assert all(
        "planets" not in value and "snapshot_text" not in value for value in values
    )


@pytest.mark.parametrize(
    "year,expected",
    [
        (2099, "IERS2010_expression_Swiss_nutation"),
        (2300, "Swiss_longterm_with_boundary_phase_alignment"),
    ],
)
def test_epoch_policy_and_limits_on_real_rest_mcp_cli(
    year, expected, rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    payload = {**BIRTH, "birth_year": year}
    prefix = "chart_profile.earth_rotation"
    fields = [
        prefix + ".policy_id",
        prefix + ".sidereal_time_model",
        prefix + ".longterm_phase_alignment",
        prefix + ".measured_eop_applied",
        prefix + ".precision_scope",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        policy = result["chart_profile"]["earth_rotation"]
        assert policy["policy_id"] == POLICY_ID
        assert policy["sidereal_time_model"] == expected
        assert policy["measured_eop_applied"] is False
        if year == 2300:
            assert (
                policy["longterm_phase_alignment"]["absolute_accuracy_certified"]
                is False
            )
            assert (
                policy["longterm_phase_alignment"]["derivative_continuity_certified"]
                is False
            )
        else:
            assert policy["longterm_phase_alignment"] is None
        assert not result.get("projection_warnings")


@pytest.mark.parametrize("year", [1800, 2024])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_historical_clock_policy_reaches_actual_rest_mcp_cli(
    year, zodiacal, rest, monkeypatch, tmp_path, capsys
):
    actual = rotation.iers2010_gast
    arguments = []

    def observed(ut1, tt, *args):
        arguments.append((ut1, tt))
        return actual(ut1, tt, *args)

    monkeypatch.setattr(rotation, "iers2010_gast", observed)
    spec = SPECS["astro_chart"]
    inputs = dict(
        birth_year=year,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=False,
        zodiacal=zodiacal,
    )
    fields = [
        "chart_profile.earth_rotation",
        "chart_profile.julian_day_tt",
        "chart_profile.julian_day_ut1",
    ]
    params = [("fields", p) for p in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http = rest.post(spec.rest_path, json=inputs, params=params)
    assert http.status_code == 200, http.text
    code, cli = call_cli(
        spec,
        inputs,
        tmp_path,
        capsys,
        [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert code == 0 and not protocol.is_error
    for value in [http.json(), cli, json.loads(protocol.content[0].text)]:
        spec.output_model.model_validate(value)
        profile = value["chart_profile"]
        policy = profile["earth_rotation"]
        assert policy["policy_id"] == "fatebridge_standard_rotation_v3"
        if year == 1800:
            assert policy["tt_argument_policy"] == (
                "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
            )
            assert any(
                abs(u - profile["julian_day_ut1"]) * 86400 <= 0.0002
                and abs(t - profile["julian_day_tt"]) * 86400 <= 0.0002
                for u, t in arguments
            )
        else:
            assert (
                policy["tt_argument_policy"] == "native_internal_sidereal_time_argument"
            )
    if year == 1800:
        assert arguments
        for ut1, tt in arguments:
            expected = ut1 + runtime.swe.deltat_ex(ut1, -1)
            assert abs(expected - tt) * 86400 <= 0.0002


def test_restored_swiss_history_and_v5_receipts_survive_strict_three_protocols(
    rest, tmp_path, capsys, native_ephemeris_files
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    fields = evidence_views(spec)["reference_points"]["fields"]
    response = rest.post(
        spec.rest_path,
        json=inputs,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        inputs,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
        h = value["horary"]
        history = h["perfection"]["event_history"]
        assert h["calculation_basis"]["ephemeris_model"] == "swieph"
        assert history["status"] == "computed"
        assert history["unavailable_reason"] is None
        assert history["unavailable_code"] is None and history["failed_sample"] is None
        policies = history["longitude_motion"]["complete_position_derivatives"]
        assert {
            f"{planet}:tropical" for planet in ("Sun", "Mercury", "Venus", "Mars")
        } <= policies.keys()
        for policy in policies.values():
            assert policy["method_id"] == "fatebridge_complete_position_derivative_v8"
            assert policy["convergence_line_arcsec_per_day"] == 0.0002
            if policy["directional_checks"]:
                assert policy["directional_checks"][-1]["passed"]
        assert h["verdict"] == "uncertain" and h["perfection"]["perfects"] is None


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_chart13"])
@pytest.mark.parametrize(
    "target",
    [
        "native_angles",
        "sun_event",
        "planetary_hour_calendar",
        "classical_obliquity",
        "tropical_house_layout",
        "sidereal_house_layout",
        "extended_utc_display",
    ],
)
def test_full_calculation_rejection_survives_unrelated_projection(
    key,
    target,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS[key]
    failure = EphemerisSourceError("changed_during")
    inject(target, failure, monkeypatch)
    payload = dict(
        birth_year=1 if target == "extended_utc_display" else 2026,
        birth_month=1,
        birth_day=1 if target == "extended_utc_display" else 4,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        hsys=0 if target == "native_angles" else 3,
        zodiacal=int(target == "sidereal_house_layout"),
    )
    flags = dict(
        fields=["person_info.name"], strict_fields=True, include_snapshot_text=False
    )
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": "person_info.name",
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    protocol = asyncio.run(native(spec, payload, **flags))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            "person_info.name",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 503, http.text
    assert protocol.is_error and code == 1
    values = [http.json(), json.loads(protocol.content[0].text), cli]
    for value in values:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "changed_during"}
        ]
        assert "person_info" not in value and "planetary_hours" not in value
