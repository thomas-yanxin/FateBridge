from fatebridge.core.astro.relationship import relationship_focus_block
from fatebridge.services.astrology import calculate_relative_chart_analysis
from tests.fixtures.surface_payloads import astro_payload


def test_relationship_focus_block_romance_filters_to_significators():
    aspects = [
        {"inner": "Venus", "outer": "Mars", "aspect": "Trine", "orb": 1.0},
        {"inner": "Mercury", "outer": "Saturn", "aspect": "Square", "orb": 2.0},
        {"inner": "Moon", "outer": "Jupiter", "aspect": "Sextile", "orb": 3.0},
    ]
    block = relationship_focus_block("romance", aspects)
    assert block["focus"] == "romance"
    assert block["emphasis_houses"] == [5]
    kept = {(a["inner"], a["outer"]) for a in block["focused_synastry_aspects"]}
    assert ("Venus", "Mars") in kept  # both significators
    assert ("Moon", "Jupiter") in kept  # Moon is a significator
    assert ("Mercury", "Saturn") not in kept  # neither is a romance significator
    assert block["focused_aspect_count"] == 2


def test_relationship_focus_block_marriage_houses_and_bodies():
    block = relationship_focus_block("婚姻", [])
    assert block["focus"] == "marriage"
    assert block["emphasis_houses"] == [7]
    assert "Saturn" in block["emphasis_bodies"]


def test_relationship_focus_block_general_does_not_filter():
    block = relationship_focus_block(
        None, [{"inner": "Venus", "outer": "Mars", "aspect": "Trine", "orb": 1.0}]
    )
    assert block["focus"] == "general"
    assert block["emphasis_houses"] == []
    assert block["focused_synastry_aspects"] == []


def test_relative_chart_attaches_focus_block_subset_of_synastry():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(
            name="甲",
            birth_longitude=121.4667,
            birth_latitude=31.2167,
            birth_place="上海",
        ),
        outer_payload=astro_payload(
            name="乙",
            birth_longitude=116.4074,
            birth_latitude=39.9042,
            birth_place="北京",
        ),
        relative_mode="Composite",
        relationship_focus="romance",
        hsys=0,
        zodiacal=0,
    )

    focus = result["relationship_profile"]["focus"]
    assert focus["focus"] == "romance"
    assert focus["emphasis_houses"] == [5]
    # 过滤子集必须是完整 synastry 相位的子集。
    assert focus["focused_aspect_count"] <= len(result["synastry_aspects"])
    significators = set(focus["emphasis_bodies"])
    for aspect in focus["focused_synastry_aspects"]:
        assert aspect["inner"] in significators or aspect["outer"] in significators
