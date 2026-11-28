"""BaZhai sitting-trigram charts, 1864 MingGua, YouNian element relations, and YangZhai SanYao."""

from __future__ import annotations

from typing import Any

from fatebridge.core.divination import BAGUA_BY_NAME
from fatebridge.core.fengshui.calendar import (
    boundary_dates,
    boundary_model_policy,
    lichun_resolution,
    year_context,
)
from fatebridge.core.fengshui.directions import (
    raw_rule_data,
    sitting_from_facing,
    sitting_from_mountain,
    sitting_support,
    wrap9,
)
from fatebridge.core.fengshui.models import BazhaiRequest, House, MingguaRequest
from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES

_FLIPS = (3, 2, 1, 2, 3, 2, 1)
_MASKS = (0, 4, 6, 7, 5, 1, 3, 2)
_EAST_TRIGRAMS = frozenset({"坎", "离", "震", "巽"})
_TRIGRAM_BITS = {
    name: sum(bit << i for i, bit in enumerate(info["lines"]))
    for name, info in BAGUA_BY_NAME.items()
}


def you_nian_trace(base_bits: int, target_bits: int) -> dict[str, Any]:
    mask = base_bits ^ target_bits
    step = _MASKS.index(mask)
    changed = [line for line in (1, 2, 3) if mask & (1 << (line - 1))]
    return {
        "operation_count": step,
        "cumulative_flip_sequence": list(_FLIPS[:step]),
        "net_changed_lines": changed,
        "net_changed_line_count": len(changed),
        "changed_line_mask": mask,
    }


def palace_star_relationship(
    palace_element: str, star_name: str, star_element: str
) -> dict[str, Any]:
    if palace_element == star_element:
        code, label = "same_element", "宫星比和"
    elif ELEMENT_GENERATES[palace_element] == star_element:
        code, label = "palace_generates_star", "宫生星"
    elif ELEMENT_GENERATES[star_element] == palace_element:
        code, label = "star_generates_palace", "星生宫"
    elif ELEMENT_CONTROLS[palace_element] == star_element:
        code, label = "palace_controls_star", "宫克星"
    else:
        code, label = "star_controls_palace", "星克宫"
    return {
        "palace_element": palace_element,
        "star_element": star_element,
        "star_name": star_name,
        "relationship": code,
        "traditional_label": label,
    }


def placement_polarity(purpose: str, aspect: str) -> str:
    return (
        "inauspicious" if purpose == "stove" and aspect == "location" else "auspicious"
    )


def placement_application(
    palace: dict[str, Any], purpose: str, aspect: str
) -> dict[str, Any]:
    expected = placement_polarity(purpose, aspect)
    return {
        "star": palace["star"],
        "expected_polarity": expected,
        "matches_convention": palace["star"]["polarity"] == expected,
        "palace_star_relation": palace["palace_star_relation"],
    }


def sectors(base: str, subject_id: str, basis: str) -> dict[str, Any]:
    stars = raw_rule_data("bazhai_stars")
    directions = raw_rule_data("directions")
    base_bits = _TRIGRAM_BITS[base]
    result: dict[str, Any] = {}
    for direction, info in directions.items():
        mask = base_bits ^ _TRIGRAM_BITS[info["trigram"]]
        star = stars[str(mask)]
        step = _MASKS.index(mask)
        rel = palace_star_relationship(info["element"], star["name"], star["element"])
        result[direction] = {
            "star": star,
            "changed_line_mask": mask,
            "operation_count": step,
            "palace_star_relation": rel["traditional_label"],
        }
    return result


