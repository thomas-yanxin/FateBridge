"""Separate native reference conventions from physically resolved event inputs."""

from typing import Any

# Swiss documentation6.2.5/7/8/9: these partitions use MC/ARMC, fixed Aries,
# or the independently defined horizon directions, rather than a unique ASC.
ASC_INDEPENDENT_HOUSES = frozenset({"D", "N", "X", "M", "H"})


def unresolved_ascendant(subject: Any) -> bool:
    definition = (getattr(subject, "calculation_basis", None) or {}).get(
        "angle_definition"
    ) or {}
    return definition.get("geometric_ascendant_resolved") is False


def unresolved_houses(subject: Any) -> bool:
    return (
        unresolved_ascendant(subject)
        and getattr(subject, "houses_system_identifier", None)
        not in ASC_INDEPENDENT_HOUSES
    )


def reference_qualification(subject: Any) -> dict[str, Any]:
    return {
        "method_id": "native_event_reference_geometry_v1",
        "status": "underdetermined_ascendant",
        "ascendant_resolved": False,
        "house_facts_limited_by_ascendant": unresolved_houses(subject),
        "house_system": getattr(subject, "houses_system_identifier", None),
        "angle_definition": (getattr(subject, "calculation_basis", None) or {}).get(
            "angle_definition"
        ),
        "ascendant_dependent_backend_values_are_physical_reference": False,
        "midheaven_and_orbital_positions_restricted": False,
        "scope": "ASC-dependent identities, lots and scores remain unknown; retained backend conventions are replay facts only. Independently defined MC and orbital facts remain available; no input/model error bound or source-method certification.",
    }
