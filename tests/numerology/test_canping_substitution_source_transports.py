"""The primary explanatory paragraph travels with the implemented pair policy."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest

rest = shared_rest
REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/canping_relative_years_v1/reference.json"
    ).read_text()
)


@pytest.fixture(autouse=True)
def native_source(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize(
    "profile,query",
    [
        ("bazi_appendix_v1", None),
        ("bazi_continuous_v1", None),
        ("legacy_minggong_v1", None),
        ("bazi_appendix_v1", "2021-11-07T05:30:00+00:00"),
    ],
)
def test_source_pair_paragraph_is_same_on_actual_rest_mcp_cli(
    profile, query, rest, tmp_path, capsys
):
    args = dict(
        date="2021-11-07",
        time="00:30",
        zone="America/Havana",
        birth_utc_offset="-05:00",
        gender="男",
        use_true_solar_time=False,
        dayun_method=profile,
    )
    if query is not None:
        args["analysis_datetime"] = query
    fields = [
        "numerology_evidence.rulesets",
        "numerology_evidence.rule_trace",
        "numerology_evidence.unresolved_rules",
        "canping_timing.profile_id",
        "canping_timing.selected",
    ]
    response, code, cli, mcp = run_three(
        SPECS["canping"], args, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    values = [response.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        SPECS["canping"].output_model.model_validate(value)
        evidence = value["numerology_evidence"]
        trace = next(
            t["facts"]
            for t in evidence["rule_trace"]
            if t["rule_id"] == "canping_luck_substitution_v1"
        )
        assert trace["bounded_excerpts"] == REFERENCE["bounded_excerpts"]
        assert (
            trace["source_pdf_page"] == 64
            and trace["source_pdf_sha256"] == REFERENCE["source_pdf"]["sha256"]
        )
        assert trace["whole_book_alignment_established"] is False
        assert trace["independent_second_review_completed"] is False
        assert trace["implemented_annual_arguments"] == [
            "annual_taisui_branch",
            "active_dayun_branch",
        ]
        if query is None:
            assert trace["query_pair"] is None
        else:
            assert trace["query_pair"] == {
                "at": value["canping_timing"]["selected"]["at"],
                "annual_taisui_branch": "丑",
                "active_dayun_branch": "戌",
            }
            assert datetime.fromisoformat(
                trace["query_pair"]["at"]
            ) == datetime.fromisoformat(query)
        assert any(
            r["ruleset_id"] == "canping_luck_substitution_v1"
            for r in evidence["rulesets"]
        )
        if profile == "legacy_minggong_v1":
            assert any(
                "出生年柱" in s and "无已核定日期区间" in s
                for s in evidence["unresolved_rules"]
            )
