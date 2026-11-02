"""The scope of a source count and its JSON types remain part of the claim."""

import copy
import hashlib

import pytest

from fatebridge.core import sukuyo_zhidu_pointer_scope as scopes
from fatebridge.core.sukuyo_sources import LoadedSource, load_source
from fatebridge.core.sukuyo_zhidu_calendar import SOURCE as LEGACY_SOURCE
from fatebridge.core.sukuyo_zhidu_calendar import zhidu_lines, zhidu_reference
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def test_original_source_and_numerical_controls_remain_unchanged():
    reference = zhidu_reference()
    assert hashlib.sha256(LEGACY_SOURCE.read_bytes()).hexdigest() == (
        "b140a869f1b4a13eb8e1ab72061160393118d17f9ee9b3867f08a1a80fc5d3c2"
    )
    assert reference["nominal_arithmetic"]["models"]["T1509"] == [
        {"slot_id": "month_1", "numerator": 61, "denominator": 2},
        {"slot_id": "month_2", "numerator": 30, "denominator": 1},
        {"slot_id": "month_3", "numerator": 914, "denominator": 31},
        {"slot_id": "month_4", "numerator": 1830, "denominator": 67},
    ]
    scope = reference["apparatus_pointer_scope"]
    assert scope["sources"]["T1509"]["own_local_locating_tokens"] == 71497
    assert scope["sources"]["T2122"]["own_local_locating_tokens"] == 72189
    assert (
        scope["sources"]["T1509"]["records_without_own_local_locating_tokens"] == 1513
    )
    assert scope["counting_policy"]["locating_attributes"] == ["target", "from", "to"]
    assert (
        "corresp"
        in scope["counting_policy"]["excluded_from_legacy_locating_denominator"]
    )
    assert (
        scope["sources"]["T1509"]["selected_reuse"]["corresp_matches_exact_xml_id"]
        is False
    )
    assert all(value is False for value in scope["interpretation_flags"].values())
    text = "\n".join(zhidu_lines(reference))
    assert "不能读成所有TEI关联均已认证" in text
    assert "两处app自身字位仍有可解析起讫" in text


@pytest.mark.parametrize("change", ["missing", "zero_for_false", "changed_count"])
def test_native_cannot_omit_or_coerce_the_current_scope(change):
    reference = zhidu_reference()
    if change == "missing":
        reference.pop("apparatus_pointer_scope")
    elif change == "zero_for_false":
        reference["apparatus_pointer_scope"]["interpretation_flags"][
            "all_TEI_associations_semantically_verified"
        ] = 0
    else:
        reference["apparatus_pointer_scope"]["sources"]["T1509"][
            "own_local_locating_tokens"
        ] = 71498
    with pytest.raises(ValueError, match="定位说明"):
        zhidu_lines(reference)


@pytest.mark.parametrize("change", ["flag", "missing_flag", "corresp", "scope"])
def test_even_a_new_review_digest_cannot_promote_association_scope(monkeypatch, change):
    loaded = load_source(scopes.SOURCE)
    data = loaded.data
    if change == "flag":
        data["interpretation_flags"][
            "all_TEI_associations_semantically_verified"
        ] = True
    elif change == "missing_flag":
        data["interpretation_flags"].pop("all_TEI_associations_semantically_verified")
    elif change == "corresp":
        data["sources"]["T1509"]["selected_reuse"][
            "corresp_matches_exact_xml_id"
        ] = True
    else:
        data["counting_policy"]["locating_attributes"].append("corresp")
    monkeypatch.setattr(scopes, "FACTS_SHA256", scopes._digest(data))
    monkeypatch.setattr(
        scopes, "load_source", lambda _: LoadedSource(data, loaded.sha256)
    )
    with pytest.raises(ValueError, match="不能"):
        zhidu_reference()


def test_returned_scope_is_detached_from_next_source_load():
    first = zhidu_reference()
    original = copy.deepcopy(first["apparatus_pointer_scope"])
    first["apparatus_pointer_scope"]["sources"]["T1509"][
        "own_local_locating_tokens"
    ] = 0
    assert zhidu_reference()["apparatus_pointer_scope"] == original


def test_bad_legacy_identity_cannot_be_bound_to_a_valid_scope():
    reference = zhidu_reference()
    with pytest.raises(ValueError, match="来源身份"):
        scopes.pointer_count_scope(reference["source_data"], "0" * 64)


@pytest.mark.parametrize("half", ["first_half", "second_half"])
def test_scope_and_native_qualification_reach_all_actual_local_adapters(
    monkeypatch, capsys, half
):
    path = (
        "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration."
        "daybreak_source_comparison.T2217_printed_collation."
        "subsequent_quotation_comparison.upstream_calendar_context."
        "apparatus_pointer_scope"
    )
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": "1903-06-25",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": half,
        },
        [path, "sukuyo.reading_text", "rulesets"],
    )
