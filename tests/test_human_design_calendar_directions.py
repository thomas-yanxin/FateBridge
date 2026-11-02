"""All original rows, full-direction error and source/frame rejection."""

import ast
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import check_human_design_calendar_directions as check
from scripts import gen_human_design_calendar_directions as gen

BASE = gen.ROOT / "docs/validation/human-design-calendar-directions-v1"
E = BASE / "evidence"


@pytest.fixture(scope="module")
def materials():
    old_plan, reference = check.reference()
    production = gen.read(E / "production-final.json.gz")
    expected = gen.read(E / "comparison-corrected.json.gz")
    return old_plan, reference, production, expected


def test_all_original24k_independent_source_facts_and_both_epochs_preserved(materials):
    plan, reference, _, _ = materials
    declared, original_plan, original = gen.inputs()
    assert declared["expected_total_positions"] == 48000
    assert (
        reference["epoch_count"] == 2400
        and reference["physical_direction_count"] == 24000
    )
    assert reference["package_source_before"] == reference["package_source_after"]
    for epoch, (pair, side) in zip(
        reference["rows"],
        [(p, s) for p in original["pairs"] for s in ("personality", "design")],
        strict=True,
    ):
        assert (epoch["label"], epoch["side"], epoch["jd_tt"]) == (
            pair["label"],
            side,
            pair[side]["jd_tt"],
        )
        for body in original_plan["bodies"]:
            assert (
                epoch["directions"][body]["original_fact"]
                == pair[side]["positions"][body]
            )
            fact = epoch["directions"][body]["original_fact"]
            recovered = check.mv(
                epoch["icrf_to_original_ecliptic_rotation"],
                epoch["directions"][body]["icrf_unit_vector"],
            )
            assert (
                check.angle(
                    check.direction(fact["longitude"], fact["latitude"]), recovered
                )
                < 6e-10
            )
            assert (
                check.angle(
                    epoch["directions"][body]["icrf_unit_vector"],
                    epoch["directions"][body]["icrf_unit_vector"],
                )
                == 0
            )


def test_full48k_frozen_comparison_keeps_all_old_failures_and_27_exposed_directions(
    materials, monkeypatch
):
    from fatebridge.core.astro import runtime

    def forbidden(*args, **kwargs):
        raise AssertionError("Native replay in frozen comparison")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    plan, reference, production, expected = materials
    current = check.compare(production, reference, plan)
    assert current == expected
    for name, counts in (
        ("selected", (1, 1, 1)),
        ("moshier_diagnostic", (2238, 2263, 2265)),
    ):
        result = current["backends"][name]
        assert result["position_count"] == 24000 and result["not_assessed"] == 0
        assert (
            result["original_longitude_failure_count"],
            result["icrf_angular_failure_count"],
            24000 - result["accepted_count"],
        ) == counts
        assert result["old_computed_longitude_difference_count"] == 0
        assert result["default_or_icrf_backend_unaccepted_count"] == 0
        assert result["default_icrf_closure_unaccepted_count"] == 0
        assert result["maximum_default_icrf_direction_closure_arcseconds"] < 6e-10
    added = current["backends"]["moshier_diagnostic"][
        "new_full_direction_failures_previously_longitude_accepted"
    ]
    assert len(added) == 27 and Counter(r["body"] for r in added) == {
        "Moon": 24,
        "Neptune": 3,
    }
    assert all(
        r["original_longitude_row"]["accepted"] and not r["accepted"] for r in added
    )
    assert (
        sum(
            not r["original_longitude_row"]["accepted"]
            and r["icrf_angular_within2arcseconds"]
            for r in current["backends"]["moshier_diagnostic"]["rows"]
        )
        == 2
    )
    assert current["status"] == "disagreements_remain"


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "reorder", "tt", "side", "body", "backend"]
)
def test_no_lost_or_rebound_original_position_cohort(materials, fault):
    plan, reference, source, _ = materials
    production = {**source, "backends": {**source["backends"]}}
    selected = {**source["backends"]["selected"]}
    rows = list(selected["rows"])
    if fault == "missing":
        rows.pop()
    if fault == "duplicate":
        rows[-1] = rows[0]
    if fault == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    if fault in {"tt", "side", "body"}:
        rows[0] = dict(rows[0])
        if fault == "tt":
            rows[0]["jd_tt"] += 1
        if fault == "side":
            rows[0]["side"] = "design"
        if fault == "body":
            rows[0]["body"] = "NorthNode"
    selected["rows"] = rows
    if fault == "backend":
        selected["requested_backend"] = "moshier"
    production["backends"]["selected"] = selected
    with pytest.raises(ValueError):
        check.compare(production, reference, plan)


