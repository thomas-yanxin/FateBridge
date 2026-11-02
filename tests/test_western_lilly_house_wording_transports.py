"""Real cusp advancement remains distinct from occupancy on all protocols."""

from tests.test_agentic_nested_outputs import rest
from tests.test_western_event_clock_transports import surfaces


def test_house_assignment_wording_reaches_rows_and_summary_on_all_protocols(
    rest, tmp_path, capsys
):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2026,
            question_month=9,
            question_day=19,
            question_hour=0,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            ut1_source="iers_c04",
            category="career",
        ),
        [
            "horary.planets.Sun.occupied_house",
            "horary.planets.Sun.house_assignment",
            "horary.fortitudes.planets.Sun.rows",
            "horary.fortitudes.planets.Venus.rows",
            "horary.fortitudes.summary.Sun.applied_conditions",
            "horary.fortitudes.summary.Venus.applied_conditions",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        assert h["planets"]["Sun"]["occupied_house"] == 3
        assert h["planets"]["Sun"]["house_assignment"]["assigned_house"] == 4
        for planet, code, occupied, scored, points in [
            ("Sun", "F02", 3, 4, 4),
            ("Venus", "F03", 4, 5, 3),
        ]:
            rows = h["fortitudes"]["planets"][planet]["rows"]
            row = next(r for r in rows if r["code"] == code)
            assert row["inputs"]["occupied_house"] == occupied
            assert row["inputs"]["scored_house"] == scored
            assert row["contribution"] == points
            assert row["label_zh"].startswith("计分归")
            assert row["source_pages"] == [33, 115]
            summary = h["fortitudes"]["summary"][planet]["applied_conditions"]
            assert (
                next(r for r in summary if r["code"] == code)["label_zh"]
                == row["label_zh"]
            )
        assert not h["fortitudes"]["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"
