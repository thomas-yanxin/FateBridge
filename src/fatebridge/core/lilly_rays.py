"""Caster-directed sign tables in Lilly's 1647 edition, pp108–109.

These sign relations supplement an independently selected degree/orb aspect.
They neither change that selection nor certify an event or a judgement.
The sixteen pairs absent from both printed tables stay unclassified here.
"""

from __future__ import annotations

from typing import Any, Optional

from fatebridge.core.astro.geometry import angle_fraction
from fatebridge.core.astrology_tables import SIGNS

METHOD_ID = "lilly1647_p108_109_directed_sign_tables_v1"
SOURCE_URL = "https://wellcomecollection.org/works/s7z7c46y"

# Literal p109 inconjunct column, in zodiac order. Do not complete this table
# with every adjacent/quincunx sign, or infer positive relations from omissions.
INCONJUNCT = (
    ("Taurus", "Scorpio"),
    ("Aries", "Gemini", "Libra", "Sagittarius"),
    ("Taurus", "Scorpio"),
    ("Leo", "Aquarius"),
    ("Cancer", "Virgo", "Capricorn", "Pisces"),
    ("Leo", "Aquarius"),
    ("Scorpio", "Taurus"),
    ("Libra", "Sagittarius", "Aries", "Gemini"),
    ("Scorpio", "Taurus"),
    ("Aquarius", "Leo"),
    ("Capricorn", "Pisces", "Cancer", "Virgo"),
    ("Aquarius", "Leo"),
)

# p108: succession is sinister; against succession is dexter. Opposition is
# one undivided printed column and is not assigned a left/right direction.
RAYS = {
    2: ("sextile", "sinister"),
    3: ("square", "sinister"),
    4: ("trine", "sinister"),
    6: ("opposition", None),
    8: ("trine", "dexter"),
    9: ("square", "dexter"),
    10: ("sextile", "dexter"),
}


def directed_sign_relationship(
    caster: str,
    caster_longitude: float,
    receiver: str,
    receiver_longitude: float,
    *,
    selected_degree_aspect: Optional[str] = None,
    zodiac_type: Optional[str] = None,
) -> dict[str, Any]:
    """Read exact half-open sign cells of the supplied finite longitudes.

    Caster/receiver is the direction of a ray, not reception's host/guest.
    A same-sign bodily configuration is distinct from a sign ray (p106).
    No rounding, tolerance band or extra observational precision is introduced.
    """
    first = int((angle_fraction(caster_longitude) % 360) // 30)
    second = int((angle_fraction(receiver_longitude) % 360) // 30)
    steps = (second - first) % 12
    caster_sign, receiver_sign = SIGNS[first], SIGNS[second]
    ray, direction = RAYS.get(steps, (None, None))
    listed = receiver_sign in INCONJUNCT[first]
    status = (
        "ray"
        if ray
        else (
            "co_present"
            if steps == 0
            else "listed_inconjunct" if listed else "not_in_either_table"
        )
    )
    agrees = None
    if selected_degree_aspect is not None and status != "not_in_either_table":
        agrees = selected_degree_aspect == ("conjunction" if steps == 0 else ray)
    return {
        "method_id": METHOD_ID,
        "caster": caster,
        "receiver": receiver,
        "caster_sign": caster_sign,
        "receiver_sign": receiver_sign,
        "forward_sign_steps": steps,
        "distinct_bodies": caster != receiver,
        "relation_status": status,
        "sign_ray": ray,
        "ray_direction": direction,
        "listed_inconjunct": listed,
        "selected_degree_aspect": selected_degree_aspect,
        "selected_degree_aspect_agrees": agrees,
        "coordinate_scope": (
            "tropical_selected_edition"
            if zodiac_type in {"Tropic", "Tropical"}
            else (
                "sidereal_extension_not_original_edition_acceptance"
                if zodiac_type == "Sidereal"
                else "coordinate_system_not_qualified"
            )
        ),
        "source_pages": [106, 108, 109],
        "source_url": SOURCE_URL,
        "boundary_policy": "exact_supplied_longitudes_half_open_30_degree_signs",
        "direction_policy": "caster_to_receiver; opposition_column_undivided",
        "quantitative_bonus_added": False,
        "full_original_text_acceptance": False,
    }


def describe_sign_relationship(
    value: dict[str, Any], caster_label: str, receiver_label: str
) -> str:
    """Render only this calculated witness; do not imply perfection/strength."""
    names = {"sextile": "六合", "square": "刑", "trine": "拱", "opposition": "冲"}
    prefix = f"按Lilly1647第108–109页星座表，{caster_label}向{receiver_label}"
    if value["relation_status"] == "ray":
        side = {"dexter": "右", "sinister": "左", None: ""}[value["ray_direction"]]
        text = prefix + f"为{side}{names[value['sign_ray']]}相"
        if value["sign_ray"] == "opposition":
            text += "（原表冲相未分左右）"
    elif value["relation_status"] == "co_present":
        text = prefix + "共处同一星座；第106页的身体合相需另核对度数，不赋左右相"
    elif value["relation_status"] == "listed_inconjunct":
        text = prefix + "属于第109页列出的不相照星座对"
    else:
        text = (
            prefix
            + "既未列入第108页相照表，也未列入第109页不相照表；此处不补推正负关系"
        )
    if value["selected_degree_aspect"] is None:
        text += "；当前所选容许度内无主星度数相位候选"
    elif value["selected_degree_aspect_agrees"] is True:
        text += "；与当前所选容许度内的度数相位候选同类"
    elif value["selected_degree_aspect_agrees"] is False:
        text += "；与当前所选容许度内的度数相位候选不一致，两者分别保留"
    else:
        text += "；已有度数相位候选，但上述两表不足以核定其星座关系"
    if not value["distinct_bodies"]:
        text += "；两角色由同一主星承担，不构成两个独立行为星"
    if value["coordinate_scope"] != "tropical_selected_edition":
        text += "；该坐标系未获此版本原典接受认证"
    return text + "。此项不加权，也不据此确认成事。"
