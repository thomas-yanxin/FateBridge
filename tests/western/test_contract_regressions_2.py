"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import json
import math
from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import fatebridge.core.astrology_election as engine
from fatebridge.application.examples import evidence_views
from fatebridge.core import horary_events as events
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.output_western import PlanetaryEventHistory
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.western.test_western_accuracy import BIRTH
from tests.western.test_western_election import CANDIDATE
from tests.western.test_western_event_clock_transports import surfaces
from tests.western.test_western_horary import QUESTION
from tests.western.test_western_horizon_precision import EXPECTED, PUBLIC, separation


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_native_election_fact_and_unknown_states_agree_across_transports(
    project, zodiac, unavailable, rest, monkeypatch, tmp_path, capsys
):
    if unavailable:
        monkeypatch.setattr(
            engine,
            "native_lunar_contacts",
            lambda subject: {
                "status": "unavailable",
                "method_id": "native_tt_lunar_contacts_before_ingress_v1",
                "constant_velocity_projection": False,
                "void_of_course": None,
                "contacts": [],
                "unavailable_reason": "Synthetic native search failure",
            },
        )
    spec = SPECS["astro_election"]
    payload = {
        **CANDIDATE,
        "topic_id": "contract",
        "house_system": "W",
        "zodiac_type": zodiac,
    }
    card = evidence_views(spec)["calculation_conditions"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", f) for f in card["fields"]] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *card["fields"],
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": card["fields"],
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **kwargs))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        e = result["election"]
        raw = 60 + sum(f["weight"] for f in e["factors"])
        assert e["axes"]["ascendant_longitude"] != e["axes"]["first_house_cusp"]
        assert e["scoring_policy"]["weights_and_band_boundaries_changed"] is False
        assert e["scoring_policy"]["full_original_text_acceptance"] is False
        if unavailable:
            assert e["score"] is None and e["score_evidence"]["status"] == "partial"
            assert e["moon"]["void_of_course"] is None
            assert e["score_bounds"] == [
                max(0, min(100, raw - 25)),
                max(0, min(100, raw)),
            ]
            assert e["unresolved_factors"][0]["code"] == "moon_void_of_course"
        else:
            assert e["score"] == max(0, min(100, raw)) and e["unresolved_factors"] == []
            assert (
                e["moon"]["motion_basis"]["start_julian_day_tt"]
                == e["calculation_basis"]["julian_day_tt"]
            )
            assert e["moon"]["motion_basis"]["constant_velocity_projection"] is False
        if project:
            assert "snapshot_text" not in result
        elif unavailable:
            assert (
                "未完成" in result["summary"]
                and '"score": null' in result["snapshot_text"]
            )


def test_source_consistency_failure_is_error_not_partial_favourable_score(
    rest, monkeypatch, tmp_path, capsys
):
    def changed(subject):
        raise EphemerisSourceError("physical_configuration_changed")

    monkeypatch.setattr(engine, "native_lunar_contacts", changed)
    spec = SPECS["astro_election"]
    payload = {**CANDIDATE, "topic_id": "general"}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 503 and code != 0 and protocol.is_error
    for result in [response.json(), cli, protocol.structured_content]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert "election" not in result


@pytest.mark.parametrize(
    "reason",
    [
        "position_motion_not_converged",
        "model_changed",
        "physical_configuration_changed",
        "coordinate_contract_changed",
    ],
)
def test_failed_search_preserves_question_states_without_substituting_rates(
    reason, monkeypatch
):
    at = 2451545.0
    calls = []

    def sample(planet, ut1=None, *, julian_day_tt, **kwargs):
        assert ut1 is None, "TT event sampling must not require an Earth-rotation epoch"
        calls.append((planet, julian_day_tt))
        if julian_day_tt != at:
            raise EphemerisSourceError(reason)
        return {"longitude": 42.0, "latitude": 0.0, "longitude_speed": 0.1}, "moshier"

    def search(epoch, sampler):
        sampler("Venus", epoch + 1)
        raise AssertionError("An unknown rate was silently substituted")

    monkeypatch.setattr(events, "_swisseph_planet_state", sample)
    monkeypatch.setattr(events, "solve_planetary_events", search)
    subject = SimpleNamespace(julian_day_tt=at, zodiac_type="Tropic")
    if reason != "position_motion_not_converged":
        with pytest.raises(EphemerisSourceError) as raised:
            events.native_planetary_events(subject)
        assert raised.value.reason == reason
        return
    result = events.native_planetary_events(subject)
    PlanetaryEventHistory.model_validate(result)
    assert result["status"] == "unavailable" and result["events"] == []
    assert result["unavailable_code"] == reason
    assert result["failed_sample"] == {"planet": "Venus", "julian_day_tt": at + 1}
    assert set(result["question_states"]) == set(events.BODIES)
    assert result["constant_velocity_projection"] is False
    assert result["full_original_text_acceptance"] is False
    assert len(calls) == len(events.BODIES) + 1


