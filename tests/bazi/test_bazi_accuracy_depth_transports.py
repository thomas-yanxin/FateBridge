"""Astronomical normalization and source-root facts share one public calculation."""

import asyncio

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

PAYLOAD = {
    "name": "虚构均时差边界回归",
    "birth_year": 2024,
    "birth_month": 12,
    "birth_day": 6,
    "birth_hour": 0,
    "birth_minute": 52,
    "gender": "男",
    "birth_longitude": 0,
    "birth_timezone": "UTC",
    "use_true_solar_time": True,
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


def test_new_hour_pillar_and_source_root_profile_match_all_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    code, local = call_cli(
        spec, PAYLOAD, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, PAYLOAD))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        birth = output["bazi_birth"]
        assert birth["four_pillars"]["hour"]["branch"] == "丑"
        assert (
            birth["person_info"]["time_adjustment"]["equation_of_time_method"]
            == "swiss_time_equ_utc_instant_v1"
        )
        assert (
            birth["classical"]["root_profile"]
            == birth["structure_profile"]["evidence_chain"]["classical_root_profile"]
        )
        assert (
            birth["classical"]["root_profile"]["global_strength_status"]
            == "not_adjudicated"
        )
        assert "原典根类（未判根损）" in output["snapshot_text"]


def test_root_profile_can_be_projected_with_published_nested_contract(rest):
    response = rest.post(
        SPECS["bazi_birth"].rest_path,
        json=PAYLOAD,
        params={
            "fields": [
                "bazi_birth.classical.root_profile",
                "bazi_birth.person_info.time_adjustment",
            ],
            "strict_fields": "true",
            "include_snapshot_text": "false",
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["bazi_birth"]
    assert len(result["classical"]["root_profile"]["roots"]) == 4
    assert result["person_info"]["time_adjustment"]["solar_time_strategy"] == "apparent"


rest = _shared_rest
