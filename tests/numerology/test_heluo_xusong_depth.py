"""Source-read Xu/Song conditions and pinned content cannot exchange meanings."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import _tiaowen, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.utils.errors import NumerologySourceError
from tests.support.heluo_source_facts import (
    COMMENTARY_RULESET_ID,
    HEADER_COUNT,
    PENDING_COUNT,
)

ROOT = Path(__file__).parents[1] / "fixtures/heluo_xusong_v1"
REF = json.loads((ROOT / "reference.json").read_text())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_text())


def test_audit_rejects_bypassing_canonical_content_identity(monkeypatch):
    from scripts.numerology import audit_numerology as audit

    monkeypatch.setattr(ht, "_pin_content", lambda data, expected: expected)
    result = audit.xusong_commentary_checks()
    assert not result["checks_passed"]
    assert {"kind": "heluo_nonempty_text_tamper_accepted", "layer": "header"} in result[
        "failures"
    ]
    assert {
        "kind": "heluo_nonempty_text_tamper_accepted",
        "layer": "commentary",
    } in result["failures"]


def test_source_words_that_change_interpretation_and_unusual_readings():
    one = yao_text("水天需", 1)
    assert (
        "恬淡之官" in one["detail"]
        and "冷淡之官" in one["text_provenance"]["inherited_detail"]
    )
    assert "郊外巡捕" in one["detail"] and "黜陟不加" in one["detail"]
    three = yao_text("水天需", 3)
    assert (
        "自貽伊戚" in three["detail"]
        and "自始伊戚" in three["text_provenance"]["inherited_detail"]
    )
    four = yao_text("水天需", 4)
    assert "幼失恃怙，老倍富豪" in four["detail"]
    assert "囹圄" in four["detail"] and "寵辱不加" in four["detail"]
    assert "正即" in yao_text("水天需", 5)["detail"]
    upper = yao_text("水天需", 6)
    assert "危疑之損" in upper["detail"] and "倉卒之患" in upper["detail"]
    song = yao_text("天水訟", 2)
    assert (
        "而貴不受殃" in song["detail"]
        and "而責不受殃" in song["text_provenance"]["inherited_detail"]
    )
    assert (
        "毀譽不遷" in song["detail"]
        and "毀辱不逮" in song["text_provenance"]["inherited_detail"]
    )
    assert "因人以成其事功" in yao_text("天水訟", 3)["detail"]
    assert "無舊" in yao_text("天水訟", 3)["detail"]
    assert "女人為女人命婦貞潔" in yao_text("天水訟", 4)["detail"]
    assert "封拜之大" in yao_text("天水訟", 5)["detail"]
    assert "自訟則吉" in yao_text("天水訟", 6)["commentary_sections"][-1]["text"]


def test_nested_conditions_and_character_omens_are_not_automatically_applied():
    for g in ("水天需", "天水訟"):
        for pos in range(1, 7):
            t = yao_text(g, pos)
            assert all(s["applicability"] is None for s in t["commentary_sections"])
            assert t["commentary_branch_selection"]["selected_section_ids"] == []
    t = yao_text("天水訟", 4)
    assert "女人為女人" in t["commentary_sections"][1]["text"]
    assert "命字、安字之義" in t["commentary_sections"][1]["text"]
    assert "如元數凶者" in yao_text("天水訟", 2)["commentary_sections"][-1]["text"]
    assert "如數空者" in yao_text("水天需", 1)["commentary_sections"][-1]["text"]


def test_draft_withdrawals_and_native_source_identity_are_preserved():
    assert (
        VERIFIED["draft_sha256"]
        == hashlib.sha256((ROOT / "reference.json").read_bytes()).hexdigest()
    )
    assert (
        VERIFIED["amendments_sha256"]
        == hashlib.sha256((ROOT / "amendments.json").read_bytes()).hexdigest()
    )
    entries = copy.deepcopy(REF["entries"])
    for c in json.loads((ROOT / "amendments.json").read_text()):
        e = next(
            e
            for e in entries
            if (e["hexagram"], e["line"]) == (c["hexagram"], c["line"])
        )
        section = next(s for s in e["sections"] if s["section_id"] == c["section"])
        assert c["before"] in section["text"]
        section["text"] = section["text"].replace(c["before"], c["after"])
    for a, b in zip(entries, VERIFIED["entries"]):
        assert {k: v for k, v in a.items() if k != "reading_notes"} == {
            k: v for k, v in b.items() if k != "reading_notes"
        }
    for w in REF["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    assert (
        REF["new_original_horoscopes"]
        == REF["new_calendar_instants"]
        == REF["independent_second_reviews"]
        == 0
    )


@pytest.mark.parametrize("layer", ["header", "commentary"])
@pytest.mark.parametrize(
    "fault", ["nonempty_text", "metadata", "fraction_total", "swapped_content"]
)
def test_valid_json_and_nonempty_fields_do_not_preserve_false_collation_identity(
    layer, fault, tmp_path, monkeypatch
):
    attr, loader, summary, reason = (
        (
            "COLLATION_PATH",
            ht._collation,
            ht.collation_summary,
            "invalid_heluo_header_collation",
        )
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            ht._commentary_collation,
            ht.commentary_collation_summary,
            "invalid_heluo_commentary_collation",
        )
    )
    d = json.loads(getattr(ht, attr).read_text())
    if fault == "metadata":
        d["review_status"] = "independently_certified"
    elif fault == "fraction_total":
        d["total_line_headers" if layer == "header" else "total_line_commentaries"] = (
            384.0
        )
    elif layer == "header":
        if fault == "swapped_content":
            d["entries"][0]["yaoci"], d["entries"][1]["yaoci"] = (
                d["entries"][1]["yaoci"],
                d["entries"][0]["yaoci"],
            )
        else:
            d["entries"][0]["yaoci"] = "非原典标题"
    else:
        sections = d["entries"][0]["sections"]
        if fault == "swapped_content":
            sections[1]["text"], sections[2]["text"] = (
                sections[2]["text"],
                sections[1]["text"],
            )
        else:
            sections[1]["text"] = "葉者這是被替換的非原典正文。"
    p = tmp_path / "source.json"
    p.write_text(json.dumps(d, ensure_ascii=False))
    loader.cache_clear()
    try:
        monkeypatch.setattr(ht, attr, p)
        with pytest.raises(NumerologySourceError) as error:
            summary()
        assert error.value.reason == reason
    finally:
        loader.cache_clear()


@pytest.mark.parametrize("layer", ["header", "commentary"])
def test_formatting_only_changes_loaded_bytes_not_pinned_content(
    layer, tmp_path, monkeypatch
):
    attr, loader, summary = (
        ("COLLATION_PATH", ht._collation, ht.collation_summary)
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            ht._commentary_collation,
            ht.commentary_collation_summary,
        )
    )
    raw = getattr(ht, attr).read_bytes()
    expected = summary()["content_sha256"]
    p = tmp_path / "reformatted.json"
    p.write_text(
        json.dumps(json.loads(raw), ensure_ascii=True, sort_keys=True, indent=4)
    )
    assert p.read_bytes() != raw
    loader.cache_clear()
    try:
        monkeypatch.setattr(ht, attr, p)
        s = summary()
        assert (
            s["content_sha256"] == expected
            and s["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        )
    finally:
        loader.cache_clear()


def test_metadata_title_counts_and_trace_describe_the_current_corpus():
    r = build_heluo_result(
        date="2000-01-11",
        time="00:30",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    e = r["numerology_evidence"]
    s = e["commentary_collation"]
    assert (s["collated_line_commentaries"], s["pending_line_commentaries"]) == (
        HEADER_COUNT,
        PENDING_COUNT,
    )
    rule = next(v for v in e["rulesets"] if v["ruleset_id"] == COMMENTARY_RULESET_ID)
    assert (
        f"{HEADER_COUNT}条" in rule["source_title"]
        and "乾坤十二" not in rule["source_title"]
    )
    assert rule["source_content_sha256"] == s["content_sha256"]
    trace = next(
        t["facts"]
        for t in e["rule_trace"]
        if t["rule_id"] == "heluo_selected_line_collation_v1"
    )
    assert trace["commentary_content_sha256"] == s["content_sha256"]
    assert trace["header_content_sha256"] == e["yaoci_collation"]["content_sha256"]
    assert not any("乾坤十二条注文" in c for c in e["interpretation_constraints"])
