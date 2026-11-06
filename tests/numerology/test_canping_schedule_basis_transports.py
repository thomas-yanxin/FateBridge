"""Actual REST/MCP/CLI expose bounded policy views and preserve source faults."""

import json
from copy import deepcopy

import pytest

from fatebridge.application.examples import evidence_views
from fatebridge.core import canping_schedule_basis as basis
from tests.numerology.test_canping_schedule_basis import BASE, READINGS
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

rest = shared_rest


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize(
    "profile", ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]
)
@pytest.mark.parametrize("view", ["timing_policy", "periods"])
def test_source_roles_and_first_period_match_on_every_local_surface(
    profile, view, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {**BASE, "dayun_method": profile}
    views = evidence_views(spec)
    response, code, cli, mcp = run_three(
        spec, payload, views[view]["fields"], rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for value in outputs:
        spec.output_model.model_validate(value)
        timing = value["canping_timing"]
        b = timing["schedule_basis"]
        assert b["profile_id"] == profile
        assert b["target_excerpt_ten_year_step_explicitly_collated"] is False
        assert len(b["clauses"]) == 6
        assert b["whole_book_alignment_established"] is False
        assert b["real_world_efficacy_validated"] is False
        assert (
            value["numerology_evidence"]["birth_clock"]["birth_instant_utc"]
            == "2021-11-07T05:30:00+00:00"
        )
        if profile == "legacy_minggong_v1":
            assert timing["first_period"] is None
        else:
            assert timing["first_period"]["pillar"] == "戊戌"
            if view == "periods":
                assert timing["first_period"] == value["dayun"][0]
        if view == "timing_policy":
            assert "solar_year_context" not in timing
        elif profile != "legacy_minggong_v1":
            assert timing["solar_year_context"]["boundary_count"] == 121


def test_narrow_source_receipt_projection_keeps_actual_profile_and_false_gate(
    rest, tmp_path, capsys
):
    fields = [
        "canping_timing.schedule_basis.profile_id",
        "canping_timing.schedule_basis.whole_book_alignment_established",
        "canping_timing.first_period.start_at",
    ]
    response, code, cli, mcp = run_three(
        SPECS["canping"], BASE, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        response.json()["canping_timing"]["first_period"]["start_at"]
        == "2021-11-07T00:30:00-05:00"
    )


@pytest.mark.parametrize("kind", ["quote", "book"])
def test_wrong_nonempty_quote_or_cross_book_relabel_is_internal_source_failure_before_projection(
    kind, rest, tmp_path, capsys, monkeypatch
):
    data = deepcopy(READINGS)
    if kind == "quote":
        data["clauses"][3]["text"] = data["clauses"][3]["text"].replace("不用", "用")
    else:
        data["clauses"][4]["source_id"] = "heluo_najda"
    path = tmp_path / "bad-basis.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    basis._collation.cache_clear()
    try:
        monkeypatch.setattr(basis, "COLLATION_PATH", path)
        response, code, cli, mcp = run_three(
            SPECS["canping"], BASE, ["benming.numShun"], rest, tmp_path, capsys
        )
        assert response.status_code == 503 and code == 1 and mcp.is_error
        assert "numerology_source_inconsistent" in str(response.json())
        assert "numerology_source_inconsistent" in str(cli)
        assert "numerology_source_inconsistent" in str(mcp.content)
    finally:
        basis._collation.cache_clear()
