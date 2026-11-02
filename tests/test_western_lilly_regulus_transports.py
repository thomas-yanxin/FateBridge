"""Actual apparent geometry in the corrected interval reaches all protocols."""

from tests.test_agentic_nested_outputs import rest
from tests.test_western_event_clock_transports import surfaces


def test_native_sun_regulus_five_to_six_degrees_on_rest_mcp_cli(rest, tmp_path, capsys):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2024,
            question_month=8,
            question_day=17,
            question_hour=12,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            category="career",
        ),
        [
            "horary.fortitudes.method_id",
            "horary.fortitudes.planets.Sun.rows",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.fortune.method_id",
            "horary.fortune.rows",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        f = h["fortitudes"]
        assert f["method_id"].endswith("v3")
        row = next(r for r in f["planets"]["Sun"]["rows"] if r["code"] == "F17")
        assert 5 < row["inputs"]["separation_degrees"] < 6
        assert row["inputs"]["orb_degrees"] == 6
        assert row["satisfied"] and row["contribution"] == 6
        assert row["condition"] == "regulus_within_six_degrees"
        assert "六度" in row["label_zh"]
        assert row["source_pages"] == [115, 179]
        fortune = h["fortune"]
        assert fortune["method_id"].endswith("v2")
        r = next(r for r in fortune["rows"] if r["code"] == "P14")
        assert r["inputs"]["orb_degrees"] == 6
        assert "declared convention" in r["inputs"]["star_policy"]
        assert r["source_pages"] == [145, 179]
        assert not f["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"
