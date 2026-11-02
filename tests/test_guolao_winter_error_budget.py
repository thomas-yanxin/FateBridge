"""Independent raw-reference replay, source-century behavior and clock guards."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_winter_error_budget as core
from fatebridge.validation import guolao_winter_error_budget as audit
from fatebridge.validation.guolao_modern_solstices import parse_horizons_observer

FIXTURES = Path(__file__).parent / "fixtures/guolao-winter-error-budget-v1"


@pytest.mark.parametrize(
    "n,interval,step",
    [
        (0, None, None),
        (99, "365.2425", "0"),
        (100, "365.2325", "-0.01"),
        (101, "365.2424", "0"),
        (199, "365.2424", "0"),
        (200, "365.2224", "-0.02"),
        (299, "365.2423", "0"),
        (300, "365.2123", "-0.03"),
        (318, "365.2422", "0"),
        (327, "365.2422", "0"),
        (399, "365.2422", "0"),
    ],
)
def test_original_year_parameter_is_not_successive_winter_interval(n, interval, step):
    row = core.century_year_diagnostic(n)
    assert row["successive_winter_interval_days_exact"] == (
        str(F(interval)) if interval else None
    )
    assert row["century_step_vs_previous_rate_days_exact"] == (
        str(F(step)) if step is not None else None
    )
    assert row["source_rule_replaced_with_cumulative_year_sum"] is False
    if n == 318:
        assert F(row["source_zhongji_days_exact"]) == F("116147.0196")
        assert F(row["century_adjustment_from_fixed_base_year_days_exact"]) * 1440 == F(
            "-137.376"
        )


@pytest.mark.parametrize("n", [-1, 400, True, False, 100.0, "100", None])
def test_diagnostic_does_not_silently_extend_or_coerce_cohort(n):
    with pytest.raises(ValueError):
        core.century_year_diagnostic(n)


def _synthetic():
    epoch = F(2188926)
    return dict(
        reference_tt_jd=epoch + 100 * F("365.2425"),
        reference_epoch_tt_jd=epoch,
        reference_local_label_serial=epoch + F(".8") + 100 * F("365.2425") + F(".01"),
        reference_epoch_local_label_serial=epoch + F(".8"),
        clock_hypothesis="local_mean_solar",
    )


def test_four_term_attribution_has_independently_specified_signed_clock_and_year_terms():
    result = core.shoushi_winter_error_budget(100, **_synthetic())
    terms = result["signed_terms_nominal_days_exact"]
    assert {k: F(v) for k, v in terms.items()} == {
        "epoch_clock_label_offset": F("-.74"),
        "source_whole_century_adjustment": F("-.01"),
        "fixed_base_year_vs_TT_interval": F(),
        "TT_interval_vs_local_clock_label_interval": F("-.01"),
    }
    assert F(result["source_minus_reference_nominal_minutes_exact"]) == F("-1094.4")
    assert result["clock_label_days_equated_to_uniform_TT_days"] is False
    assert result["physical_accuracy_or_prediction_certified"] is False


@pytest.mark.parametrize(
    "key,value,error",
    [
        ("reference_tt_jd", 1.0, TypeError),
        ("reference_epoch_tt_jd", True, TypeError),
        ("clock_hypothesis", "UTC", ValueError),
        ("reference_tt_jd", F(2451545), ValueError),
        ("reference_epoch_tt_jd", F(2451545), ValueError),
        ("reference_local_label_serial", F(1), ValueError),
        ("reference_epoch_local_label_serial", F(1), ValueError),
    ],
)
def test_mixed_scales_wrong_years_and_implicit_inputs_rejected(key, value, error):
    arguments = _synthetic()
    arguments[key] = value
    with pytest.raises(error):
        core.shoushi_winter_error_budget(100, **arguments)


def test_zero_elapsed_years_cannot_hide_a_different_reference_epoch():
    args = _synthetic()
    args["reference_tt_jd"] = args["reference_epoch_tt_jd"] + F(".001")
    args["reference_local_label_serial"] = args["reference_epoch_local_label_serial"]
    with pytest.raises(ValueError, match="距算0"):
        core.shoushi_winter_error_budget(0, **args)


def test_all_raw_requests_replay_the_complete_independent_reference_search():
    source, _ = audit.load_reference()
    manifest = source["raw_reference_file_hashes"]
    for name, wanted in manifest.items():
        assert (
            hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == wanted
        ), name
    responses = {}
    request_count = 0
    for query in sorted(FIXTURES.glob("*.query.json")):
        q = json.loads(query.read_bytes())
        name = query.name.removesuffix(".query.json")
        stamps = [F(v) for v in q["requested_tt_jds_exact"]]
        clock = name.startswith("historical-clocks-")
        assert len(stamps) == 50
        assert q["plan_sha256"] == source["plan_sha256"]
        result = parse_horizons_observer(
            (FIXTURES / (name + ".response.json")).read_bytes(), stamps, clock=clock
        )
        group = name.split("-part")[0]
        responses.setdefault(group, {}).update(
            {tt: row for tt, row in zip(stamps, result["rows"])}
        )
        request_count += 1
    assert request_count == 192
    assert len(responses["coarse"]) == 2400
    for case in source["cases"]:
        lo = F(case["coarse_lower_tt_jd_exact"])
        hi = lo + 1
        assert (
            F(responses["coarse"][lo]["ObsEcLon"])
            < 270
            <= F(responses["coarse"][hi]["ObsEcLon"])
        )
        for round_number in range(1, 18):
            mid = (lo + hi) / 2
            row = responses[f"refine{round_number:02d}"][mid]
            if F(row["ObsEcLon"]) < 270:
                lo = mid
            else:
                hi = mid
        assert str(lo) == case["lower_tt_jd_exact"]
        assert str(hi) == case["upper_tt_jd_exact"]
        stamp = (lo + hi) / 2
        assert responses["historical-clocks"][stamp] == {
            k: v for k, v in case["clock"].items() if k != "tt_jd_requested_exact"
        }


@pytest.mark.parametrize(
    "mutation",
    ["omit_year", "reorder", "rate", "width", "sign", "clock_time", "fitted"],
)
def test_reference_changes_fail_before_comparison(tmp_path, monkeypatch, mutation):
    source = json.loads(audit.DATA.read_bytes())
    if mutation == "omit_year":
        source["cases"].pop(100)
    elif mutation == "reorder":
        source["cases"][99], source["cases"][100] = (
            source["cases"][100],
            source["cases"][99],
        )
    elif mutation == "rate":
        source["plan"]["source_base_year_exact"] = "365.2422"
    elif mutation == "width":
        source["plan"]["reference_bracket_width_seconds_exact"] = "1"
    elif mutation == "sign":
        source["cases"][100]["lower_longitude"] = "270.1"
    elif mutation == "clock_time":
        source["cases"][100]["clock"]["tt_jd_requested_exact"] = "2451545"
    else:
        source["plan"]["fit_epoch_year_rate_site_deltaT_or_frame"] = True
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(source))
    monkeypatch.setattr(audit, "DATA", path)
    # A future explicitly versioned reference must still satisfy semantic guards;
    # these checks must not pass solely because the release fingerprint differs.
    monkeypatch.setattr(
        audit, "REFERENCE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError):
        audit.load_reference()


def test_unversioned_reference_edit_is_rejected_by_frozen_release_hash(
    tmp_path, monkeypatch
):
    path = tmp_path / "changed.json"
    path.write_bytes(audit.DATA.read_bytes() + b"\n")
    monkeypatch.setattr(audit, "DATA", path)
    with pytest.raises(ValueError, match="哈希"):
        audit.load_reference()


def test_complete400_year_audit_keeps_all800_clock_hypotheses_and_unrounded_native_roots():
    result = audit.audit_winter_error_budget()
    assert result["case_count"] == 400
    assert result["historical_through1644_count"] == 365
    assert result["post1644_extrapolation_count"] == 35
    assert result["source_epoch_or_rate_fitted"] is False
    assert result["clock_hypothesis_selected_by_smallest_error"] is False
    for i, row in enumerate(result["rows"]):
        assert row["case"]["elapsed_years"] == i
        for hypothesis in core.CLOCK_HYPOTHESES:
            budget = row["budgets"][hypothesis]
            assert budget["algebraic_closure_error_nominal_days_exact"] == "0"
            assert budget["source_midnight_calibrated"] is False
        native = row["native_moshier_TT"]
        assert F(native["bracket_width_seconds_exact"]) < F(1, 1000)
        lo, hi = map(F, native["bracket_residual_degrees_exact"])
        assert lo <= 0 <= hi
    # A broad diagnostic must retain large residuals; algebraic closure does not
    # turn them into passing calendar accuracy or successful real predictions.
    assert (
        abs(
            F(
                result["summaries"]["local_apparent_solar"][
                    "largest_absolute_nominal_minutes"
                ]["signed_exact"]
            )
        )
        > 240
    )
    assert result["real_world_predictive_efficacy_established"] is False


@pytest.mark.parametrize("n", ["-1", "400", "100.0"])
def test_cli_bad_year_does_not_emit_a_success_payload(monkeypatch, capsys, n):
    script = Path(__file__).parents[1] / "scripts/audit_guolao_winter_error_budget.py"
    monkeypatch.setattr(sys, "argv", [str(script), "year", "--elapsed-years", n])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script))["main"]()
    assert error.value.code == 2
    assert not capsys.readouterr().out
