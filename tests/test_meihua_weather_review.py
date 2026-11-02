"""Frozen original scores, independent source tokens and synthetic clock controls."""

import ast
import copy
import gzip
import hashlib
import json
import shutil
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_reference_study as strict
from fatebridge.validation import meihua_weather_review as review
from fatebridge.validation.meihua_weather_references import (
    climatology_reference,
    monthly_climatology_profile,
)
from fatebridge.validation.meihua_weather_study import (
    RainObservation,
    _aware,
    parse_hko_rainfall,
)

FOLDER = Path(__file__).parent / "fixtures/meihua_weather_review_v1"
STUDY = FOLDER / "study"
for name, expected in [
    (
        "original-manifest.json",
        "5b38bb09a71bef658050b1429cc5bc3270ba841b2613594a868780ddaf4d45a4",
    ),
    (
        "independent-manifest.json",
        "31ed804a9a36922a2126db206f7899255b1ad4b32c9123cf6f37414d6a1b15c0",
    ),
]:
    raw = (FOLDER / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    for relative, digest in json.loads(raw)["files"].items():
        assert hashlib.sha256((FOLDER / relative).read_bytes()).hexdigest() == digest
assert (
    hashlib.sha256((FOLDER / "climate-input-profile.json").read_bytes()).hexdigest()
    == "0777119f724c70bdf53b575dcf476befd08b26014a572691ed94b6c0fba0bd3d"
)
LEGACY = Path(__file__).parent / "fixtures/meihua_temporal_gates_v1"
assert (
    hashlib.sha256((LEGACY / "manifest.json").read_bytes()).hexdigest()
    == "065cb780830bd1922965ee2c714cbcf771450bbe8563b539302bb975c989b0cf"
)
for n, digest in json.loads((LEGACY / "manifest.json").read_bytes())["files"].items():
    assert hashlib.sha256((LEGACY / n).read_bytes()).hexdigest() == digest
CLOCKS = json.loads((LEGACY / "cases324.json").read_bytes())
CLIMATE = json.loads((FOLDER / "independent-climate-clock81.json").read_bytes())
ALL_CLOCKS = [*CLOCKS, *CLIMATE]
assert len(ALL_CLOCKS) == 405


@pytest.mark.parametrize("case", ALL_CLOCKS, ids=lambda r: r["id"])
def test_legacy_study_clock_uses_the_independent_integer_instant(case):
    expected = datetime(*case["expected_utc_components"], tzinfo=timezone.utc)
    assert _aware(case["label"]).astimezone(timezone.utc) == expected


@pytest.fixture(scope="module")
def synthetic_training():
    observations, publications = {}, {}
    day = date(1991, 1, 1)
    while day < date(2021, 1, 1):
        observations[day] = RainObservation(
            day, "0", "C", "complete_numeric", Decimal(0)
        )
        publications[day] = datetime.combine(
            day + timedelta(days=1), time(), timezone(timedelta(hours=8))
        )
        day += timedelta(days=1)
    assert len(observations) == 10958
    return observations, publications


@pytest.mark.parametrize("case", CLIMATE, ids=lambda r: r["id"])
def test_publication_maximum_and_availability_preserve_true_instants(
    case, synthetic_training
):
    issue = datetime(2021, 2, 28, 12, tzinfo=timezone.utc)
    expected = datetime(*case["expected_utc_components"], tzinfo=timezone.utc)
    first = datetime(
        *case["wall_components"],
        tzinfo=timezone(timedelta(microseconds=case["offset_microseconds"])),
    )
    assert first.astimezone(timezone.utc) == expected
    observations, original_times = synthetic_training
    times = dict(original_times)
    times[date(1991, 3, 1)], times[date(1992, 3, 1)] = first, issue
    profile = monthly_climatology_profile(observations, publication_times=times)
    maximum = profile["months"][2]["latest_declared_publication"]
    # Decode by the two input identities, not by the implementation under test.
    actual_maximum = (
        expected
        if maximum == first.isoformat()
        else issue if maximum == issue.isoformat() else None
    )
    assert actual_maximum == max(expected, issue)
    result = climatology_reference(date(2021, 3, 1), issue, profile)
    assert (result["label_under_declared_availability"] == "dry") == case[
        "expected_publication_available_at_issue"
    ]
    direct = json.loads((FOLDER / "climate-input-profile.json").read_bytes())
    direct["months"][2]["latest_declared_publication"] = case["label"]
    result = climatology_reference(date(2021, 3, 1), issue, direct)
    assert (result["label_under_declared_availability"] == "dry") == case[
        "expected_publication_available_at_issue"
    ]
    assert not result["source_provenance_authenticated"]
    assert not result["classical_rule_or_engine_forecast"]


def test_all13057_source_tokens_flags_and_rainfall_events_match_independent_reference():
    expected = json.loads(
        gzip.decompress((FOLDER / "independent-source-rows13057.json.gz").read_bytes())
    )
    values = parse_hko_rainfall(
        (STUDY / "sources/daily_HKO_RF_ALL.csv").read_bytes(),
        start=date(1991, 1, 1),
        end=date(2026, 10, 1),
    )
    actual = [
        {
            "date": day.isoformat(),
            "source_value": v.raw_value,
            "source_completeness": v.completeness,
            "expected_rain_ge0_1_mm": v.occurred(Decimal("0.1")),
        }
        for day, v in sorted(values.items())
    ]
    assert len(actual) == 13057
    assert actual == expected


def test_reviewed_whole_report_retains_original_negative_scores_and_unknown_vintages():
    expected = json.loads((STUDY / "evaluation.json").read_bytes())
    value = review.audit_reviewed_weather_reference(STUDY)
    assert value["replay"] == expected
    assert value["complete_original_report_equal"]
    assert value["forecast_records_retained"] == 2008
    assert value["unique_target_dates_retained"] == 1004
    assert value["source_rows_compared"] == 13057
    assert value["original_primary_endpoint"]["correct_credit"] == 29
    assert value["original_primary_endpoint"]["better_constant_baseline_credit"] == 158
    assert not value["original_primary_gate_met"]
    assert not value["original_strict_binding_gate_met"]
    assert value["replay"]["input_publication_times_known"] is False
    assert value["new_forecasts"] == value["new_real_outcomes"] == 0
    assert value["independent_model_evaluations"] == 0
    assert not value["real_world_predictive_efficacy_established"]
    assert not value["authority_certified"]


def test_original_strict_entry_still_rejects_instead_of_rebasing_old_hashes():
    with pytest.raises(ValueError, match="Locked reference source or protocol changed"):
        strict.audit_weather_reference_study(STUDY)


def test_reviewed_current_implementation_requires_complete_dependency_proof():
    review.verify_reviewed_implementation(
        review.load_review_binding(), review.PACKAGE_ROOT
    )


def package_copy(tmp_path):
    record = copy.deepcopy(review.load_review_binding())
    for name in record["current_package_files"]:
        source, dest = review.PACKAGE_ROOT / name, tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    return record


@pytest.mark.parametrize(
    "kind",
    [
        "score",
        "trace_constant",
        "training",
        "cohort",
        "clock_math",
        "clock_regex",
        "source_guard",
        "kernel_signature",
        "timestamp_import",
    ],
)
def test_updating_only_file_hash_cannot_bless_unreviewed_semantics(tmp_path, kind):
    record = package_copy(tmp_path)
    name = {
        "score": "validation/meihua_weather_study.py",
        "trace_constant": "validation/meihua_weather_study.py",
        "training": "validation/meihua_weather_references.py",
        "cohort": "validation/meihua_weather_reference_study.py",
        "clock_math": "core/meihua_clock_iso.py",
        "clock_regex": "core/meihua_clock_iso.py",
        "source_guard": "validation/meihua_source_guard.py",
        "kernel_signature": "validation/meihua_weather_reference_study.py",
        "timestamp_import": "validation/meihua_weather_study.py",
    }[kind]
    path = tmp_path / name
    tree = ast.parse(path.read_text())
    if kind == "score":
        function = review._function(tree, "evaluate_weather_cohort")
        node = next(
            n
            for n in ast.walk(function)
            if isinstance(n, ast.AugAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "correct"
        )
        node.value = ast.Constant(1)
    elif kind in {"trace_constant", "training", "clock_regex"}:
        target = {
            "trace_constant": "_TRACE_DEFINITIONS",
            "training": "TRAINING_START",
            "clock_regex": "_TIME",
        }[kind]
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(k, ast.Name) and k.id == target for k in n.targets)
        )
        if kind == "trace_constant":
            node.value = ast.Set(elts=[ast.Constant("unreviewed")])
        elif kind == "training":
            node.value.args[0] = ast.Constant(1992)
        else:
            node.value.args[0] = ast.Constant(".*")
    elif kind == "cohort":
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and type(n.value) is int and n.value == 273
        )
        node.value = 272
    elif kind == "clock_math":
        function = review._function(tree, "_clock_time_and_offset")
        node = next(
            n
            for n in ast.walk(function)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.UnaryOp)
            and isinstance(n.value.op, ast.USub)
        )
        node.value = node.value.operand
    elif kind == "kernel_signature":
        review._function(tree, "_evaluate_reference_material").decorator_list.append(
            ast.Name(id="unreviewed", ctx=ast.Load())
        )
    elif kind == "timestamp_import":
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.ImportFrom)
            and n.module == "fatebridge.core.meihua_clock_iso"
        )
        node.names.append(ast.alias(name="_clock_time_parts", asname="datetime"))
    else:
        review._function(tree, "verify_package_sources").body = [ast.Pass()]
    path.write_text(ast.unparse(ast.fix_missing_locations(tree)) + "\n")
    record["current_package_files"][name] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="AST|Unreviewed"):
        review.verify_reviewed_implementation(record, tmp_path)


