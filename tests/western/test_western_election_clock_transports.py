"""Published clocks retain their own physical event evidence on all adapters."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.support.transports import SPECS, three_surfaces

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-election-worked-sources.json"
    ).read_text()
)
CASES = [
    case
    for case in REFERENCE["cases"]
    if case["id"] == "w2001-image"
    or case["chart"] in {"warnock_2003_04", "gillman_figure6"}
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_source_clock_hypothesis_delivers_its_own_marriage_evidence(
    case, tmp_path, monkeypatch, capsys
):
    result = three_surfaces(
        SPECS["astro_election"],
        case["input"],
        (
            []
            if case["id"] == "w2001-image"
            else [
                "analysis_context",
                "calendar_conversion",
                "clock_conversion",
                "election",
            ]
        ),
        case["as_of"],
        tmp_path,
        monkeypatch,
        capsys,
    )
    context = result["analysis_context"]
    assert context["input_calendar"] == case["input"].get(
        "candidate_calendar", "proleptic_gregorian"
    )
    assert context["input_clock_basis"] == case["input"].get(
        "candidate_clock_basis", "civil"
    )
    assert context["timezone"] == case["input"].get("timezone_name")
    election = result["election"]
    evidence = election["marriage_significators"]
    assert evidence["method_id"] == "ramesey_1653_p175_marriage_significators_v2"
    assert evidence["score_contribution"] == 0
    assert evidence["full_original_text_acceptance"] is False
    assert [(row["house"], row["role_in_source"]) for row in evidence["houses"]] == [
        (1, "first_source_party"),
        (7, "second_source_party"),
        (10, "between_parties"),
        (4, "conclusion"),
    ]
    history = evidence["event_history"]
    epoch_tt = election["calculation_basis"]["julian_day_tt"]
    expected_label = {
        "w2001-image": (2001, 1, 8, 17, 5, 0),
        "w2003-body-EST": (2003, 4, 14, 18, 14, 0),
        "w2003-image-EDT": (2003, 4, 14, 17, 14, 50),
        "g1613-proleptic_gregorian-civil": (1613, 2, 14, 9, 46, 0),
        "g1613-proleptic_gregorian-local_mean_solar": (1613, 2, 14, 9, 46, 40),
        "g1613-julian-civil": (1613, 2, 24, 9, 46, 0),
        "g1613-julian-local_mean_solar": (1613, 2, 24, 9, 46, 40),
    }[case["id"]]
    expected_datetime = datetime(*expected_label, tzinfo=timezone.utc)
    expected_day = (
        expected_datetime.toordinal()
        + 1721424.5
        + (
            expected_datetime.hour * 3600
            + expected_datetime.minute * 60
            + expected_datetime.second
        )
        / 86400
    )
    if expected_datetime.year >= 1972:
        assert abs(epoch_tt - (expected_day + 64.184 / 86400)) * 86400 < 0.001
    else:
        assert (
            abs(election["calculation_basis"]["julian_day_ut1"] - expected_day) * 86400
            < 0.001
        )
    assert history["status"] == "computed"
    assert history["constant_velocity_projection"] is False
    assert history["window_tt"] == [epoch_tt - 30, epoch_tt + 30]
    first, second = evidence["parties"]
    assert first["contact"]["julian_day_tt"] < epoch_tt
    assert second["contact"]["julian_day_tt"] > epoch_tt
    assert all(party["contact_order_established"] is True for party in [first, second])
    if case["id"] == "w2001-image":
        assert [row["ruler"] for row in evidence["houses"][:2]] == ["Mars", "Venus"]
        assert second["lunar_significator"] == "Venus"
        assert result["summary"] and result["analysis_type"] == "西占择日"
    else:
        assert case["source_clock_or_calendar_resolved"] is False
