"""Satyacharya planetary relationships in Brihat Jataka II.16-18.

Profile selects the explicitly enumerated table, not the alternative opinion
reported in II.15 or the optional exaltation-sign temporary friendship in II.18.
Relations are from one graha to another; they need not be reciprocal.
"""

from typing import Any

SOURCE_ID = "brihat_jataka_aiyar_1905"
SOURCE = {
    "id": SOURCE_ID,
    "title": "Varahamihira, Brihat Jataka, translated by N. Chidambaram Aiyar, second edition, 1905",
    "url": "https://archive.org/details/brihatjataka00varaiala",
    "sections": ["II.16-18, printed pp.21-22"],
    "text_witness_url": "https://archive.org/download/brihatjataka00varaiala/brihatjataka00varaiala_djvu.txt",
    "text_witness_sha256": "bf1afe4510937e04157ba06f2c3a6d849c262ea3fffa1b922662973172bc0152",
    "scope": "Satyacharya enumerated relationship table and primary temporary rule only; not whole-text conformity",
}
NATURAL = {
    "Sun": ({"Moon", "Mars", "Jupiter"}, {"Venus", "Saturn"}),
    "Moon": ({"Sun", "Mercury"}, set()),
    "Mars": ({"Sun", "Moon", "Jupiter"}, {"Mercury"}),
    "Mercury": ({"Sun", "Venus"}, {"Moon"}),
    "Jupiter": ({"Sun", "Moon", "Mars"}, {"Mercury", "Venus"}),
    "Venus": ({"Mercury", "Saturn"}, {"Sun", "Moon"}),
    "Saturn": ({"Mercury", "Venus"}, {"Sun", "Moon", "Mars"}),
}
COMPOUND = {
    -2: "great_enemy",
    -1: "enemy",
    0: "neutral",
    1: "friend",
    2: "great_friend",
}


def relationship(planet: str, other: str, signs: dict[str, int]) -> dict[str, Any]:
    if planet not in NATURAL or other not in NATURAL:
        raise ValueError("No node relationship doctrine registered")
    if planet == other:
        return {
            "from_planet": planet,
            "to_planet": other,
            "natural": "self",
            "temporary": "not_applicable",
            "compound": "self",
            "rule_id": "jyotish.satyacharya_relationships.v1",
        }
    friends, enemies = NATURAL[planet]
    natural = 1 if other in friends else -1 if other in enemies else 0
    distance = (signs[other] - signs[planet]) % 12 + 1
    temporary = 1 if distance in {2, 3, 4, 10, 11, 12} else -1
    return {
        "from_planet": planet,
        "to_planet": other,
        "natural": {1: "friend", 0: "neutral", -1: "enemy"}[natural],
        "relative_sign_distance": distance,
        "temporary": "friend" if temporary == 1 else "enemy",
        "compound": COMPOUND[natural + temporary],
        "source_id": SOURCE_ID,
        "source_section": "II.16-18",
        "rule_id": "jyotish.satyacharya_relationships.v1",
        "scope": "D1 sign placements; graha-to-graha traditional relation, not human friendship or trust",
    }
