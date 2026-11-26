"""Shared zodiac and dignity tables without chart or predictive dependencies.

Egyptian bounds retain the horosa data/dignities.js provenance and values.
"""

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


SIGN_LABELS_ZH = {
    "Aries": "白羊",
    "Taurus": "金牛",
    "Gemini": "双子",
    "Cancer": "巨蟹",
    "Leo": "狮子",
    "Virgo": "处女",
    "Libra": "天秤",
    "Scorpio": "天蝎",
    "Sagittarius": "射手",
    "Capricorn": "摩羯",
    "Aquarius": "水瓶",
    "Pisces": "双鱼",
}


ELEMENT_BY_SIGN = {
    "Aries": "Fire",
    "Leo": "Fire",
    "Sagittarius": "Fire",
    "Taurus": "Earth",
    "Virgo": "Earth",
    "Capricorn": "Earth",
    "Gemini": "Air",
    "Libra": "Air",
    "Aquarius": "Air",
    "Cancer": "Water",
    "Scorpio": "Water",
    "Pisces": "Water",
}


MODALITY_BY_SIGN = {
    "Aries": "Cardinal",
    "Cancer": "Cardinal",
    "Libra": "Cardinal",
    "Capricorn": "Cardinal",
    "Taurus": "Fixed",
    "Leo": "Fixed",
    "Scorpio": "Fixed",
    "Aquarius": "Fixed",
    "Gemini": "Mutable",
    "Virgo": "Mutable",
    "Sagittarius": "Mutable",
    "Pisces": "Mutable",
}


DOMICILE_RULERS = {
    "Sun": ("Leo",),
    "Moon": ("Cancer",),
    "Mercury": ("Gemini", "Virgo"),
    "Venus": ("Taurus", "Libra"),
    "Mars": ("Aries", "Scorpio"),
    "Jupiter": ("Sagittarius", "Pisces"),
    "Saturn": ("Capricorn", "Aquarius"),
}


EXALTATION_SIGNS = {
    "Sun": "Aries",
    "Moon": "Taurus",
    "Mercury": "Virgo",
    "Venus": "Pisces",
    "Mars": "Capricorn",
    "Jupiter": "Cancer",
    "Saturn": "Libra",
}


def _opposite_sign(sign: str) -> str:
    return SIGNS[(SIGNS.index(sign) + 6) % 12]


RULER_BY_SIGN = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}


EGYPTIAN_BOUNDS_BY_SIGN = {
    "Aries": [
        ("Jupiter", 0.0, 6.0),
        ("Venus", 6.0, 12.0),
        ("Mercury", 12.0, 20.0),
        ("Mars", 20.0, 25.0),
        ("Saturn", 25.0, 30.0),
    ],
    "Taurus": [
        ("Venus", 0.0, 8.0),
        ("Mercury", 8.0, 14.0),
        ("Jupiter", 14.0, 22.0),
        ("Saturn", 22.0, 27.0),
        ("Mars", 27.0, 30.0),
    ],
    "Gemini": [
        ("Mercury", 0.0, 6.0),
        ("Jupiter", 6.0, 12.0),
        ("Venus", 12.0, 17.0),
        ("Mars", 17.0, 24.0),
        ("Saturn", 24.0, 30.0),
    ],
    "Cancer": [
        ("Mars", 0.0, 7.0),
        ("Venus", 7.0, 13.0),
        ("Mercury", 13.0, 19.0),
        ("Jupiter", 19.0, 26.0),
        ("Saturn", 26.0, 30.0),
    ],
    "Leo": [
        ("Jupiter", 0.0, 6.0),
        ("Venus", 6.0, 11.0),
        ("Saturn", 11.0, 18.0),
        ("Mercury", 18.0, 24.0),
        ("Mars", 24.0, 30.0),
    ],
    "Virgo": [
        ("Mercury", 0.0, 7.0),
        ("Venus", 7.0, 17.0),
        ("Jupiter", 17.0, 21.0),
        ("Mars", 21.0, 28.0),
        ("Saturn", 28.0, 30.0),
    ],
    "Libra": [
        ("Saturn", 0.0, 6.0),
        ("Mercury", 6.0, 14.0),
        ("Jupiter", 14.0, 21.0),
        ("Venus", 21.0, 28.0),
        ("Mars", 28.0, 30.0),
    ],
    "Scorpio": [
        ("Mars", 0.0, 7.0),
        ("Venus", 7.0, 11.0),
        ("Mercury", 11.0, 19.0),
        ("Jupiter", 19.0, 24.0),
        ("Saturn", 24.0, 30.0),
    ],
    "Sagittarius": [
        ("Jupiter", 0.0, 12.0),
        ("Venus", 12.0, 17.0),
        ("Mercury", 17.0, 21.0),
        ("Saturn", 21.0, 26.0),
        ("Mars", 26.0, 30.0),
    ],
    "Capricorn": [
        ("Mercury", 0.0, 7.0),
        ("Jupiter", 7.0, 14.0),
        ("Venus", 14.0, 22.0),
        ("Saturn", 22.0, 26.0),
        ("Mars", 26.0, 30.0),
    ],
    "Aquarius": [
        ("Mercury", 0.0, 7.0),
        ("Venus", 7.0, 13.0),
        ("Jupiter", 13.0, 20.0),
        ("Mars", 20.0, 25.0),
        ("Saturn", 25.0, 30.0),
    ],
    "Pisces": [
        ("Venus", 0.0, 12.0),
        ("Jupiter", 12.0, 16.0),
        ("Mercury", 16.0, 19.0),
        ("Mars", 19.0, 28.0),
        ("Saturn", 28.0, 30.0),
    ],
}
