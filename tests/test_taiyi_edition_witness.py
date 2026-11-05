"""A named second facsimile witnesses three rows, without erasing the first."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_source_alignment import source_alignment_text
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_taiyi_source_alignment import board


@pytest.mark.parametrize(
    "ju,expected,old_shiji,old_guest,images",
    [
        (37, (4, "寅", "坤", "申", 1, 25), "午", 25, [17, 18]),
        (43, (2, "午", "巳", "寅", 2, 1), "坤", 38, [20]),
        (44, (2, "未", "坤", "丑", 39, 38), "酉", 31, [20]),
    ],
)
def test_named_1599_edition_support_is_bounded_and_preserves_jinjing(
    ju, expected, old_shiji, old_guest, images
):
    assessment = board(ju, yin=True)["count_source_assessment"]
    (witness,) = assessment["edition_comparisons"]
    assert witness["source_id"] == "wujing_yonezawa_wanli27_yin_v1"
    assert witness["catalog_url"] == (
        "https://www.library.yonezawa.yamagata.jp/dg/AA040.html"
    )
    assert witness["catalog_identity"] == "米沢善本40 / AA040001 / 20冊"
    assert witness["edition"] == "万暦27年（1599）跋重刻本"
    assert witness["source_title"] == "武經總要後集卷之二十"
    assert witness["review_status"] == "ai_facsimile_reading_pending_expert_collation"
    assert witness["textual_lineage_independence_established"] is False
    assert witness["whole_work_acceptance_passed"] is False
    assert [image["image_number"] for image in witness["images"]] == images
    fields = (
        "taiyi_number",
        "wenchang_palace",
        "shiji",
        "jishen",
        "main_count",
        "guest_count",
    )
    facts = {f["field"]: f for f in witness["observations"]}
    assert tuple(facts) == fields
    assert tuple(facts[f]["edition_value"] for f in fields) == expected
    assert all(f["matches_current"] for f in facts.values())
    assert facts["shiji"]["selected_source_value"] == old_shiji
    assert not facts["shiji"]["matches_selected_source"]
    assert facts["guest_count"]["selected_source_value"] == old_guest
    # The original source warning, selected facts and denominators remain intact.
    assert assessment["summary"]["status"] == "differences_unadjudicated"
    assert (
        next(f for f in assessment["positions"] if f["field"] == "shiji")[
            "source_value"
        ]
        == old_shiji
    )
    text = source_alignment_text(assessment)
    assert "1599" in text and "谱系独立性未证" in text
    assert "原《金镜》分歧保留" in text


def test_unread_rows_and_yang_twins_do_not_acquire_edition_support():
    for yin, ju in [(False, 37), (False, 43), (False, 44), (True, 36), (True, 45)]:
        assert board(ju, yin)["count_source_assessment"]["edition_comparisons"] == []


def test_returned_witness_cannot_mutate_later_runs():
    first = board(37, yin=True)["count_source_assessment"]["edition_comparisons"][0]
    first["images"][0]["sha256"] = "caller annotation"
    first["observations"][2]["edition_value"] = "caller annotation"
    second = board(37, yin=True)["count_source_assessment"]["edition_comparisons"][0]
    assert second["images"][0]["sha256"] == (
        "dec593b89d9db04cfacfd1cb608bbbc10e0ec0b7a30aeb57c54c6494cc95bff9"
    )
    assert second["observations"][2]["edition_value"] == "坤"


@pytest.mark.parametrize(
    "ju,jishen,wenchang,expected_shiji,addends,expected_guest",
    [
        (37, "申", "寅", "坤", [7, 6, 1, 8, 3], 25),
        (43, "寅", "午", "巳", [1], 1),
        (44, "丑", "未", "坤", [7, 6, 1, 8, 3, 4, 9], 38),
    ],
)
def test_three_selected_rows_against_independent_ring_and_integer_arithmetic(
    ju, jishen, wenchang, expected_shiji, addends, expected_guest
):
    # Literal compass order and principal weights, independently from core tables.
    ring = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
    weights = {"乾": 1, "子": 8, "艮": 3, "卯": 4, "巽": 9, "午": 2, "坤": 7, "酉": 6}
    steps = (ring.index(wenchang) - ring.index(jishen)) % 16
    marker = ring[(ring.index("艮") + steps) % 16]
    assert marker == expected_shiji
    core = board(ju, yin=True)["core_board"]
    assert core["shiji"] == marker
    target = next(p for p, value in weights.items() if value == core["taiyi_number"])
    values = [] if marker in weights else [1]
    index = ring.index(marker)
    while ring[index] != target:
        if ring[index] in weights:
            values.append(weights[ring[index]])
        index = (index + 1) % 16
    assert values == addends and sum(values) == expected_guest
    assert core["guest_count"] == expected_guest


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "day,hour,ju", [(24, 16, 37), (25, 4, 43), (25, 6, 44), (23, 16, 25)]
)
def test_actual_rest_mcp_cli_keep_both_editions(
    key, day, hour, ju, capsys, monkeypatch
):
    # Modern hour-phase twins exercise delivery; no ancient civil date is inferred.
    if key == "taiyi":
        payload = {
            "analysis_year": 2026,
            "analysis_month": 6,
            "analysis_day": day,
            "analysis_hour": hour,
            "analysis_timezone": "+08:00",
            "calculation_mode": "hour",
            "use_true_solar_time": False,
        }
    else:
        payload = {
            "date": f"2026-06-{day}",
            "time": f"{hour:02d}:00:00",
            "zone": "+08:00",
            "taiyi_options": {"calculation_mode": "hour"},
            "use_true_solar_time": False,
        }
    fields = ["taiyi.core_board", "taiyi.count_source_assessment"]
    spec = next(s for s in CATALOG if s.key == key)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post(
            spec.rest_path,
            json=payload,
            params=[
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
                *[("fields", f) for f in fields],
            ],
        )
    assert response.status_code == 200, response.text
    expected = response.json()["taiyi"]
    assert expected["core_board"]["yin_dun"] is True
    assert expected["core_board"]["kook_number"] == ju
    assessment = expected["count_source_assessment"]
    assert assessment["summary"]["status"] == "differences_unadjudicated"
    assert assessment["edition_comparisons"][0]["matching_current_observations"] == (
        1 if ju == 25 else 6
    )
    assert assessment["edition_comparisons"][0]["ju"] == ju
    args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
    for name, value in payload.items():
        if name != "use_true_solar_time":
            args += [
                "--" + name.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["taiyi"] == expected

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key,
                {
                    **payload,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            assert result.structured_content["taiyi"] == expected

    asyncio.run(call())


@pytest.mark.parametrize(
    "yin,ju,field,printed,selected",
    [
        (False, 39, "main_count", 35, 25),
        (False, 50, "main_count", 16, 6),
        (True, 11, "guest_count", 26, 36),
        (True, 15, "guest_count", 25, 29),
        (True, 25, "main_count", 31, 21),
        (True, 26, "main_count", 30, 31),
        (True, 27, "main_count", 29, 39),
        (True, 43, "guest_count", 1, 38),
        (True, 44, "guest_count", 38, 31),
        (True, 46, "guest_count", 1, 2),
        (True, 70, "main_count", 32, 22),
    ],
)
def test_all_original_count_conflicts_have_named_variants_without_regrading(
    yin, ju, field, printed, selected
):
    assessment = board(ju, yin)["count_source_assessment"]
    (witness,) = assessment["edition_comparisons"]
    fact = next(f for f in witness["observations"] if f["field"] == field)
    assert fact["edition_value"] == printed
    assert fact["selected_source_value"] == selected
    assert fact["matches_current"]
    assert not fact["matches_selected_source"]
    assert witness["yin_dun"] is yin
    assert (
        witness["count_conflict_status"]
        == "printed_edition_variant_observed_pending_expert_collation"
    )
    assert witness["whole_work_acceptance_passed"] is False
    assert assessment["summary"]["status"] == "differences_unadjudicated"
    if ju not in (43, 44):
        assert witness["required_observations"] == 1
        assert len(witness["unread_fields"]) == 5
    assert "原《金镜》分歧保留" in source_alignment_text(assessment)
