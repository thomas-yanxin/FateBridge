"""Primary missing-label scope and conditional same-gua/different-line fidelity."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, transform_houtian, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

ROOT = Path(__file__).parent / "fixtures/heluo_xiaochuli_v1"
DRAFT = json.loads((ROOT / "reference.json").read_bytes())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_bytes())


@pytest.mark.parametrize(
    "e", VERIFIED["entries"], ids=lambda e: e["hexagram"] + str(e["line"])
)
def test_all_source_words_and_actual_printed_sections_are_used(e):
    t = yao_text(e["hexagram"], e["line"])
    p = t["text_provenance"]
    assert t["detail"] == "".join(s["text"] for s in e["sections"])
    assert t["commentary_sections"] == [
        dict(s, applicability=None) for s in e["sections"]
    ]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []
    assert (
        p["commentary_pdf_pages"] == e["pdf_pages"]
        and p["commentary_reading_notes"] == e["reading_notes"]
    )
    old = _tiaowen()[e["hexagram"]]["yao"][str(e["line"])]
    assert p["inherited_detail"] == old["detail"]
    assert (t["shige"], t["verdict"]) == (old["shige"], old["verdict"])
    bits = [1, 1, 1, 0, 1, 1] if e["hexagram"] == "風天小畜" else [1, 1, 0, 1, 1, 1]
    timed = _selected_text(dict(gua=e["hexagram"], pos=e["line"], lines=bits), "annual")
    assert timed["heluo_commentary"] == t
    assert timed["branch_selection"] == "no_automatic_xie_or_buxie_selection"


@pytest.mark.parametrize("e", VERIFIED["headers"], ids=lambda e: str(e["line"]))
def test_lu_headers_have_specific_primary_pages_and_separate_identity(e):
    t = yao_text("天澤履", e["line"])
    p = t["text_provenance"]
    assert t["yaoci"] == e["yaoci"] and p["pdf_page"] == e["pdf_page"]
    assert p["yaoci_status"] == "source_header_visually_collated"
    assert p["header_content_sha256"] == ht.HEADER_CONTENT_SHA256
    assert p["source_pdf_sha256"] == VERIFIED["source_pdf_sha256"]


def test_unprinted_buxie_does_not_create_a_false_or_fabricated_branch():
    t = yao_text("風天小畜", 3)
    sections = t["commentary_sections"]
    branch = t["commentary_branch_selection"]
    assert [s["section_id"] for s in sections] == ["opening", "xie", "annual"]
    assert "不葉者" not in t["detail"]
    assert branch["condition_labels_not_separately_printed"] == ["不葉者"]
    assert branch["status"] == "not_evaluated" and branch["selected_section_ids"] == []
    assert all(s["applicability"] is None for s in sections)
    assert "反遭傷害" in sections[1]["text"] and "謀則不從" in sections[1]["text"]
    assert "百孽病生" in sections[-1]["text"]
    # The printed 葉者 label is not a promise of favorable reality.
    assert (
        t["text_provenance"]["verdict_status"]
        == "inherited_summary_not_source_branch_judgment"
    )


def test_conditional_xun_initial_and_normal_xun_fourth_share_only_the_gua_name():
    ref = VERIFIED["conditional_reference"]
    actual = yao_text("風天小畜", 1)["commentary_cross_references"][0]
    assert actual == {k: v for k, v in ref.items() if k != "comparison_normal_houtian"}
    before = ref["source_lines"][:]
    for half in (False, True):
        normal = transform_houtian("風天小畜", before, 1, half)
        assert normal == dict(name="巽為風", lines=[0, 1, 1, 0, 1, 1], yuan=4)
        assert (
            normal["name"] == actual["target_hexagram"]
            and normal["yuan"] != actual["target_line"]
        )
    assert before == [1, 1, 1, 0, 1, 1]
    assert actual["target_line"] == 1 and actual["applicability"] is None
    assert actual["automatic_application"] is actual["replaces_chart"] is False
    assert yao_text("巽為風", 1)["text_provenance"]["commentary_status"].endswith(
        "pending"
    )
    assert "commentary_cross_references" not in yao_text("天澤履", 6)
    assert "變為引兌之小人" in yao_text("天澤履", 6)["detail"]


def test_draft_withdrawals_are_not_counted_as_inherited_corrections():
    assert (
        hashlib.sha256((ROOT / "reference.json").read_bytes()).hexdigest()
        == VERIFIED["draft_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "amendments.json").read_bytes()).hexdigest()
        == VERIFIED["amendments_sha256"]
    )
    entries = copy.deepcopy(DRAFT["entries"])
    amendments = json.loads((ROOT / "amendments.json").read_bytes())
    assert len(amendments) == 8
    for a in amendments:
        e = next(
            e
            for e in entries
            if (e["hexagram"], e["line"]) == (a["hexagram"], a["line"])
        )
        section = next(s for s in e["sections"] if s["section_id"] == a["section"])
        assert section["text"] == a["before"]
        section["text"] = a["after"]
    assert [{k: v for k, v in e.items() if k != "reading_notes"} for e in entries] == [
        {k: v for k, v in e.items() if k != "reading_notes"}
        for e in VERIFIED["entries"]
    ]
    for w in DRAFT["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    assert all(144 not in e["pdf_pages"] for e in VERIFIED["entries"])
    assert (
        VERIFIED["new_original_horoscopes"]
        == VERIFIED["new_calendar_instants"]
        == VERIFIED["new_real_world_outcomes"]
        == VERIFIED["independent_second_reviews"]
        == 0
    )
    assert (
        ht.commentary_collation_summary()["collated_line_commentaries"] == HEADER_COUNT
    )
    assert ht.collation_summary()["pending_line_headers"] == PENDING_COUNT


def test_rare_source_words_and_real_inherited_errors_remain_distinct():
    pairs = [
        ("風天小畜", 1, "僧道之儔耳", "僧道之壽耳"),
        ("風天小畜", 2, "為儕長", "為僚長"),
        ("風天小畜", 3, "謀則不從", "諫則不從"),
        ("風天小畜", 4, "上人合意", "士人合志"),
        ("風天小畜", 5, "獨力自畜", "獨力自奮"),
        ("風天小畜", 6, "而君子受其害", "而害乎君子"),
        ("天澤履", 1, "坑君", "玩君"),
        ("天澤履", 2, "無欺", "無歉"),
        ("天澤履", 3, "眇目", "鼓目"),
        ("天澤履", 4, "虎符", "虛符"),
        ("天澤履", 5, "自恃", "自待"),
    ]
    for gua, pos, correct, old in pairs:
        t = yao_text(gua, pos)
        assert correct in t["detail"] and old not in t["detail"]
        assert old in t["text_provenance"]["inherited_detail"]
    assert (
        "主同協意" in yao_text("風天小畜", 5)["detail"]
        and "膺備夫" in yao_text("風天小畜", 5)["detail"]
    )
    assert "飢煖無求" in yao_text("天澤履", 2)["detail"]
    assert "甚則喪亡" in yao_text("天澤履", 5)["detail"]
    four = yao_text("天澤履", 4)
    assert (
        "愬愬" in four["yaoci"] and "愬恕" in four["text_provenance"]["inherited_yaoci"]
    )
    assert "女命得此" in four["commentary_sections"][-1]["text"]
    assert [
        s["section_id"] for s in yao_text("風天小畜", 6)["commentary_sections"]
    ] == ["opening", "xie", "buxie", "female", "annual"]


@pytest.mark.parametrize("fault", ["fabricated_buxie", "wrong_gua_exception"])
def test_layout_exception_does_not_allow_fabricated_or_unregistered_omission(
    fault, tmp_path, monkeypatch
):
    d = json.loads(ht.COMMENTARY_PATH.read_bytes())
    if fault == "fabricated_buxie":
        e = next(
            e for e in d["entries"] if (e["hexagram"], e["line"]) == ("風天小畜", 3)
        )
        e["sections"].insert(
            2,
            dict(
                section_id="buxie",
                condition_label="不葉者",
                text="不葉者這是補造的分支。",
            ),
        )
    else:
        e = next(e for e in d["entries"] if (e["hexagram"], e["line"]) == ("乾為天", 1))
        e["sections"] = [s for s in e["sections"] if s["section_id"] != "buxie"]
    p = tmp_path / "changed.json"
    p.write_text(json.dumps(d, ensure_ascii=False))
    ht._commentary_collation.cache_clear()
    try:
        monkeypatch.setattr(ht, "COMMENTARY_PATH", p)
        # Even if the content pin is bypassed, source-specific shape must reject these.
        monkeypatch.setattr(ht, "_pin_content", lambda data, expected: expected)
        with pytest.raises(NumerologySourceError):
            ht.commentary_collation_summary()
    finally:
        ht._commentary_collation.cache_clear()


@pytest.mark.parametrize("fault", ["quote", "wrong_bits", "wrong_target"])
def test_inconsistent_xiao_initial_reference_is_a_source_error(fault, monkeypatch):
    from fatebridge.core import heluo_hexagrams

    e = copy.deepcopy(
        next(
            e
            for e in VERIFIED["entries"]
            if (e["hexagram"], e["line"]) == ("風天小畜", 1)
        )
    )
    if fault == "quote":
        e["sections"][-1]["text"] = e["sections"][-1]["text"].replace(
            "巽初爻", "巽四爻"
        )
    elif fault == "wrong_bits":
        monkeypatch.setattr(
            heluo_hexagrams, "gua_lines", lambda up, low: [0, 1, 1, 0, 1, 1]
        )
    else:
        monkeypatch.setattr(
            heluo_hexagrams, "lines_to_gua", lambda lines: dict(name="天澤履")
        )
    with pytest.raises(NumerologySourceError):
        ht._commentary_cross_references(e)


def test_audit_rejects_same_gua_but_wrong_reference_line(monkeypatch):
    from scripts import audit_numerology as audit

    original = ht._commentary_cross_references

    def wrong(entry):
        rows = original(entry)
        if entry["hexagram"] == "風天小畜" and rows:
            rows[0]["target_line"] = 4
        return rows

    monkeypatch.setattr(ht, "_commentary_cross_references", wrong)
    result = audit.xiaochuli_commentary_checks()
    assert (
        not result["checks_passed"]
        and dict(kind="xiaochu1_conditional_reference") in result["failures"]
    )
