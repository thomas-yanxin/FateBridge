"""Expose the selected ARC readings without erasing uncertainties or history."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence

BEFORE_PATH = Path(__file__).parent / "data/sukuyo-arc-clock-before-code-v111.json"
BEFORE = json.loads(BEFORE_PATH.read_bytes())
ROOT = Path(__file__).resolve().parents[1]


def test_bound_first_readings_and_correction_are_unchanged():
    for record in BEFORE["source_records"]:
        assert (
            hashlib.sha256((ROOT / record["public_record"]).read_bytes()).hexdigest()
            == record["sha256"]
        )


def test_day_reference_exposes_layers_without_inventing_a_boundary_or_priority():
    calendar = calendar_mansion(
        "0806-07-23",
        "23:59:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    reference = day_evidence(calendar)["calendar_day"]["clock_doctrine"].get(
        "arc_printed_reference"
    )
    assert reference is not None
    assert calendar["natal_su27"] is None
    assert calendar["candidate_su27s"] == ["星", "鬼"]
    assert calendar["calendar_day_part"] == "first_half"
    rows = {r["id"]: r for r in reference["selected_readings"]}
    assert rows["dawn_apparatus"]["working_literal"] == "平明一作平旦"
    assert rows["dawn_apparatus"]["root_first_working_literal"] == "平明一作平日"
    assert rows["body_before_day_division"]["accepted_unique_glyph"] is None
    assert not rows["body_before_day_division"][
        "full_sentence_exact_transcription_accepted"
    ]
    assert rows["weekday_handover_body"]["working_literal"].endswith("曜當")
    assert rows["following_zhi_apparatus"]["reported_addition"] == "直"
    assert rows["following_zhi_apparatus"]["layer"] == "upper_printed_apparatus"
    assert not rows["following_zhi_apparatus"]["reported_exemplars_obtained"]
    assert not any(reference["acceptance_scope"].values())


def test_unknown_glyph_and_reported_exemplar_cannot_be_silently_normalized(
    tmp_path, monkeypatch
):
    from fatebridge.core import sukuyo_arc_clock as source

    changed = json.loads(BEFORE_PATH.read_bytes())
    changed["selected_readings"][1]["accepted_unique_glyph"] = "晝"
    changed["selected_readings"][3]["reported_exemplars_obtained"] = True
    file = tmp_path / "silently-normalized.json"
    file.write_text(json.dumps(changed, ensure_ascii=False))
    monkeypatch.setattr(source, "SOURCE", file)
    with pytest.raises(ValueError, match="ARC.*来源"):
        source.arc_clock_reference()


def test_reading_references_are_detached_from_caller_mutation():
    from fatebridge.core.sukuyo_arc_clock import arc_clock_reference

    first = arc_clock_reference()
    first["selected_readings"][1]["accepted_unique_glyph"] = "每"
    first["acceptance_scope"]["leap_short_month_priority_established"] = True
    second = arc_clock_reference()
    assert second["selected_readings"][1]["accepted_unique_glyph"] is None
    assert not second["acceptance_scope"]["leap_short_month_priority_established"]
