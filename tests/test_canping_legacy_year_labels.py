"""A legacy age-label table must begin with the actual birth year pillar."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.canping import liunian_series
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.services.tool_catalog import CATALOG

FIXTURE = Path(__file__).parent / "fixtures/canping_legacy_year_labels_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def request(case):
    return {k: v for k, v in case.items() if k not in {"id", "year", "year_pillar"}} | {
        "gender": "男",
        "dayun_method": "legacy_minggong_v1",
    }


@pytest.fixture(autouse=True)
def native_source(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


def test_frozen_oracle_is_the_reused_official_minute_with_safe_probe_margin():
    source = REFERENCE["reused_calendar_source"]
    assert (
        hashlib.sha256((FIXTURE / source["file"]).read_bytes()).hexdigest()
        == source["sha256"]
    )
    assert (
        "<Data><M>02</M><D>04</D><hm>04:02</hm></Data>"
        in (FIXTURE / source["file"]).read_text()
    )
    assert source["probe_margin_seconds"] > source["precision_seconds"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["id"])
def test_legacy_first_year_is_coherent_with_real_birth_pillar_on_both_sides(case):
    result = build_canping_result(**request(case))
    pillar = result["four_pillars"]["year"]
    assert pillar["stem"] + pillar["branch"] == case["year_pillar"]
    series = result["liunian_series"]
    first = series["rows"][0]
    assert (first["year"], first["ganzhi"], first["taisuiBranch"]) == (
        case["year"],
        case["year_pillar"],
        pillar["branch"],
    )
    assert series["birth_pillar_year"] == case["year"]
    assert series["year_boundary"] == "lichun_year_labels_only"
    assert (
        series["age_policy"]
        == "nominal_age_by_lichun_year_labels; no_actual_boundaries"
    )
    assert [row["year"] for row in series["rows"]] == list(
        range(case["year"], case["year"] + 120)
    )
    assert [row["age"] for row in series["rows"]] == list(range(1, 121))
    assert result["canping_timing"]["first_period"] is None
    assert (
        result["canping_timing"]["schedule_basis"]["has_actual_date_mapping"] is False
    )
    assert all("start_at" not in row and "end_at" not in row for row in series["rows"])
    assert "year_boundaries" not in series
    next(s for s in CATALOG if s.key == "canping").output_model.model_validate(result)


def test_january_wrong_taisui_changes_real_numbers_and_selected_luck_text():
    result = build_canping_result(**request(REFERENCE["cases"][0]))
    first = result["liunian_series"]["rows"][0]
    expected = REFERENCE["january_manual_number"]
    assert result["element"] == expected["element"]
    assert (first["taisuiBranch"], first["dayunBranch"]) == ("巳", "申")
    assert (first["numShun"], first["numNi"]) == (
        expected["num_shun"],
        expected["num_ni"],
    )
    assert first["verses"]["selectionShun"]["number"] == expected["num_shun"]
    assert first["verses"]["selectionNi"]["number"] == expected["num_ni"]
    assert (
        "2025" in result["snapshot_text"]
        and "旧命宫流年年序" in result["snapshot_text"]
    )


def test_direct_fixed_pillar_helper_rejects_a_contradictory_first_year_label():
    with pytest.raises(ValueError, match="年标签.*年柱"):
        liunian_series(
            year_gz="乙巳",
            month_branch="子",
            day_branch="子",
            hour_branch="午",
            birth_year=2026,
        )
