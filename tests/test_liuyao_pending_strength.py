"""Unresolved outgoing support cannot prove an unsupported weak target."""

import asyncio

import pytest

from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.services.divination import calculate_sixyao_analysis
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

CASES = [
    pytest.param(
        "2026-01-27",
        "001000",
        "001101",
        6,
        5,
        "pending_supports",
        None,
        id="pending-own-si-keeps-target-unknown",
    ),
    pytest.param(
        "2026-01-31",
        "001000",
        "001101",
        6,
        5,
        "supports",
        True,
        id="qualified-own-si-keeps-confirmed-support",
    ),
    pytest.param(
        "2026-01-27",
        "001101",
        "101101",
        1,
        4,
        "blocked_supports",
        False,
        id="certain-back-control-still-blocks-support",
    ),
]


def payload_for(date, base, changed):
    return dict(
        date=date,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
    )


def check(output, source, target, bucket, matched):
    c = output["liuyao_evidence"]["conditional_analysis"]
    s = c["generation_conditions"]["sources"][source - 1]
    pair = next(
        p
        for p in c["generation_conditions"]["generations"]
        if (p["source_position"], p["target_position"]) == (source, target)
    )
    assert s["condition_match"] is pair["condition_match"] is matched
    assert pair["target_reception_condition"] is True
    assert pair["benefit_now"] is matched
    strength = c["classical_assessment"]["lines"][target - 1]["strength"]
    actor = next(a for a in strength[bucket] if a.get("position") == source)
    assert actor["generation_condition_match"] is matched
    assert actor["benefit_now"] is matched
    for other in {"supports", "pending_supports", "blocked_supports"} - {bucket}:
        assert not any(a.get("position") == source for a in strength[other])
    if matched is None:
        own = c["growth_conditions"]["lines"][source - 1]["own_changed_si"]
        assert own["changed_void"] is True
        assert own["condition_match"] is own["qualified_back_control_condition"] is None
        assert strength["status"] == "contested_or_pending"
        assert strength["is_supported"] is strength["is_weak"] is None
        assert actor["reason"] == "本位金化巳的长生或回头克资格待审"


@pytest.mark.parametrize("date,base,changed,source,target,bucket,matched", CASES)
def test_unresolved_source_keeps_strength_unknown(
    date, base, changed, source, target, bucket, matched
):
    request = SixYaoRequest.model_validate(payload_for(date, base, changed))
    result = calculate_sixyao_analysis(**request.model_dump())
    check(result, source, target, bucket, matched)


def test_pending_source_does_not_override_month_broken_day_controlled_target():
    request = SixYaoRequest.model_validate(
        payload_for("2026-05-24", "001000", "001101")
    )
    result = calculate_sixyao_analysis(**request.model_dump())
    c = result["liuyao_evidence"]["conditional_analysis"]
    pair = next(
        p
        for p in c["generation_conditions"]["generations"]
        if (p["source_position"], p["target_position"]) == (6, 5)
    )
    assert pair["condition_match"] is None
    assert pair["target_reception_condition"] is pair["benefit_now"] is False
    assert (
        pair["target_status"] == "month_broken_day_controlled_without_independent_root"
    )
    strength = c["classical_assessment"]["lines"][4]["strength"]
    assert strength["is_weak"] is strength["is_failing"] is True
    assert any(a.get("position") == 6 for a in strength["blocked_supports"])


@pytest.mark.parametrize("date,base,changed,source,target,bucket,matched", CASES)
def test_pending_support_qualification_matches_real_transports(
    date, base, changed, source, target, bucket, matched, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = payload_for(date, base, changed)
    fields = [
        "nongli.dayGanZi",
        "liuyao_evidence.conditional_analysis.classical_assessment.lines",
        "liuyao_evidence.conditional_analysis.growth_conditions.lines",
        "liuyao_evidence.conditional_analysis.generation_conditions",
    ]
    response = rest.post(
        spec.rest_path, json=payload, params={"fields": fields, "strict_fields": True}
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=("--fields", *fields, "--strict-fields")
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    expected = business(response.json())
    assert expected == business(cli) == business(protocol.structured_content)
    check(expected, source, target, bucket, matched)
