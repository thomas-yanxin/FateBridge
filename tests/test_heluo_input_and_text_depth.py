"""Explicit calculation inputs and source-specific quotation integrity."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import _tiaowen, build_snapshot_text, calculate, yao_text
from fatebridge.core.heluo_texts import COLLATION_PATH, collation_summary
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import require_birth_clock
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from tests.heluo_current_source_reference import (
    ALL_HEADER_PAGES,
    HEADER_COUNT,
    PENDING_COUNT,
)

PILLARS = {"year": "甲子", "month": "丁卯", "day": "庚申", "hour": "庚辰"}
ARGS = dict(four_pillars=PILLARS, hour_zhi="辰", birth_year=1924, month_zhi="卯")


@pytest.mark.parametrize(
    "value",
    [None, "", " ", "未知", "24:00", "12:00:60", "09:33:00Z", "09:33+08:00", 0, False],
)
def test_missing_or_invalid_clock_cannot_become_midnight(value):
    with pytest.raises(ValueError):
        require_birth_clock(value)
    for model in (HeluoRequest, CanpingRequest):
        with pytest.raises(ValidationError):
            model(date="2000-05-15", time=value, gender="女", use_true_solar_time=False)
    for build in (build_heluo_result, build_canping_result):
        with pytest.raises(ValueError):
            build(date="2000-05-15", time=value, gender="女", use_true_solar_time=False)


@pytest.mark.parametrize(
    "value,expected",
    [("0:0", "00:00:00"), (" 9:3 ", "09:03:00"), ("09:03:04.125", "09:03:04.125")],
)
def test_explicit_clock_normalization_preserves_supplied_precision(value, expected):
    assert require_birth_clock(value) == expected
    for model in (HeluoRequest, CanpingRequest):
        request = model(
            date="2000-05-15", time=value, gender="女", use_true_solar_time=False
        )
        # The request retains supplied components; the domain still receives
        # the exact original canonical numerical reference through this parser.
        assert request.time == value.strip()
        assert require_birth_clock(request.time) == expected


@pytest.mark.parametrize("value", [True, False, 0, 1])
def test_direct_canping_gender_cannot_bypass_public_string_contract(value):
    with pytest.raises(ValueError):
        build_canping_result(date="2000-05-15", time="09:33", gender=value)


@pytest.mark.parametrize("gender", [None, "", "未知", "typo", True, False, 0, 1])
def test_fixed_pillars_cannot_silently_supply_a_calculation_gender(gender):
    with pytest.raises(ValueError):
        calculate(**ARGS, gender=gender)


def test_gender_is_a_required_public_and_domain_input():
    with pytest.raises(TypeError):
        calculate(**ARGS)
    with pytest.raises(ValidationError):
        HeluoRequest(date="2000-05-15", time="09:33:00", use_true_solar_time=False)
    for gender in (None, "", "未知", "typo"):
        with pytest.raises(ValueError):
            build_heluo_result(date="2000-05-15", time="09:33:00", gender=gender)


@pytest.mark.parametrize("alias", ["女", "female", "FEMALE", "F", " f "])
def test_female_aliases_do_not_follow_the_male_fixed_pillar_path(alias):
    result = calculate(**ARGS, gender=alias)
    # Rule-derived from the original first four-pillar example: yang female
    # puts earth Xun outside sky Qian, then flips upper used line and swaps.
    assert result["gender"] == "女"
    assert result["xian"]["name"] == "風天小畜" and result["xian"]["yuan"] == 6
    assert result["hou"]["name"] == "天水訟" and result["hou"]["yuan"] == 3
    assert result == calculate(**ARGS, gender="女")
    assert result["xian"]["name"] != calculate(**ARGS, gender="男")["xian"]["name"]


@pytest.mark.parametrize(
    "gua,pos,page,expected,old_error",
    [
        ("坤為地", 4, 123, "括囊，無咎，無譽。", "曩"),
        (
            "水雷屯",
            2,
            125,
            "屯如邅如，乘馬班如，匪寇婚媾，女子貞不字，十年乃字。",
            "遭",
        ),
        ("天水訟", 4, 132, "不克訟，復即命渝，安貞吉。", "諭"),
        ("天水訟", 6, 133, "或錫之鞶帶，終朝三褫之。", "擊帶"),
        ("地水師", 1, 134, "師出以律，否臧凶。", "贓"),
    ],
)
def test_scanned_header_corrections_have_specific_page_and_old_reading(
    gua, pos, page, expected, old_error
):
    selected = yao_text(gua, pos)
    assert selected["yaoci"] == expected
    provenance = selected["text_provenance"]
    assert provenance["pdf_page"] == page
    assert provenance["source_url"].endswith(f"#page={page}")
    assert old_error in provenance["inherited_yaoci"]
    assert provenance["commentary_status"] == (
        "source_commentary_visually_collated"
        if gua
        in {
            "乾為天",
            "坤為地",
            "水雷屯",
            "山水蒙",
            "水天需",
            "天水訟",
            "地水師",
            "水地比",
            "風天小畜",
            "天澤履",
        }
        else "inherited_transcription_collation_pending"
    )
    assert provenance["poem_status"] == (
        "source_poems_visually_collated"
        if gua in {"乾為天", "坤為地", "水雷屯", "山水蒙", "水天需", "天水訟", "地水師"}
        else "inherited_poem_source_unverified"
    )
    assert provenance["automatic_branch_selection"] is False


def test_collation_identity_has_90_headers_and_294_still_pending():
    data = json.loads(COLLATION_PATH.read_text())
    summary = collation_summary()
    assert summary["sha256"] == hashlib.sha256(COLLATION_PATH.read_bytes()).hexdigest()
    assert summary["total_line_headers"] == 384
    assert summary["collated_line_headers"] == HEADER_COUNT
    assert summary["pending_line_headers"] == PENDING_COUNT
    assert "independent_second_review_pending" in summary["review_status"]
    root = Path(__file__).parent / "fixtures/numerology_nlc_v1"
    manifest = json.loads((root / "yaoci-manifest.json").read_text())
    assert manifest["pdf_sha256"] == data["source_pdf_sha256"]
    old_pages = {e["pdf_page"] for e in data["entries"][:114]}
    assert old_pages == set(range(119, 166))
    assert {e["pdf_page"] for e in data["entries"][114:120]} == {166, 167}
    assert {e["pdf_page"] for e in data["entries"][120:126]} == {168, 169, 170}
    assert {e["pdf_page"] for e in data["entries"][126:132]} == {170, 171, 172}
    assert {e["pdf_page"] for e in data["entries"][132:138]} == {173, 174, 175}
    assert {e["pdf_page"] for e in data["entries"][138:150]} == {
        175,
        176,
        177,
        178,
        179,
    }
    assert {e["pdf_page"] for e in data["entries"][150:]} == {180, 181}
    assert {e["pdf_page"] for e in data["entries"]} == ALL_HEADER_PAGES
    assert ALL_HEADER_PAGES == old_pages | {
        166,
        167,
        168,
        169,
        170,
        171,
        172,
        173,
        174,
        175,
        176,
        177,
        178,
        179,
        180,
        181,
    }
    for image in manifest["images"]:
        assert (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    for entry in data["entries"]:
        selected = yao_text(entry["hexagram"], entry["line"])
        assert selected["yaoci"] == entry["yaoci"]
        assert selected["text_provenance"]["pdf_page"] == entry["pdf_page"]


def test_source_variants_are_retained_and_uncollated_headers_remain_explicit():
    assert yao_text("水雷屯", 1)["yaoci"].startswith("盤桓")
    assert "龍戰于野" in yao_text("坤為地", 6)["yaoci"]
    assert "用脫桎梏" in yao_text("山水蒙", 1)["yaoci"]
    pending = yao_text("天風姤", 6)
    assert pending["text_provenance"]["yaoci_status"].endswith("pending")
    assert "pdf_page" not in pending["text_provenance"]
    assert yao_text("不存在", 1) is None


def test_selection_cannot_mutate_cached_inherited_or_collated_texts():
    before = copy.deepcopy(_tiaowen())
    for gua in ("坤為地", "天風姤"):
        selected = yao_text(gua, 4)
        selected["yaoci"] = "污染"
        selected["text_provenance"]["commentary_status"] = "伪认证"
        assert yao_text(gua, 4)["yaoci"] != "污染"
        assert yao_text(gua, 4)["text_provenance"]["commentary_status"] == (
            "source_commentary_visually_collated"
            if gua == "坤為地"
            else "inherited_transcription_collation_pending"
        )
    assert _tiaowen() == before


def test_natal_snapshot_and_timing_reference_the_actual_same_collation():
    chart = calculate(**ARGS, gender="FEMALE")
    snapshot = build_snapshot_text(chart, None, None)
    assert "后天·天水訟·六三：食舊德" in snapshot
    assert "先天·風天小畜·上九：既雨既處" in snapshot
    assert "PDF第141页" in snapshot and "待独立复核" in snapshot
    assert "诗歌未见于这些爻解段落，来源待核" in snapshot
    assert snapshot.count("单次目校，待独立复核") >= 2
    selected = _selected_text(
        {"gua": "坤為地", "pos": 4, "lines": [0] * 6}, "day_ordinal"
    )
    assert selected["heluo_commentary"]["yaoci"] == "括囊，無咎，無譽。"
    assert selected["heluo_commentary"]["text_provenance"]["pdf_page"] == 123
    assert selected["zhouyi_verse"]["position"] == 4
