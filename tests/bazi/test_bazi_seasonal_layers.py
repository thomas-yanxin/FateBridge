"""Source layers and positional evidence do not become final 用神 decisions."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.classical import (
    build_classical_overview,
    classical_snapshot_lines,
    seasonal_climate_god,
)
from fatebridge.core.output_classical_seasonal import SeasonalClimateReference
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_seasonal_jia_v1"
SOURCE = json.loads((FIXTURE / "source-collation.json").read_text())
PILLARS = {
    "year": ("庚", "午"),
    "month": ("乙", "酉"),
    "day": ("甲", "子"),
    "hour": ("丁", "卯"),
}


def test_source_profile_is_frozen_and_not_mislabelled_as_a_blind_trial():
    frozen = (FIXTURE / "source-collation.json").read_bytes()
    assert (
        hashlib.sha256(frozen).hexdigest()
        == (FIXTURE / "source-collation.sha256").read_text().strip()
    )
    assert (
        frozen
        == (
            ROOT / "src/fatebridge/data/bazi_seasonal_qiongtong_jia_v1.json"
        ).read_bytes()
    )
    protocol = json.loads((FIXTURE / "audit-protocol.json").read_text())
    assert "not blind validation" in protocol["scope"]
    assert set(SOURCE["months"]) == set("寅卯辰巳午未申酉戌亥子丑")
    assert SOURCE["source"]["source_sha256"] == protocol["source_sha256"]


@pytest.mark.parametrize("branch", list("寅卯辰巳午未申酉戌亥子丑"))
def test_each_jia_month_keeps_its_distinct_outline_and_body(branch):
    result = seasonal_climate_god("甲", branch)
    assert result["source_layers"] == SOURCE["months"][branch]
    assert result["source_ref"] == SOURCE["source"]
    assert result["chart_adjudication_status"] == "not_performed"
    assert result["source_layers"]["chart_conditions_status"] == "not_adjudicated"
    summary = result["source_layers"]["summary"]
    assert summary["top_listed_stem"] == result["primary"]
    assert set(summary["listed_stems"]) == {result["primary"], *result["secondary"]}


def test_rank_disagreements_and_half_month_unknown_are_not_overwritten():
    for month, body in [
        ("申", ["丁", "庚"]),
        ("酉", ["丁", "丙", "庚"]),
        ("丑", ["庚", "丁"]),
    ]:
        result = seasonal_climate_god("甲", month)
        assert result["source_layers"]["body"]["stem_sequence"] == body
        assert result["primary"] != body[0]
    june = seasonal_climate_god("甲", "未", {**PILLARS, "month": ("辛", "未")})
    assert "上半月" in june["source_layers"]["summary"]["partition_note"]
    assert "原文半月界尚未形式化" in june["source_layers"]["summary"]["partition_note"]
    assert june["source_layers"]["chart_conditions_status"] == "not_adjudicated"


def test_observations_use_actual_positions_without_inventing_hidden_or_visible_stems():
    result = seasonal_climate_god("甲", "酉", PILLARS)
    by_stem = {row["stem"]: row for row in result["stem_observations"]}
    assert by_stem["丁"] == {
        "stem": "丁",
        "visible_positions": ["hour"],
        "hidden_positions": [{"pillar": "year", "branch": "午", "hidden_rank": 0}],
    }
    assert by_stem["庚"]["visible_positions"] == ["year"]
    assert by_stem["庚"]["hidden_positions"] == []
    assert by_stem["丙"]["visible_positions"] == by_stem["丙"]["hidden_positions"] == []
    assert "得用" in result["observation_scope"]
    result["source_layers"]["body"]["pdf_pages"].append(999)
    assert (
        999
        not in seasonal_climate_god("甲", "酉")["source_layers"]["body"]["pdf_pages"]
    )


def test_snapshot_keeps_outline_and_body_conditions_instead_of_a_final_use_claim():
    lines = "\n".join(classical_snapshot_lines(build_classical_overview(PILLARS)))
    assert "调候简表候选：首列庚" in lines
    assert "丁先、丙次、庚再次" in lines
    assert "全盘取用未裁定" in lines
    assert "调候用神：主用" not in lines


def test_reference_contract_does_not_promote_lookup_or_pending_sources_to_acceptance():
    with pytest.raises(ValidationError):
        SeasonalClimateReference.model_validate(
            {"chart_adjudication_status": "adjudicated"}
        )
    with pytest.raises(ValidationError):
        SeasonalClimateReference.model_validate(
            {
                "source_review_status": "source_not_collated",
                "source_ref": {"title": "claimed_critical_edition"},
            }
        )
    # A valid projection may contain just a source leaf or position.
    SeasonalClimateReference.model_validate({"source_ref": {"title": "窮通寶鑑評註"}})
    SeasonalClimateReference.model_validate({"stem_observations": [{"stem": "丁"}]})


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("birth_day,reviewed", [(16, True), (17, False)])
def test_ten_published_views_preserve_source_review_and_positions_on_three_surfaces(
    topic, birth_day, reviewed, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    payload = {
        **inputs(spec),
        "birth_year": 1990,
        "birth_month": 9,
        "birth_day": birth_day,
        "birth_hour": 12,
        "use_true_solar_time": False,
    }
    fields = suggested_fields(spec, view="seasonal_reference")
    opts = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
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
    assert http.status_code == 200 and not protocol.is_error and code == 0
    data = business(http.json())
    assert data == business(protocol.structured_content) == business(cli)
    climate = data
    for part in fields[0].split("."):
        climate = climate[part]
    assert climate["chart_adjudication_status"] == "not_performed"
    assert climate["stem_observations"]
    if reviewed:
        assert climate["source_layers"]["body"]["pdf_pages"] == [33, 34]
        assert climate["source_layers"]["body"]["stem_sequence"] == ["丁", "丙", "庚"]
        assert climate["primary"] == "庚"
    else:
        assert climate["source_review_status"] == "source_not_collated"
        assert "source_ref" not in climate
