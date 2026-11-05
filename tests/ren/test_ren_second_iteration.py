"""Independent source depth, unresolved readings and bounded strength claims."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from fatebridge.core.metaphysics.jinkou_strength import internal_strength
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.requests.metaphysics import (
    JinkouAnalysisRequest,
    LiuRengGodsRequest,
    LiuRengRunyearRequest,
)
from fatebridge.services.metaphysics import (
    calculate_jinkou_analysis,
    calculate_liureng_gods,
)
from tests.ren.test_ren_classical_depth import AUDIT as V1

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_ren_depth", ROOT / "scripts/ren/audit_ren_depth.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.load_reference()


def rows(elements):
    return [
        dict(label=label, element=element)
        for label, element in zip(("人元", "贵神", "将神", "地分"), elements)
    ]


def test_depth_audit_counts_unique_boards_and_preserves_contradictions():
    report = AUDIT.audit()
    assert report["implemented_excerpt_checks_passed"]
    assert len(report["checks"]) == 39  # 12 strength, 20 starts, 4 placements, 3 ties.
    table = report["transcribed_table"]
    assert table["printed_rows"] == 720
    assert table["unique_compared"] == table["matched"] == 712
    assert table["missing_count"] == len(table["missing"]) == 8
    assert len(table["duplicate_keys"]) == 8
    assert table["failures"] == table["duplicate_conflicts"] == []
    assert not table["second_host_is_independent_edition"]
    combined = report["combined_table"]
    assert combined["unique_compared"] == combined["matched"] == 720
    assert combined["text_transcribed"] == 712
    assert combined["scan_supplements"] == 8
    assert combined["missing_count"] == 0 and not combined["failures"]
    assert not combined["all_720_rows_visually_collated"]
    assert len(report["selected_scan_checks"]) == 11
    assert all(c["matched"] for c in report["selected_scan_checks"])
    conflicts = report["unresolved_preamble_comparisons"]
    assert len(conflicts) == 3 and all(not c["matched"] for c in conflicts)
    assert all(c["transmissions"] == list("卯午子") for c in conflicts)
    assert conflicts[0]["table_value"] is None
    assert conflicts[1]["table_value"] == conflicts[2]["table_value"] == list("卯子午")
    assert all(c["scan_table_value"] == list("卯子午") for c in conflicts)
    assert all(c["scan_preamble_value"] == list("卯午子") for c in conflicts)
    assert not report["all_source_assertions_matched"]
    assert not report["classical_acceptance_passed"]
    assert not report["authority_certified"]
    assert report["real_world_prediction"] == "not_tested"


@pytest.mark.parametrize("case", REFERENCE["jinkou-internal"]["cases"])
def test_twelve_explicit_internal_strength_examples(case):
    strength = internal_strength(rows(case["elements"]))
    assert strength["anchor_element"] == case["anchor"]
    assert strength["powers"]["贵神"] == case["god_power"]
    assert strength["status"] == "resolved_excerpt"


def test_seasonal_and_internal_powers_are_independent_and_traced():
    board = V1.observe_jinkou(V1.load_frozen_corpus()["cases"]["cases"][0])
    assert [r["seasonal_power"] for r in board["rows"]] == ["相", "休", "休", "囚"]
    assert [r["internal_power"] for r in board["rows"]] == ["死", "旺", "旺", "休"]
    assert all("power" not in r for r in board["rows"])
    assert board["internal_strength"]["anchor_element"] == "水"
    assert (
        next(
            t for t in board["rule_trace"] if t["rule_id"] == "jinkou.internal_strength"
        )["result"]
        == board["internal_strength"]
    )


def test_multiple_uncontrolled_phases_do_not_invent_a_strongest_or_use_rule():
    strength = internal_strength(rows("木火木火"))
    assert strength["candidate_elements"] == ["木", "火"]
    assert strength["anchor_element"] is None
    assert strength["powers"] == dict.fromkeys(("人元", "贵神", "将神", "地分"))
    assert strength["status"] == "ambiguous_excerpt"
    assert strength["has_control"] is False
    assert {r["relation"] for r in strength["relations"]} == {"生", "比和"}
    assert "取用" in strength["scope"]


@pytest.mark.parametrize(
    "calculate", [calculate_liureng_gods, calculate_jinkou_analysis]
)
def test_independent_solar_correction_crosses_a_real_hour_boundary(calculate):
    # NOAA's Meeus spreadsheet formula at 2026-04-04T12:57Z gives EoT
    # -2.946410 min; longitude 121.5E adds 6 min => +3.053590 min.
    # Thus apparent time passes 21:00; the old seasonal sinusoid missed it.
    # https://gml.noaa.gov/grad/solcalc/calcdetails.html
    result = calculate(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=20,
        analysis_minute=57,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.5,
        use_true_solar_time=True,
    )
    assert result["analysis_context"]["total_correction_minutes"] == pytest.approx(
        3.053590, abs=0.02
    )
    assert result["analysis_context"]["corrected_datetime"].startswith(
        "2026-04-04 21:00:"
    )
    assert result["four_pillars"]["hour"] == {"stem": "癸", "branch": "亥"}
    if "jinkou" in result:
        assert result["jinkou"]["overview"]["di_fen"] == "亥"


@pytest.mark.parametrize(
    "bad_rows", [[], rows("木火土"), rows("木火土X"), [rows("木火土金")[0]] * 4]
)
def test_invalid_four_positions_are_rejected(bad_rows):
    with pytest.raises(ValueError):
        internal_strength(bad_rows)


def test_noble_profiles_change_only_the_da_liuren_gods():
    seed = V1.make_seed(dict(day="甲辰", hour="卯"))
    common = build_liureng_board(seed, month_general_override="亥")
    source = build_liureng_board(
        seed, month_general_override="亥", guiren_profile="tanyuan_xieji_v1"
    )
    assert common["meta"]["guiren_profile"] == "liuren_common_v1"
    assert source["meta"]["guiren_profile"] == "tanyuan_xieji_v1"
    assert common["meta"]["guiren_earth_branch"] == "巳"
    assert source["meta"]["guiren_earth_branch"] == "亥"
    for position in ("initial", "middle", "final"):
        assert (
            common["three_transmissions"][position]["branch"]
            == source["three_transmissions"][position]["branch"]
        )
    assert common["four_lessons"] == source["four_lessons"]
    assert build_jinkou_board(seed, common, di_fen="申") == build_jinkou_board(
        seed, source, di_fen="申"
    )
    assert source["ruleset"]["classical_acceptance_passed"] is False


@pytest.mark.parametrize(
    "model", [LiuRengGodsRequest, LiuRengRunyearRequest, JinkouAnalysisRequest]
)
def test_unknown_noble_profile_cannot_fall_back_to_another_school(model):
    with pytest.raises(ValidationError):
        model.model_validate(dict(guiren_profile="whatever"))
    with pytest.raises(ValueError, match="配置"):
        build_liureng_board(
            V1.make_seed(dict(day="甲子", hour="午")), guiren_profile="whatever"
        )


@pytest.mark.parametrize("change", ["labels", "missing", "extra"])
def test_v2_freeze_rejects_drift_without_changing_v1(tmp_path, change):
    target = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, target)
    if change == "labels":
        path = target / "tanyuan-rules.json"
        data = json.loads(path.read_text())
        data["conflicting_preamble"] = []
        path.write_text(json.dumps(data))
    elif change == "missing":
        (target / "jinkou-internal.json").unlink()
    else:
        (target / "hidden.json").write_text("{}")
    with pytest.raises(ValueError, match="Reference"):
        AUDIT.load_reference(target)
    assert V1.load_frozen_corpus()["cases"]["unresolved"]


@pytest.mark.parametrize("name", ["collation.json", "selected-pages.pdf"])
def test_scan_evidence_cannot_silently_change(tmp_path, name):
    target = tmp_path / "scan"
    shutil.copytree(AUDIT.SCAN_CORPUS, target)
    path = target / name
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Reference scan changed"):
        AUDIT.load_scan_reference(target)