def _trigram_pair_relation(
    from_role: str, from_trigram: str, to_role: str, to_trigram: str
) -> dict[str, Any]:
    """Compute YouNian star and five-element relation between two SanYao trigrams."""
    stars = raw_rule_data("bazhai_stars")
    star = stars[str(_TRIGRAM_BITS[from_trigram] ^ _TRIGRAM_BITS[to_trigram])]
    from_elem = BAGUA_BY_NAME[from_trigram]["element"]
    to_elem = BAGUA_BY_NAME[to_trigram]["element"]
    if from_elem == to_elem:
        elem_rel, elem_label = "same_element", f"{from_role}{to_role}比和"
    elif ELEMENT_GENERATES[from_elem] == to_elem:
        elem_rel, elem_label = "first_generates_second", f"{from_role}生{to_role}"
    elif ELEMENT_GENERATES[to_elem] == from_elem:
        elem_rel, elem_label = "second_generates_first", f"{to_role}生{from_role}"
    elif ELEMENT_CONTROLS[from_elem] == to_elem:
        elem_rel, elem_label = "first_controls_second", f"{from_role}克{to_role}"
    else:
        elem_rel, elem_label = "second_controls_first", f"{to_role}克{from_role}"
    return {
        "from_trigram": from_trigram,
        "to_trigram": to_trigram,
        "from_element": from_elem,
        "to_element": to_elem,
        "younian_star": star,
        "element_relation": elem_rel,
        "element_label": elem_label,
        "same_group": (from_trigram in _EAST_TRIGRAMS)
        == (to_trigram in _EAST_TRIGRAMS),
    }


def yangzhai_sanyao(
    house_sitting_trigram: str | None, placements: list[Any]
) -> dict[str, Any] | None:
    """Evaluate 《阳宅三要》 (门/主/灶) trigram relations & East/West 4-house coherence."""
    directions = raw_rule_data("directions")
    role_dirs: dict[str, str] = {}
    for p in placements:
        if p.location_direction is None:
            continue
        if p.purpose == "door" and "door" not in role_dirs:
            role_dirs["door"] = p.location_direction
        elif p.purpose == "bed" and "master_room" not in role_dirs:
            role_dirs["master_room"] = p.location_direction
        elif p.purpose == "stove" and "stove" not in role_dirs:
            role_dirs["stove"] = p.location_direction

    if not role_dirs:
        return None

    nodes: dict[str, dict[str, Any]] = {}
    if house_sitting_trigram is not None:
        nodes["house_sitting"] = {
            "trigram": house_sitting_trigram,
            "element": BAGUA_BY_NAME[house_sitting_trigram]["element"],
            "group": "east" if house_sitting_trigram in _EAST_TRIGRAMS else "west",
        }
    for role, direction in role_dirs.items():
        info = directions[direction]
        tri = info["trigram"]
        nodes[role] = {
            "direction": direction,
            "trigram": tri,
            "element": info["element"],
            "group": "east" if tri in _EAST_TRIGRAMS else "west",
        }

    groups = {n["group"] for n in nodes.values()}
    coherence = (
        "east_four_coherent"
        if groups == {"east"}
        else "west_four_coherent" if groups == {"west"} else "east_west_mixed"
    )
    relations: dict[str, Any] = {}
    if "door" in nodes and "master_room" in nodes:
        relations["door_to_master"] = _trigram_pair_relation(
            "门", nodes["door"]["trigram"], "主", nodes["master_room"]["trigram"]
        )
    if "master_room" in nodes and "stove" in nodes:
        relations["master_to_stove"] = _trigram_pair_relation(
            "主", nodes["master_room"]["trigram"], "灶", nodes["stove"]["trigram"]
        )
    if "door" in nodes and "stove" in nodes:
        relations["door_to_stove"] = _trigram_pair_relation(
            "门", nodes["door"]["trigram"], "灶", nodes["stove"]["trigram"]
        )
    return {
        "nodes": nodes,
        "east_west_coherence": coherence,
        "relations": relations,
        "complete_sanyao": all(
            k in role_dirs for k in ("door", "master_room", "stove")
        ),
    }


