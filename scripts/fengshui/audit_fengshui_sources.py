"""Report every source disagreement; return nonzero while any remain."""

import argparse
import hashlib
import json
from pathlib import Path

from fatebridge.validation.fengshui import (
    audit_bazhai_depth,
    audit_city_gate_reference,
    audit_classical_reference,
)
from fatebridge.validation.fengshui_angle_sources import (
    audit_angle_source_reference,
    load_angle_source_reference,
)
from fatebridge.validation.fengshui_day_calendar import (
    audit_calendar_selection_hypotheses,
    load_day_calendar_reference,
)
from fatebridge.validation.fengshui_day_hour import (
    audit_day_hour_reference,
    load_day_hour_reference,
)
from fatebridge.validation.fengshui_host_guest import (
    audit_host_guest_reference,
    load_host_guest_reference,
)
from fatebridge.validation.fengshui_lingzheng import audit_lingzheng_reference
from fatebridge.validation.fengshui_lower_clauses import (
    audit_lower_clauses,
    load_lower_clause_reference,
)
from fatebridge.validation.fengshui_lower_diagrams import (
    audit_lower_diagrams,
    load_lower_diagram_reference,
)
from fatebridge.validation.fengshui_monthly import audit_monthly_reference
from fatebridge.validation.fengshui_mutual_geometry import (
    audit_mutual_geometry_reference,
    load_mutual_geometry_reference,
)
from fatebridge.validation.fengshui_opposite import audit_opposite_reference
from fatebridge.validation.fengshui_patterns import audit_classical_patterns
from fatebridge.validation.fengshui_replacement import audit_replacement_reference
from fatebridge.validation.fengshui_replacement_diagrams import (
    audit_replacement_diagrams,
    load_replacement_diagram_reference,
)
from fatebridge.validation.fengshui_structure import audit_printed_structures
from fatebridge.validation.fengshui_timeliness import audit_timeliness_reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "tests/data/fengshui_classical_v1/reference.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--facsimile", type=Path)
    parser.add_argument(
        "--city-gate-reference",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "tests/data/fengshui_city_gate_v1/reference.json",
    )
    parser.add_argument(
        "--bazhai-depth-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "tests/data/fengshui_classical_v2",
    )
    args = parser.parse_args()
    facsimile_path = args.facsimile or args.reference.with_name("facsimile-checks.json")
    facsimile = None
    if facsimile_path.exists():
        facsimile = json.loads(facsimile_path.read_text(encoding="utf-8"))
        for item in facsimile["images"]:
            raw = (facsimile_path.parent / item["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("Facsimile page image changed")
    result = audit_classical_reference(
        json.loads(args.reference.read_text(encoding="utf-8")), facsimile
    )
    # This count covers web prose versus three earlier facsimile spots.
    # It must not erase conflicts within the separately fixed 2011 edition.
    result["unresolved_disagreement_count_scope"] = (
        "web_versus_earlier_facsimile_spot_checks_only"
    )
    lower_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_lower_clauses_v1"
    )
    result["same_edition_lower_clauses"] = audit_lower_clauses(
        load_lower_clause_reference(lower_folder),
        json.loads(args.reference.read_text(encoding="utf-8")),
    )
    diagram_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_lower_diagrams_v1"
    )
    result["complete_lower_diagrams"] = audit_lower_diagrams(
        load_lower_diagram_reference(diagram_folder)
    )
    replacement_diagram_folder = (
        Path(__file__).resolve().parents[2]
        / "tests/data/fengshui_replacement_diagrams_v1"
    )
    result["complete_replacement_diagrams"] = audit_replacement_diagrams(
        load_replacement_diagram_reference(replacement_diagram_folder)
    )
    if args.bazhai_depth_dir.exists():
        result["bazhai_depth"] = audit_bazhai_depth(
            json.loads(
                (args.bazhai_depth_dir / "you-nian-origin.json").read_text(
                    encoding="utf-8"
                )
            ),
            json.loads(
                (args.bazhai_depth_dir / "elements.json").read_text(encoding="utf-8")
            ),
        )
    city_gate_reference = json.loads(
        args.city_gate_reference.read_text(encoding="utf-8")
    )
    for item in city_gate_reference["images"]:
        if (
            hashlib.sha256(
                (args.city_gate_reference.parent / item["file"]).read_bytes()
            ).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("City gate primary page image changed")
    result["city_gate"] = audit_city_gate_reference(city_gate_reference)
    replacement_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_replacement_v1"
    )
    manifest = json.loads((replacement_folder / "hashes.json").read_text())
    for filename, digest in manifest.items():
        if (
            hashlib.sha256((replacement_folder / filename).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError(
                "Replacement primary source or numeric transcription changed"
            )
    result["replacement"] = audit_replacement_reference(
        json.loads((replacement_folder / "reference.json").read_text()),
        json.loads((replacement_folder / "wang-numeric-reference.json").read_text()),
    )
    angle_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_angle_sources_v1"
    )
    result["angle_source_research"] = audit_angle_source_reference(
        load_angle_source_reference(angle_folder)
    )
    pattern_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_patterns_v1"
    )
    pattern_manifest = json.loads((pattern_folder / "hashes.json").read_text())
    for filename, digest in pattern_manifest.items():
        if (
            hashlib.sha256((pattern_folder / filename).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("Numeric pattern original page or transcription changed")
    result["classical_patterns"] = audit_classical_patterns(
        json.loads((pattern_folder / "reference.json").read_text())
    )
    timeliness_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_timeliness_v1"
    )
    for filename, digest in json.loads(
        (timeliness_folder / "hashes.json").read_text()
    ).items():
        if (
            hashlib.sha256((timeliness_folder / filename).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("Printed timeliness transcription changed")
    result["wang_timeliness"] = audit_timeliness_reference(
        json.loads((timeliness_folder / "reference.json").read_text())
    )
    result["wang_mutual_geometry"] = audit_mutual_geometry_reference(
        load_mutual_geometry_reference(
            Path(__file__).resolve().parents[2]
            / "tests/data/fengshui_mutual_geometry_v1"
        )
    )
    result["shen_host_guest"] = audit_host_guest_reference(
        load_host_guest_reference(
            Path(__file__).resolve().parents[2] / "tests/data/fengshui_host_guest_v1"
        )
    )
    lingzheng_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_lingzheng_v1"
    )
    for filename, digest in json.loads(
        (lingzheng_folder / "hashes.json").read_text()
    ).items():
        if (
            hashlib.sha256((lingzheng_folder / filename).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("零正原文数字转录改变")
    result["fixed_lingzheng"] = audit_lingzheng_reference(
        json.loads((lingzheng_folder / "reference.json").read_text())
    )
    structure_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_structure_reading_v1"
    )
    structure_reference = structure_folder / "printed-charts.json"
    if (
        hashlib.sha256(structure_reference.read_bytes()).hexdigest()
        != "66e4dc34c1d6eba8ced19705d6e68a11f2ae31efa5e71bde243faad05b044e98"
    ):
        raise ValueError("Printed independent structure reference changed")
    result["printed_structures"] = audit_printed_structures(
        json.loads((structure_folder / "printed-charts.json").read_text())
    )
    opposite_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_opposite_v1"
    )
    for filename, digest in json.loads(
        (opposite_folder / "hashes.json").read_text()
    ).items():
        if (
            hashlib.sha256((opposite_folder / filename).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("对宫原书配对转录改变")
    result["opposite_star_comparison"] = audit_opposite_reference(
        json.loads((opposite_folder / "reference.json").read_text()),
        json.loads((structure_folder / "printed-charts.json").read_text()),
    )
    monthly_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_monthly_v1"
    )
    for filename, expected in json.loads(
        (monthly_folder / "hashes.json").read_text()
    ).items():
        if (
            hashlib.sha256((monthly_folder / filename).read_bytes()).hexdigest()
            != expected
        ):
            raise ValueError("月紫白原表或转录改变")
    result["monthly_purple_white"] = audit_monthly_reference(
        json.loads((monthly_folder / "reference.json").read_text())
    )
    day_hour_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_day_hour_tables_v1"
    )
    result["day_hour_table_research"] = audit_day_hour_reference(
        load_day_hour_reference(day_hour_folder)
    )
    calendar_folder = (
        Path(__file__).resolve().parents[2] / "tests/data/fengshui_day_calendar_v1"
    )
    result["day_hour_calendar_selection_research"] = (
        audit_calendar_selection_hypotheses(
            load_day_calendar_reference(calendar_folder),
            load_day_hour_reference(day_hour_folder),
        )
    )
    # The source gate includes these local table checks. Their success still
    # does not verify civil-date selection or a complete daily/hourly tool.
    result["all_scoped_source_checks_passed"] = (
        result["numeric_clause_acceptance_passed"]
        and result["same_edition_lower_clauses"][
            "complete_printed_clause_acceptance_passed"
        ]
        and result["complete_lower_diagrams"]["complete_diagram_acceptance_passed"]
        and result["complete_replacement_diagrams"][
            "complete_diagram_acceptance_passed"
        ]
        and result.get("bazhai_depth", {}).get("scoped_acceptance_passed", False)
        and result["city_gate"]["scoped_acceptance_passed"]
        and result["replacement"]["scoped_acceptance_passed"]
        and result["angle_source_research"]["declared_composition_agreement"]
        # Cross-source geometry and predicates do not certify the original
        # source's units, origin, exceptions or exact boundary policy.
        and result["angle_source_research"]["source_angle_applicability_verified"]
        and result["classical_patterns"]["scoped_acceptance_passed"]
        and result["wang_timeliness"]["scoped_acceptance_passed"]
        and result["wang_mutual_geometry"]["scoped_geometry_acceptance_passed"]
        and result["shen_host_guest"]["scoped_operation_definitions_passed"]
        and result["shen_host_guest"]["complete_literal_relation_acceptance_passed"]
        and result["wang_timeliness"]["chapter_consistency_established"]
        and result["fixed_lingzheng"]["scoped_acceptance_passed"]
        and result["printed_structures"]["scoped_acceptance_passed"]
        and result["opposite_star_comparison"]["scoped_acceptance_passed"]
        and result["monthly_purple_white"]["numeric_scoped_acceptance_passed"]
        and result["monthly_purple_white"]["printed_calendar_labels_all_conform"]
        and result["day_hour_table_research"][
            "table_arithmetic_and_shared_flight_conform"
        ]
        # This is a civil-calendar comparison only. Successful astronomical
        # inputs cannot award either selection hypothesis source conformity.
        and result["day_hour_calendar_selection_research"][
            "independent_calendar_comparison_passed"
        ]
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["all_scoped_source_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
