"""Per-stem source root classes remain facts, not a repaired strength verdict."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.test_bazi_year_contract import TOPICS


def roots(text):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))
    model = ElementAnalysis.analyze_day_master_strength(pillars)
    force = build_natal_evidence(pillars, model)["force_components"]
    observed = force["source_root_observations"]
    return force, {s["stem"]: s for s in observed["stems"]}


def by_position(stem):
    return {r["pillar"]: r for r in stem["roots"]}


def test_ma_body_hidden_water_is_not_replaced_by_a_yang_growth_or_seal_root():
    force, stems = roots("己巳 癸酉 癸未 庚申")
    body = by_position(stems["癸"])
    seal = by_position(stems["庚"])
    assert stems["癸"]["role"] == "body" and stems["癸"]["is_day_master"]
    assert stems["庚"]["role"] == "seal" and not stems["庚"]["is_day_master"]
    assert body["hour"]["life_stage"] == "死"
    assert body["hour"]["kind"] == "other_hidden_root"
    assert body["hour"]["matching_hidden_stems"] == ["壬"]
    assert body["hour"]["source_weight_class"] == "not_ranked_by_this_rule"
    assert seal["year"]["kind"] == "yang_growth_root"
    assert seal["month"]["kind"] == "yang_blade_root"
    assert seal["hour"]["kind"] == "lu_root"
    # Known source/model disagreement is deliberately unchanged.
    assert force["engineering_composition"]["strength_level"] == "强"
    assert set(force["classical_adjudication"].values()) == {"not_adjudicated"}


def test_mao_clashed_growth_root_is_retained_without_claiming_its_remaining_force():
    force, stems = roots("壬寅 戊申 壬辰 壬寅")
    body = by_position(stems["壬"])
    assert body["month"]["kind"] == "yang_growth_root"
    assert body["month"]["hidden_element_present"]
    assert body["month"]["clash_partners"] == ["year", "hour"]
    assert body["day"]["kind"] == "storage_root"
    assert stems["壬"]["visible_positions"] == ["year", "day", "hour"]
    assert stems["壬"]["force_status"] == "not_adjudicated"
    assert force["engineering_composition"]["strength_level"] == "中和"


def test_yang_one_growth_root_does_not_automatically_flip_the_global_model():
    force, stems = roots("壬寅 壬寅 庚辰 辛巳")
    body = by_position(stems["庚"])
    assert body["hour"]["kind"] == "yang_growth_root"
    assert body["hour"]["matching_hidden_stems"] == ["庚"]
    assert body["hour"]["clash_partners"] == []
    assert by_position(stems["辛"])["hour"]["kind"] == "other_hidden_root"
    assert force["engineering_composition"]["strength_level"] == "弱"
    assert stems["庚"]["force_status"] == "not_adjudicated"


def test_yin_growth_reference_does_not_manufacture_a_hidden_stem_or_support_vote():
    # Synthetic relation fixture, not a newly discovered classical chart.
    _, stems = roots("甲子 乙酉 丁卯 辛酉")
    day = stems["丁"]
    assert day["visible_positions"] == ["day"]
    assert set(stems) == set("甲乙丁辛癸")
    for position in ("month", "hour"):
        row = by_position(day)[position]
        assert row["kind"] == "yin_growth_reference"
        assert row["matching_hidden_stems"] == []
        assert row["hidden_element_present"] is False
    assert day["force_status"] == "not_adjudicated"


@pytest.mark.parametrize("topic", TOPICS)
def test_per_stem_root_view_matches_actual_rest_native_mcp_cli(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    payload = {**inputs(spec), "use_true_solar_time": False}
    fields = suggested_fields(spec, view="force_roots")
    opts = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(local)
    )
    observed = response.json()
    for part in fields[0].split("."):
        observed = observed[part]
    assert observed["method_id"] == "observed_stem_root_categories_v1"
    assert observed["source"]["pdf_pages"] == [22, 23]
    assert len({s["stem"] for s in observed["stems"]}) == len(observed["stems"])
    assert all(
        len(s["roots"]) == 4 and s["force_status"] == "not_adjudicated"
        for s in observed["stems"]
    )