def test_original_source_cannot_be_replaced_in_a_review_record(tmp_path):
    record = package_copy(tmp_path)
    record["original_source_texts"]["meihua_weather_study.py"] += "\n# replacement\n"
    with pytest.raises(ValueError, match="original weather source bytes"):
        review.verify_reviewed_implementation(record, tmp_path)


def test_dependencies_cannot_be_dropped_from_the_review(tmp_path):
    record = package_copy(tmp_path)
    del record["current_package_files"]["core/meihua_clock_iso.py"]
    with pytest.raises(ValueError, match="complete reviewed dependency set"):
        review.verify_reviewed_implementation(record, tmp_path)


@pytest.mark.parametrize("kind", ["drop_forecast", "primary_gate", "threshold", "lock"])
def test_original_material_cannot_be_rebound_or_narrowed(tmp_path, kind, monkeypatch):
    shutil.copytree(STUDY, tmp_path / "study")
    base = tmp_path / "study"
    if kind == "drop_forecast":
        path = base / "parent/forecasts.json"
        value = json.loads(path.read_bytes())
        value.pop()
    elif kind == "primary_gate":
        path = base / "evaluation.json"
        value = json.loads(path.read_bytes())
        value["old_primary_endpoint"]["passes_full_cohort_baselines"] = True
    elif kind == "threshold":
        path = base / "plan.json"
        value = json.loads(path.read_bytes())
        value["threshold_mm"] = "0.2"
    else:
        path = base / "reference-lock.json"
        value = json.loads(path.read_bytes())
        value["implementation_files"][
            "meihua_weather_study.py"
        ] = review.load_review_binding()["current_package_files"][
            "validation/meihua_weather_study.py"
        ]
    path.write_text(json.dumps(value))

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed material must be rejected before computation")

    monkeypatch.setattr(strict, "_evaluate_reference_material", forbidden)
    with pytest.raises(ValueError, match="Frozen original study"):
        review.audit_reviewed_weather_reference(base)


