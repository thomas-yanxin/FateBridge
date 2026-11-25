"""Preserved selected cycles, conditional origins and correct-hash forgeries."""

from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design.human_design_cycle_origins import (
    comparison_rows,
    origin_body_row,
)
from fatebridge.core.human_design.human_design_cycles import (
    ROOT_SECONDS,
    derive_body_contacts,
)
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.support.reference_data import read, sha
from tests.support.transports import AS_OF, SPECS, three_surfaces
from validation.human_design import verify_human_design_reading
from validation.human_design_clocks import verify_clock_records
from validation.human_design_cycle_origins import verify_cycle_origin_comparison
from validation.human_design_cycles import verify_cycle_context

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


ROOT = Path(__file__).resolve().parents[2]
E = ROOT / "tests/data/human_design/cycle_origins"
ANALYTIC_SHA = "5b78b73a17ae3cb177d853696d58babc67a6da4b0fd9ae9f47e7e7bbf6ed8f4e"


def frac(pair):
    return Fraction(int(pair[0]), int(pair[1]))


@pytest.fixture(scope="module")
def analytic():
    p = E / "independent-analytic-controls.json"
    assert sha(p) == ANALYTIC_SHA
    return read(p)


def analytical_reader(case, base):
    knots = [(frac(x), frac(y)) for x, y in case["knots"]]

    def evaluate(t):
        u = Fraction(t) - base
        for index, ((x, a), (y, b)) in enumerate(zip(knots, knots[1:])):
            if x <= u <= y:
                rate = (b - a) / (y - x)
                value = a + (u - x) * rate
                if u == y and index + 2 < len(knots):
                    z, c = knots[index + 2]
                    if rate * ((c - b) / (z - y)) < 0:
                        rate = Fraction(0)
                    else:
                        pass
                else:
                    pass
                return [t, float(value % 360), float(rate), 258]
            else:
                pass
        raise AssertionError("Unregistered analytic evaluation outside source curve")

    return evaluate


@pytest.mark.parametrize("index", range(9))
def test_both_origins_match_pre_edit_independent_rational_curves(
    analytic, index
) -> None:
    case = analytic["rows"][index]
    for side, expected in case["expected"].items():
        epoch = float(frac(expected["origin_jd_tt"]))
        result = derive_body_contacts(
            case["body"], epoch, analytical_reader(case, frac(analytic["base_jd_tt"]))
        )
        assert result["status"] == "sampled_search_completed"
        roots = [frac(x) for x in expected["root_jd_tt"]]
        assert len(result["contacts"]) == len(roots)
        for actual, wanted in zip(result["contacts"], roots, strict=True):
            assert abs(Fraction(actual["jd_tt"]) - wanted) * 86400 <= Fraction(
                ROOT_SECONDS
            )
        converted = origin_body_row(result)
        assert converted["origin_jd_tt"] == epoch
        assert "birth_jd_tt" not in converted and "natal_longitude" not in converted
        assert converted["contacts"] == result["contacts"]


def test_unequal_sets_remain_three_and_five_without_index_pairing(analytic) -> None:
    primary, alternative = [], []
    for case in analytic["rows"][-3:]:
        for side, collection in [("personality", primary), ("design", alternative)]:
            epoch = float(frac(case["expected"][side]["origin_jd_tt"]))
            row = derive_body_contacts(
                case["body"],
                epoch,
                analytical_reader(case, frac(analytic["base_jd_tt"])),
            )
            for contact in row["contacts"]:
                contact.update(
                    utc_label=None,
                    utc_label_status="analytic_control_only",
                    future_leap_seconds_assumed_unchanged=False,
                )
            collection.append(row if side == "personality" else origin_body_row(row))
    summary = comparison_rows(
        primary, alternative, frac(analytic["base_jd_tt"]) + 12615
    )
    for row in summary:
        assert row["selected_personality"]["observed_contact_count"] == 3
        assert row["design_hypothesis"]["observed_contact_count"] == 5
        assert row["chronological_contact_pairing_assumed"] is False
        assert row["first_observed_shift_seconds"] == -120 * 86400
        assert (
            len(row["selected_personality"]["first_observed_contact"]["bracket_jd_tt"])
            == 2
        )