def minggua(req: MingguaRequest, subject_id: str = "occupant") -> dict[str, Any]:
    time = year_context(
        req.birth_year,
        req.birth_at,
        req.timezone_name,
        req.year_boundary,
        resolve_interval=req.birth_at is not None,
    )
    year = time["effective_year"]
    missing = []
    required_year_input = "birth_at_or_birth_year"
    if time.get("effective_year_status") == "requires_confirmation":
        year = None
        required_year_input = (
            "confirmed_birth_year_due_to_undefined_local_clock"
            if req.year_boundary == "january_1"
            else "confirmed_birth_year_due_to_boundary_precision"
        )
    if req.birth_date is not None:
        day = req.birth_date
        resolution = (
            lichun_resolution(day.year, req.timezone_name)
            if req.year_boundary == "lichun"
            else None
        )
        projected_boundary = (
            boundary_dates(resolution, req.timezone_name)
            if resolution is not None
            else None
        )
        unresolved_boundary_date = resolution is not None and projected_boundary is None
        boundary_day, possible_dates = projected_boundary or (None, set())
        uncertain_boundary = bool(
            resolution
            and boundary_day is not None
            and day in possible_dates
            and day != boundary_day
        )
        year = (
            None
            if unresolved_boundary_date or day == boundary_day or uncertain_boundary
            else day.year - int(boundary_day is not None and day < boundary_day)
        )
        time = {
            "effective_year": year,
            "year_boundary": req.year_boundary,
            "timezone_name": req.timezone_name,
            "input_basis": "civil_date_no_fabricated_birth_hour",
            "birth_date": day.isoformat(),
        }
        if resolution is not None:
            time["boundary_resolution"] = resolution
            policy = boundary_model_policy(resolution, date_only=True)
            if uncertain_boundary and policy is not None:
                time["boundary_precision_policy"] = {
                    **policy,
                    "boundary_possible_civil_dates": sorted(
                        d.isoformat() for d in possible_dates
                    ),
                }
        if unresolved_boundary_date:
            time["effective_year_status"] = "requires_confirmation"
            required_year_input = "confirmed_birth_year_due_to_undefined_local_clock"
        elif uncertain_boundary:
            required_year_input = "confirmed_birth_year_due_to_boundary_precision"
        else:
            required_year_input = "birth_at_on_year_boundary"
    if year is None:
        missing.append(f"occupants.{subject_id}.{required_year_input}")
    if req.gender is None:
        missing.append(f"occupants.{subject_id}.gender")

    candidates: list[dict[str, Any]] = []
    if year is not None:
        directions = raw_rule_data("directions")
        for convention in [req.gender] if req.gender else ["male", "female"]:
            raw = wrap9(
                1 - (year - 1864) if convention == "male" else 5 + (year - 1864)
            )
            number = (2 if convention == "male" else 8) if raw == 5 else raw
            trigram = next(
                i["trigram"]
                for i in directions.values()
                if i["palace_number"] == number
            )
            candidates.append(
                {
                    "gender": convention,
                    "raw_number": raw,
                    "palace_number": number,
                    "substitution": raw == 5,
                    "trigram": trigram,
                    "group": "east" if number in {1, 3, 4, 9} else "west",
                    "sectors": sectors(trigram, subject_id, "personal_minggua"),
                }
            )
    return {
        "status": "partial" if missing else "complete",
        "subject_id": subject_id,
        "time_context": time,
        "candidates": candidates,
        "missing_inputs": missing,
    }


def _house_inputs(req: BazhaiRequest) -> tuple[House | None, float, str]:
    natal = getattr(req, "xuankong", None)
    house = req.house or (natal.house if natal is not None else None)
    origin = "house" if req.house is not None else "xuankong.house"
    radius = (
        house.bearing_uncertainty_degrees
        if (house and house.bearing_uncertainty_degrees is not None)
        else 0.0
    )
    return house, radius, origin