@pytest.mark.parametrize(
    "fault",
    [
        "raw_longitude",
        "nan_default",
        "nan_icrf",
        "missing_icrf",
        "default_error",
        "icrf_flags",
        "default_flags",
        "distance",
        "matrix",
        "latitude_closure",
    ],
)
def test_unavailable_or_detached_row_never_becomes_a_match(materials, fault):
    _, reference, production, expected = materials
    row = deepcopy(production["backends"]["selected"]["rows"][0])
    legacy = expected["backends"]["selected"]["rows"][0]["original_longitude_row"]
    if fault == "raw_longitude":
        row["default_raw"]["native_coordinates"][0] += 1
    if fault == "nan_default":
        row["default_raw"]["native_coordinates"][1] = "nan"
    if fault == "nan_icrf":
        row["icrf_native_coordinates"][1] = "nan"
    if fault == "missing_icrf":
        row["icrf_native_coordinates"] = None
    if fault == "default_error":
        row["default_batch_error"] = {"type": "RuntimeError", "message": "unavailable"}
    if fault == "icrf_flags":
        row["icrf_return_flags"] = 133476
    if fault == "default_flags":
        row["default_raw"]["return_flags"] = 260
    if fault == "distance":
        row["default_raw"]["native_coordinates"][2] = 0
    if fault == "matrix":
        row["icrf_to_default_frame"]["matrix"][0][0] = 0
    if fault == "latitude_closure":
        row["default_raw"]["native_coordinates"][1] += 1
    result = check.compare_row(row, reference["rows"][0], legacy, 2)
    assert result["accepted"] is False
    assert result["original_longitude_row"] == legacy


def test_an_old_failure_is_not_passed_when_the_new_direction_happens_to_agree(
    materials,
):
    _, reference, production, expected = materials
    rows = expected["backends"]["moshier_diagnostic"]["rows"]
    index = next(
        i
        for i, r in enumerate(rows)
        if not r["original_longitude_row"]["accepted"]
        and r["icrf_angular_within2arcseconds"]
    )
    row = production["backends"]["moshier_diagnostic"]["rows"][index]
    epoch = reference["rows"][index // 10]
    result = check.compare_row(row, epoch, rows[index]["original_longitude_row"], 4)
    assert result["icrf_angular_within2arcseconds"] is True
    assert result["accepted"] is False


def test_reference_generator_capture_source_and_original_independence_are_retained():
    original = (
        BASE / "before-source/scripts/gen_human_design_calendar_directions.py"
    ).read_bytes()
    current = Path(gen.__file__).read_bytes()
    guarded = (BASE / "before-source/scripts/gen-directions-guarded-v1.py").read_bytes()
    # Package-origin guard has no numeric branch; its prior actual source stays pinned.
    guard = b'        if module.__file__ is None:\n            raise ValueError("Reference package has no readable origin: " + name)\n'
    assert guard in guarded and guarded.replace(guard, b"") == original
    value = gen.read(E / "icrf-reference.json.gz")
    assert value["generator_sha256"] == hashlib.sha256(original).hexdigest()
    corrected = gen.read(E / "icrf-reference-exact-inverse.json.gz")
    assert corrected["generator_sha256"] == hashlib.sha256(current).hexdigest()
    assert (
        corrected["inverse_policy"]
        == "exact_rational_inverse_of_stored_binary64_matrix_times_exact_binary64_vector_then_one_final_rounding"
    )
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        and any(s in ast.unparse(n) for s in ("fatebridge", "swisseph"))
        for n in ast.walk(ast.parse(current))
    )


def test_full_direction_does_not_collapse_to_longitude_only():
    assert check.angle(
        check.direction(17, 0), check.direction(17, 3 / 3600)
    ) == pytest.approx(3, abs=1e-12)
    with pytest.raises(ValueError):
        check.angle([0, 0, 0], [1, 0, 0])


def test_recovered_reference_matches_the_separately_captured_direct_icrf_anchor(
    materials,
):
    _, reference, _, _ = materials
    center = next(
        row
        for row in reference["rows"]
        if row["label"] == "2236-03-01T12:00:00 TT" and row["side"] == "design"
    )
    direct = gen.read(
        gen.ROOT
        / "docs/validation/human-design-icrf-horizons-v1/evidence/de440-icrf-reference.json"
    )
    body = next(r for r in direct["records"] if r["body"] == "Uranus")
    old = next(r for r in body["rows"] if r["offset_days"] == 0)
    assert old["jd_tt"] == center["jd_tt"]
    assert (
        check.angle(
            check.direction(
                old["icrf_apparent"]["right_ascension"],
                old["icrf_apparent"]["declination"],
            ),
            center["directions"]["Uranus"]["icrf_unit_vector"],
        )
        < 1e-8
    )