INPUT = dict(
    birth_year=1980,
    birth_month=1,
    birth_day=1,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.fixture(scope="module")
def complete():
    spec = next(s for s in CATALOG if s.key == "human_design")
    value = execute_tool(
        spec,
        spec.request_model(
            **INPUT,
            cycle_reference_datetime="1980-01-01T00:00:00.000001Z",
            compare_cycle_origins=True,
        ),
    )
    return value


def test_comparison_without_reference_preserves_contacts_and_replays(complete) -> None:
    request = HumanDesignRequest(**INPUT, compare_cycle_origins=True)
    spec = next(s for s in CATALOG if s.key == "human_design")
    result = execute_tool(spec, request)
    context = result["cycle_context"]
    comparison = result["cycle_origin_comparison"]
    assert (
        context["reference_status"] == comparison["reference_status"] == "not_requested"
    )
    assert context["reference_ordering"] is None
    assert context["reference_utc"] is None
    assert context["reference_jd_tt"] is None
    assert comparison["reference_exact_jd_tt"] is None
    assert context["bodies"] == complete["cycle_context"]["bodies"]
    assert (
        comparison["alternative"] == complete["cycle_origin_comparison"]["alternative"]
    )
    summary = result["cycle_summary"]
    assert summary["reference_status"] == "not_requested"
    assert summary["reference_contact_ordering"] is None
    assert all(body["reference_relation"] is None for body in summary["bodies"])
    clock = verify_clock_records(result)
    assert verify_cycle_context(result, clock_replay=clock)["errors"] == []
    assert verify_cycle_origin_comparison(result, clock_replay=clock)["errors"] == []
    context["reference_ordering"] = complete["cycle_context"]["reference_ordering"]
    assert verify_cycle_origin_comparison(result, clock_replay=clock)["errors"]


def test_full_comparison_replays_without_native_sky_calls(complete) -> None:
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier called native sky"),
    ):
        clock = verify_clock_records(complete)
        cycle = verify_cycle_context(complete, clock_replay=clock)
        origin = verify_cycle_origin_comparison(complete, clock_replay=clock)
    assert cycle["errors"] == origin["errors"] == []
    report = complete["cycle_origin_comparison"]
    ordering = complete["cycle_context"]["reference_ordering"]
    assert ordering["relation"] == "after"
    assert (
        ordering["reference"]["physical_jd_tt"] == ordering["birth"]["physical_jd_tt"]
    )
    assert report["reference_exact_jd_tt"] == ordering["reference"]["exact_jd_tt"]
    assert (
        report["selected_origin"]["jd_tt"]
        == complete["time_scales"]["personality"]["jd_tt"]
    )
    assert (
        report["hypothesis_origin"]["jd_tt"]
        == complete["time_scales"]["design"]["jd_tt"]
    )
    assert report["hypothesis_origin"]["source_preferred"] is False
    assert report["summary"]["current_traditional_phase"] is None
    for row in report["alternative"]["bodies"]:
        assert row["origin_jd_tt"] == report["hypothesis_origin"]["jd_tt"]
        assert "birth_jd_tt" not in row
    assert origin["checked_cycle_origin_evaluation_count"] > 0
    assert cycle["checked_cycle_evaluation_count"] == sum(
        len(r["evaluation_witnesses"]) for r in complete["cycle_context"]["bodies"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "remove",
        "wrong_epoch",
        "wrong_origin_longitude",
        "drop_contact",
        "first_shift",
        "preferred",
        "interpretation",
        "complete_cert",
        "source_index",
        "witness",
        "birth_label",
        "pair_by_index",
        "missing_request_marker",
        "missing_policy",
    ],
)
def test_correct_hash_cannot_legitimize_inconsistent_origins(
    complete, fault: str
) -> None:
    value = deepcopy(complete)
    report = value["cycle_origin_comparison"]
    row = report["alternative"]["bodies"][0]
    if fault == "remove":
        del value["cycle_origin_comparison"]
    elif fault == "wrong_epoch":
        report["hypothesis_origin"]["jd_tt"] = complete["time_scales"]["personality"][
            "jd_tt"
        ]
    elif fault == "wrong_origin_longitude":
        row["origin_longitude"] = complete["cycle_context"]["bodies"][0][
            "natal_longitude"
        ]
    elif fault == "drop_contact":
        row["contacts"].pop()
    elif fault == "first_shift":
        report["summary"]["bodies"][0]["first_observed_shift_seconds"] += 1
    elif fault == "preferred":
        report["hypothesis_origin"]["source_preferred"] = True
    elif fault == "interpretation":
        report["interpretation"] = "设计原点是唯一原典标准，已据此确定人生阶段。"
    elif fault == "complete_cert":
        report["continuous_completeness_certified"] = True
    elif fault == "source_index":
        row["evaluation_source_context_indices"][0] = 99999
    elif fault == "witness":
        row["evaluation_witnesses"][0][1] += 1
    elif fault == "birth_label":
        row["birth_jd_tt"] = row.pop("origin_jd_tt")
    elif fault == "pair_by_index":
        report["summary"]["bodies"][0]["chronological_contact_pairing_assumed"] = True
    elif fault == "missing_request_marker":
        del value["clock_evidence"]["compare_cycle_origins"]
    elif fault == "missing_policy":
        del value["calculation_policy"]["compare_cycle_origins"]
    else:
        pass
    proof = verify_human_design_reading((value))
    assert proof["status"] == "rejected"
    assert {"code": "cycle_origin_comparison_mismatch"} in proof["errors"]


def test_undated_origins_surface_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = three_surfaces(
        SPECS["human_design"],
        {**INPUT, "compare_cycle_origins": True},
        [
            "cycle_summary.reference_status",
            "cycle_summary.reference_utc",
            "cycle_context.reference_ordering",
            "cycle_origin_comparison.reference_status",
        ],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    assert output["cycle_summary"] == {
        "reference_status": "not_requested",
        "reference_utc": None,
    }
    assert output["cycle_context"] == {"reference_ordering": None}
    assert output["cycle_origin_comparison"] == {"reference_status": "not_requested"}
