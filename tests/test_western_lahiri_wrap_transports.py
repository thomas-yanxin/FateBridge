"""The corrected angular branch must reach facts and Lilly's rule ledger."""

from tests.test_agentic_nested_outputs import rest
from tests.test_western_event_clock_transports import surfaces


def test_wrap_epoch_has_retrograde_saturn_across_rest_mcp_cli(rest, tmp_path, capsys):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=285,
            question_month=9,
            question_day=2,
            question_hour=21,
            question_minute=51,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            zodiac_type="Sidereal",
            category="career",
        ),
        [
            "horary.planets.Saturn",
            "horary.calculation_basis.longitude_motion",
            "horary.fortitudes.physical_inputs.motion.Saturn",
            "horary.fortitudes.planets.Saturn.rows",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        assert h["planets"]["Saturn"]["retrograde"] is True
        assert -0.1 < h["planets"]["Saturn"]["speed"] < 0
        assert (
            abs(
                h["calculation_basis"]["longitude_motion"][
                    "display_longitude_offset_speed_degrees_per_day"
                ]
            )
            < 0.01
        )
        ledger = h["fortitudes"]
        motion = ledger["physical_inputs"]["motion"]["Saturn"]
        assert motion["status"] == "computed" and motion["direction"] == "retrograde"
        assert motion["daily_motion_degrees"] < 0
        rows = {r["code"]: r for r in ledger["planets"]["Saturn"]["rows"]}
        assert rows["D03"]["contribution"] == -5
        assert rows["F06"]["contribution"] == 0
        assert not ledger["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"
