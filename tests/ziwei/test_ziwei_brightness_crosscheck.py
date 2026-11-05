"""Full independent iztro transcription, including gaps and uncovered stars."""

import json
from pathlib import Path

from fatebridge.core.ziwei_tables import ZIWEI_STAR_BRIGHTNESS, lookup_star_brightness
from scripts.ziwei.gen_ziwei_brightness_fixture import BRANCHES, build_fixture

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/ziwei_brightness_reference.json").read_text(
        encoding="utf-8"
    )
)


def test_fixture_matches_independent_transcription():
    assert REFERENCE == build_fixture()


def test_complete_table_and_brightness_gaps_match_reference():
    stars = {key.split("@", 1)[0] for key in REFERENCE}
    assert len(stars) == 20
    assert set(ZIWEI_STAR_BRIGHTNESS) == stars
    for star in stars:
        assert len(ZIWEI_STAR_BRIGHTNESS[star]) == 12
        for branch in BRANCHES:
            assert lookup_star_brightness(star, branch) == REFERENCE.get(
                f"{star}@{branch}"
            ), (star, branch)


def test_uncovered_stars_have_no_brightness():
    for star in ("天刑", "天钺", "天魁", "左辅", "右弼", "禄存", "天马", "天姚"):
        for branch in BRANCHES:
            assert lookup_star_brightness(star, branch) is None
