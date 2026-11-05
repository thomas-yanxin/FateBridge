"""Named source coordinates, edition differences and exact local boundaries."""

import hashlib
import json
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import MANSIONS, HistoricalMansions
from fatebridge.core.guolao_coordinates import (
    NLC166_MANSIONS,
    NLC166_PALACES,
    PROFILES,
    WIKISOURCE_PALACES,
)

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-historical-coordinates-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
NLC = REFERENCE["nlc166_transcription"]


@pytest.mark.parametrize(
    "file,expected",
    [
        (
            REFERENCE["primary_scan"]["extracted_file"],
            REFERENCE["primary_scan"]["extracted_sha256"],
        ),
        *[(e["file"], e["sha256"]) for e in REFERENCE["luwei_comparison"]["images"]],
        (
            REFERENCE["wikisource"]["excerpt_file"],
            REFERENCE["wikisource"]["excerpt_sha256"],
        ),
    ],
)
def test_primary_artifact_bytes_are_frozen(file, expected):
    assert hashlib.sha256((FIXTURE / file).read_bytes()).hexdigest() == expected


def test_scan_circle_and_28_widths_match_selected_source_not_luwei_emendation():
    assert NLC166_MANSIONS.circle_du == F(NLC["circle_du"])
    assert NLC166_MANSIONS.widths_du == tuple(map(F, NLC["widths_du"]))
    assert sum(NLC166_MANSIONS.widths_du) == F("365.2575")
    assert REFERENCE["primary_scan"]["original_pdf_pages_one_based"] == [55, 57, 58]
    assert not REFERENCE["luwei_comparison"]["luwei_table_emended"]
    assert "東北大学附属図書館所蔵" in REFERENCE["luwei_comparison"]["credit"]


@pytest.mark.parametrize("profile_key", PROFILES)
@pytest.mark.parametrize("row", NLC["twelve_entrances"], ids=lambda r: r["branch"])
def test_each_named_entrance_and_both_sides_against_source(profile_key, row):
    profile = PROFILES[profile_key]
    degree = row["degree_du"]
    if profile_key == "wikisource":
        for variant in REFERENCE["wikisource"]["variants_against_selected_nlc_scan"]:
            if variant["branch"] == row["branch"]:
                degree = variant["wikisource_du"]
    epsilon = F(1, 10**70)
    at = profile.from_mansion(row["mansion"], F(degree))
    assert at["branch"] == row["branch"]
    assert F(at["degree_in_branch_interval_du_exact"]) == 0
    before = profile.from_mansion(row["mansion"], F(degree) - epsilon)
    previous_row = NLC["twelve_entrances"][NLC["twelve_entrances"].index(row) - 1]
    assert before["branch"] == previous_row["branch"]
    after = profile.from_mansion(row["mansion"], F(degree) + epsilon)
    assert after["branch"] == row["branch"]
    assert F(after["degree_in_branch_interval_du_exact"]) == epsilon


@pytest.mark.parametrize("case", REFERENCE["independent_coordinate_cases"])
def test_hand_arithmetic_source_cases_including_real_edition_classification_change(
    case,
):
    result = PROFILES[case["profile"]].from_mansion(
        case["mansion"], F(case["degree_du"])
    )
    assert result["branch"] == case["branch"]
    assert F(result["degree_in_branch_interval_du_exact"]) == F(case["offset_du"])


@pytest.mark.parametrize("profile", list(PROFILES.values()), ids=lambda p: p.profile_id)
def test_all_mansion_edges_and_negative_full_circle_round_trip(profile):
    angle = F()
    for mansion, width in zip(MANSIONS, map(F, NLC["widths_du"])):
        for delta in (F(), width / 2, width - F(1, 10**60)):
            result = profile.locate(angle + delta - 17 * F(NLC["circle_du"]))
            assert result["mansion"] == mansion
            assert F(result["degree_in_mansion_du_exact"]) == delta
            assert (
                profile.from_palace(
                    result["branch"], F(result["degree_in_branch_interval_du_exact"])
                )
                == result
            )
            assert F(result["angle_from_jiao_du_exact"]) == angle + delta
        angle += width
    assert profile.locate(angle) == profile.locate(F())


