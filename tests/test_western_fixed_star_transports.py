"""Real local transports retain star frame, provenance and partial-layer state."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.core import fixed_stars
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH

PAYLOAD = {
    **BIRTH,
    "birth_year": 2000,
    "birth_month": 12,
    "birth_day": 10,
    "birth_hour": 1,
    "birth_minute": 55,
    "birth_longitude": 120.4667,
    "birth_latitude": 32.5417,
}


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_india"])
def test_published_star_evidence_card_uses_strict_resolvable_fields(key, rest):
    spec = SPECS[key]
    card = evidence_views(spec)["fixed_stars"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=[("fields", p) for p in card["fields"]]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    assert not response.json().get("projection_warnings")
    assert response.json()["chart_profile"]["fixed_stars"]["status"] == "computed"


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_native_star_facts_agree_across_three_transports(
    key, zodiacal, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**PAYLOAD, "zodiacal": zodiacal}
    fields = ["fixed_stars", "chart_profile.fixed_stars", "chart_profile.julian_day_tt"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
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
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        profile = result["chart_profile"]["fixed_stars"]
        assert profile["status"] == "computed"
        assert (
            profile["catalogue_size"] == 20 and len(profile["catalogue_sha256"]) == 64
        )
        assert profile["julian_day_tt"] == result["chart_profile"]["julian_day_tt"]
        assert profile["longitude_frame"] == (
            "sidereal_lahiri" if zodiacal else "tropical_true_ecliptic_of_date"
        )
        antares = next(
            h
            for h in result["fixed_stars"]
            if h["star"] == "Antares" and h["point"] == "Mercury"
        )
        assert antares["orb"] < 0.2
        assert antares["catalogue_identifier"] == "alpha Sco"
        assert antares["astrometry_source_url"].startswith(
            "https://simbad.cds.unistra.fr/"
        )
        assert antares["nature_source_url"].endswith("#9")


def test_unavailable_star_layer_is_preserved_in_full_text(rest, monkeypatch):
    def unavailable(*args, **kwargs):
        return {}, {
            "status": "unavailable",
            "model_id": fixed_stars.MODEL_ID,
            "unavailable_reason": "synthetic native error",
            "note_zh": "恒星层未计算；空列表不表示没有恒星合相。",
        }

    monkeypatch.setattr(fixed_stars, "apparent_positions", unavailable)
    response = rest.post(
        SPECS["astro_chart"].rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["fixed_stars"] == []
    assert result["chart_profile"]["fixed_stars"]["status"] == "unavailable"
    assert "[恒星]\n恒星层未计算" in result["snapshot_text"]
    assert "[恒星]\n无" not in result["snapshot_text"]
