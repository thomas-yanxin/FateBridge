"""Full table retention, exact interpolation and positive-weight uncertainty."""

import copy
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import witte1925_table as actual
from fatebridge.core.output_midpoints import Witte1925SourceTable
from fatebridge.utils.errors import handle_calculation_error
from scripts import replay_witte1925_table as reference


def test_entire_transcription_and_common_year_extension_are_retained():
    raw = actual.RECORD.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == reference.RECORD_SHA256
    record = actual.load_table()
    rows = actual.normalized_rows(record)
    assert len(rows) == 38
    assert sum(len(r["raw_age_cells"]) for r in rows) == 342
    for index, row in enumerate(rows):
        assert row["raw_age_cells"] == record["rows"][index]["raw_age_cells"]
        date = datetime(2001, 1, 1) + timedelta(days=index * 10)
        expected = date.strftime("%m-%d") + ("+1" if date.year == 2002 else "")
        assert row["printed_date"] == expected
    assert rows[0]["raw_until_january_zero_arcminutes"] == 61
    assert rows[-1]["raw_until_january_zero_arcminutes"] == 1
    assert rows[-1]["printed_date"] == "01-06+1"


def test_every_source_node_including_all_unresolved_nodes_is_checked():
    record = actual.load_table()
    expected = reference.reference_cells(record)
    states = []
    for (row, age), value in expected.items():
        result = actual.interpolate(record, row * 10, age)
        if value is None:
            assert result["status"] == "underdetermined"
            assert result["arcminutes"] is result["arcminutes_fraction"] is None
        else:
            assert result["status"] == "computed"
            assert Fraction(*result["arcminutes_fraction"]) == value
        states.append(result["status"])
    assert len(states) == 342
    assert states.count("computed") == 318
    assert states.count("underdetermined") == 24
    assert {(r, a) for (r, a), value in expected.items() if value is None} == {
        (r, 20) for r in range(6, 30)
    }


def test_all_predeclared_half_step_axis_probes_use_independent_lagrange_reference():
    record = actual.load_table()
    count, unknown = 0, 0
    for day in range(0, 371, 5):
        for age in range(10, 91, 5):
            expected = reference.reference_interpolate(
                record, Fraction(day), Fraction(age)
            )
            result = actual.interpolate(record, day, age)
            weights = [Fraction(*r["weight_fraction"]) for r in result["corners"]]
            assert sum(weights) == 1 and all(w > 0 for w in weights)
            if expected is None:
                unknown += 1
                assert (
                    result["status"] == "underdetermined"
                    and result["arcminutes_fraction"] is None
                )
            else:
                assert result["status"] == "computed"
                assert Fraction(*result["arcminutes_fraction"]) == expected
            count += 1
    assert count == 1275 and unknown > 0


@pytest.mark.parametrize(
    "day,age,status",
    [
        (50, 20, "computed"),
        (math.nextafter(50, math.inf), 20, "underdetermined"),
        (300, 20, "computed"),
        (math.nextafter(300, -math.inf), 20, "underdetermined"),
        (100, 10, "computed"),
        (100, math.nextafter(10, math.inf), "underdetermined"),
        (100, 30, "computed"),
        (100, math.nextafter(30, -math.inf), "underdetermined"),
    ],
)
def test_zero_weight_unknowns_do_not_contaminate_or_disappear_after_any_positive_weight(
    day, age, status
):
    result = actual.interpolate(actual.load_table(), day, age)
    assert result["status"] == status
    assert all(Fraction(*r["weight_fraction"]) > 0 for r in result["corners"])


def test_both_axis_endpoints_and_extension_use_the_printed_rows():
    r = actual.load_table()
    assert actual.interpolate(r, 0, 10)["arcminutes"] == 611
    assert actual.interpolate(r, 370, 90)["arcminutes"] == 5430
    assert actual.interpolate(r, Fraction(26), Fraction(54))["arcminutes_fraction"] == [
        81426,
        25,
    ]


def test_printed_stages_are_not_replaced_by_a_more_precise_hypothetical_policy():
    result = actual.source_table_analysis()
    Witte1925SourceTable.model_validate(result)
    assert result["coverage"]["all_printed_raw_cells_retained"] is True
    assert result["coverage"]["all_degrees_resolved"] is False
    worked = result["worked_example"]
    assert worked["printed_components_arcminutes"] == [56, 3257, 34]
    assert (
        worked["literal_components_sum_arcminutes"]
        == worked["printed_total_arcminutes"]
        == 3347
    )
    assert worked["literal_arithmetic_matches_print"] is True
    assert worked["hypothetical_total_fraction"] == [133917, 40]
    assert worked["printed_minus_hypothetical_total_arcminutes"] == -0.925
    assert worked["hypothetical_unrounded_policy_adopted_as_original"] is False
    assert result["full_original_method_accepted"] is False
    assert result["computed_for_current_chart"] is False
    assert result["real_world_efficacy"] == "not_tested"
    independent = reference.replay(actual.load_table())
    assert independent["all_table_degrees_resolved"] is False
    assert independent["worked_example"]["hypothetical_unrounded_total_fraction"] == [
        133917,
        40,
    ]


@pytest.mark.parametrize(
    "day,age",
    [
        (-1, 50),
        (371, 50),
        (1, 9),
        (1, 91),
        (True, 50),
        (1, True),
        ("26", 50),
        (1, "54"),
        (math.nan, 50),
        (1, math.inf),
    ],
)
def test_numeric_probe_rejects_out_of_scope_or_coerced_axes(day, age):
    with pytest.raises(ValueError):
        actual.interpolate(actual.load_table(), day, age)


def test_modified_source_never_fills_the_missing_degree_by_fitting(
    tmp_path, monkeypatch
):
    record = actual.load_table()
    record["rows"][6]["raw_age_cells"][1] = "19 57"
    changed = tmp_path / "fitted.json"
    changed.write_text(json.dumps(record))
    monkeypatch.setattr(actual, "RECORD", changed)
    with pytest.raises(RuntimeError, match="checksum") as failure:
        actual.load_table()
    assert handle_calculation_error(failure.value, "原表来源")["status_code"] == 500
    target = tmp_path / "unearned.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(reference.__file__)),
            "--source-record",
            str(changed),
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0 and not target.exists()


def test_cli_retains_unresolved_source_as_failure_and_does_not_overwrite(tmp_path):
    target = tmp_path / "source.json"
    command = [
        sys.executable,
        str(Path(reference.__file__)),
        "--output",
        str(target),
        "--day-offset",
        "26",
        "--age-years",
        "54",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(target.read_text())
    assert report["all_table_degrees_resolved"] is False
    assert len(report["unresolved_age_cells"]) == 24
    assert report["numeric_probe"]["arcminutes_fraction"] == [81426, 25]
    raw = target.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert target.read_bytes() == raw


def test_public_typed_unknowns_cannot_be_replaced_with_text_or_false_counts():
    result = actual.source_table_analysis()
    bad = copy.deepcopy(result)
    bad["rows"][6]["normalized_arcminutes"][1] = "unknown"
    with pytest.raises(ValidationError):
        Witte1925SourceTable.model_validate(bad)
    bad = copy.deepcopy(result)
    bad["coverage"]["unresolved_age_cells"] = "24"
    with pytest.raises(ValidationError):
        Witte1925SourceTable.model_validate(bad)
