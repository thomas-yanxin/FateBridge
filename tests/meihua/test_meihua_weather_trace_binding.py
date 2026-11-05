"""A logical weather label is not proof that the supplied cast produced it."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_trace_binding as verifier
from fatebridge.validation.meihua_weather_policy_v3 import scope_aware_weather_label

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_weather_binding_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
FORGERY = json.loads((FIXTURE / "forgery-probe.json").read_bytes())


def first():
    return copy.deepcopy(REFERENCE["samples"]["first"])


@pytest.mark.parametrize("name", list(REFERENCE["samples"]))
def test_original_full_records_keep_their_original_labels(name):
    record = copy.deepcopy(REFERENCE["samples"][name])
    untouched = copy.deepcopy(record)
    result = verifier.bound_weather_label(record)
    assert result["decision"] == untouched["decision"]
    assert result["verification"]["mechanical_binding_verified"]
    assert result["verification"]["rules_checked"] == 40
    assert result["verification"]["selected_readings_verified"]
    assert not result["verification"]["calendar_labels_independently_authenticated"]
    assert not result["verification"]["source_semantics_independently_adjudicated"]
    assert not result["verification"]["prediction_efficacy_established"]
    assert record == untouched


def test_preimplementation_literal_geometry_and_original_pins_are_preserved():
    row = first()
    expected = REFERENCE["literal_first_geometry"]
    for key in ["base_code", "mutual_code", "changed_code"]:
        assert row[key] == expected[key]
    assert row["seed"]["moving_line"] == expected["moving_line"]
    assert row["weather"]["trigram_counts"] == expected["trigram_counts"]
    assert REFERENCE["before_production_edit"]
    assert REFERENCE["original_file_pins"] == verifier.STUDY_PINS
    assert hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest() == (
        "b69c03c346a1cb0dbe607b7b6f8e94ed513dacb699866a4c7fc7bc8f4a84dd9a"
    )


def test_legacy_logical_adapter_does_not_claim_full_cast_attestation():
    forged = copy.deepcopy(FORGERY["forged_record"])
    assert forged["weather"]["trigram_counts"]["乾"] == 0
    row = next(
        r for r in forged["weather"]["rule_trace"] if r["rule_id"] == "symbol_qian"
    )
    assert row["conditions"][0]["met"] is False
    assert row["status"] == "matched"
    decision = scope_aware_weather_label(
        forged["weather"],
        expected_profile_sha256=verifier.PROFILE_SHA256,
        expected_control_profile_sha256=verifier.CONTROL_SHA256,
    )
    assert decision["label"] == "dry"
    with pytest.raises(ValueError, match="rule_trace"):
        verifier.bound_weather_label(forged)


def mutate(row, kind):
    weather = row["weather"]
    if kind == "calendar":
        row["calendar_actual"]["day"] = 13
    elif kind == "target":
        row["date"] = "2026-01-02"
    elif kind == "moving_bool":
        row["seed"]["moving_line"] = True
    elif kind in {"base_code", "mutual_code", "changed_code"}:
        row[kind] = "111111"
    elif kind == "slot":
        weather["trigram_slots"][0]["trigram"] = "乾"
    elif kind == "count":
        weather["trigram_counts"]["乾"] = 1
    elif kind == "frequency":
        weather["frequency_views"][1]["slot_count"] = 6
    elif kind == "control":
        weather["controls"][0][
            "status"
        ] = "met_under_declared_threshold_and_scope_probes"
    elif kind == "condition":
        weather["rule_trace"][0]["conditions"][0]["met"] = True
    elif kind == "condition_bool_alias":
        weather["rule_trace"][0]["conditions"][0]["met"] = 0
    elif kind == "condition_status":
        weather["rule_trace"][0]["status"] = "matched"
    elif kind == "qualification":
        weather["rule_trace"][1]["controlled_tags"] = ["rain"]
    elif kind == "matched_index":
        weather["matched_rule_ids"] = []
    elif kind == "reading":
        weather["selected_readings"][0]["reading"] = "certain real-world forecast"
    elif kind == "reading_source":
        weather["selected_readings"][0]["quote"] = "different source"
    elif kind == "context":
        weather["context"]["season"] = "summer"
    elif kind == "threshold_bool":
        row["input"]["weather_context"]["many_min_count"] = True
    elif kind == "profile":
        weather["ruleset"]["title"] = "different profile"
    elif kind == "decision":
        row["decision"]["label"] = "rain"
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind",
    [
        "calendar",
        "target",
        "moving_bool",
        "base_code",
        "mutual_code",
        "changed_code",
        "slot",
        "count",
        "frequency",
        "control",
        "condition",
        "condition_bool_alias",
        "condition_status",
        "qualification",
        "matched_index",
        "reading",
        "reading_source",
        "context",
        "threshold_bool",
        "profile",
        "decision",
    ],
)
def test_inconsistent_computation_or_reading_is_rejected(kind):
    record = first()
    mutate(record, kind)
    with pytest.raises(ValueError):
        verifier.bound_weather_label(record)


@pytest.mark.parametrize("value", [False, 0, "", []])
def test_false_like_context_cannot_be_replaced_by_unknown_defaults(value):
    record = first()
    record["input"]["weather_context"] = value
    with pytest.raises(ValueError, match="context"):
        verifier.verify_weather_trace_binding(record)


def test_binding_failure_precedes_legacy_label_evaluation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No label evaluation before a complete binding check")

    monkeypatch.setattr(verifier, "scope_aware_weather_label", forbidden)
    with pytest.raises(ValueError, match="rule_trace"):
        verifier.bound_weather_label(copy.deepcopy(FORGERY["forged_record"]))


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_ambiguous_json_is_rejected(raw):
    with pytest.raises(ValueError):
        verifier._json(raw)


def test_wrong_study_bytes_fail_before_parsing(tmp_path, monkeypatch):
    (tmp_path / "plan.json").write_bytes(b"invalid bytes")
    monkeypatch.setattr(
        verifier, "_json", lambda raw: pytest.fail("unverified bytes parsed")
    )
    with pytest.raises(ValueError, match="file changed"):
        verifier.audit_bound_weather_study(tmp_path)


def test_study_symlink_cannot_escape_root(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.write_bytes(b"not a study")
    (tmp_path / "plan.json").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        verifier.audit_bound_weather_study(tmp_path)


def test_optimized_python_still_rejects_the_frozen_forgery():
    script = (
        "import json,sys; from fatebridge.validation.meihua_weather_trace_binding "
        "import bound_weather_label; "
        "row=json.load(open(sys.argv[1]))['forged_record']; "
        "bound_weather_label(row)"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", script, str(FIXTURE / "forgery-probe.json")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Weather evidence binding mismatch: rule_trace" in result.stderr


AUDIT_CHECKS = [
    ("trace", "mechanical_binding_verified"),
    ("calendar", "published_lunar_date_binding_verified"),
    ("solar", "published_solar_context_verified"),
    ("context-capacity", "context_capacity_verified"),
]


@pytest.mark.parametrize("check,error_field", AUDIT_CHECKS)
def test_cli_reports_invalid_source_without_a_success_receipt(
    tmp_path, check, error_field
):
    study = tmp_path / "study"
    study.mkdir()
    (study / "plan.json").write_text("{}")
    output = tmp_path / "receipt.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.meihua.audit_meihua_weather_study",
            "--check",
            check,
            "--study",
            str(study),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stderr)[error_field] is False
    assert not output.exists()


@pytest.mark.parametrize("check,error_field", AUDIT_CHECKS)
@pytest.mark.parametrize(
    "target", ["inside", "source", "existing", "symlink", "hardlink"]
)
def test_cli_preserves_original_study_and_existing_receipts(
    tmp_path, check, error_field, target
):
    study = tmp_path / "study"
    study.mkdir()
    original = study / "plan.json"
    original.write_bytes(b'{"immutable":true}')
    output = tmp_path / "receipt.json"
    if target == "inside":
        output = study / "new-receipt.json"
    elif target == "source":
        output = original
    elif target == "existing":
        output.write_bytes(b"previous receipt")
    elif target == "symlink":
        output.symlink_to(original)
    else:
        output.hardlink_to(original)
    before = {path: path.read_bytes() for path in [original, output] if path.exists()}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.meihua.audit_meihua_weather_study",
            "--check",
            check,
            "--study",
            str(study),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, result.stderr
    error = json.loads(result.stderr)
    assert error[error_field] is False
    assert "new file outside the immutable study" in error["error"]
    for path, raw in before.items():
        assert path.read_bytes() == raw
    if target == "inside":
        assert not output.exists()


@pytest.mark.parametrize("verified", [False, True])
def test_cli_keeps_failed_solar_gate_in_the_complete_report(
    tmp_path, monkeypatch, verified
):
    from scripts.meihua import audit_meihua_weather_study as cli

    report = {
        "published_solar_context_binding": {
            "evidence_records": 2,
            "counts": {"verified": int(verified), "unresolved": int(not verified)},
            "all_original_records_verified_under_declared_guard": verified,
        }
    }
    monkeypatch.setitem(
        cli.AUDITS, "solar", (lambda study: report, "published_solar_context_verified")
    )
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--check",
            "solar",
            "--study",
            str(tmp_path / "study"),
            "--output",
            str(output),
        ],
    )
    assert cli.main() == (0 if verified else 2)
    assert json.loads(output.read_bytes()) == report


@pytest.mark.parametrize("possible", [False, True])
@pytest.mark.parametrize("required", [False, True])
def test_cli_capacity_requirement_keeps_diagnostic_and_required_gate_separate(
    tmp_path, monkeypatch, possible, required
):
    from scripts.meihua import audit_meihua_weather_study as cli

    report = {
        "original_evidence_records": 2,
        "symbolic_context_domain": {"symbolic_cases": 2880},
        "cohort_scenario_reports": [
            {
                "cohort": "primary_2026_ytd_through_last_complete_month",
                "scenario": "calendar_season_supplied",
                "context_oracle_families": [
                    {
                        "family": "all_current_context_options",
                        "bound": {
                            "cannot_strictly_beat_better_constant_even_with_context_oracle": not possible,
                            "exact_maximum_margin_over_better_constant": (
                                1 if possible else -1
                            ),
                        },
                    }
                ],
            }
        ],
    }
    monkeypatch.setitem(
        cli.AUDITS,
        "context-capacity",
        (lambda study: report, "context_capacity_verified"),
    )
    output = tmp_path / "report.json"
    argv = [
        "audit",
        "--check",
        "context-capacity",
        "--study",
        str(tmp_path / "study"),
        "--output",
        str(output),
    ]
    if required:
        argv.append("--require-primary-potential-superiority")
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == (2 if required and not possible else 0)
    actual = json.loads(output.read_bytes())
    assert actual["cohort_scenario_reports"] == report["cohort_scenario_reports"]
    assert actual["primary_capacity_requirement"] == {
        "required_by_command": required,
        "necessary_condition_only": True,
        "satisfied": possible,
        "predictive_efficacy_established": False,
    }