def test_audit_cannot_pass_unavailable_events_as_an_empty_success(monkeypatch):
    from scripts.western import audit_western_reference_points as audit

    monkeypatch.setattr(
        audit,
        "native_planetary_events",
        lambda subject: {
            "status": "unavailable",
            "unavailable_code": "position_motion_not_converged",
        },
    )
    monkeypatch.setattr(
        audit,
        "_swisseph_planet_state",
        lambda *args, **kwargs: ({"longitude": 0.0}, "moshier"),
    )
    result = audit.audit()
    assert result["same_point_event_times_compared"] == 0
    assert result["same_point_event_times_expected"] == 212
    assert len(result["unavailable_event_cases"]) == 2
    assert result["complete_event_comparison"] is False
    assert result["same_point_numerical_acceptance"] is False
    assert result["body_center_comparison_passed"] is False


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_event_histories_and_conditions_match_rest_native_mcp_cli(
    project, zodiac, rest, tmp_path, capsys, monkeypatch
):
    # This is the explicit native fallback contract. Strict complete-position
    # derivatives and their unavailable coverage are tested separately.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career", "zodiac_type": zodiac}
    fields = evidence_views(spec)["event_paths"]["fields"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", p) for p in fields] + [
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
    response = rest.post(spec.rest_path, json=inputs, params=params)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, inputs, **kwargs))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        assert not out.get("projection_warnings")
        h = out["horary"]
        assert h["calculation_basis"]["ephemeris_model"] == "moshier"
        p = h["perfection"]
        events = p["event_history"]
        assert events["status"] == "computed" and len(events["events"]) > 100
        assert (
            events["question_julian_day_tt"] == h["calculation_basis"]["julian_day_tt"]
        )
        assert events["window_tt"] == [
            events["question_julian_day_tt"] - 30,
            events["question_julian_day_tt"] + 30,
        ]
        facts = p["lilly_conditions"]["event_paths"]
        same_body = (
            h["significators"]["querent"]["planet"]
            == h["significators"]["quesited"]["planet"]
        )
        assert facts["status"] == (
            "same_body_insufficient" if same_body else "computed_conditions"
        )
        assert bool(facts["paths"]) is not same_body
        assert h["verdict"] == "uncertain" and p["perfects"] is None
        assert events["full_original_text_acceptance"] is False
        for path in facts["paths"]:
            assert path["full_path_accepted"] is False
            for receipt in path["event_receptions"]:
                assert receipt["chart_sect"] == "day"
                assert len(receipt["endpoint_receptions"]) == 2
                assert isinstance(receipt["boundary_uncertainty"], bool)
        if project:
            assert "snapshot_text" not in out
        else:
            assert "主星历史分离与传光星历史分离分别核对" in out["snapshot_text"]


def test_failed_event_history_remains_unknown_and_source_failure_is_not_a_result(
    rest, monkeypatch, tmp_path, capsys
):
    import fatebridge.core.astrology_horary as engine
    import fatebridge.core.horary_events as events

    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    original = engine.native_planetary_events
    monkeypatch.setattr(
        engine,
        "native_planetary_events",
        lambda subject: dict(
            status="unavailable",
            constant_velocity_projection=False,
            events=[],
            unavailable_reason="Controlled unavailable history",
            full_original_text_acceptance=False,
        ),
    )
    response = rest.post(spec.rest_path, json=inputs, params={"response_char_limit": 0})
    assert response.status_code == 200
    p = response.json()["horary"]["perfection"]
    assert (
        p["event_history"]["status"] == "unavailable"
        and p["lilly_conditions"]["event_paths"]["status"] == "unavailable"
    )
    assert p["perfects"] is None
    monkeypatch.setattr(engine, "native_planetary_events", original)

    def changed(*args, **kwargs):
        raise EphemerisSourceError("model_changed")

    monkeypatch.setattr(events, "_swisseph_planet_state", changed)
    response = rest.post(spec.rest_path, json=inputs)
    code, cli = call_cli(spec, inputs, tmp_path, capsys)
    mcp = asyncio.run(native(spec, inputs))
    assert response.status_code == 503 and code != 0 and mcp.is_error
    assert cli.get("error") and response.json().get("error")


