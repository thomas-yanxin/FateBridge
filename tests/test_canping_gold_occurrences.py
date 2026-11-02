"""Frozen cross-edition evidence must preserve source numbers and primary results."""

import copy
import gzip
import hashlib
import json
import os
from pathlib import Path

import pytest

from fatebridge.core import canping_texts as texts
from fatebridge.utils.errors import NumerologySourceError

FIXTURE = Path(
    os.environ.get(
        "FATEBRIDGE_TEST_CANPING_GOLD_WITNESS",
        str(Path(__file__).parent / "fixtures/canping_gold_wenming_v1"),
    )
)
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
MATCHED = [row for row in REFERENCE["rows"] if row["printed_number"] != 2328]
UNMATCHED = [row for row in REFERENCE["rows"] if row["printed_number"] == 2328]


@pytest.mark.parametrize("row", MATCHED)
def test_same_printed_number_column_and_actual_pages(row):
    result = texts.lookup_record("金", row["printed_number"], row["kind"])
    witness = next(
        w
        for w in result["selection"]["witnesses"]
        if w["source_occurrence_id"] == row["source_occurrence_id"]
    )
    assert witness["number"] == row["printed_number"]
    assert witness["kind"] == row["kind"] and witness["text"] == row["text"]
    assert witness["pdf_pages"] == row["pdf_pages"]
    assert witness["body_pdf_page"] == row["body_pdf_page"]
    assert witness["replaces_selected_text"] is False
    assert witness["inherited_reading_matches"] is row["inherited_reading_matches"]
    assert witness["header_pdf_page"] == row["header_pdf_page"]
    if row["printed_number"] == 3322:
        assert witness["number_occurrence_ambiguous"] is True
        assert witness["number_occurrence_count"] == 2


@pytest.mark.parametrize("row", UNMATCHED)
def test_printed2328_observations_cannot_be_assigned_to3328(row):
    data = texts.source_readings(comparison=True)
    observed = next(
        item for item in data["unmatched_observations"] if item["kind"] == row["kind"]
    )
    assert observed["number"] == 2328 and observed["text"] == row["text"]
    assert observed["pdf_pages"] == [93, 94]
    assert observed["header_pdf_page"] == 93 and observed["body_pdf_page"] == 94
    assert (
        observed["matching_status"]
        == "unmatched_observation_not_assigned_to_a_computed_key"
    )
    for number in [2328, 3328]:
        result = texts.lookup_record("金", number, row["kind"])
        assert "witnesses" not in result["selection"]
    alignment = data["gold_tail_alignment"]
    assert alignment["requested_numbers"] == REFERENCE["requested_numbers"]
    assert alignment["unmatched_target_numbers_in_reviewed_tail"] == [3328]
    assert alignment["all_requested_same_number_counterparts_observed"] is False
    assert alignment["observed_printed_other_number"] == 2328


def test_observed_and_registered_denominators_include_unmatched_cells():
    result = texts.witness_summary()
    assert result["version"] == "1.2.0"
    assert result["cells_examined"] == 72
    assert result["registered_counterpart_cells"] == 69
    assert result["unmatched_observed_cells"] == 3
    assert result["clear_readings"] == 70 and result["uncertain_readings"] == 2
    assert result["part_coverage"]["金"] == {
        "cells_examined": 36,
        "registered_counterpart_cells": 33,
        "registered_counterpart_keys": 30,
        "ambiguous_counterpart_keys": 3,
        "unmatched_observed_cells": 3,
        "clear_readings": 36,
        "uncertain_readings": 0,
    }
    assert result["part_coverage"]["水"] == {
        "cells_examined": 36,
        "registered_counterpart_cells": 36,
        "registered_counterpart_keys": 36,
        "ambiguous_counterpart_keys": 0,
        "unmatched_observed_cells": 0,
        "clear_readings": 34,
        "uncertain_readings": 2,
    }
    assert result["registered_counterpart_keys"] == 66
    assert result["ambiguous_counterpart_keys"] == 3
    for group in result["number_occurrence_ambiguities"]:
        assert group["header_pdf_pages"] == [87, 94]
        assert group["source_occurrence_ids"] == [
            "nlc43061-gold-p087-header7",
            "nlc43061-gold-p094-header2",
        ]
        assert group["attribution_resolved"] is False
    assert result["primary_collation_count_increase"] == 0
    primary = texts.collation_summary()
    assert primary["collated_cells"] == 1123
    assert primary["unresolved_reading_cells"] == primary["pending_cells"] == 47
    assert primary["visually_examined_cells"] == primary["total_cells"] == 1170


