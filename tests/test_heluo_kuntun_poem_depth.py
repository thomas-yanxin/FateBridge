"""Source-first draft withdrawals and twelve new groups, not new horoscopes."""

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from fatebridge.core import heluo_poems as hp
from fatebridge.core.heluo import _tiaowen, gua_lines, yao_text
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures/heluo_kuntun_poems_v1"
VERIFIED = json.loads((ROOT / "verified-readings-v2.json").read_bytes())
AMENDMENTS = json.loads((ROOT / "amendments.json").read_bytes())


def test_new_source_identity_preserves_draft_images_and_previous_six_entries():
    for name, key in [
        ("draft-transcription.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == VERIFIED[key]
    for image in VERIFIED["images"]:
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert (VERIFIED["new_line_poem_groups"], VERIFIED["new_individual_poems"]) == (
        12,
        27,
    )
    assert (
        VERIFIED["independent_second_reviews"]
        == VERIFIED["real_world_observations_added"]
        == 0
    )
    assert hp.collation_summary()["covered_hexagrams"] == [
        "乾為天",
        "坤為地",
        "水雷屯",
        "山水蒙",
        "水天需",
        "天水訟",
        "地水師",
        "水地比",
    ]


@pytest.mark.parametrize(
    "entry", VERIFIED["entries"], ids=lambda e: e["hexagram"] + str(e["line"])
)
def test_every_new_poem_matches_accepted_reading_and_page_not_inherited_summary(entry):
    g, p = entry["hexagram"], entry["line"]
    text = yao_text(g, p)
    inherited = _tiaowen()[g]["yao"][str(p)]
    provenance = text["text_provenance"]
    assert text["poem_sections"] == [
        dict(s, applicability=None) for s in entry["poems"]
    ]
    assert text["shige"] == "\n".join(s["text"] for s in entry["poems"])
    assert provenance["poem_pdf_pages"] == entry["pdf_pages"]
    assert provenance["poem_heading_pdf_page"] == entry["heading_pdf_page"]
    assert provenance["poem_heading_text"] == entry["heading_text"]
    assert provenance["inherited_shige"] == inherited["shige"]
    assert provenance["poem_status"] == "source_poems_visually_collated"
    assert (
        provenance["poem_source_pdf_sha256"]
        != provenance["commentary_source_pdf_sha256"]
    )
    assert text["verdict"] == inherited["verdict"]
    assert "unverified" in text["inherited_xiang_reference"]["status"]
    assert (
        text["inherited_xiang_reference"]["text"] == inherited["shige"].split("\n")[0]
    )
    assert text["poem_selection"]["selected_poem_indices"] == []
    assert text["poem_selection"]["automatic_selection"] is False
    assert (
        _selected_text(
            dict(
                gua=g,
                pos=p,
                changed_pos=7 - p,
                lines=gua_lines(*({"坤為地": ("坤", "坤"), "水雷屯": ("坎", "震")}[g])),
            ),
            "day_ordinal",
        )["heluo_commentary"]
        == text
    )


@pytest.mark.parametrize("entry", AMENDMENTS["source_specific_differences"])
def test_ten_source_specific_differences_have_retained_inherited_witness(entry):
    t = yao_text(entry["hexagram"], entry["line"])
    assert entry["adopted"] in t["shige"]
    assert entry["inherited"] not in t["shige"]
    assert entry["inherited"] in t["text_provenance"]["inherited_shige"]


@pytest.mark.parametrize("entry", AMENDMENTS["draft_withdrawals"])
def test_seven_rejected_draft_readings_are_not_production_defects(entry):
    draft = json.loads((ROOT / "draft-transcription.json").read_bytes())
    old = next(
        e
        for e in draft["entries"]
        if (e["hexagram"], e["line"]) == (entry["hexagram"], entry["line"])
    )["poems"][entry["poem_index"] - 1]["text"]
    actual = yao_text(entry["hexagram"], entry["line"])["poem_sections"][
        entry["poem_index"] - 1
    ]["text"]
    assert entry["draft"] in old and entry["adopted"] in actual
    if entry["draft"] != "進步且盤桓":
        assert entry["draft"] not in actual


@pytest.mark.parametrize(
    "fault", ["negation", "single_count", "heading", "label", "cross_source"]
)
def test_extended_group_forgery_rejects_without_borrowing_version(
    fault, tmp_path, monkeypatch
):
    d = json.loads(hp.COLLATION_PATH.read_bytes())
    target = next(
        e for e in d["entries"] if (e["hexagram"], e["line"]) == ("水雷屯", 1)
    )
    if fault == "negation":
        target["poems"][0]["text"] = target["poems"][0]["text"].removeprefix("不當")
    elif fault == "single_count":
        e = next(e for e in d["entries"] if (e["hexagram"], e["line"]) == ("水雷屯", 4))
        e["poems"].append(copy.deepcopy(e["poems"][0]))
    elif fault == "heading":
        target["heading_pdf_page"] = 7
    elif fault == "label":
        target["poems"][1]["printed_label"] = "不葉者"
    elif fault == "cross_source":
        d["corpus_id"] = "heluo_nlc_volume3_qian_line_poems_v1"
    path = tmp_path / "fault.json"
    path.write_text(json.dumps(d, ensure_ascii=False))
    hp._collation.cache_clear()
    try:
        monkeypatch.setattr(hp, "COLLATION_PATH", path)
        with pytest.raises(NumerologySourceError) as error:
            yao_text("山水蒙", 1)
        assert error.value.reason == "invalid_heluo_poem_collation"
    finally:
        hp._collation.cache_clear()


def test_printed_boundary_vectors_reject_the_first_accepted_missegmentation():
    source = json.loads((ROOT / "printed-boundaries.json").read_bytes())
    before = json.loads(
        (ROOT / "runtime-adoption-before-punctuation.json").read_bytes()
    )

    def mismatches(entries):
        bad = []
        for entry in entries:
            if entry["hexagram"] not in source["clause_lengths"]:
                continue
            for index, poem in enumerate(entry["poems"]):
                lengths = [len(s) for s in re.split("[，。]", poem["text"]) if s]
                if (
                    lengths
                    != source["clause_lengths"][entry["hexagram"]][entry["line"] - 1][
                        index
                    ]
                ):
                    bad.append((entry["hexagram"], entry["line"], index + 1, lengths))
        return bad

    assert mismatches(before["entries"]) == [("水雷屯", 4, 1, [4, 6, 5, 5])]
    assert mismatches(VERIFIED["entries"]) == []
    selected = yao_text("水雷屯", 4)["poem_sections"][0]
    assert selected["printed_clauses"] == source["exception"]["printed_clauses"]
    assert selected["text"].startswith("乘馬班如進，求婚媾吉貞。")
    assert (
        hashlib.sha256((ROOT / "verified-readings.json").read_bytes()).hexdigest()
        == VERIFIED["previous_verified_readings_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "printed-boundaries.json").read_bytes()).hexdigest()
        == VERIFIED["printed_boundaries_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "punctuation-amendment.json").read_bytes()).hexdigest()
        == VERIFIED["punctuation_amendment_sha256"]
    )
