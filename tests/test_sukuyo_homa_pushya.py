"""A date match is not an accepted glyph, cited exemplar or clock rule."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_commentarial_clock as clock
from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_profiles import _fullmoon_from_loaded, source_bundle
from fatebridge.core.sukuyo_sources import LoadedSource
from scripts.check_sukuyo_homa_pushya import verify_primary
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize("permutation", ["reverse", "rotate"])
def test_anchor_month_labels_remain_authoritative_for_all_360_month_days(permutation):
    original = source_bundle()
    permuted = deepcopy(original)
    rows = permuted["fullmoon_anchors"]
    permuted["fullmoon_anchors"] = (
        rows[::-1] if permutation == "reverse" else rows[1:] + rows[:1]
    )
    for month in range(1, 13):
        for day in range(1, 31):
            expected = _fullmoon_from_loaded(
                month, day, SU27_ORDER, original, "original"
            )
            actual = _fullmoon_from_loaded(month, day, SU27_ORDER, permuted, "permuted")
            for key in ["fullmoon_mansion", "direct_mansion", "shortcut_mansion"]:
                assert actual[key] == expected[key]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "omit", "boolean", "string", "cow", "non_name"]
)
def test_incomplete_or_misidentified_month_anchor_tables_are_rejected(mutation):
    source = source_bundle()
    rows = source["fullmoon_anchors"]
    if mutation == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "omit":
        rows.pop()
    elif mutation == "boolean":
        rows[0]["month"] = True
    elif mutation == "string":
        rows[0]["month"] = "1"
    elif mutation == "cow":
        rows[0]["fullmoon_mansion"] = "牛"
    else:
        rows[0]["fullmoon_mansion"] = 1
    with pytest.raises(ValueError, match="十二月望宿表"):
        _fullmoon_from_loaded(1, 1, SU27_ORDER, source, "invalid")


def test_selected_manuscript_dates_keep_twenty_third_and_unaccepted_star_glyph():
    result = clock.commentarial_boundary_reference()
    manuscript = result["same_titled_manuscript_reference"]
    assert manuscript["source_reference"]["shelfmark"] == "109-5"
    assert manuscript["date_controls_matching_T2216"] == 12
    row = next(
        r for r in manuscript["selected_date_comparisons"] if r["lunar_month"] == 8
    )
    assert row["manuscript_date_literal"] == "八月二十三日"
    assert row["manuscript_lunar_day"] == row["T2216_quoted_lunar_day"] == 23
    assert row["host_mansion"] == "柳"
    assert not row["manuscript_unique_mansion_literal_accepted"]
    assert manuscript["star_name_reference"]["accepted_literal"] is None
    assert (
        manuscript["star_name_reference"]["marginal_note_selected_literal"]
        == "此字未詳"
    )
    assert not manuscript["T2216_comparison_context"][
        "identified_as_exact_cited_exemplar"
    ]
    assert not manuscript["T2216_comparison_context"][
        "independent_textual_lineage_established"
    ]
    assert result["monthly_pushya_reference"]["differing_controls"] == 1


@pytest.mark.parametrize("mutation", ["duplicate", "omit", "changed_T2216"])
def test_manuscript_control_completeness_and_quoted_source_identity(
    monkeypatch, mutation
):
    original = clock.load_source
    loaded = original(clock.MANUSCRIPT_SOURCE)
    data = loaded.data
    if mutation == "duplicate":
        data["monthly_day_observations"][-1] = deepcopy(
            data["monthly_day_observations"][0]
        )
    elif mutation == "omit":
        data["monthly_day_observations"].pop()
    else:
        data["T2216_comparison_context"]["publisher_capture_sha256"] = "changed"
    monkeypatch.setattr(
        clock,
        "load_source",
        lambda path: (
            LoadedSource(data, loaded.sha256)
            if path == clock.MANUSCRIPT_SOURCE
            else original(path)
        ),
    )
    with pytest.raises(ValueError, match="完整唯一|来源不一致"):
        clock.commentarial_boundary_reference()


def test_returned_manuscript_cannot_mutate_following_results_or_choose_precedence():
    first = clock.commentarial_boundary_reference()
    first["same_titled_manuscript_reference"]["monthly_day_observations"][7]["day"] = 22
    assert (
        clock.commentarial_boundary_reference()["same_titled_manuscript_reference"][
            "monthly_day_observations"
        ][7]["day"]
        == 23
    )
    result = day_evidence(
        calendar_mansion(
            "1903-06-25",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    assert result["calendar"]["candidate_su27s"] == ["鬼", "参"]
    assert result["day_mansion"] is None
    assert "八月也清楚作二十三" in result["reading_text"]
    assert "同名具名抄本，尚未识别为T2216实际引用本" in result["reading_text"]
    assert "必得速成与T2216皆得速成分别保留" in result["reading_text"]


def test_offline_primary_check_does_not_claim_glyph_or_cited_exemplar_acceptance():
    result = verify_primary()
    assert result["selected_month_day_controls"] == 12
    assert result["actual_image_bytes_rechecked"] == []
    assert not result["actual_manifest_bytes_rechecked"]
    assert not result["independent_palaeographic_reading_performed_by_script"]
    assert not result["unique_star_name_glyph_accepted"]


@pytest.mark.parametrize("kind", ["image", "manifest"])
def test_primary_checker_rejects_replaced_capture_bytes(tmp_path, kind):
    path = tmp_path / kind
    path.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="指纹不一致"):
        verify_primary(
            **({"images": {29: path}} if kind == "image" else {"manifest_path": path})
        )


@pytest.mark.parametrize("date", ["2024-09-25", "1903-06-25"])
def test_actual_rest_native_mcp_cli_keep_physical_witness_and_existing_candidates(
    monkeypatch, capsys, date
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "04:30:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.commentarial_boundary_reference.same_titled_manuscript_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )
