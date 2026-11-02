"""Sitting-trigram house chart and separately scoped personal charts."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
from fatebridge.core.divination import BAGUA_BY_NAME
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL

from .bazhai_interpretation import palace_star_relationship, you_nian_trace
from .bearing_support import sitting_support
from .calendar import (
    boundary_candidate_dates,
    boundary_model_policy,
    lichun_resolution,
    year_context,
)
from .directions import rule_data, sitting_from_facing, wrap9
from .models import BazhaiRequest, House, MingguaRequest


def placement_polarity(purpose: str, aspect: str) -> str:
    """One rule for current findings and inverse direction calculations."""
    return (
        "inauspicious" if purpose == "stove" and aspect == "location" else "auspicious"
    )


def placement_application(
    palace: Dict[str, Any], purpose: str, aspect: str
) -> Dict[str, Any]:
    """The same scoped evidence for a current or proposed direction."""
    expected = placement_polarity(purpose, aspect)
    return {
        "star": palace["star"],
        "expected_polarity": expected,
        "matches_convention": palace["star"]["polarity"] == expected,
        "matches_convention_scope": "basic_star_polarity_only_not_element_or_whole_house_verdict",
        "you_nian_trace": palace["you_nian_trace"],
        "palace_star_relationship": palace["palace_star_relationship"],
        "rule_id": (
            "bazhai_sitting_v1.stove_seat_fire_mouth"
            if purpose == "stove"
            else "bazhai_sitting_v1.placement_application"
        ),
        "source_ids": ["S3"],
        "application_scope": "selected_ruleset_convention",
    }


def sectors(base: str, subject_id: str, basis: str) -> Dict[str, Any]:
    bits = {
        name: sum(bit << i for i, bit in enumerate(info["lines"]))
        for name, info in BAGUA_BY_NAME.items()
    }
    stars = rule_data("bazhai_stars")
    return {
        direction: {
            **info,
            "star": stars[str(bits[base] ^ bits[info["trigram"]])],
            "changed_line_mask": bits[base] ^ bits[info["trigram"]],
            "you_nian_trace": you_nian_trace(bits[base], bits[info["trigram"]]),
            "palace_star_relationship": palace_star_relationship(
                info["element"],
                stars[str(bits[base] ^ bits[info["trigram"]])]["name"],
                stars[str(bits[base] ^ bits[info["trigram"]])]["element"],
            ),
            "base_trigram": base,
            "subject_id": subject_id,
            "basis": basis,
            "method": "bazhai",
            "rule_id": "bazhai_sitting_v1.dayounian_xor",
            "source_ids": ["S3"],
        }
        for direction, info in rule_data("directions").items()
    }


def minggua(req: MingguaRequest, subject_id: str = "occupant") -> Dict[str, Any]:
    time = year_context(
        req.effective_birth_year,
        req.birth_at,
        req.timezone_name,
        req.year_boundary,
        resolve_interval=req.birth_at is not None,
    )
    year = time["effective_year"]
    missing = []
    if time.get("effective_year_status") == "requires_confirmation":
        year = None
        missing.append(
            f"occupants.{subject_id}.confirmed_effective_birth_year_due_to_boundary_precision"
        )
    if req.birth_date is not None:
        day = req.birth_date
        resolution = (
            lichun_resolution(day.year, req.timezone_name)
            if req.year_boundary == "lichun"
            else None
        )
        boundary_day = (
            date.fromisoformat(resolution["moment"][:10]) if resolution else None
        )
        # Do not certify a boundary date from the linear fallback. The adjacent
        # days are conservatively held for a confirmed effective birth year.
        uncertain_boundary = bool(
            resolution
            and boundary_day is not None
            and day in boundary_candidate_dates(resolution, req.timezone_name)
            and (resolution["approximate"] or day != boundary_day)
        )
        year = (
            None
            if day == boundary_day or uncertain_boundary
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
            policy = boundary_model_policy(resolution)
            if uncertain_boundary and policy is not None:
                model_name = (
                    "moshier"
                    if policy["ephemeris_model"] == "moshier"
                    else (
                        "vsop2013_solar"
                        if policy["ephemeris_model"] == VSOP2013_SOLAR_MODEL
                        else (
                            "aa1996_solar"
                            if policy["ephemeris_model"] == AA1996_SOLAR_MODEL
                            else "analytic_solar"
                        )
                    )
                )
                time["boundary_precision_policy"] = {
                    **policy,
                    "reason": model_name
                    + "_guard_crosses_civil_date_not_fabricated_birth_hour",
                    "boundary_possible_civil_dates": sorted(
                        d.isoformat()
                        for d in boundary_candidate_dates(resolution, req.timezone_name)
                    ),
                }
        if year is None:
            missing.append(
                f"occupants.{subject_id}.confirmed_effective_birth_year_due_to_boundary_precision"
                if uncertain_boundary
                else f"occupants.{subject_id}.birth_at_on_year_boundary"
            )
    if year is None:
        if not missing:
            missing.append(f"occupants.{subject_id}.birth_at_or_effective_birth_year")
    if req.gender_convention is None:
        missing.append(f"occupants.{subject_id}.gender_convention")
    candidates: List[Dict[str, Any]] = []
    if year is not None:
        for convention in (
            [req.gender_convention] if req.gender_convention else ["male", "female"]
        ):
            raw = wrap9(
                1 - (year - 1864) if convention == "male" else 5 + (year - 1864)
            )
            number = (2 if convention == "male" else 8) if raw == 5 else raw
            trigram = next(
                i["trigram"]
                for i in rule_data("directions").values()
                if i["palace_number"] == number
            )
            candidates.append(
                {
                    "gender_convention": convention,
                    "raw_number": raw,
                    "palace_number": number,
                    "substitution": raw == 5,
                    "trigram": trigram,
                    "group": "east" if number in {1, 3, 4, 9} else "west",
                    "sectors": sectors(trigram, subject_id, "personal_minggua"),
                    "rule_id": "bazhai_sitting_v1.minggua_1864",
                    "source_ids": ["S2", "S4"],
                    "trace": {
                        "epoch_year": 1864,
                        "elapsed_years": year - 1864,
                        "raw_five_mapped_after_cycle": True,
                    },
                }
            )
    return {
        "status": "partial" if missing else "complete",
        "subject_id": subject_id,
        "time_context": time,
        "candidates": candidates,
        "missing_inputs": missing,
    }


def _house_inputs(req: BazhaiRequest) -> Tuple[Optional[House], float, str, str]:
    # Assess is a BazhaiRequest subclass. Its optional natal branch describes
    # the same physical house, as enforced by the assessment input contract.
    natal = getattr(req, "xuankong", None)
    house = req.house or (natal.house if natal is not None else None)
    origin = "house" if req.house is not None else "xuankong.house"
    if house is not None and house.bearing_uncertainty_degrees is not None:
        return (
            house,
            house.bearing_uncertainty_degrees,
            origin,
            origin + ".bearing_uncertainty_degrees",
        )
    if natal is not None and natal.bearing_uncertainty_degrees is not None:
        return (
            house,
            natal.bearing_uncertainty_degrees,
            origin,
            "xuankong.bearing_uncertainty_degrees",
        )
    return house, 0, origin, "not_provided_point_input_convention"


def bazhai(req: BazhaiRequest) -> Dict[str, Any]:
    house = None
    house_candidates: List[Dict[str, Any]] = []
    orientation = None
    missing: List[str] = []
    declared_house, radius, origin, radius_source = _house_inputs(req)
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
                            "candidate_id": "house-sitting:" + trigram,
                            "candidate_only": ambiguous,
                            "bearing_support": {
                                **support,
                                "policy_id": "house_bearing_closed_interval_v1",
                                "policy_version": "1.0.0",
                                "author": "FateBridge",
                                "source_ids": ["S4"],
                                "source_scope": "direction_mapping_only; interval_policy_is_engineering",
                                "arithmetic": "exact_rational_values_of_supplied_binary_floats",
                                "coordinate_system": "unwrapped_about_normalized_reported_facing",
                                "scope": "input_interval_support_not_probability_or_site_measurement_certification",
                            },
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
                    "uncertainty_input_path": radius_source,
                    "north_reference": data["north_reference"],
                    "confirmed_sitting_trigram": sitting,
                    "policy_id": "house_bearing_closed_interval_v1",
                    "policy_version": "1.0.0",
                    "author": "FateBridge",
                    "zero_radius_policy": "existing_left_closed_right_open_point_convention",
                    "positive_radius_policy": "closed_interval_all_intersecting_sectors",
                    "scope": "bounded_input_not_certified_site_error_or_WMM_sigma_interval",
                }
                if ambiguous:
                    missing.append("house.unambiguous_sitting_trigram")
                else:
                    house = house_candidates[0]
            else:
                sitting = bearing["trigram"]
                data["sitting_bearing"] = bearing
        if sitting is not None and not house_candidates:
            house = {
                **data,
                "sitting_trigram": sitting,
                "sectors": sectors(sitting, data["object_id"], "house_sitting_trigram"),
            }
    if house is None and not house_candidates:
        missing.append("house.sitting_trigram_or_confirmed_facing")
    occupants = [minggua(o, o.subject_id) for o in req.occupants]
    for o in occupants:
        missing.extend(o["missing_inputs"])
    if not occupants:
        missing.append("occupants")
    findings = []
    for placement in req.placements:
        if placement.location_direction is None:
            missing.append(f"placements.{placement.object_id}.location_direction")
        bases = []
        if house_candidates:
            for candidate in house_candidates:
                bases.append(
                    (
                        candidate["object_id"],
                        "house",
                        candidate["sectors"],
                        None,
                        {
                            "house_candidate_id": candidate["candidate_id"],
                            "house_sitting_trigram": candidate["sitting_trigram"],
                        },
                        candidate["candidate_only"],
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
                            c["gender_convention"],
                            {},
                            o["status"] == "partial",
                        )
                    )
        for (
            subject_id,
            basis,
            chart,
            convention,
            candidate_context,
            candidate_only,
        ) in bases:
            for aspect, direction in [
                ("location", placement.location_direction),
                ("facing", placement.facing_direction),
            ]:
                if direction is None:
                    continue
                entry = chart[direction]
                findings.append(
                    {
                        "method": "bazhai",
                        "subject_id": subject_id,
                        "subject_kind": basis,
                        "gender_convention": convention,
                        **candidate_context,
                        "object_id": placement.object_id,
                        "purpose": placement.purpose,
                        "aspect": aspect,
                        "facing_role": (
                            placement.facing_role if aspect == "facing" else None
                        ),
                        "direction": direction,
                        **placement_application(entry, placement.purpose, aspect),
                        "observation_basis": placement.observation_basis,
                        "candidate_only": candidate_only,
                    }
                )
    if (
        req.placements
        and house is None
        and not house_candidates
        and not any(o["candidates"] for o in occupants)
    ):
        missing.append("placements.usable_house_or_personal_chart")
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
        "missing_inputs": missing,
    }
