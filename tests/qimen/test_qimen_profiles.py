"""Chapter variants stay explicit; neither labels nor outcomes choose a rule."""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.core.metaphysics.qimen import _qimen_build_palaces
from fatebridge.core.qimen_profiles import (
    GOD_PROFILES,
    SEASON_PROFILES,
    describe_profiles,
    star_season_state,
)
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.validation.qimen import audit_chapter_profiles
from tests.qimen.test_qimen_depth import fixed_board, seed

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v4"
REFERENCE = json.loads((BUNDLE / "sources-and-profiles.json").read_text())


def test_frozen_chapter_audit_keeps_coverage_separate_from_whole_book():
    report = audit_chapter_profiles(BUNDLE)
    assert report["god_diagram_cases"] == 4
    assert report["god_palace_observations"] == 32
    assert report["season_table_month_cases"] == 60
    assert report["season_verse_prose_relation_cases"] == 10
    assert report["god_text_sequence_checked"]
    assert report["disagreements"] == []
    assert not report["whole_book_conformance_established"]
    assert not report["real_world_efficacy_validated"]


@pytest.mark.parametrize("case", REFERENCE["god_diagrams"], ids=lambda c: c["id"])
def test_four_scanned_god_circles_including_both_centre_hosts(case):
    palaces = _qimen_build_palaces(
        time_ganzhi=case["hour"],
        ju_text=f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元',
        dun_type=case["dun"],
        current_term="冬至",
        god_profile="yanyi_diagrams",
    )
    assert {p["trigram"]: p["god"] for p in palaces if p["trigram"] != "中"} == case[
        "gods"
    ]
    center = next(p for p in palaces if p["trigram"] == "中")
    assert center["god"] is None and center["god_sequence_index"] is None


@pytest.mark.parametrize("dun,number", list(product(["阳遁", "阴遁"], range(1, 10))))
def test_label_profile_preserves_every_star_door_stem_and_slot_in_1080_boards(
    dun, number
):
    for index in range(60):
        hour = (
            "甲乙丙丁戊己庚辛壬癸"[index % 10] + "子丑寅卯辰巳午未申酉戌亥"[index % 12]
        )
        args = dict(
            time_ganzhi=hour,
            ju_text=f'{dun}{"一二三四五六七八九"[number-1]}局上元',
            dun_type=dun,
            current_term="冬至",
        )
        text = _qimen_build_palaces(**args, god_profile="yanyi_text")
        diagrams = _qimen_build_palaces(**args, god_profile="yanyi_diagrams")
        for before, after in zip(text, diagrams):
            assert {k: v for k, v in before.items() if k != "god"} == {
                k: v for k, v in after.items() if k != "god"
            }
            if before["god"] != after["god"]:
                assert (before["god"], after["god"]) in [
                    ("白虎", "勾陈"),
                    ("玄武", "朱雀"),
                ]
        assert sorted(
            p["god_sequence_index"] for p in diagrams if p["trigram"] != "中"
        ) == list(range(8))


@pytest.mark.parametrize("profile", SEASON_PROFILES)
def test_season_definition_and_god_roles_follow_actual_profile(monkeypatch, profile):
    b = fixed_board(
        monkeypatch,
        {"dun": "阳遁", "ju": 1, "hour": "甲子"},
        month="甲子",
        god_profile="yanyi_diagrams",
        season_profile=profile,
    )
    kan = b["palaces"][0]
    expected = {
        "yanyi_vol1_verse": "相",
        "yanyi_vol3_table": "旺",
        "yanyi_vol3_prose": "旺",
    }
    assert kan["evidence"]["star_season_state"] == expected[profile]
    assert kan["evidence"]["star_season_profile"] == profile
    assert kan["evidence"]["star_season_relation"] == "same_element"
    assert (
        kan["evidence"]["star_season_source_section"]
        == b["rule_profiles"]["season"]["section"]
    )
    for palace in b["palaces"]:
        if palace["god"] in {"勾陈", "朱雀"}:
            meaning = palace["evidence"]["god_interpretation"]
            assert meaning["interpretation_status"] == "name_only_not_equated"
            assert meaning["outcome_inferred"] is False
    assert b["assessment"]["classical_conformance"] == "partial_excerpt"
    assert b["assessment"]["real_world_efficacy"] == "not_tested"