def bazhai(req: BazhaiRequest) -> dict[str, Any]:
    house = None
    house_candidates: list[dict[str, Any]] = []
    orientation = None
    missing: list[str] = []
    declared_house, radius, origin = _house_inputs(req)
    directions = raw_rule_data("directions")

    if declared_house is not None:
        data = declared_house.model_dump(exclude={"bearing_uncertainty_degrees"})
        sitting = data["sitting_trigram"]
        if data["facing_degrees"] is not None:
            bearing = sitting_from_facing(
                data["facing_degrees"], data["north_reference"]
            )
            data["facing_degrees"] %= 360
            if radius > 0:
                supported = sitting_support(
                    data["facing_degrees"], radius, data["north_reference"]
                )
                if sitting is not None:
                    supported = [
                        s for s in supported if s["sitting_trigram"] == sitting
                    ]
                if not supported:
                    raise ValueError("宅向误差区间与已确认 sitting_trigram 不一致")
                ambiguous = len(supported) > 1
                for support in supported:
                    trigram = support["sitting_trigram"]
                    house_candidates.append(
                        {
                            **data,
                            "sitting_trigram": trigram,
                            "candidate_id": f"house-sitting:{trigram}",
                            "candidate_only": ambiguous,
                            "bearing_support": support,
                            "sectors": sectors(
                                trigram, data["object_id"], "house_sitting_trigram"
                            ),
                        }
                    )
                orientation = {
                    "status": (
                        "candidate_only" if ambiguous else "resolved_sitting_trigram"
                    ),
                    "house_input_path": origin,
                    "nominal_facing_degrees": data["facing_degrees"],
                    "nominal_sitting_bearing": bearing,
                    "bearing_uncertainty_degrees": radius,
                }
                if ambiguous:
                    missing.append("house.unambiguous_sitting_trigram")
                else:
                    house = house_candidates[0]
            else:
                sitting = bearing["trigram"]
                data["sitting_bearing"] = bearing
        elif data.get("facing_mountain") is not None:
            mountain_bearing = sitting_from_mountain(data["facing_mountain"])
            sitting = mountain_bearing["trigram"]
            data["sitting_bearing"] = mountain_bearing
        if sitting is not None and not house_candidates:
            house = {
                **data,
                "sitting_trigram": sitting,
                "sectors": sectors(sitting, data["object_id"], "house_sitting_trigram"),
            }
    if house is None and not house_candidates:
        missing.append("house.sitting_trigram_or_confirmed_facing")

    occupants = [minggua(o, o.subject_id or "occupant") for o in req.occupants]
    for o in occupants:
        missing.extend(o["missing_inputs"])
    if not occupants:
        missing.append("occupants")

    findings = []
    for placement in req.placements:
        assert placement.object_id is not None
        if placement.location_direction is None:
            missing.append(f"placements.{placement.object_id}.location_direction")
        bases = []
        if house_candidates:
            for cand in house_candidates:
                bases.append(
                    (
                        cand["object_id"],
                        "house",
                        cand["sectors"],
                        None,
                        {"house_candidate_id": cand["candidate_id"]},
                        cand["candidate_only"],
                    )
                )
        elif house is not None:
            bases.append(
                (house["object_id"], "house", house["sectors"], None, {}, False)
            )
        for o in occupants:
            if placement.applies_to_occupant(o["subject_id"]):
                for c in o["candidates"]:
                    bases.append(
                        (
                            o["subject_id"],
                            "occupant",
                            c["sectors"],
                            c["gender"],
                            {},
                            o["status"] == "partial",
                        )
                    )
        for subject_id, basis, chart, convention, cand_ctx, cand_only in bases:
            for aspect, direction in (
                ("location", placement.location_direction),
                ("facing", placement.facing_direction),
            ):
                if direction is None:
                    continue
                finding: dict[str, Any] = {
                    "subject_id": subject_id,
                    "subject_kind": basis,
                    **({"gender": convention} if convention is not None else {}),
                    **cand_ctx,
                    "object_id": placement.object_id,
                    "purpose": placement.purpose,
                    "aspect": aspect,
                    **(
                        {"facing_role": placement.facing_role}
                        if aspect == "facing" and placement.facing_role
                        else {}
                    ),
                    "direction": direction,
                    **placement_application(
                        chart[direction], placement.purpose, aspect
                    ),
                }
                if cand_only:
                    finding["candidate_only"] = True
                findings.append(finding)
    if (
        req.placements
        and house is None
        and not house_candidates
        and not any(o["candidates"] for o in occupants)
    ):
        missing.append("placements.usable_house_or_personal_chart")

    sanyao = yangzhai_sanyao(
        house["sitting_trigram"] if house else None, req.placements
    )
    return {
        "status": "partial" if missing else "complete",
        "house": house,
        **(
            {
                "house_candidates": house_candidates,
                "house_orientation_context": orientation,
            }
            if house_candidates
            else {}
        ),
        "occupants": occupants,
        "placement_findings": findings,
        **({"yangzhai_sanyao": sanyao} if sanyao is not None else {}),
        "missing_inputs": missing,
    }
