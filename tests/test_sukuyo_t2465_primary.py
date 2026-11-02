"""Direct primary quotations retain apparatus and the prior punctuation finding."""

import json
from pathlib import Path

import pytest

from scripts.audit_sukuyo_t2465_primary import SATQuotationParser, verify_primary

ROOT = Path(__file__).resolve().parents[1]


def test_offline_quotation_check_does_not_claim_full_response_rechecked():
    result = verify_primary()
    assert result["selected_quotation_lines_checked"] == 15
    assert len(result["calendar_apparatus"]) == 5
    assert not result["full_publisher_response_bytes_rechecked"]
    assert not result["facsimile_collation_complete"]
    assert not result["full_publisher_response_redistributed"]
    assert not result["cached_calendar_windows_exactly_match_downloaded_quotations"]
    assert result["cached_quotation_discrepancies"] == [
        {
            "locator": "T2465_.78.0030c26",
            "cached_terminal_text": "眞宿無改代也。",
            "downloaded_terminal_text": "眞宿無改代也｣",
            "meaning_changed": False,
            "old_cached_fixture_modified": False,
        }
    ]


def test_delivered_active_edition_matches_frozen_quotations_and_original_apparatus():
    source = json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_t1299_calendar_profiles.json").read_bytes()
    )["hinoo_addendum"]
    result = verify_primary()
    primary = source["downloaded_primary_edition"]
    assert source["active_primary_evidence"] == "downloaded_primary_edition"
    for key in [
        "publisher_html_response_sha256",
        "publisher_html_response_bytes",
        "downloaded_calendar_windows",
        "calendar_apparatus",
        "edition_witness_note_html",
        "calendar_window_sha256",
    ]:
        assert primary[key] == result[key]
    assert "建久六年寫高山寺藏本" in primary["edition_witness_note_html"]
    assert "寶暦十一年寫智山專門學校藏本" in primary["edition_witness_note_html"]
    notes = {row["line"]: row["notes_html"] for row in primary["calendar_apparatus"]}
    assert notes["0030c23"] == ["半＋（也）＜甲＞"]
    assert notes["0030c17"] == ["十＝月＜甲＞"]
    assert "十六字" in notes["0030c18"][0]
    assert not primary["facsimile_collation_complete"]
    assert primary["downloaded_calendar_windows"][1]["text"].endswith("也｣")
    retained = json.loads(
        (ROOT / "tests/fixtures/sukuyo-hinoo-primary-cache.json").read_bytes()
    )
    assert source["cached_primary_excerpt"] == retained


def test_wrong_or_truncated_full_response_is_rejected(tmp_path):
    path = tmp_path / "primary.html"
    path.write_text("<a name='0030c23'>半已上</a>")
    with pytest.raises(ValueError, match="fingerprint changed"):
        verify_primary(path)


def test_footnote_button_numbers_are_not_primary_characters_and_duplicates_fail():
    parser = SATQuotationParser()
    parser.feed(
        '<a name="0030c23">初一日<button title="半＋（也）＜甲＞">34</button>半已上者</a>'
    )
    assert "".join(parser.lines["0030c23"]) == "初一日半已上者"
    assert parser.notes["0030c23"] == ["半＋（也）＜甲＞"]
    with pytest.raises(ValueError, match="Duplicate primary text line"):
        parser.feed('<a name="0030c23">duplicate</a>')
