"""Fixed residential examples shared by transport and golden coverage."""

from copy import deepcopy

PAYLOADS = {
    "directions": {"bearing_degrees": 360, "north_reference": "magnetic"},
    "minggua": {"birth_year": 1990, "gender": "female"},
    "bazhai": {
        "house": {
            "object_id": "home",
            "facing_degrees": 180,
            "north_reference": "magnetic",
        },
        "occupants": [
            {
                "subject_id": "a",
                "birth_year": 1990,
                "gender": "male",
            },
            {
                "subject_id": "b",
                "birth_year": 1990,
                "gender": "female",
            },
        ],
        "placements": [
            {
                "object_id": "stove",
                "purpose": "stove",
                "location_direction": "NE",
                "facing_direction": "S",
                "facing_role": "fire_mouth",
                "subject_id": "a",
            },
            {
                "object_id": "bed",
                "purpose": "bed",
                "location_direction": "N",
                "facing_direction": "E",
                "facing_role": "headboard",
                "subject_id": "a",
            },
        ],
    },
    "jinsuo": {
        "features": [
            {
                "object_id": "pond",
                "direction": "S",
                "classification": "water",
                "classification_basis": "user_confirmed",
                "evidence": "确认南方水体",
            },
            {
                "object_id": "hill",
                "direction": "N",
                "classification": "sand",
                "classification_basis": "measured",
                "evidence": "北方高于宅基的实体，已测量确认",
            },
        ]
    },
    "annual_stars": {"effective_year": 2026},
    "monthly_stars": {"query_at": "2027-01-10T12:00:00+08:00"},
    "xuankong_natal": {
        "house": {
            "object_id": "home",
            "facing_degrees": 255,
            "north_reference": "magnetic",
        },
        "period": {
            "basis": "construction_completion",
            "event_year": 2004,
            "evidence": "示例：立春后竣工，按竣工事件定运",
        },
    },
}
PAYLOADS["assess"] = {
    **PAYLOADS["bazhai"],
    **PAYLOADS["jinsuo"],
    **PAYLOADS["annual_stars"],
}


def payload(name):
    return deepcopy(PAYLOADS[name])
