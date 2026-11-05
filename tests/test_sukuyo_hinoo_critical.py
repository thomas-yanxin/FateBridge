"""Direct manuscript controls and complete unresolved reconstruction receipts."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion
from fatebridge.core.sukuyo_hinoo_critical import critical_calendar_reference
from fatebridge.core.sukuyo_profiles import fullmoon_calculation, source_bundle
from scripts.check_sukuyo_hinoo_critical import verify_primary

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = json.loads((ROOT / "tests/data/sukuyo-t2465-kyoto-primary.json").read_bytes())


def reference():
    return critical_calendar_reference(
        source_bundle()["hinoo_addendum"],
        [fullmoon_calculation(12, day, SU27_ORDER) for day in (1, 15, 30)],
    )


@pytest.mark.parametrize("key,mansion", PRIMARY["expected_month_day_mansions"].items())
def test_direct_manuscript_month_day_controls_and_retained_taisho_reading(key, mansion):
    month, day = map(int, key.split("/"))
    row = next(
        r
        for r in reference()["selected_example_comparisons"]
        if (r["lunar_month"], r["lunar_day"]) == (month, day)
    )
    assert row["kyoto_manuscript_mansion"] == mansion
    assert row["host_calculated_mansion"] == mansion
    assert row["manuscript_matches_host"]
    assert not row["source_example_applied_as_calendar_override"]
    if day == 30:
        assert row["taisho_literal_mansion"] == "星"
        assert not row["taisho_literal_matches_host"]


def test_offline_quotation_check_does_not_claim_reopened_images_or_complete_collation():
    report = verify_primary()
    assert report["selected_manuscript_fragments_checked"] == 8
    assert report["apparatus_span_characters"] == 16
    assert report["shorter_sentence_boundary_candidate_characters"] == 13
    assert not report["full_image_bytes_rechecked"]
    assert not report["full_manifest_bytes_rechecked"]
    assert not report["copy_identified_as_taisho_ko"]
    assert not report["complete_manuscript_collation"]
    assert not report["intercalation_short_month_priority_established"]


@pytest.mark.parametrize("kind", ["image", "manifest"])
def test_changed_private_primary_bytes_are_rejected(tmp_path, kind):
    p = tmp_path / kind
    p.write_bytes(b"not the captured primary source")
    with pytest.raises(ValueError, match="fingerprint changed"):
        verify_primary(
            **{"manuscript_image" if kind == "image" else "manifest_path": p}
        )


@pytest.mark.parametrize(
    "field", ["publisher_html_response_sha256", "downloaded_calendar_windows"]
)
def test_companion_reference_rejects_a_different_taisho_source(field):
    source = source_bundle()["hinoo_addendum"]
    source["downloaded_primary_edition"][field] = "changed"
    with pytest.raises(ValueError, match="原文不一致"):
        critical_calendar_reference(
            source, [fullmoon_calculation(12, day, SU27_ORDER) for day in (1, 15, 30)]
        )


@pytest.mark.parametrize("days", [(1, 15), (1, 15, 15, 30), (1, 15, 29)])
def test_example_context_cannot_be_omitted_duplicated_or_substituted(days):
    with pytest.raises(ValueError, match="不完整或重复"):
        critical_calendar_reference(
            source_bundle()["hinoo_addendum"],
            [fullmoon_calculation(12, day, SU27_ORDER) for day in days],
        )


@pytest.mark.parametrize(
    "date,expected", [("1903-06-25", ["鬼", "参"]), ("1957-09-24", ["角", "轸"])]
)
def test_both_reconstruction_derivations_remain_available_without_picking_a_priority(
    date, expected
):
    result = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part="first_half"
    )
    assert result["status"] == "partial" and result["natal_su27"] is None
    assert result["candidate_su27s"] == expected
    profile = result["profile_calculation"]
    precedence = profile["short_month_assignment"]["leap_short_month_precedence"]
    assert not precedence["source_rule_priority_established"]
    branches = precedence["reconstruction_calculations"]
    assert [b["first_half_calculation"]["direct_mansion"] for b in branches] == expected
    assert len(branches) == 2
    for branch in branches:
        for key in ["first_half_calculation", "second_half_calculation"]:
            assert (
                branch[key]["source_bundle_sha256"] == profile["source_bundle_sha256"]
            )
    source = profile["hinoo_source"]["critical_calendar_reference"]
    assert not source["calendar_interaction_reference"][
        "selected_runtime_profile_changed"
    ]
    second = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part="second_half"
    )
    assert second["status"] == "computed"
    assert {b["second_half_calculation"]["direct_mansion"] for b in branches} == {
        second["natal_su27"]
    }


def test_manuscript_and_apparatus_do_not_supply_a_modern_clock_or_resolve_priority():
    report = reference()
    span = report["apparatus_span_reference"]
    assert span["normalized_candidate_span"].endswith("故傍月")
    assert not span["unconditional_ko_deletion_accepted"]
    clock = report["day_boundary_reference"]
    assert clock["starting_boundary_literal"] == "平明"
    assert clock["next_boundary_literal"] == "明日曉時"
    assert clock["day_parts"] == clock["night_parts"] == 8
    assert not clock["source_supplies_modern_clock"]
    assert not clock["source_supplies_solar_altitude"]
    assert not clock["source_supplies_intradaily_luminary_order"]
    assert not clock["hinoo_half_equated_to_day_or_night"]
    assert not report["calendar_interaction_reference"][
        "repeat_and_short_month_priority_established"
    ]


def test_returned_critical_text_is_detached_from_next_profile_and_source_cache():
    first = reference()
    expected = copy.deepcopy(first)
    first["selected_primary"]["observations"][0]["normalized_transcription"] = "changed"
    first["selected_example_comparisons"][2]["calculation"]["direct_mansion"] = "牛"
    assert reference() == expected


def test_literal_verb_correction_does_not_hide_adverse_model_mansion_reading():
    selected = reference()["selected_primary"]
    first = next(r for r in selected["observations"] if r["id"] == "twelfth_day_1")
    assert first["normalized_transcription"] == "十二月一日重宿是虚宿"
    assert first["mansion"] == "虚"
    readings = selected["supplemental_model_collation"]
    assert readings["conflicts"][1]["generator"] == "婁"
    assert readings["conflicts"][1]["reviewer"] == "室"
    assert not readings["selected_root_control_independently_certified"]
    assert not readings["complete_collation_accepted"]
    from fatebridge.core.sukuyo import day_evidence

    day = day_evidence(
        calendar_mansion("2006-08-24", calendar_profile="hinoo_t1299_host27"),
        "室",
        "travel",
    )
    assert "生成角色读婁、复核角色读室" in day["reading_text"]
    assert day["day_mansion"] is None


def test_default_profile_does_not_inherit_or_switch_to_a_manuscript_policy():
    result = calendar_mansion("1903-06-25")
    assert result["status"] == "partial"
    assert result["profile_calculation"]["hinoo_source"] is None
    assert result["leap_month_policy"] == "unresolved"
