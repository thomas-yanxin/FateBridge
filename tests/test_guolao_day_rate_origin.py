"""A printed empty rate and its explicit lookup zero are different facts."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_cumulative_table as literal
from fatebridge.core import guolao_day_rate as rate
from fatebridge.validation.guolao_day_rate_origin import compare_origin_schema_outputs

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-day-rate-origin-v1"


def test_original_initial_cell_is_empty_and_inspection_is_pinned():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    for artifact in reference["artifacts"]:
        contents = (FIXTURE / artifact["path"]).read_bytes()
        assert len(contents) == artifact["bytes"]
        assert hashlib.sha256(contents).hexdigest() == artifact["sha256"]
    assert reference["observed_day_rate_mark"] == "空"
    assert reference["numeric_printed_day_rate"] is None
    assert reference["effective_lookup_day_rate_days"] == "0.0000"
    assert not reference["independent_second_collator"]


@pytest.mark.parametrize("anomaly", ["0", ".041", "13.8183", "27.5546", "-27.5136"])
def test_raw_empty_is_never_presented_as_a_printed_zero(anomaly):
    result = rate.gujin45_day_rate(F(anomaly))
    assert result["whole_limit_index"] == 0
    assert result["selected_printed_day_rate_days"] is None
    assert result["selected_effective_day_rate_days"] == "0.0000"
    assert result["selected_day_rate_source_mark"] == "空"
    assert result["empty_day_rate_origin_interpreted_as_zero"]
    assert result["day_rate_origin_policy"] == rate.ORIGIN_POLICY
    assert (
        result["day_rate_output_schema_version"] == "gujin45-day-rate-source-values-v2"
    )
    assert result["status"] == "origin_zero_interpretation_bracket"
    assert result["next_printed_day_rate_days"] == "0.0820"


@pytest.mark.parametrize(
    "method", [rate.gujin_day_rate_lunar, literal.gujin_literal_lunar]
)
@pytest.mark.parametrize(
    "anomaly,angle", [(".041", "-443263/8000000"), ("13.8183", "443263/8000000")]
)
def test_both_interpolations_use_effective_zero_and_keep_analytic_half_increment(
    method, anomaly, angle
):
    result = method(F(anomaly))
    assert result["selected_printed_day_rate_days"] is None
    assert result["selected_effective_day_rate_days"] == "0.0000"
    assert F(result["signed_correction_ancient_du_exact"]) == F(angle)
    assert result["interpolation_fraction_exact"] == "1/2"
    if method is literal.gujin_literal_lunar:
        assert result["source_selected_cumulative_ancient_du"] is None
        assert result["empty_cumulative_origin_interpreted_as_zero"]


@pytest.mark.parametrize(
    "anomaly,index", [(".082", 1), ("9.5129", 116), ("13.7773", 168)]
)
def test_numeric_source_cells_and_endpoint_are_not_relabelled_as_empty(anomaly, index):
    result = rate.gujin45_day_rate(F(anomaly))
    assert result["whole_limit_index"] == index
    assert result["selected_day_rate_source_mark"] == "numeric"
    assert (
        result["selected_printed_day_rate_days"]
        == result["selected_effective_day_rate_days"]
    )
    assert not result["empty_day_rate_origin_interpreted_as_zero"]


def test_unresolved_rate_is_not_filled_by_origin_policy():
    result = rate.gujin45_day_rate(F("7.285"))
    assert result["whole_limit_index"] is None
    assert result["selected_printed_day_rate_days"] is None
    assert result["selected_effective_day_rate_days"] is None
    assert result["selected_day_rate_source_mark"] is None
    assert not result["empty_day_rate_origin_interpreted_as_zero"]
    assert result["status"] == "ambiguous_literal_rate_not_repaired"


@pytest.mark.parametrize(
    "module,method",
    [
        (rate, rate.gujin_day_rate_conjunction),
        (literal, literal.gujin_literal_conjunction),
    ],
)
@pytest.mark.parametrize("anomaly", [".041", "13.8183"])
def test_conjunction_contains_raw_empty_and_real_velocity_without_numeric_failure(
    monkeypatch, module, method, anomaly
):
    context = module.source_conjunction(F(), 0, profile_id=module.GUJIN_COMPONENTS)
    context["lunar"]["anomaly_phase_days_exact"] = str(F(anomaly))
    monkeypatch.setattr(module, "source_conjunction", lambda *a, **kw: context)
    result = method(F(), 0)
    lunar = result["angular_components"]["lunar"]
    assert lunar["selected_printed_day_rate_days"] is None
    assert lunar["selected_effective_day_rate_days"] == "0.0000"
    assert result["lunar_velocity"]["whole_limit_index"] == 0
    assert result["lunar_velocity"]["printed_velocity_ancient_du_per_limit"] is not None
    expected_lunar = F(-443263 if lunar["phase"] == "疾" else 443263, 8000000)
    assert F(result["time_correction_days_exact"]) == (
        F(".082")
        * (F(context["solar"]["signed_correction_ancient_du_exact"]) + expected_lunar)
        / F(result["lunar_velocity"]["printed_velocity_ancient_du_per_limit"])
    )


@pytest.mark.parametrize(
    "index,flag", [(0, False), (0, None), (0, 1), (1, True), (1, 0)]
)
def test_empty_source_flag_cannot_be_missing_numeric_or_moved_to_another_cell(
    tmp_path, monkeypatch, index, flag
):
    data = json.loads(rate.DATA.read_text())
    data["rows"][index]["printed_empty_origin"] = flag
    path = tmp_path / "bad-table.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(rate, "DATA", path)
    with pytest.raises(ValueError, match="原刊日率空格"):
        rate.gujin45_day_rate(F(".041"))


def test_audit_counts_empty_position_separately_from_numeric_source_cells():
    result = rate.audit_day_rate_table()
    assert result["model_id"] == "gujin_literal_day_rate_table_audit_v2"
    assert "literal_rate_count" not in result
    assert result["rate_position_count"] == result["effective_lookup_rate_count"] == 169
    assert (
        result["printed_numeric_rate_count"]
        == result["equal_step_diagnostic_numeric_compared_count"]
        == 168
    )
    assert result["printed_empty_rate_indices"] == [0]
    assert [r["limit_index"] for r in result["equal_step_diagnostic_conflicts"]] == [
        90,
        154,
        166,
    ]
    assert result["nonzero_boundary_jumps"] == 19
    cumulative = literal.audit_gujin45_cumulative_table()
    assert cumulative["day_rate_origin_policy"] == rate.ORIGIN_POLICY
    assert cumulative["empty_day_rate_origin_interpreted_as_zero_at_boundary1"]
    assert cumulative["nonzero_boundary_jumps"] == 21


@pytest.mark.parametrize(
    "script", ["audit_guolao_day_rate.py", "audit_guolao_cumulative.py"]
)
def test_both_cli_outputs_distinguish_printed_empty_from_calculation_zero(
    monkeypatch, capsys, script
):
    monkeypatch.setattr(sys, "argv", [script, "--anomaly-days", ".041"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / "scripts" / script), run_name="__main__")
    assert exited.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["selected_printed_day_rate_days"] is None
    assert result["selected_effective_day_rate_days"] == "0.0000"
    assert result["empty_day_rate_origin_interpreted_as_zero"]


def _prior_lookup_stdout():
    return (FIXTURE / "before-origin-lookup.json").read_text()


def test_strict_migration_verifier_accepts_actual_old_lookup_and_no_other_changes():
    after = json.dumps(rate.gujin45_day_rate(F(".041")))
    result = compare_origin_schema_outputs(
        {"origin": _prior_lookup_stdout()}, {"origin": after}
    )
    assert result["prior_cases"] == result["prior_cases_with_changed_stdout"] == 1
    assert result["prior_cases_dropped"] == 0
    assert result["origin_empty_components_now_explicit"] == 1
    assert result["all_previous_calculation_values_and_undeclared_fields_equal"]
    assert not result["complete_calendar_accuracy_demonstrated"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("within_half_days_exact", "42/1000"),
        ("selected_effective_day_rate_days", "0.0820"),
        ("selected_printed_day_rate_days", "0.0000"),
        ("selected_day_rate_source_mark", "numeric"),
        ("empty_day_rate_origin_interpreted_as_zero", False),
        ("status", "unique_literal_rate_bracket"),
        ("source_data_sha256", "changed"),
        ("unexpected_field", 1),
    ],
)
def test_migration_verifier_rejects_calculation_source_and_undeclared_changes(
    field, value
):
    after = rate.gujin45_day_rate(F(".041"))
    after[field] = value
    with pytest.raises(ValueError):
        compare_origin_schema_outputs(
            {"origin": _prior_lookup_stdout()}, {"origin": json.dumps(after)}
        )


def test_migration_verifier_preserves_every_prior_case_and_labels_added_cases():
    before = {"origin": _prior_lookup_stdout()}
    with pytest.raises(ValueError, match="旧命令案例被删除"):
        compare_origin_schema_outputs(before, {})
    after = {"origin": json.dumps(rate.gujin45_day_rate(F(".041"))), "new-case": "{}"}
    result = compare_origin_schema_outputs(before, after)
    assert result["prior_cases"] == 1
    assert result["additional_cases_without_prior_baseline"] == ["new-case"]


def test_migration_verifier_accepts_actual_audit_count_changes_and_rejects_boolean_index():
    before = {
        "rate-audit": (FIXTURE / "before-rate-table-audit.json").read_text(),
        "cumulative-audit": (
            FIXTURE / "before-cumulative-table-audit.json"
        ).read_text(),
        "nonorigin-lunar": (FIXTURE / "before-nonorigin-lunar.json").read_text(),
    }
    result = rate.audit_day_rate_table()
    after = {
        "rate-audit": json.dumps(result),
        "cumulative-audit": json.dumps(literal.audit_gujin45_cumulative_table()),
        "nonorigin-lunar": json.dumps(rate.gujin_day_rate_lunar(F("23.310758"))),
    }
    assert compare_origin_schema_outputs(before, after)["prior_cases"] == 3
    result["printed_empty_rate_indices"] = [False]
    after["rate-audit"] = json.dumps(result)
    with pytest.raises(ValueError, match="输出类型改变"):
        compare_origin_schema_outputs(before, after)


def test_migration_cli_checks_complete_stdout_mapping(tmp_path, monkeypatch, capsys):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps({"origin": _prior_lookup_stdout()}))
    after.write_text(
        json.dumps({"origin": json.dumps(rate.gujin45_day_rate(F(".041")))})
    )
    script = ROOT / "scripts/audit_guolao_day_rate_origin.py"
    monkeypatch.setattr(
        sys, "argv", [str(script), "--before", str(before), "--after", str(after)]
    )
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(script), run_name="__main__")
    assert exited.value.code == 0
    assert json.loads(capsys.readouterr().out)["prior_cases"] == 1


@pytest.mark.parametrize("bad", [[], {"origin": None}])
def test_migration_mapping_type_errors_fail_with_an_input_error(bad):
    with pytest.raises(ValueError, match="完整stdout字符串"):
        compare_origin_schema_outputs(bad, {})
