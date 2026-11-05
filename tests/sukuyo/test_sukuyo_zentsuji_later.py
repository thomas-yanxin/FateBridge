"""Later evidence must qualify old literals without choosing a calendar rule."""

import pytest

from fatebridge.core import sukuyo_zentsuji_later as later
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_hinoo_critical import ZENTSUJI_SOURCE
from fatebridge.core.sukuyo_sources import LoadedSource, load_source
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def reference():
    legacy = load_source(ZENTSUJI_SOURCE)
    return later.later_reading_reference(legacy.data, legacy.sha256)


def test_old_capture_and_new_native_evidence_coexist_with_unaccepted_glyphs():
    legacy = load_source(ZENTSUJI_SOURCE).data
    result = reference()
    assert (
        legacy["colophon_reference"]["inspection_capture"]
        == "1800 pixel derivative only"
    )
    assert "timed out" in legacy["colophon_reference"]["scope"]
    native = result["native_colophon_followup"]
    assert native["image_dimensions"] == [6153, 4677]
    assert (
        native["image_sha256"]
        == "90c8f76fcc64462f497be98e51b8ec9db05e8f1c483d447f667e8cab26627eb1"
    )
    assert (
        native["long_column_working"] == "明和七年十月法眼光恕拜寫訖同月十七日校合故識"
    )
    assert native["separate_signature_working"] == "僧正光國"
    assert not native["writing_day_given"]
    assert not native["name_independently_human_accepted"]
    assert len(result["calendar_columns"]) == 12
    assert result["calendar_columns"][10]["literal"].endswith("無日")
    assert result["calendar_columns"][11]["literal"].startswith("不得")
    disputed = {row["id"]: row for row in result["unresolved_calendar_readings"]}
    assert disputed["closing-clause"]["candidates"] == ["改", "放形"]
    assert disputed["preceding-day-pronoun"]["candidates"] == ["彼", "被"]
    assert all(row["accepted_literal"] is None for row in disputed.values())
    assert all(value is False for value in result["acceptance_flags"].values())


@pytest.mark.parametrize(
    "key", ["source_bundle_sha256", "id", "image_sha256", "call_number"]
)
def test_later_record_cannot_bind_another_legacy_source(key):
    legacy = load_source(ZENTSUJI_SOURCE)
    value = legacy.data
    identity = legacy.sha256
    if key == "source_bundle_sha256":
        identity = "0" * 64
    else:
        value[key] = "changed"
    with pytest.raises(ValueError, match="来源身份不一致"):
        later.later_reading_reference(value, identity)


@pytest.mark.parametrize(
    "change", ["true_flag", "missing_flag", "null_flag", "accepted_glyph"]
)
def test_working_evidence_does_not_silently_become_acceptance(monkeypatch, change):
    loaded = load_source(later.SOURCE)
    data = loaded.data
    if change == "true_flag":
        data["acceptance_flags"]["modern_clock_mapping_established"] = True
    elif change == "missing_flag":
        data["acceptance_flags"].pop("modern_clock_mapping_established")
    elif change == "null_flag":
        data["acceptance_flags"]["modern_clock_mapping_established"] = None
    else:
        data["unresolved_calendar_readings"][-1]["accepted_literal"] = "改"
    monkeypatch.setattr(
        later, "load_source", lambda _: LoadedSource(data, loaded.sha256)
    )
    with pytest.raises(ValueError, match="不能"):
        reference()


def test_returned_later_readings_are_copy_isolated():
    first = reference()
    first["calendar_columns"][0]["literal"] = "changed"
    first["unresolved_calendar_readings"][-1]["candidates"].clear()
    second = reference()
    assert second["calendar_columns"][0]["literal"].startswith("勘宿曜經")
    assert second["unresolved_calendar_readings"][-1]["candidates"] == ["改", "放形"]


@pytest.mark.parametrize("half,expected", [("first_half", None), ("second_half", "参")])
def test_returned_source_and_reading_qualify_current_uncertainty(half, expected):
    result = calendar_mansion(
        "1903-06-25", calendar_profile="hinoo_t1299_host27", calendar_day_part=half
    )
    assert result["natal_su27"] == expected
    witness = result["profile_calculation"]["hinoo_source"][
        "critical_calendar_reference"
    ]["supplemental_witnesses"][0]
    assert witness["later_reading_followup"] == reference()
    text = day_evidence(result)["reading_text"]
    assert "以下善通寺原文为既有首录" in text
    assert "当前统一定字仍未接纳" in text
    assert "第33帧后续已取得原尺寸图6153×4677" in text
    assert "另栏署记僧正光國分别保留" in text
    assert "未改变配宿算法" in text
