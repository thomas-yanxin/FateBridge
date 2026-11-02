"""Register the frozen reviewed bytes to isolate the old uniqueness restriction.

The test does not let mutated bytes choose their own pin. The positive pin is
the fixed reviewed fixture identity; every negative mutation keeps that pin.
"""

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.core.output_numerology import CanpingTextWitness
from fatebridge.utils.errors import NumerologySourceError

F = Path(
    os.environ.get(
        "FATEBRIDGE_TEST_CANPING_GOLD_WITNESS",
        str(Path(__file__).parent / "fixtures/canping_gold_wenming_v1"),
    )
)
REFERENCE = json.loads((F / "reference.json").read_text())
RAW = (F / "reviewed-witness-data.json").read_bytes()
REVIEWED = json.loads(RAW)


def register_reviewed(monkeypatch, data):
    original = texts._loaded
    monkeypatch.setattr(
        texts, "WITNESS_CONTENT_SHA256", REFERENCE["source_canonical_sha256"]
    )
    monkeypatch.setattr(
        texts,
        "_loaded",
        lambda path: (
            {"data": data, "sha256": hashlib.sha256(RAW).hexdigest()}
            if path == texts.WITNESSES_PATH
            else original(path)
        ),
    )


def test_reviewed_same_book_same_number_different_pages_must_both_be_returned(
    monkeypatch,
):
    register_reviewed(monkeypatch, copy.deepcopy(REVIEWED))
    data = texts.source_readings(comparison=True)
    assert len(data["entries"]) == 69
    selected = texts.lookup_record("金", 3322, "male")["selection"]["witnesses"]
    assert [row["header_pdf_page"] for row in selected] == [87, 94]
    assert [row["text"] for row in selected] == [
        "重重又重重，好彈無絃琴。",
        "天河玉浪起，爭奮鴻雁飛。",
    ]
    for row in selected:
        assert (
            row["number_occurrence_count"] == 2
            and row["number_occurrence_ambiguous"] is True
        )
        assert row["replaces_selected_text"] is False
        CanpingTextWitness.model_validate(row)


@pytest.mark.parametrize(
    "fault", ["exact_duplicate", "same_location", "missing_location", "forged_page"]
)
def test_different_page_support_does_not_accept_duplicate_or_unbound_entries(
    fault, monkeypatch
):
    data = copy.deepcopy(REVIEWED)
    group = [
        row
        for row in data["entries"]
        if (row["element"], row["number"], row["kind"]) == ("金", 3322, "male")
    ]
    assert len(group) == 2
    if fault == "exact_duplicate":
        data["entries"].append(copy.deepcopy(group[0]))
    elif fault == "same_location":
        group[1]["source_occurrence_id"] = group[0]["source_occurrence_id"]
    elif fault == "missing_location":
        group[1].pop("source_occurrence_id")
    else:
        group[1]["header_pdf_page"] = 86
    register_reviewed(monkeypatch, data)
    with pytest.raises(NumerologySourceError) as caught:
        texts.source_readings(comparison=True)
    assert caught.value.as_result()["status_code"] == 503
    assert caught.value.as_result()["retryable"] is False