@pytest.mark.parametrize(
    "key",
    ["astro_chart", "astro_chart13", "astro_hellen", "astro_india", "astro_germany"],
)
def test_named_solar_policy_view_keeps_definition_and_textual_conflict_together(
    key, rest
):
    spec = SPECS[key]
    card = evidence_views(spec)["solar_conditions"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", p) for p in card["fields"]]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    result = response.json()
    assert not result.get("projection_warnings")
    node = result["base_chart"] if key == "astro_germany" else result
    policy = node["classical"]["solar_condition_policy"]
    assert policy["under_beams_limit_degrees"] == 17
    assert policy["combust_requires_same_sign"] is True
    assert policy["full_page_acceptance"] is False
    assert "Sun 18 Aries, planet 28 Aries" in policy["printed_example_discrepancy"]


@pytest.mark.parametrize("project", [False, True])
def test_native_lunar_events_and_unverified_conditions_match_three_transports(
    project, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    payload = {**QUESTION, "category": "general"}
    fields = evidence_views(spec)["motion_conditions"]["fields"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", p) for p in fields] + [
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
        kwargs = {
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **kwargs))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        horary = result["horary"]
        assert horary["perfection"]["perfects"] is None
        assert horary["perfection"]["candidate"] is False
        assert horary["perfection"]["status"] == "same_ruler_insufficient"
        assert horary["verdict"] == "uncertain"
        assert horary["rule_profile"]["full_original_text_acceptance"] is False
        basis = horary["moon"]["motion_basis"]
        assert basis["status"] == "computed" and basis["time_scale"] == "TT"
        assert basis["constant_velocity_projection"] is False
        assert basis["physical_ephemeris_source"]["accuracy_certified"] is False
        assert (
            horary["calculation_basis"]["julian_day_tt"] == basis["start_julian_day_tt"]
        )
        if project:
            assert "heuristic_verdict" not in horary and "snapshot_text" not in result
        else:
            assert "尚未完成Lilly" in result["snapshot_text"]


def test_failed_native_event_search_remains_unknown_in_public_schema(rest, monkeypatch):
    import fatebridge.core.astrology_horary as horary

    monkeypatch.setattr(
        horary,
        "native_lunar_contacts",
        lambda subject: {
            "status": "unavailable",
            "method_id": "native_tt_lunar_contacts_before_ingress_v1",
            "constant_velocity_projection": False,
            "void_of_course": None,
            "contacts": [],
            "unavailable_reason": "Synthetic source unavailable",
        },
    )
    result = rest.post(
        SPECS["astro_horary"].rest_path,
        json={**QUESTION, "category": "career"},
        params={"response_char_limit": 0},
    )
    assert result.status_code == 200
    output = result.json()["horary"]
    assert output["moon"]["void_of_course"] is None
    assert output["moon"]["motion_basis"]["status"] == "unavailable"
    assert not any(row["code"] == "C05" for row in output["radicality"]["strictures"])
    assert output["verdict"] == "uncertain"


def test_published_horary_description_matches_actual_cast_and_verification_scope():
    summary = SPECS["astro_horary"].summary
    assert "按明确提问时刻起盘" in summary and "原典条件缺项" in summary
    assert "求解天文时刻后起盘" not in summary


@pytest.mark.parametrize("hsys", [0, 2, 6])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_precision_receipt_and_coordinates_survive_all_local_surfaces(
    hsys, zodiacal, rest, tmp_path, capsys
):
    case = PUBLIC[0]
    spec = SPECS["astro_chart"]
    payload = dict(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=hsys,
        zodiacal=zodiacal,
    )
    fields = [
        "chart_profile.house_axis_convention.eastern_direction_precision",
        "angles",
        "houses",
        "summary",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", path) for path in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
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
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        p = result["chart_profile"]["house_axis_convention"][
            "eastern_direction_precision"
        ]
        assert p["delivered_ascendant"] == result["angles"]["ascendant"]["longitude"]
        assert p["delivered_cusps"] == [h["cusp_longitude"] for h in result["houses"]]
        assert p["ascendant_action"] == "antipodal_endpoint"
        assert not result.get("projection_warnings")
        if zodiacal == 0:
            assert (
                separation(p["delivered_ascendant"], EXPECTED[case["id"]]["ascendant"])
                <= 1
            )


def test_unresolved_endpoint_rejects_even_an_unrelated_projection_on_all_surfaces(
    monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.core.astro import house_axes

    def unresolved(*args, **kwargs):
        raise ArithmeticError("injected unresolved endpoint")

    monkeypatch.setattr(house_axes, "horizon_geometry", unresolved)
    case = PUBLIC[0]
    spec = SPECS["astro_chart"]
    payload = dict(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=0,
    )
    flags = dict(
        fields=["person_info.name"], strict_fields=True, include_snapshot_text=False
    )
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            ("fields", "person_info.name"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    protocol = asyncio.run(native(spec, payload, **flags))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "person_info.name",
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 503 and protocol.is_error and code == 1
    for value in [http.json(), json.loads(protocol.content[0].text), cli]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "horizon_direction_precision_unavailable",
            }
        ]
        assert "person_info" not in value and "angles" not in value


@pytest.mark.parametrize(
    "anchor",
    [
        math.nextafter(240.0, 0),
        math.nextafter(360.0, 0),
        math.nextafter(0.0, -math.inf),
        0.0,
        15.0,
    ],
)
def test_equal_house_rotation_preserves_the_exact_input_side_of_zero(anchor):
    result = _build_houses(anchor, "equal")
    with localcontext() as ctx:
        ctx.prec = 1100
        for i, record in enumerate(result):
            exact = (Decimal.from_float(anchor) + Decimal(30 * i)) % Decimal(360)
            if exact < 0:
                exact += 360
            value = record["cusp_longitude"]
            assert 0 <= value < 360
            assert abs(value - float(exact)) <= math.ulp(float(exact))
            assert int(Decimal.from_float(value) // 30) == int(exact // 30)


def test_frozen_half_ulp_counterexample_retains_pisces_not_aries():
    record = _build_houses(math.nextafter(240.0, 0), "equal")[4]
    assert record["cusp_longitude"] == math.nextafter(360.0, 0)
    assert record["sign"] == "Pisces"


def test_whole_sign_does_not_underflow_a_tiny_negative_ascendant_to_aries():
    assert (
        _build_houses(math.nextafter(0.0, -math.inf), "whole_sign")[0]["cusp_longitude"]
        == 330
    )


@pytest.mark.parametrize("mc", [0.0, 17.0, 150.125, 270.0, math.nextafter(240.0, 0)])
def test_equal_mc_anchors_the_tenth_cusp_rather_than_the_house_center(mc):
    houses = _build_houses(77.0, "equal_mc", midheaven=mc)
    assert houses[9]["cusp_longitude"] == mc
    assert houses[0]["cusp_longitude"] != 77.0
    assert (
        house_system_fields("D")["house_system_label_zh"] == "天顶为第10宫宫头的等宫制"
    )


def test_equal_mc_uses_its_tenth_cusp_name():
    assert normalize_house_system("天顶为第10宫宫头的等宫制") == "D"
    assert "宫头" in house_system_fields("D")["house_system_label_zh"]
    with pytest.raises(ValueError):
        normalize_house_system("天顶为10宫中点等宫制")


@pytest.mark.parametrize("key", ["astro_chart", "astro_chart13"])
def test_equal_mc_tenth_cusp_and_canonical_label_on_all_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**BIRTH, "hsys": 8}
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in [response.json(), cli, mcp.structured_content]:
        assert (
            result["chart_profile"]["house_system_label_zh"]
            == "天顶为第10宫宫头的等宫制"
        )
        assert result["houses"][9]["cusp_longitude"] == pytest.approx(
            result["angles"]["midheaven"]["longitude"], abs=1e-10
        )
        assert "天顶为第10宫宫头的等宫制" in result["snapshot_text"]
        assert "天顶为10宫中点等宫制" not in result["snapshot_text"]


def test_wrap_epoch_has_retrograde_saturn_across_rest_mcp_cli(rest, tmp_path, capsys):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=285,
            question_month=9,
            question_day=2,
            question_hour=21,
            question_minute=51,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            zodiac_type="Sidereal",
            category="career",
        ),
        [
            "horary.planets.Saturn",
            "horary.calculation_basis.longitude_motion",
            "horary.fortitudes.physical_inputs.motion.Saturn",
            "horary.fortitudes.planets.Saturn.rows",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        assert h["planets"]["Saturn"]["retrograde"] is True
        assert -0.1 < h["planets"]["Saturn"]["speed"] < 0
        assert (
            abs(
                h["calculation_basis"]["longitude_motion"][
                    "display_longitude_offset_speed_degrees_per_day"
                ]
            )
            < 0.01
        )
        ledger = h["fortitudes"]
        motion = ledger["physical_inputs"]["motion"]["Saturn"]
        assert motion["status"] == "computed" and motion["direction"] == "retrograde"
        assert motion["daily_motion_degrees"] < 0
        rows = {r["code"]: r for r in ledger["planets"]["Saturn"]["rows"]}
        assert rows["D03"]["contribution"] == -5
        assert rows["F06"]["contribution"] == 0
        assert not ledger["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"
