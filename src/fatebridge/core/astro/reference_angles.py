"""Carry angle-model qualifications into dependent specialty geometry.

Formal contacts can be computed from a backend convention. That does not
resolve a physical Ascendant when the shared angle model says it cannot.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

UNRESOLVED_REFERENCE_BASES = frozenset(
    {"backend_numeric_convention_only", "geographic_pole_meridian_convention"}
)


def reference_angle_basis(
    definition: Mapping[str, Any] | None, name: str
) -> str | None:
    if not definition:
        return None
    if name == "Ascendant":
        basis = definition.get("retained_ascendant_role", definition["status"])
        if basis is None or isinstance(basis, str):
            return basis
        raise ValueError("Reference-angle basis must be a string or unknown")
    if (
        name == "Midheaven"
        and definition["status"] == "geographic_pole_meridian_convention"
    ):
        return "geographic_pole_meridian_convention"
    return None


def qualify_reference_geometry(
    geometry: Dict[str, Any], definition: Mapping[str, Any] | None
) -> None:
    """Annotate only rows that actually depend on a qualified reference angle."""
    if not definition:
        return

    def qualify(row: Dict[str, Any], names: list[str]) -> None:
        bases = {
            name: basis
            for name in names
            if (basis := reference_angle_basis(definition, name)) is not None
        }
        if bases:
            row["reference_angle_basis"] = bases
            row["physical_reference_geometry_resolved"] = not any(
                basis in UNRESOLVED_REFERENCE_BASES for basis in bases.values()
            )

    def qualify_reading(row: Dict[str, Any]) -> None:
        qualify(row, list(row.get("factor_longitudes", {})))
        if row.get("physical_reference_geometry_resolved") is False:
            row.setdefault("backend_reading_zh", row["reading_zh"])
            row["source_application_status"] = "underdetermined_reference_geometry"
            row["reading_zh"] = (
                "这条原文解释依赖未解析的物理参考；当前仅有后端约定下的形式条件，"
                "不能据此判定该主题适用。"
            )

    for row in geometry.get("midpoint_axes", []):
        qualify(row, [row["id_a"], row["id_b"]])
    for dial in geometry.get("dials", {}).values():
        for field in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            for row in dial[field]:
                qualify(
                    row,
                    [
                        row[k]
                        for k in ("point", "id_a", "id_b", "id_c", "id_d")
                        if k in row
                    ],
                )
                if "sensitive_point" in row and "reference_angle_basis" in row:
                    row["sensitive_point"].update(
                        reference_angle_basis=row["reference_angle_basis"],
                        physical_reference_geometry_resolved=row[
                            "physical_reference_geometry_resolved"
                        ],
                    )
                if "source_interpretation" in row:
                    qualify_reading(row["source_interpretation"])
    for row in geometry.get("interpretations", []):
        qualify_reading(row)