def test_all1170_primary_results_and_old36_counterparts_remain_exact():
    previous = json.loads(
        gzip.decompress((FIXTURE / "primary-lookup-before.json.gz").read_bytes())
    )
    assert len(previous) == 1170
    added = {(row["printed_number"], row["kind"]) for row in MATCHED}
    changed = []
    for row in previous:
        actual = texts.lookup_record(row["element"], row["number"], row["kind"])
        old = row["result"]
        if row["element"] == "金" and (row["number"], row["kind"]) in added:
            assert "witnesses" not in old["selection"]
            assert len(actual["selection"]["witnesses"]) == (
                2 if row["number"] == 3322 else 1
            )
            actual = copy.deepcopy(actual)
            actual["selection"].pop("witnesses")
            changed.append((row["number"], row["kind"]))
        assert actual == old
    assert len(changed) == 30 and set(changed) == added
    old_data = json.loads((FIXTURE / "witness-data-before.json").read_text())
    current = texts.source_readings(comparison=True)
    assert len(old_data["entries"]) == 36
    assert current["entries"][:36] == old_data["entries"]
    assert (
        hashlib.sha256(texts.COLLATION_PATH.read_bytes()).hexdigest()
        == REFERENCE["primary_corpus_sha256"]
    )


@pytest.mark.parametrize(
    "fault", ["renumber", "apply", "erase", "page", "swap_literal", "promote"]
)
def test_positive_reviewed_source_rejects_nonempty_false_bindings(monkeypatch, fault):
    original = texts._loaded
    baseline = texts.source_readings(comparison=True)
    assert (
        len(baseline["unmatched_observations"]) == 3 and baseline["version"] == "1.2.0"
    )
    data = copy.deepcopy(baseline)
    if fault == "renumber":
        data["unmatched_observations"][0]["number"] = 3328
    elif fault == "apply":
        data["entries"].append(data["unmatched_observations"][0])
    elif fault == "erase":
        data["unmatched_observations"] = []
    elif fault == "page":
        next(
            e
            for e in data["entries"]
            if (e["element"], e["number"], e["kind"]) == ("金", 3326, "male")
        )["pdf_pages"] = [94]
    elif fault == "swap_literal":
        next(
            e
            for e in data["entries"]
            if (e["element"], e["number"], e["kind"]) == ("金", 3322, "male")
        )["text"] = "圭田如玉潔，一點不生塵。"
    else:
        data["gold_tail_alignment"][
            "all_requested_same_number_counterparts_observed"
        ] = True
    monkeypatch.setattr(
        texts,
        "_loaded",
        lambda path: {"data": data} if path == texts.WITNESSES_PATH else original(path),
    )
    with pytest.raises(NumerologySourceError) as caught:
        texts.source_readings(comparison=True)
    assert caught.value.as_result()["status_code"] == 503
    assert caught.value.as_result()["retryable"] is False


def test_source_pdf_native_pages_and_initial_wrong_readings_are_preserved():
    assert (
        hashlib.sha256((FIXTURE / REFERENCE["source_pdf"]).read_bytes()).hexdigest()
        == REFERENCE["source_pdf_sha256"]
    )
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((FIXTURE / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    assert len(REFERENCE["rows"]) == 36 and len(MATCHED) == 33 and len(UNMATCHED) == 3
    first = json.loads((FIXTURE / "transcription-first.json").read_text())
    final = json.loads((FIXTURE / "transcription-final-v2.json").read_text())
    before = {(e["printed_number"], e["kind"]): e["text"] for e in first["rows"]}
    after = {(e["printed_number"], e["kind"]): e["text"] for e in final["rows"]}
    assert before[(2324, "luck")] == "春水初淨處，任便戲新魚。"
    assert after[(2324, "luck")] == "春水初泮處，任便戲新魚。"
    assert before[(2425, "luck")] == "殺雞煩鳳怒，忠信自無疑。"
    assert after[(2425, "luck")] == "殺雞煩鼠終，忠信自無疑。"
    assert before[(3326, "male")] == "風行江上去，松竹競爭春。"
    assert after[(3326, "male")] == "風行江上去，松竹竟爭春。"
