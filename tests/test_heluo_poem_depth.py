"""Image-bound partial poem readings; same reader, not independent validation."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_poems as hp
from fatebridge.core.heluo import _tiaowen, build_snapshot_text, yao_text
from fatebridge.core.heluo_texts import SOURCE_PDF_SHA256
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures/heluo_poem_source_v1"
REF = json.loads((ROOT / "reference.json").read_bytes())
VERIFIED = json.loads((ROOT / "verified-readings.json").read_bytes())


def test_poem_witness_and_discovery_draft_identities_are_retained():
    for witness in REF["images"]:
        assert (
            hashlib.sha256((ROOT / witness["file"]).read_bytes()).hexdigest()
            == witness["sha256"]
        )
    for name, key in [
        ("reference.json", "source_reference_sha256"),
        ("draft-transcription.json", "draft_sha256"),
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == VERIFIED[key]
    assert REF["accepted_runtime_poem_groups_added"] == 0  # historical discovery state
    assert (
        VERIFIED["independent_second_reviews"]
        == VERIFIED["real_world_observations_added"]
        == 0
    )
    s = hp.collation_summary()
    assert (
        s["collated_line_poem_groups"],
        s["pending_line_poem_groups"],
        s["total_line_poem_groups"],
    ) == (48, 336, 384)
    assert s["collated_individual_poems"] == 117 and s["total_individual_poems"] is None
    assert s["source_pdf_sha256"] == REF["source_pdf_sha256"] != SOURCE_PDF_SHA256
    assert s["sha256"] == hashlib.sha256(hp.COLLATION_PATH.read_bytes()).hexdigest()
    assert s["content_sha256"] == hp.CONTENT_SHA256


@pytest.mark.parametrize("entry", VERIFIED["entries"])
def test_every_printed_poem_and_label_is_adopted_with_its_own_source(entry):
    line = entry["line"]
    result = yao_text("乾為天", line)
    inherited = _tiaowen()["乾為天"]["yao"][str(line)]
    p = result["text_provenance"]
    assert result["shige"] == "\n".join(x["text"] for x in entry["poems"])
    assert result["poem_sections"] == [
        dict(x, applicability=None) for x in entry["poems"]
    ]
    assert p["inherited_shige"] == inherited["shige"]
    assert (
        result["inherited_xiang_reference"]["text"] == inherited["shige"].split("\n")[0]
    )
    assert "unverified" in result["inherited_xiang_reference"]["status"]
    assert "象曰" not in result["shige"]
    assert p["poem_pdf_pages"] == entry["pdf_pages"]
    assert p["poem_heading_pdf_page"] == entry["heading_pdf_page"]
    assert (
        p["poem_source_pdf_sha256"]
        == hp.SOURCE_PDF_SHA256
        != p["commentary_source_pdf_sha256"]
    )
    assert p["poem_status"] == "source_poems_visually_collated"
    assert result["poem_selection"]["selected_poem_indices"] == []
    assert result["poem_selection"]["automatic_selection"] is False
    assert result["verdict"] == inherited["verdict"]
    assert p["verdict_status"] == "inherited_summary_not_source_branch_judgment"
    timing = _selected_text(
        dict(gua="乾為天", pos=line, changed_pos=1, lines=[1] * 6), "day_ordinal"
    )
    assert timing["heluo_commentary"] == result


@pytest.mark.parametrize(
    "entry",
    json.loads((ROOT / "amendments.json").read_bytes())[
        "source_specific_lexical_differences"
    ],
)
def test_selected_witness_differences_do_not_silently_emend_the_book(entry):
    result = yao_text("乾為天", entry["line"])
    assert (
        entry["adopted"] in result["shige"]
        and entry["inherited"] not in result["shige"]
    )
    assert entry["inherited"] in result["text_provenance"]["inherited_shige"]


def test_unknown_poem_control_and_cached_data_remain_unmodified():
    inherited = copy.deepcopy(_tiaowen())
    result = yao_text("乾為天", 5)
    result["poem_sections"][1]["text"] = "pollution"
    result["text_provenance"]["poem_pdf_pages"].append(999)
    entry = hp.poems_for_line("乾為天", 5)
    entry["poems"].clear()
    assert "pollution" not in str(yao_text("乾為天", 5))
    assert 999 not in yao_text("乾為天", 5)["text_provenance"]["poem_pdf_pages"]
    from tests.heluo_guan_shi_revision_reference import (
        assert_r84_poem_control_and_all_pending,
    )

    assert assert_r84_poem_control_and_all_pending() == 336
    assert (
        yao_text("地水師", 1)["text_provenance"]["inherited_shige"]
        == inherited["地水師"]["yao"]["1"]["shige"]
    )
    assert _tiaowen() == inherited
    # Meng is already collated; keep an actual unreviewed poem control.
    unknown = yao_text("天雷無妄", 1)
    assert (
        unknown["text_provenance"]["poem_status"] == "inherited_poem_source_unverified"
    )
    assert "poem_sections" not in unknown
    chart = dict(
        tian=1,
        tianGua="乾",
        di=2,
        diGua="坤",
        xian=dict(name="乾為天", lines=[1] * 6, yuan=5),
        hou=dict(name="天雷無妄", lines=[1, 0, 0, 1, 1, 1], yuan=1),
    )
    snapshot = build_snapshot_text(chart, None, None)
    assert "本爻3首诗" in snapshot and "来源待核" in snapshot
    assert unknown["shige"] in snapshot


@pytest.mark.parametrize(
    "fault",
    [
        "text",
        "label",
        "count",
        "line_bool",
        "identity",
        "missing",
        "swapped",
        "heading",
    ],
)
def test_nonempty_source_forgery_cannot_borrow_the_collated_identity(
    fault, monkeypatch, tmp_path
):
    data = json.loads(hp.COLLATION_PATH.read_bytes())
    if fault == "text":
        data["entries"][0]["poems"][0]["text"] = "非空伪文"
    elif fault == "label":
        data["entries"][0]["poems"][1]["printed_label"] = "吉者"
    elif fault == "count":
        data["entries"][0]["poems"].pop()
    elif fault == "line_bool":
        data["entries"][0]["line"] = True
    elif fault == "identity":
        data["source_pdf_sha256"] = SOURCE_PDF_SHA256
    elif fault == "missing":
        data["entries"].pop()
    elif fault == "swapped":
        (
            data["entries"][0]["poems"][0]["text"],
            data["entries"][0]["poems"][1]["text"],
        ) = (
            data["entries"][0]["poems"][1]["text"],
            data["entries"][0]["poems"][0]["text"],
        )
    elif fault == "heading":
        data["entries"][0]["heading_pdf_page"] = 3
    path = tmp_path / "fault.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    hp._collation.cache_clear()
    try:
        monkeypatch.setattr(hp, "COLLATION_PATH", path)
        with pytest.raises(NumerologySourceError) as error:
            yao_text(
                "坤為地", 1
            )  # validation must not depend on selecting a covered poem
        assert error.value.reason == "invalid_heluo_poem_collation"
    finally:
        hp._collation.cache_clear()


def test_formatting_changes_loaded_byte_hash_but_not_the_content_identity(
    monkeypatch, tmp_path
):
    raw = hp.COLLATION_PATH.read_bytes()
    data = json.loads(raw)
    path = tmp_path / "format.json"
    path.write_bytes(raw)
    hp._collation.cache_clear()
    try:
        monkeypatch.setattr(hp, "COLLATION_PATH", path)
        first = hp.collation_summary()
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        assert (
            hp.collation_summary() == first
        )  # loaded bytes remain truthful to cached text
        hp._collation.cache_clear()
        second = hp.collation_summary()
        assert second["sha256"] != first["sha256"]
        assert second["content_sha256"] == first["content_sha256"]
    finally:
        hp._collation.cache_clear()
