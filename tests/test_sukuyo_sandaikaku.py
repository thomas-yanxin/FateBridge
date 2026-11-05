"""A quoted day number cannot silently fill a missing ganzhi or calendar."""

import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_historical_calendar import date_reference
from fatebridge.core.sukuyo_sandaikaku import (
    SOURCE,
    month_reference,
    reference_lines,
    validate_bundle,
)
from fatebridge.core.sukuyo_sources import load_source


def test_822_document_and_766_quote_bind_to_before_code_primary_facts_separately():
    raw = (Path(__file__).parent / "data/sukuyo-sandaikaku-source-v1.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "c0c6f02d1b1d0803efbe969a060f37bfff3be0eeac9dcda0670e9e1620c92df9"
    )
    expected = json.loads(raw)
    correction_raw = (
        Path(__file__).parent / "data/sukuyo-sandaikaku-boundary-v2.json"
    ).read_bytes()
    assert hashlib.sha256(correction_raw).hexdigest() == (
        "c2ae313577ab507f863485e57e0f2d52d62fe70d897ad92a8abb2d471473c432"
    )
    correction = json.loads(correction_raw)
    assert correction["original_source_facts_sha256"] == hashlib.sha256(raw).hexdigest()
    assert correction["gate_or_question_changes"] is False
    old_boundary = expected["transmitted_record"].pop(
        "frame322_begins_other_record_and_not_part_of_target"
    )
    assert old_boundary is True
    expected["transmitted_record"]["record_boundary"] = correction[
        "replacement_record_boundary"
    ]
    for y, m, role in [
        (766, 2, "quoted_earlier_edict_month"),
        (822, 3, "transmitted_document_month"),
    ]:
        r = month_reference(y, m, False)
        assert r["witness"] == expected["witness"]
        assert r["transmitted_record"] == expected["transmitted_record"]
        assert (
            r["source_fact_correction_sha256"]
            == hashlib.sha256(correction_raw).hexdigest()
        )
        assert r["scope"] == expected["scope"]
        assert r["selected_month_binding_role"] == role
        assert r["inferred_original_event_ganzhi"] is None
        assert r["inferred_historical_month_start"] is None
        assert r["inferred_absolute_civil_date"] is None
        assert not r["current_calendar_rewritten"]
        assert not r["source_image_reread_at_runtime"]
    data = month_reference(766, 2, False)
    data["transmitted_record"]["quoted_earlier_day_ganzhi_literal"] = "丙午"
    assert (
        month_reference(766, 2, False)["transmitted_record"][
            "quoted_earlier_day_ganzhi_literal"
        ]
        is None
    )


@pytest.mark.parametrize(
    "args", [(True, 2, False), (766, 0, False), (766, 13, False), (766, 2, 0)]
)
def test_bad_month_keys_do_not_silently_coerce(args):
    with pytest.raises(ValueError):
        month_reference(*args)


@pytest.mark.parametrize(
    "args",
    [
        (766, 2, True),
        (822, 3, True),
        (766, 3, False),
        (822, 2, False),
        (841, 11, False),
    ],
)
def test_not_inherited_by_adjacent_month_leap_or_another_year(args):
    assert month_reference(*args) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "swap_dates",
        "ganzhi",
        "ndlsame",
        "physical",
        "independent",
        "fees",
        "frame",
        "real",
    ],
)
def test_quote_knowledge_or_source_status_cannot_be_silently_rewritten(mutation):
    d = deepcopy(load_source(SOURCE).data)
    if mutation == "swap_dates":
        d["transmitted_record"]["quoted_earlier_date"]["year"] = 822
    elif mutation == "ganzhi":
        d["transmitted_record"]["quoted_earlier_day_ganzhi_literal"] = "丙午"
    elif mutation == "ndlsame":
        d["scope"]["author_citation_page352_edition_identified"] = True
    elif mutation == "physical":
        d["scope"]["extant_original_822_document_certified"] = True
    elif mutation == "independent":
        d["scope"]["genealogical_independence_from_shoku_established"] = True
    elif mutation == "fees":
        d["transmitted_record"]["document_total_quantity"]["amount"] = 50000
    elif mutation == "frame":
        d["witness"]["selected_pages"].pop()
    else:
        d["scope"]["real_samples"] = 1
    with pytest.raises(ValueError):
        validate_bundle(d)


def test_every_day_of_both_host_months_keeps_its_binding_role_and_real_input():
    raw = json.loads(
        (Path(__file__).parent / "data/sukuyo-sandaikaku-source-v1.json").read_bytes()
    )
    for expected in raw["independent_before_code_host_reference"]["months"]:
        first = date.fromisoformat(expected["host_month_start_civil_label"])
        for n in range(expected["host_length"]):
            r = date_reference(first + timedelta(days=n))
            assert r["source_month_length_days"] == expected["host_length"]
            e = r["sandaikaku_edict_reference"]
            assert e["selected_month_key"] == expected["month_key"]
            assert e["transmitted_record"]["reported_document_date"]["year"] == 822
            assert e["transmitted_record"]["quoted_earlier_date"]["year"] == 766
            assert e["inferred_original_event_ganzhi"] is None
        assert (
            date_reference(first - timedelta(days=1))["sandaikaku_edict_reference"]
            is None
        )
        assert (
            date_reference(first + timedelta(days=expected["host_length"]))[
                "sandaikaku_edict_reference"
            ]
            is None
        )


@pytest.mark.parametrize("civil", ["0766-03-19", "0822-03-31", "0822-04-27"])
def test_product_reading_keeps_actual_source_dates_unknowns_and_remaining_conflicts(
    civil,
):
    c = calendar_mansion(
        civil, "12:00:00", "+09:00", calendar_basis="japanese_naoj_historical_utc09"
    )
    ref = c["calendar_reference"]["sandaikaku_edict_reference"]
    text = day_evidence(c)["reading_text"]
    for s in [
        "822年三月二十八日",
        "766年二月二十日",
        "没有甲午或丙午干支",
        "同一版",
        "同时代原件",
        "真实预测样本0",
        "52项研究方向分歧及1项未知均保留",
    ]:
        assert s in text
    assert "五万斛" in "".join(reference_lines(ref))


def test_no_selected_quotation_is_explicit_without_suppressing_actual_calendar():
    c = calendar_mansion(
        "0766-04-18",
        "12:00:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert c["calendar_reference"]["sandaikaku_edict_reference"] is None
    assert c["lunar_year"] == 766 and c["lunar_month"] == 3 and c["lunar_day"] == 1
    text = day_evidence(c)["reading_text"]
    assert "sandaikaku_edict_reference为空" in text
    assert "未绑定不等于否定其他史料" in text