@pytest.mark.parametrize("profile", list(PROFILES.values()), ids=lambda p: p.profile_id)
def test_actual_palace_widths_close_without_30_degree_modulus(profile):
    total = sum((profile.width(e.branch) for e in profile.entrances), F())
    assert total == F("365.2575")
    assert len({profile.width(e.branch) for e in profile.entrances}) > 1
    for entrance in profile.entrances:
        width = profile.width(entrance.branch)
        with pytest.raises(ValueError, match="首含尾不含"):
            profile.from_palace(entrance.branch, width)
        result = profile.from_palace(entrance.branch, width - F(1, 10**60))
        assert result["branch"] == entrance.branch
        assert F(result["degree_in_branch_interval_du_exact"]) < width
    assert NLC166_PALACES.width("丑") == F("29.6653")
    assert WIKISOURCE_PALACES.width("丑") == F("28.6653")
    assert NLC166_PALACES.from_palace("丑", F(29))["mansion"] == "女"
    with pytest.raises(ValueError):
        WIKISOURCE_PALACES.from_palace("丑", F(29))


def test_two_profile_variants_remain_distinct_and_digitized_passage_is_pinned():
    first = {e.branch: e.degree_du for e in NLC166_PALACES.entrances}
    second = {e.branch: e.degree_du for e in WIKISOURCE_PALACES.entrances}
    assert {key for key in first if first[key] != second[key]} == {"丑", "巳"}
    text = (FIXTURE / REFERENCE["wikisource"]["excerpt_file"]).read_text()
    assert "斗，三度七十六分八十五秒。" in text
    assert "張，十五度二十六分六秒。" in text
    assert "oldid=1959444" in WIKISOURCE_PALACES.source_url
    for profile in PROFILES.values():
        result = profile.locate(F())
        assert result["modern_longitude"] is None and result["life_degree"] is None
        assert not result["modern_epoch_calibrated"]


@pytest.mark.parametrize("value", [1.0, 1, True, "1", None])
def test_implicit_units_or_float_coordinates_rejected(value):
    for profile in PROFILES.values():
        with pytest.raises(TypeError):
            profile.locate(value)
        with pytest.raises(TypeError):
            profile.from_mansion("角", value)
        with pytest.raises(TypeError):
            profile.from_palace("丑", value)


def test_float_table_constructor_cannot_round_an_interior_offset_to_mansion_end():
    # Before the fix this table accepted float widths and locate(2-1e-30)
    # returned 亢,1.0. The exact offset is 1-1e-30 and must be below its width.
    with pytest.raises(TypeError, match="Fraction"):
        HistoricalMansions("float_widths", F(28), (1.0,) * 28)
    with pytest.raises(TypeError, match="Fraction"):
        HistoricalMansions("float_circle", 28.0, (F(1),) * 28)
    exact = HistoricalMansions("synthetic_exact", F(28), (F(1),) * 28)
    tiny = F(1, 10**30)
    assert exact.locate(F(2) - tiny) == ("亢", F(1) - tiny)


def test_input_collections_cannot_mutate_a_validated_coordinate_table():
    widths = [F(1)] * 28
    table = HistoricalMansions("synthetic_exact", F(28), widths)
    widths[0] = F(2)
    assert table.widths_du == (F(1),) * 28
    assert table.locate(F(3, 2)) == ("亢", F(1, 2))
    entrances = list(NLC166_PALACES.entrances)
    profile = replace(NLC166_PALACES, entrances=entrances)
    before = profile.audit()
    entrances.pop()
    assert profile.audit() == before


def test_invalid_profiles_and_noncanonical_local_offsets_are_rejected():
    profile = NLC166_PALACES
    with pytest.raises(ValueError, match="十二个不同"):
        replace(profile, entrances=(profile.entrances[0],) * 12)
    duplicate = replace(
        profile.entrances[-1],
        mansion=profile.entrances[0].mansion,
        degree_du=profile.entrances[0].degree_du,
    )
    with pytest.raises(ValueError, match="入口重合"):
        replace(profile, entrances=profile.entrances[:-1] + (duplicate,))
    for name, degree in [("", F()), ("觜", F("0.05")), ("角", F(-1))]:
        with pytest.raises(ValueError):
            profile.from_mansion(name, degree)
    with pytest.raises(ValueError):
        profile.from_palace("官禄", F())