def csv_control(first, tail):
    return (
        first
        + "\nDaily Total Rainfall (mm) at the Hong Kong Observatory\n年/Year,月/Month,日/Day,數值/Value,數據完整性/data Completeness\n"
        + tail
    ).encode()


def test_trace_legend_in_metadata_does_not_adjudicate_trace_values():
    raw = csv_control(
        "metadata: Trace means rainfall less than 0.05 mm", "2025,1,1,Trace,C\n"
    )
    row = parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 2))[
        date(2025, 1, 1)
    ]
    assert row.occurred(Decimal("0.1")) is None


def test_conflicting_trace_footer_is_unknown_instead_of_guessed_dry():
    raw = csv_control(
        "metadata",
        "2025,1,1,Trace,C\nTrace means rainfall less than 0.05 mm\nTrace means rainfall less than 0.10 mm\n",
    )
    row = parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 2))[
        date(2025, 1, 1)
    ]
    assert row.occurred(Decimal("0.1")) is None


def test_data_after_a_footer_is_not_silently_merged_into_source_rows():
    raw = csv_control(
        "metadata",
        "2025,1,1,Trace,C\nTrace means rainfall less than 0.05 mm\n2025,1,2,0,C\n",
    )
    with pytest.raises(ValueError, match="cannot follow the source footer"):
        parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 3))
