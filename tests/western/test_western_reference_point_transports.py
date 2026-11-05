"""Declared reference centers and motion provenance survive the actual protocols."""

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.ephemeris_case_runtime import native_ephemeris_files
from tests.support.transports import SPECS, business, rest, surface_calls
from tests.western.test_western_horary import QUESTION


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_reference_points_match_rest_mcp_cli(
    project, zodiac, native_ephemeris_files, surface_calls
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career", "zodiac_type": zodiac}
    fields = evidence_views(spec)["reference_points"]["fields"]
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
    response, protocol, code, cli = surface_calls(
        spec, inputs, params=params, options=kwargs, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for out in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        assert not out.get("projection_warnings")
        h = out["horary"]
        b = h["calculation_basis"]
        history = h["perfection"]["event_history"]
        if history.get("status") == "unavailable":
            assert history["unavailable_code"] == "position_motion_not_converged"
            assert history["failed_sample"]["planet"] in {
                "Sun",
                "Mercury",
                "Venus",
                "Mars",
            }
            assert (
                h["perfection"]["lilly_conditions"]["event_paths"]["status"]
                == "unavailable"
            )
            assert h["perfection"]["perfects"] is None
        assert b["ephemeris_model"] in {"moshier", "swieph", "jpl", "mixed"}
        p = b["ephemeris_reference_points"]
        assert "Saturn" in p["system_barycenters"] and "Saturn" not in p["body_centers"]
        assert (
            p["theoretical_points"] == ["North Node"]
            and p["center_body_correction_applied"] is False
        )
        assert history["ephemeris_reference_points"]["system_barycenters"] == [
            "Mars",
            "Jupiter",
            "Saturn",
        ]
        for s in history["question_states"].values():
            assert sum(
                s.get(k, 0.0)
                for k in (
                    "speed_native",
                    "speed_light_time_correction",
                    "speed_spatial_aberration_correction",
                    "speed_lunar_source_remainder_correction",
                    "speed_sidereal_origin_wrap_correction",
                    "speed_rotation_correction",
                    "speed_analytic_frame_correction",
                    "speed_position_derivative_correction",
                    "speed_display_offset_correction",
                )
            ) == pytest.approx(s["speed"], abs=1e-14)
        frame = history["longitude_motion"]["lunar_tropical_frame"]
        if frame["status"] == "applied":
            assert (
                history["question_states"]["Moon"]["speed_analytic_frame_correction"]
                == frame["additional_correction_degrees_per_native_argument_day"]
            )
        assert (
            h["verdict"] == "uncertain"
            and h["rule_profile"]["full_original_text_acceptance"] is False
        )


def test_a_native_subject_cannot_mix_configuration_changes_between_planets(
    monkeypatch, tmp_path, surface_calls
):
    import fatebridge.core.predictive.native_chart as chart

    original = chart._swisseph_planet_state
    counter = 0

    def changed(*args, **kwargs):
        nonlocal counter
        result = original(*args, **kwargs)
        counter += 1
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / f"changed-{counter}"))
        return result

    monkeypatch.setattr(chart, "_swisseph_planet_state", changed)
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    response, protocol, code, cli = surface_calls(spec, inputs)
    assert response.status_code == 503 and code != 0 and protocol.is_error
    assert cli.get("error") and response.json().get("error")


@pytest.mark.parametrize("project", [False, True])
def test_unconverged_history_survives_all_protocols_and_summary_projection(
    project, monkeypatch, tmp_path, surface_calls
):
    import fatebridge.core.horary_events as events

    original = events._swisseph_planet_state
    question_epoch = []

    def fail_future(*args, **kwargs):
        at = kwargs["julian_day_tt"]
        if not question_epoch:
            question_epoch.append(at)
        if at != question_epoch[0]:
            raise EphemerisSourceError("position_motion_not_converged")
        return original(*args, **kwargs)

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(events, "_swisseph_planet_state", fail_future)
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    fields = evidence_views(spec)["reference_points"]["fields"]
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
    response, protocol, code, cli = surface_calls(
        spec, inputs, params=params, options=kwargs, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        assert not result.get("projection_warnings")
        h = result["horary"]
        p = h["perfection"]
        assert p["event_history"]["status"] == "unavailable"
        assert p["event_history"]["unavailable_code"] == "position_motion_not_converged"
        assert p["event_history"]["failed_sample"]["planet"] == "Sun"
        assert set(p["event_history"]["question_states"]) == set(events.BODIES)
        assert p["perfects"] is None
        assert p["lilly_conditions"]["event_paths"]["status"] == "unavailable"
        assert h["verdict"] == "uncertain"
        assert "事件历史当前不可用" in h["reasoning"]
