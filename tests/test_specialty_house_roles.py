"""Recorded B houses, E angle extraction and X cusps are different roles."""

import copy

import pytest

from fatebridge.core.astro import runtime
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from fatebridge.validation.house_roles import audit_specialty_house_roles
from tests.test_other_chart_angle_qualification import PAYLOAD


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("kind", ["germany", "chart13"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_actual_native_calls_separate_selected_houses_reference_angles_and_partition(
    monkeypatch, kind, zodiacal
):
    original = runtime.ephemeris_call
    calls = []

    def observed(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name == "houses_ex":
            calls.append((args, result))
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", observed)
    request = {
        **PAYLOAD,
        "birth_longitude": 10.0,
        "birth_latitude": 20.0,
        "zodiacal": zodiacal,
    }
    payload = (
        calculate_germany_chart_analysis(**request)
        if kind == "germany"
        else calculate_core_chart_analysis(**request, chart_variant="chart13")
    )
    assert "error" not in payload, payload
    base = payload.get("base_chart", payload)
    profile = base["chart_profile"]
    assert profile["house_system"] == "alcabitus"
    assert profile["house_system_code"] == 1
    assert profile["house_system_label_zh"] == "Alcabitus"
    base_calls = [(args, result) for args, result in calls if args[3] == b"B"]
    assert base_calls, "The recorded Alcabitus label must have a real B call"
    assert [row["cusp_longitude"] for row in base["houses"]] == list(
        base_calls[0][1][0]
    )
    native = payload.get("midpoint_analysis", payload)
    models = [
        row["reference_angle_model"] for row in native["time_sensitivity"]["samples"]
    ]
    if kind == "germany":
        models.append(native["profile"]["reference_angle_model"])
        assert native["meridian_houses"]["profile"]["house_code"] == "X"
        assert any(args[3] == b"X" for args, _ in calls)
    else:
        assert payload["sector_profile"]["ruleset_id"] == "fatebridge_equal13_v1"
    for model in models:
        assert model["house_code"] == "E"
        assert model["cusp_output_used"] is False
        assert model["role"] == "reference_angles_only"
        assert any(
            args[3] == b"E" and len(args) > 4 and args[4] == model["house_flags"]
            for args, _ in calls
        )
    roles = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Alcabitus"
    )
    assert roles["status"] == "consistent_recorded_roles", roles
    assert roles["base_house_system"]["swiss_house_code"] == "B"
    wrong = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Equal"
    )
    assert wrong["status"] == "mismatch"
    assert "declared_base_house_system_differs_from_recorded_base" in wrong["issues"]


def test_unrecorded_reference_model_is_not_inferred_from_the_house_label():
    payload = {
        "base_chart": {
            "chart_profile": {
                "house_system": "alcabitus",
                "house_system_code": 1,
                "house_system_label_zh": "Alcabitus",
            }
        },
        "midpoint_analysis": {
            "profile": {},
            "meridian_houses": {"profile": {"house_code": "X"}},
        },
    }
    roles = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Alcabitus"
    )
    assert roles["status"] == "partial"
    assert roles["native_reference_angle_model"] is None
    assert roles["missing_evidence"] == ["native_reference_angle_model"]
    altered = copy.deepcopy(payload)
    altered["base_chart"]["chart_profile"]["house_system_label_zh"] = "等宫制"
    assert audit_specialty_house_roles(altered)["status"] == "mismatch"


@pytest.mark.parametrize("code", [True, 1.0, -1, 9, "1"])
def test_invalid_requested_codes_do_not_become_partial_evidence(code):
    with pytest.raises(ValueError, match="integer0..8"):
        audit_specialty_house_roles({}, requested_hsys=code)


def test_a_house_label_alone_does_not_certify_unrecorded_specialty_roles():
    profile = {
        "house_system": "alcabitus",
        "house_system_code": 1,
        "house_system_label_zh": "Alcabitus",
    }
    audit = audit_specialty_house_roles({"chart_profile": profile}, requested_hsys=1)
    assert audit["status"] == "partial"
    assert "specialty_geometry_layer" in audit["missing_evidence"]