def test_verse_table_and_prose_differences_are_retained_instead_of_normalized():
    assert [star_season_state("水", "水", p) for p in SEASON_PROFILES] == [
        "相",
        "旺",
        "旺",
    ]
    assert [star_season_state("水", "木", p) for p in SEASON_PROFILES] == [
        "旺",
        "相",
        "相",
    ]
    assert [star_season_state("水", "金", p) for p in SEASON_PROFILES] == [
        "废",
        "废",
        "休",
    ]
    assert [star_season_state("水", "火", p) for p in SEASON_PROFILES] == [
        "休",
        "休",
        "死",
    ]


def test_default_profile_keeps_qualifications_and_cannot_mutate_global_definition(
    monkeypatch,
):
    b = fixed_board(monkeypatch, {"dun": "阴遁", "ju": 5, "hour": "甲子"})
    assert b["god_profile"] == "yanyi_text"
    assert b["season_profile"] == "yanyi_vol1_verse"
    assert sorted(p["god"] for p in b["palaces"] if p["god"]) == sorted(
        REFERENCE["god_text"]["sequence"]
    )
    for palace in b["palaces"]:
        if palace["god"] in REFERENCE["god_text"]["qualification_gods"]:
            meaning = palace["evidence"]["god_interpretation"]
            assert meaning["qualification_evaluated"] is False
            assert "得奇门会合" in meaning["source_qualification"]
    original = deepcopy(GOD_PROFILES)
    described = describe_profiles(b["god_profile"], b["season_profile"])
    described["god"]["sequence"][0] = "changed"
    assert GOD_PROFILES == original


@pytest.mark.parametrize("name", ["god_profile", "season_profile"])
@pytest.mark.parametrize("value", [None, {}, [], 1, True, "automatic_best"])
def test_invalid_profile_has_a_clear_validation_error(name, value):
    with pytest.raises(ValueError, match=name):
        build_qimen_with_options(seed(), {name: value})


def test_sanshi_passes_source_profiles_into_qimen_and_readable_snapshot():
    result = calculate_sanshiunited_analysis(
        date="2026-01-19",
        time="23:00",
        zone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={
            "god_profile": "yanyi_diagrams",
            "season_profile": "yanyi_vol3_prose",
        },
    )
    assert "error" not in result, result
    assert result["qimen"]["god_profile"] == "yanyi_diagrams"
    assert result["subresults"]["qimen"]["pan"] == result["qimen"]
    assert "卷四圆图八神（yanyi_diagrams）" in result["snapshot_text"]
    assert "卷三九星旺衰正文（yanyi_vol3_prose）" in result["snapshot_text"]


@pytest.mark.parametrize(
    "change", ["pdf", "diagram", "missing_diagram", "missing_month"]
)
def test_source_audit_refuses_corrupt_or_reduced_reference(tmp_path, change):
    import shutil

    shutil.copytree(BUNDLE, tmp_path / "qimen_classical_v4")
    shutil.copytree(
        BUNDLE.parent / "qimen_classical_v3", tmp_path / "qimen_classical_v3"
    )
    root = tmp_path / "qimen_classical_v4"
    path = root / "sources-and-profiles.json"
    data = json.loads(path.read_text())
    if change in {"pdf", "diagram"}:
        key = "excerpt_file" if change == "pdf" else "diagram_excerpt_file"
        linked = root / data[key]
        linked.write_bytes(linked.read_bytes() + b"changed")
    elif change == "missing_diagram":
        data["god_diagrams"].pop()
    else:
        data["season_profiles"][1]["states_by_star_element"]["土"]["旺"] = "丑未"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹|四幅|十二月"):
        audit_chapter_profiles(root)
