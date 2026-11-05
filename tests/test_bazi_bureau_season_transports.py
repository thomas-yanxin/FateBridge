"""Public routes expose the actual false gate alongside the true branch grouping."""

import asyncio

import pytest

from fatebridge.application.examples import evidence_views
from fatebridge.core.output_bureau_season import BureauSeasonReference
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest

KEYS = [
    "bazi_birth",
    "bazi_career",
    "bazi_wealth",
    "bazi_marriage",
    "bazi_romance",
    "bazi_education",
    "bazi_personality",
    "bazi_relatives",
    "bazi_children",
    "bazi_health",
    "analyze_destiny",
]


rest = _shared_rest


@pytest.mark.parametrize("key", KEYS)
def test_branch_group_and_actual_gate_match_on_rest_native_mcp_and_cli(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = inputs(spec)
    # A fictional coverage input selected for a complete 寅卯辰 group in 辰月.
    # This is transport coverage, not an independent calendrical oracle.
    payload.update(
        name="虚构季支与季相回归",
        birth_year=1986,
        birth_month=4,
        birth_day=29,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_place="上海",
        use_true_solar_time=False,
    )
    fields = evidence_views(spec)["bureau_season_reference"]["fields"]
    rest_spec = SPECS["bazi_birth"] if key == "analyze_destiny" else spec
    response = rest.post(
        rest_spec.rest_path,
        json=payload,
        params={
            "fields": (
                ["bazi_birth." + f for f in fields]
                if key == "analyze_destiny"
                else fields
            ),
            "strict_fields": "true",
            "include_snapshot_text": "false",
            "response_char_limit": 0,
        },
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
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    raw = business(response.json())
    raw = raw["bazi_birth"] if key == "analyze_destiny" else raw
    assert raw == business(cli) == business(protocol.structured_content)
    result = cli
    for component in fields[0].split("."):
        result = result[component]
    BureauSeasonReference.model_validate(result)
    assert result["month_branch"] == "辰"
    assert result["principal_branch_element"] == "土"
    assert result["branch_group_element"] == "木"
    row = result["combination_observations"][0]
    assert row["month_in_target_branch_group"] is True
    # 三命通會·論五行旺相休囚死：土旺时「木尅土則木囚」。
    # https://www.shidianguji.com/zh/book/SK1610/chapter/1kf5v6ol1tqg5
    # 辰整月采用土本气是本工具已声明的范围，不是古典司令日数认证。
    # Keep the branch-group observation separate from that numerical gate.
    assert result["calculated_phases"] == {
        "木": "囚",
        "火": "休",
        "土": "旺",
        "金": "相",
        "水": "死",
    }
    assert row["calculated_target_phase"] == "囚"
    assert row["supplied_season_support_flag"] is False
    assert row["criteria_differ"] is True
    assert row["classical_transformation"] == "not_adjudicated"
    assert result["calculation_effect"] == "none"
