"""An earlier printing is counterevidence, never an automatic table repair."""

import copy
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.audit_jyotish_motion_witnesses import audit_text, build_report

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "tests/fixtures/jyotish-motion-primary.json",
    ROOT / "tests/fixtures/jyotish-raman-1942-motion-primary.json",
    ROOT / "tests/fixtures/jyotish-raman-1942-motion-text.json",
]


def witnesses():
    return [json.loads(p.read_text()) for p in PATHS]


def test_independently_transcribed_source_fingerprints_and_unresolved_gates():
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS] == [
        "76e7238582e91df6c2c0f8cee1d13ab8797dd60f033f9490d20ced4fe7b6de9a",
        "07c1f1a6d11ccb6393ef88148aef4fb1a1addcf3b969e6f957449ac89f6ab0a9",
        "010d9c4a08e996e9cd41c09305ef3fb2fcad090950ceef94dd0499c137b6cb91",
    ]
    report = build_report(*witnesses())
    assert report["status"] == "source_conflicts_retained"
    assert report["comparable_clear_cells"] == 250
    assert len(report["numeric_differences"]) == 19
    assert len(report["legibility_differences"]) == 2
    assert len(report["equal_value_display_precision_differences"]) == 1
    for key, evaluated, conflicts in [
        ("existing_witness", 383, 54),
        ("earlier_witness", 392, 34),
    ]:
        audit = report["relation_audits"][key]
        assert audit["evaluated_relations"] == evaluated
        assert len(audit["conflicts"]) == conflicts
    assert not report["historical_mean_model_activation_eligible"]
    assert not report["complete_single_original_accepted"]
    assert not report["blinded"]
    assert report["real_event_cases"] == 0


def test_earlier_witness_can_remove_one_conflict_and_introduce_another():
    existing, earlier, _ = witnesses()
    # The earlier solar2000-day cell is independently consistent with twice
    # its1000-day cell within the original display-quantum envelope.
    sun = earlier["tables"]["Sun"]["rows"]
    assert abs(Fraction(sun[1][2]) - (2 * Fraction(sun[0][2])) % 360) == Fraction(
        "0.0001"
    )
    # The earlier Mars500-day cell is worse than the existing witness's
    # literal relation; never select the earlier printing wholesale as truth.
    mars = earlier["tables"]["Mars"]["rows"]
    assert Fraction(mars[4][1]) - 5 * Fraction(mars[0][1]) == Fraction("0.61")
    old_mars = existing["tables"]["Mars"]["rows"]
    assert Fraction(old_mars[4][1]) - 5 * Fraction(old_mars[0][1]) == Fraction("0.01")


def test_readability_in_another_printing_does_not_fill_old_unknowns_or_round_cells():
    existing, earlier, text = witnesses()
    original = copy.deepcopy(existing)
    report = build_report(existing, earlier, text)
    assert existing == original
    assert existing["tables"]["Mercury"]["rows"][0][4] is None
    assert existing["tables"]["Mercury"]["rows"][6][1] is None
    assert earlier["tables"]["Mercury"]["rows"][6][3] == "206.234"
    assert any(
        r["earlier_witness_literal"] == "206.234" for r in report["numeric_differences"]
    )


@pytest.mark.parametrize("fault", ["row", "cell", "column", "table"])
def test_missing_domains_cannot_silently_disappear_from_comparison(fault):
    existing, earlier, _ = witnesses()
    if fault == "row":
        earlier["tables"]["Sun"]["rows"].pop()
    elif fault == "cell":
        earlier["tables"]["Sun"]["rows"][0].pop()
    elif fault == "column":
        earlier["tables"]["Sun"]["columns_days"].pop()
    else:
        earlier["tables"].pop("Venus")
    with pytest.raises(ValueError):
        build_report(existing, earlier)


@pytest.mark.parametrize("value", [True, 0.1, "NaN", "1/2", "360.0"])
def test_literal_numeric_cells_reject_substituted_types_and_expressions(value):
    existing, earlier, _ = witnesses()
    earlier["tables"]["Sun"]["rows"][0][0] = value
    with pytest.raises(ValueError):
        build_report(existing, earlier)


def test_selected_text_uses_its_own_clock_and_keeps_printed_summary_conflicts():
    _, _, text = witnesses()
    result = audit_text(text)
    assert text["standard_clock"]["birth_local_mean_hms"] == [14, 0, 0]
    assert Fraction(result["exact_converted_reference_seconds_after_midnight"]) == (
        13 * 3600 + 53 * 60 + 40
    )
    assert Fraction(result["displayed_reference_time_minus_exact_seconds"]) == 20
    assert Fraction(
        result["exact_reference_time_minus_displayed_fractional_day_seconds"]
    ) == Fraction("80.8")
    assert result["mercury_body_and_example_year_coefficients_equal"]
    assert Fraction(result["venus_listed_sum"]) == Fraction("878.35")
    assert result["venus_listed_sum_matches_printed_total"]
    assert result["venus_listed_modulo_matches_printed_modulo"]
    assert [Fraction(r["difference_degrees"]) for r in result["source_conflicts"]] == [
        4,
        -7,
    ]


def test_source_gate_reports_failure_and_exclusively_writes_new_report(tmp_path):
    before = [p.read_bytes() for p in PATHS]
    report = tmp_path / "report.json"
    command = [
        sys.executable,
        "-m",
        "scripts.audit_jyotish_motion_witnesses",
        "--report",
    ]
    done = subprocess.run([*command, str(report)], cwd=ROOT, capture_output=True)
    assert done.returncode == 1, done.stderr
    assert json.loads(report.read_text())["status"] == "source_conflicts_retained"
    for path in [report, *PATHS]:
        raw = path.read_bytes()
        rejected = subprocess.run([*command, str(path)], cwd=ROOT, capture_output=True)
        assert rejected.returncode == 2
        assert path.read_bytes() == raw
    assert [p.read_bytes() for p in PATHS] == before


def test_omitting_a_printed_term_never_disappears_behind_matching_final_number():
    _, _, text = witnesses()
    text["Venus"]["example48_signed_terms"].remove("3.20")
    result = audit_text(text)
    assert not result["venus_listed_sum_matches_printed_total"]
    assert not result["venus_listed_modulo_matches_printed_modulo"]
    assert [
        Fraction(r["difference_degrees"])
        for r in result["source_conflicts"]
        if "listed" in r["location"]
    ] == [Fraction("3.20"), Fraction("3.20")]
