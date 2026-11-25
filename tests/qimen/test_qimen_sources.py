"""Bind each declared chapter to its own independently retrieved revision."""

import json
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.qimen import (
    QIMEN_YANG_TERMS,
    _qimen_ju_number_for_term,
)
from fatebridge.core.qimen.qimen_sources import (
    SCAN_SOURCE,
    YANYI_FULL_VIEW,
    YANYI_VOLUMES,
)
from fatebridge.services.metaphysics import calculate_qimen_analysis

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/qimen-source-revisions-v1.json").read_text()
)
JU_CAPTIONS = json.loads(
    (Path(__file__).parents[1] / "fixtures/qimen-ju-captions-v1.json").read_text()
)


def test_shared_sources_are_individual_chapters_rather_than_the_full_view() -> None:
    assert YANYI_FULL_VIEW == REFERENCE["full_view"]["source"]
    assert YANYI_VOLUMES == {
        int(volume): record["source"] for volume, record in REFERENCE["volumes"].items()
    }
    assert YANYI_FULL_VIEW not in YANYI_VOLUMES.values()
    uses = [use for diagram in JU_CAPTIONS["diagrams"] for use in diagram["uses"]]
    assert len(JU_CAPTIONS["diagrams"]) == 18
    assert len(uses) == len({(use["term"], use["yuan"]) for use in uses}) == 72
    assert len({use["term"] for use in uses}) == 24


@pytest.mark.parametrize("god", ["yanyi_text", "yanyi_diagrams"])
@pytest.mark.parametrize("method", ["zhirun", "chaibu"])
@pytest.mark.parametrize(
    "season", ["yanyi_vol1_verse", "yanyi_vol3_table", "yanyi_vol3_prose"]
)
def test_actual_board_profiles_patterns_and_traces_keep_their_chapter_sources(
    god: str, method: str, season: str
) -> None:
    result = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=25,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        qimen_options={
            "ju_method": method,
            "god_profile": god,
            "season_profile": season,
        },
    )
    assert "error" not in result, result
    sources = {
        int(volume): record["source"] for volume, record in REFERENCE["volumes"].items()
    }
    qimen = result["qimen"]
    profiles = qimen["rule_profiles"]
    god_source = sources[3 if god == "yanyi_text" else 4]
    season_source = sources[1 if season == "yanyi_vol1_verse" else 3]
    assert profiles["god"]["source"] == god_source
    assert profiles["season"]["source"] == season_source
    for name in [
        "wonder_tomb",
        "six_instrument_punishment",
        "door_palace_relation",
        "three_deceptions",
        "five_jia",
    ]:
        assert profiles[name]["source"] == sources[2]
    ruleset = qimen["rulesets"][0]
    assert ruleset["source_revision_scope"] == "individual_volume_revisions"
    assert ruleset["volume_sources"] == [
        {"volume": volume, "source": source}
        for volume, source in sorted(sources.items())
    ]
    for palace in qimen["palaces"]:
        if palace["trigram"] == "中":
            continue
        else:
            pass
        evidence = palace["evidence"]
        assert evidence["star_season_source"] == season_source
        god_evidence = evidence["god_interpretation"]
        expected_volume = (
            4 if god_evidence["interpretation_status"] == "name_only_not_equated" else 3
        )
        assert god_evidence["source"] == sources[expected_volume]
    assert qimen["patterns"]
    assert all(pattern["source"] == sources[2] for pattern in qimen["patterns"])
    for trace in qimen["rule_trace"]:
        if trace["rule_id"] in {"leaders", "ju_resolution"}:
            assert trace["source"] == sources[1]
        elif trace["rule_id"] == "ju_table":
            assert trace["source"] == JU_CAPTIONS["source_url"] == SCAN_SOURCE
            assert trace["source_scan_pages"] == list(range(63, 72))
            assert trace["inputs"] == {
                "ju_term": qimen["ju_term"],
                "yuan": qimen["yuan"],
            }
            assert trace["outputs"] == {
                "dun_type": qimen["dun_type"],
                "ju_number": qimen["ju_number"],
            }
        elif trace["rule_id"] == "chapter_profiles":
            assert set(trace["sources"]) == {p["source"] for p in profiles.values()}
        elif trace["rule_id"] == "palace_relations":
            assert {sources[1], sources[2], season_source} <= set(trace["sources"])
        else:
            pass
    assert "全书导航：" in result["snapshot_text"]
    assert "逐卷固定转录：" in result["snapshot_text"]
    assert all(source in result["snapshot_text"] for source in sources.values())
    assert sum(trace["rule_id"] == "ju_table" for trace in qimen["rule_trace"]) == 1


@pytest.mark.parametrize(
    "term,yuan,dun,ju",
    [
        (use["term"], use["yuan"], diagram["dun"], diagram["ju_number"])
        for diagram in JU_CAPTIONS["diagrams"]
        for use in diagram["uses"]
    ],
)
def test_each_term_yuan_ju_matches_the_visually_read_siku_caption(
    term, yuan, dun, ju
) -> None:
    assert _qimen_ju_number_for_term(current_term=term, yuan=yuan) == ju
    assert ("阳遁" if term in QIMEN_YANG_TERMS else "阴遁") == dun
