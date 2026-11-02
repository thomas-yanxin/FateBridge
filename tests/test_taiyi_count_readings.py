"""Independent numeric rules, source variants, same-core text and transports."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_counts import (
    contextual_harmony,
    count_assessment,
    count_reading,
    counts_text,
)
from fatebridge.core.metaphysics.taiyi_year import count_categories, cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_counts import TaiyiCountReading
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_count_readings import CORPUS, audit
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload

CASES = json.loads((CORPUS / "numeric-cases.json").read_text())["cases"]


def test_all_five_source_profiles_and_unresolved_words_remain_visible():
    report = audit()
    assert report["source_numeric_domain"] == 40 and report["source_profiles"] == 5
    assert report["catalogue_transcriptions_match"] is True
    assert report["all_selected_numeric_and_inference_checks_passed"] is True
    assert [r["count"] for r in report["literal_rank_differences"]] == [23]
    assert 33 in report["partial_listings_not_negatives"]
    assert report["whole_classic_acceptance_passed"] is False
    assert len(report["source_unadjudicated_readings"]) == 2
    assert report["source_unadjudicated_readings"][1]["values"] == [44, 48]


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["count"]))
def test_complete_frozen_domain_not_only_easy_or_harmonious_values(case):
    n = case["count"]
    row = count_reading(n)
    assert count_categories(n) == case["expected_labels"]
    assert row["missing_labels"] == case["expected_missing"]
    assert row["three_talents_inferred"] is case["expected_fullness_inference"]
    assert row["duse"] is case["expected_duse"]
    assert row["length_label"] == case["expected_length"]
    assert sum(row["components"].values()) == n
    TaiyiCountReading.model_validate(row)


@pytest.mark.parametrize("value", [0, 41, 44, 48, True, False, 15.0, "15"])
def test_invalid_count_is_not_coerced_or_extended_to_fit_source_variants(value):
    with pytest.raises(ValueError):
        count_reading(value)
    with pytest.raises(ValueError):
        count_categories(value)


def test_all_5120_same_core_context_combinations_use_their_own_reference():
    # Literal physical and polarity maps, independent of production constants.
    palaces = {1: "乾", 2: "午", 3: "艮", 4: "卯", 6: "酉", 7: "坤", 8: "子", 9: "巽"}
    numbers = {1: "阴", 2: "阴", 3: "阳", 4: "阳", 6: "阴", 7: "阴", 8: "阳", 9: "阳"}
    positions = dict.fromkeys("子艮卯巽午坤酉乾", "阳") | dict.fromkeys(
        "丑寅辰巳未申戌亥", "阴"
    )
    odd = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39}
    table = {
        ("阳", "奇"): False,
        ("阳", "偶"): True,
        ("阴", "奇"): True,
        ("阴", "偶"): False,
    }
    total = 0
    for taiyi in palaces:
        for marker in positions:
            for n in range(1, 41):
                c = {
                    **cyclic_core(1),
                    "taiyi_number": taiyi,
                    "taiyi_palace": palaces[taiyi],
                    "wenchang_palace": marker,
                    "shiji": marker,
                    "main_count": n,
                    "guest_count": n,
                }
                a = count_assessment(c)
                parity = "奇" if n in odd else "偶"
                for row in a["entries"]:
                    assert resolve({"core_board": c}, row["field"]) == row["value"]
                    for context, polarity in zip(
                        row["contexts"], [numbers[taiyi], positions[marker]]
                    ):
                        assert context["polarity"] == polarity
                        assert context["is_harmonious"] is table[(polarity, parity)]
                        assert context["value"] == resolve(
                            {"core_board": c, "wenchang_palace": marker},
                            context["field"],
                        )
                assert a["overall_harmony_assessed"] is False
                total += 1
    assert total == 5120


def test_unmapped_reference_remains_unknown_not_automatically_yin():
    for ref, value in [("太乙", 5), ("文昌", "中"), ("始击", "未知")]:
        c = contextual_harmony(15, reference=ref, field="test", value=value)
        assert c["polarity"] is c["is_harmonious"] is None


def test_boolean_reference_cannot_be_coerced_into_palace_one():
    with pytest.raises(ValueError):
        contextual_harmony(15, reference="太乙", field="test", value=True)


def test_literal_tiers_are_not_contextual_harmony_or_negative_membership():
    a = count_reading(23)
    assert a["literal_rank_status"] == "different_source_ranks"
    assert a["literal_rank_consensus"] is None
    a = count_reading(33)
    assert a["literal_rank_status"] == "partial_listing_not_unified"
    assert a["literal_rank_consensus"] is None
    by_id = {s["profile_id"]: s for s in a["source_memberships"]}
    assert by_id["siku_wang_vol2"]["harmony_tiers"] == ["上和"]
    assert by_id["ncl_vol2"]["harmony_tiers"] == []
    assert (
        contextual_harmony(33, reference="太乙", field="test", value=9)["is_harmonious"]
        is False
    )
    a = count_reading(37)
    by_id = {s["profile_id"]: s for s in a["source_memberships"]}
    assert a["three_talents_inferred"] is True
    assert by_id["taojin_prose"]["three_talents_listed"] is False
    assert by_id["mishu_transcription"]["three_talents_listed"] is True
    assert count_reading(10)["is_long"] is None
    assert count_reading(15)["duse"] is True
    assert count_reading(15)["three_talents_inferred"] is False


def test_actual_snapshot_and_all_assessment_projection_leaves_are_typed():
    r = calculate_taiyi_analysis(**transport_payload("taiyi", 1915))
    b = r["taiyi"]
    a = b["count_assessment"]
    assert counts_text(a) in r["snapshot_text"]
    for field in a:
        Taiyi.model_validate(
            project_fields(r, ["taiyi.count_assessment." + field], strict_fields=True)[
                "taiyi"
            ]
        )
    row = a["entries"][1]
    for field in row:
        TaiyiCountReading.model_validate(
            project_fields({"row": row}, ["row." + field], strict_fields=True)["row"]
        )
    for row in a["entries"]:
        assert row["value"] == resolve(b, row["field"])
        assert row["field"] in r["snapshot_text"]
        assert len(row["contexts"]) == 2
    Taiyi.model_validate(b)


@pytest.mark.parametrize(
    "mutation", ["drop_count", "edit_source_tier", "erase_out_of_range", "image"]
)
def test_expected_values_source_variants_and_images_cannot_be_erased(
    tmp_path, mutation
):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    if mutation == "image":
        (target / "ncl06604-page39.jpg").write_bytes(b"altered")
    else:
        p = target / (
            "numeric-cases.json" if mutation == "drop_count" else "source-profiles.json"
        )
        d = json.loads(p.read_text())
        if mutation == "drop_count":
            d["cases"].pop(14)
        elif mutation == "edit_source_tier":
            d["profiles"][0]["harmony_tiers"]["上和"].remove(33)
        else:
            d["profiles"][-1]["out_of_range_readings"] = []
        p.write_text(json.dumps(d, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹"):
        audit(target)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_actual_rest_mcp_cli_same_counts_source_gaps_and_corrected_labels(
    key, monkeypatch, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    fields = [
        "taiyi.core_board.main_count_des",
        "taiyi.core_board.guest_count_des",
        "taiyi.count_assessment",
    ]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = {}
    with TestClient(api.app) as c:
        for year in [1908, 1922, 1915]:
            response = c.post(
                spec.rest_path,
                json=transport_payload(key, year),
                params=[
                    ("strict_fields", "true"),
                    ("response_char_limit", "0"),
                    *[("fields", f) for f in fields],
                ],
            )
            assert response.status_code == 200, response.text
            rest[year] = response.json()["taiyi"]

    async def mcp():
        out = {}
        async with Client(create_mcp_app()) as c:
            for year in rest:
                r = await c.call_tool(
                    spec.tool_name,
                    {
                        **transport_payload(key, year),
                        "fields": fields,
                        "strict_fields": True,
                        "include_snapshot_text": False,
                        "response_char_limit": 0,
                    },
                    raise_on_error=False,
                )
                assert not r.is_error, r
                out[year] = r.structured_content["taiyi"]
        return out

    native = asyncio.run(mcp())
    for year in rest:
        args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
        for name, value in transport_payload(key, year).items():
            if name != "use_true_solar_time":
                args.extend(
                    [
                        "--" + name.replace("_", "-"),
                        json.dumps(value) if isinstance(value, dict) else str(value),
                    ]
                )
        assert run(args) == 0
        cli = json.loads(capsys.readouterr().out)["taiyi"]
        assert rest[year] == native[year] == cli
        if year == 1908:
            assert "杜塞（淘金歌）" in cli["core_board"]["guest_count_des"]
            assert "三才足数" not in cli["core_board"]["guest_count_des"]


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_published_count_view_preserves_every_requested_business_field_at_default_budget(
    key,
):
    spec = next(s for s in CATALOG if s.key == key)
    view = "counts" if key == "taiyi" else "taiyi_counts"

    async def call():
        async with Client(create_mcp_app()) as c:
            for year in [1908, 1922, 1915]:
                r = await c.call_tool(
                    spec.tool_name,
                    {
                        **transport_payload(key, year),
                        "fields": suggested_fields(spec, view=view),
                        "strict_fields": True,
                        "include_snapshot_text": False,
                    },
                    raise_on_error=False,
                )
                await _same_run_payload(c, r, require_business_inline=True)
                a = r.structured_content["taiyi"]["count_assessment"]
                assert len(a["entries"]) == 2
                assert len(a["sources"]) == 5
                assert len(a["unadjudicated_source_readings"]) == 2
                assert a["overall_harmony_assessed"] is False

    asyncio.run(call())
