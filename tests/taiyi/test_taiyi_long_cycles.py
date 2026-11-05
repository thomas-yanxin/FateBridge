"""Complete source-table comparison and independent historical calculations."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.taiyi_long_cycles import (
    annual_long_cycles,
    four_spirit_records,
)
from fatebridge.core.metaphysics.taiyi_year import yearly_core
from fatebridge.core.output_taiyi_long_cycles import TaiyiLongCycles
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_long_cycles import CORPUS, audit
from scripts.taiyi.build_taiyi_long_cycle_reference import TARGET, render

TABLE = json.loads((CORPUS / "four-spirit-cases.json").read_text())
WORKED = json.loads((CORPUS / "worked-cases.json").read_text())


@pytest.mark.parametrize("row", TABLE["rows"], ids=lambda c: c["id"])
def test_every_original_row_is_compared_without_skipping_failed_cells(row):
    mismatched = []
    for field, expected in row["expected"].items():
        star, yuan = field.split(".")
        counter = row["year_index"] + 60 * ("upper", "middle", "lower").index(yuan)
        actual = four_spirit_records(counter)[star]
        # Table fact and prose derivation are returned separately.
        assert actual["table_position"] == expected
        assert actual["table_disagreement"] is (actual["position"] != expected)
        if actual["position"] != expected:
            mismatched.append(field)
    assert mismatched == (["zhifu.middle"] if row["year_index"] >= 28 else [])


@pytest.mark.parametrize("case", WORKED, ids=lambda c: c["id"])
def test_independent_worked_examples_and_epoch_facts(case):
    result = annual_long_cycles(case["year"])
    for name, fields in case.get("expected", {}).items():
        for field, expected in fields.items():
            assert result["records"][name][field] == expected
    for name, expected in case.get("expected_accumulations", {}).items():
        assert result["records"][name]["accumulation"] == expected


def test_all_raw_failures_remain_in_audit_and_source_collation():
    result = audit()
    assert (result["source_rows"], result["source_columns"]) == (60, 12)
    assert (result["checked_fields"], result["matching_fields"]) == (720, 687)
    assert result["classical_acceptance_passed"] is False
    assert all(r["passed"] for r in result["worked_examples"])
    assert {k: v["matching"] for k, v in result["by_star"].items()} == {
        "sishen": 180,
        "tianyi": 180,
        "diyi": 180,
        "zhifu": 147,
    }
    col = json.loads((CORPUS / "collation.json").read_text())
    assert {
        (c["year_index"], c["field"], c["reading"]) for c in col["disputed_cells"]
    } == {
        (c["year_index"], c["field"], c["source_value"])
        for c in result["disagreements"]
    }


@pytest.mark.parametrize("attempt", ["drop_row", "drop_column", "alter_scan"])
def test_frozen_audit_rejects_removed_cases_or_changed_primary_sources(
    tmp_path, attempt
):
    copy = tmp_path / "corpus"
    shutil.copytree(CORPUS, copy)
    if attempt == "alter_scan":
        (copy / "cadal06056495-page23.jpg").write_bytes(b"changed")
        with pytest.raises(ValueError, match="指纹"):
            audit(copy)
        return
    path = copy / "four-spirit-cases.json"
    data = json.loads(path.read_text())
    if attempt == "drop_row":
        data["rows"].pop(27)
    else:
        del data["rows"][27]["expected"]["zhifu.middle"]
    path.write_text(json.dumps(data))
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["source_files"]:
        if item["file"] == path.name:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="60|12"):
        audit(copy)


def test_packaged_original_reference_is_generated_without_domain_recalculation():
    assert TARGET.read_text() == render()
    assert (
        json.loads(TARGET.read_text())["source_transcription_sha256"]
        == hashlib.sha256((CORPUS / "four-spirit-cases.json").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("invalid", [True, 0, -1, 10000, "2026", 2026.0])
def test_invalid_year_is_never_silently_coerced(invalid):
    with pytest.raises(ValueError):
        annual_long_cycles(invalid)


def test_independent_epochs_do_not_alias_eight_generals_counter():
    cycles = annual_long_cycles(724)
    assert yearly_core(724)["accumulation"] == 1937281
    assert {r["accumulation"] for r in cycles["records"].values()} == {
        285011,
        13331,
        3361,
    }
    assert (
        cycles["records"]["junji"]["palace"] == "午"
    )  # Not the old 命起午+250 formula.
    assert cycles["records"]["wufu"]["palace"] == "艮"


def test_ming_diyi_corroboration_does_not_replace_the_siku_epoch():
    cycles = annual_long_cycles(724)
    record = cycles["records"]["diyi"]
    assert record["accumulation"] == 3361
    assert record["source_method"] == "siku_table_corroborated_by_ming_prose"
    assert "NCL-06604" in record["source_reference"]
    assert record["source_reference"].endswith("#page=74")
    assert "未替换积年" in record["source_edition"]


def test_small_you_and_annual_taiyi_are_not_independent_positions():
    # The two printed epochs differ by a multiple of both 24 and 72.
    # Their common phase must not become an extra vote in SanShi.
    for year in (1, 622, 724, 904, 930, 1900, 2026, 2100, 9999):
        assert (
            annual_long_cycles(year)["records"]["xiaoyou"]["palace_number"]
            == yearly_core(year)["taiyi_number"]
        )


def test_first_three_year_dwell_boundary_uses_all_printed_rows():
    assert [four_spirit_records(n)["sishen"]["position"] for n in range(1, 8)] == [
        "1",
        "1",
        "1",
        "2",
        "2",
        "2",
        "3",
    ]
    assert [four_spirit_records(n)["sishen"]["position"] for n in (34, 35, 36, 37)] == [
        "玉",
        "玉",
        "玉",
        "1",
    ]


def test_long_cycle_contract_rejects_non_integer_facts_and_text_booleans():
    with pytest.raises(ValidationError):
        TaiyiLongCycles.model_validate(
            {"records": {"junji": {"accumulation": "285011"}}}
        )
    with pytest.raises(ValidationError):
        TaiyiLongCycles.model_validate(
            {"records": {"zhifu": {"table_disagreement": "false"}}}
        )


def standalone(year=2026, month=4, day=4, mode="year"):
    return calculate_taiyi_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        calculation_mode=mode,
        use_true_solar_time=False,
    )


def test_every_annual_marker_is_preserved_in_ring_center_or_extra_palace():
    # Several complete four-spirit revolutions, including table conflicts.
    for year in range(1900, 2100):
        board = standalone(year)["taiyi"]
        cycles = board["long_cycles"]
        TaiyiLongCycles.model_validate(cycles)
        by_palace = {
            p["palace"]: p["markers"]
            for p in board["palace_marks"]
            + [board["center_marks"]]
            + board["extra_palace_marks"]
        }
        for marker in cycles["records"].values():
            label = marker["label"] + (
                "（表异）" if marker.get("table_disagreement") else ""
            )
            assert label in by_palace[marker["palace"]]
            assert 1 <= marker["year_in_palace"] <= marker["years_per_position"]
        for extra in board["extra_palace_marks"]:
            assert extra["palace"] in {"绛宫", "明堂", "玉堂"}


def test_lunar_new_year_controls_long_cycles_and_birth_time_cannot_rewrite_it():
    a = standalone(month=2, day=16)["taiyi"]["long_cycles"]
    b = standalone(month=2, day=17)["taiyi"]["long_cycles"]
    assert (a["year"], b["year"]) == (2025, 2026)
    for key in a["records"]:
        assert (
            a["records"][key]["accumulation"] + 1 == b["records"][key]["accumulation"]
        )


@pytest.mark.parametrize("mode", ["month", "hour"])
def test_non_annual_board_does_not_relabel_month_or_hour_counter_as_year(mode):
    result = standalone(mode=mode)
    assert result["taiyi"]["long_cycles"]["status"] == "not_computed_for_selected_mode"
    assert "records" not in result["taiyi"]["long_cycles"]
    assert "本盘采用月/时计" in result["snapshot_text"]


def test_current_source_conflict_is_visible_in_same_run_interpretation():
    year = next(
        y
        for y in range(1900, 2100)
        if annual_long_cycles(y)["records"]["zhifu"]["table_disagreement"]
    )
    result = standalone(year)
    assert result["taiyi"]["long_cycles"]["records"]["zhifu"]["table_disagreement"]
    assert "直符有异文：正文通则" in result["snapshot_text"]
    assert any(
        s["title"] == "年运十神" and s["included"]
        for s in result["snapshot_export"]["sections"]
    )


def test_sanshi_keeps_the_same_annual_positions_without_using_them_as_votes():
    joined = calculate_sanshiunited_analysis(
        date="2026-04-04",
        time="12:00:00",
        zone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    assert joined["taiyi"] == standalone()["taiyi"]
    assert joined["synthesis"]["independent_evidence_count"] is None
    assert "[太乙年运十神]" in joined["snapshot_text"]
    assert (
        joined["taiyi"]["long_cycles"]["interpretation_scope"]
        in joined["snapshot_text"]
    )
