"""Distinct physical witnesses may agree without deciding rule precedence."""

import copy
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_hinoo_critical as critical
from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import fullmoon_calculation, source_bundle
from fatebridge.core.sukuyo_sources import LoadedSource
from scripts.check_sukuyo_zentsuji_hinoo import verify_primary
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def reference():
    return critical.critical_calendar_reference(
        source_bundle()["hinoo_addendum"],
        [fullmoon_calculation(12, day, SU27_ORDER) for day in (1, 15, 30)],
    )


def test_three_witness_layers_keep_thirtieth_day_disagreement_and_source_identity():
    result = reference()
    extra = result["supplemental_witnesses"][0]
    assert extra["call_number"] == "109-4"
    assert extra["canvas_count"] == 34
    assert extra["canvas_one_based"] == 29
    assert result["selected_primary"]["id"] == "kyoto_RB00017868_selected_calendar_v2"
    rows = extra["selected_example_comparisons"]
    assert [(r["lunar_day"], r["witness_literal_mansion"]) for r in rows] == [
        (1, "虚"),
        (15, "星"),
        (30, "室"),
    ]
    last = rows[-1]
    assert last["taisho_literal_mansion"] == "星"
    assert last["host_calculated_mansion"] == "室"
    assert not last["source_example_applied_as_calendar_override"]
    assert not extra["identified_as_taisho_base_or_ko"]
    assert not extra["independent_textual_lineage_established"]
    assert not extra["leap_short_month_priority_established"]


@pytest.mark.parametrize("mutation", ["duplicate", "omit"])
@pytest.mark.parametrize("witness", ["kyoto", "zentsuji"])
def test_incomplete_or_duplicate_control_rows_are_rejected(
    monkeypatch, mutation, witness
):
    original = critical.load_source
    target = critical.SOURCE if witness == "kyoto" else critical.ZENTSUJI_SOURCE
    source = original(target)
    data = source.data
    holder = data["selected_primary"] if witness == "kyoto" else data
    row = next(r for r in holder["observations"] if r.get("day") == 30)
    if mutation == "duplicate":
        holder["observations"].append(copy.deepcopy(row))
    else:
        holder["observations"].remove(row)
    monkeypatch.setattr(
        critical,
        "load_source",
        lambda path: (
            LoadedSource(data, source.sha256) if path == target else original(path)
        ),
    )
    with pytest.raises(ValueError, match="不完整或重复"):
        reference()


def test_supplemental_source_and_results_cannot_be_mutated_between_calls():
    a = reference()
    a["supplemental_witnesses"][0]["observations"][0]["normalized_transcription"] = "x"
    a["supplemental_witnesses"][0]["selected_example_comparisons"][-1][
        "witness_literal_mansion"
    ] = "星"
    b = reference()["supplemental_witnesses"][0]
    assert b["observations"][0]["normalized_transcription"].endswith("依口説")
    assert b["selected_example_comparisons"][-1]["witness_literal_mansion"] == "室"


def test_offline_verifier_does_not_claim_image_reading_or_lift_limits():
    r = verify_primary()
    assert r["selected_fragments_checked_against_prior_record"] == 10
    assert not r["full_image_bytes_rechecked"]
    assert not r["full_manifest_bytes_rechecked"]
    assert not r["independent_palaeographic_reading_performed_by_script"]
    assert not r["calendar_algorithm_changed"]


@pytest.mark.parametrize("kind", ["image", "manifest"])
def test_changed_capture_bytes_are_rejected(tmp_path, kind):
    path = tmp_path / kind
    path.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="指纹不一致"):
        verify_primary(
            **{("manuscript_image" if kind == "image" else "manifest_path"): path}
        )


@pytest.mark.parametrize("half,expected", [("first_half", None), ("second_half", "参")])
def test_new_witness_does_not_select_rule_precedence_or_erase_old_glyph_conflicts(
    half, expected
):
    r = calendar_mansion(
        "1903-06-25", calendar_profile="hinoo_t1299_host27", calendar_day_part=half
    )
    assert r["natal_su27"] == expected
    if expected is None:
        assert r["candidate_su27s"] == ["鬼", "参"]
    text = day_evidence(r)["reading_text"]
    assert "善通寺首日直与京都所选重分别保留" in text
    assert "善通寺末句直宿無改代也不用于补定京都未决末句" in text
    assert "半与上者之间、半与下者之间的字形未定" in text
    assert "不是善通寺109-5" in text
    assert "依口説不据此认作甲本" in text


@pytest.mark.parametrize("half", ["first_half", "second_half"])
def test_new_witness_across_actual_rest_native_mcp_cli(monkeypatch, capsys, half):
    run_transport_check(
        monkeypatch,
        capsys,
        "sukuyo_compatibility",
        {
            "person1_date": "1903-06-25",
            "person2_date": "1957-09-24",
            "calendar_profile": "hinoo_t1299_host27",
            "person1_calendar_day_part": half,
            "person2_calendar_day_part": half,
        },
        ["person1", "person2", "candidate_relation_analysis", "summary", "rulesets"],
    )
