"""Audit seasonal source components and sparse output fidelity independently.

Named course formulae, last-eighteen-days partitioning and comprehensive
judgments remain unadjudicated. Symbolic boards are not civil calendar evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from scripts.ren.audit_liuren_seasonal import BRANCHES
from scripts.ren.audit_liuren_seasonal import reference as seasonal_reference
from scripts.ren.audit_liuren_seasonal import seed_for

ROOT = Path(__file__).resolve().parents[2]
OUTLINE = ROOT / "tests/fixtures/liuren_seasonal_outline_v1"
FIDELITY = ROOT / "tests/fixtures/liuren_seasonal_fidelity_v1"
OUTLINE_PIN = "878ea9938b2998167eb812c13c3f8bfd3a74d680d3c70ad88c8aeb8b656a809f"
FIDELITY_PIN = "dd6059d6ba0a6f4fdbd5137ef763082601ba54e7fbc6642d1f8d019edbc4f84d"
BASELINE_PIN = "43b0c59c85cd1b95c683463886972331b86bcdbc456bca31f72905032a786c3c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def frozen(folder: Path, pin: str, names: set[str]) -> None:
    if sha(folder / "freeze.json") != pin:
        raise ValueError("Seasonal source manifest identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest) != names or {p.name for p in folder.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Seasonal source inventory changed")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Seasonal source bytes changed")


def outline_reference(folder: Path = OUTLINE) -> dict[str, Any]:
    frozen(
        folder,
        OUTLINE_PIN,
        {
            "readings.json",
            "protocol.json",
            "page-112.png",
            "page-113.jpg",
            "page-114.png",
        },
    )
    value: dict[str, Any] = json.loads((folder / "readings.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/liuren_course_conditions_v1/source.pdf")
        != value["source_sha256"]
    ):
        raise ValueError("Original source PDF identity changed")
    if (
        [g["id"] for g in value["course_groups"]] != ["Q056", "Q057", "Q058", "Q059"]
        or value["full_named_predicate_adjudicated"] is not False
        or value["upper_role_quantifier_adjudicated"] is not False
        or value["transformation_confirmed"] is not None
    ):
        raise ValueError("Original four source groups or unresolved scope changed")
    return value


def fidelity_reference(folder: Path = FIDELITY) -> dict[str, Any]:
    frozen(folder, FIDELITY_PIN, {"reference.json", "protocol.json"})
    value: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    literal = seasonal_reference()
    if (
        len(value["days"]) != 60
        or value["literal_phase_table"] != literal["literal_phase_table"]
        or value["declared_month_partition"] != literal["declared_month_partition"]
        or value["stem_elements"] != literal["stem_elements"]
    ):
        raise ValueError("Independent seasonal literals or input denominator changed")
    return value


def audit_outline() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = outline_reference()
    ref = seasonal_reference()
    # Import the producer only after verifying independent, previously frozen labels.
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_seasonal import MONTH_PARTITION, POWERS

    failures: list[dict[str, Any]] = []
    counts = dict(
        literal_cells=0,
        course_phase_components=0,
        month_components=0,
        boards=0,
        rows=0,
        objects=0,
        board_course_components=0,
    )
    ledger = hashlib.sha256()

    def check(kind: str, key: Any, actual: Any, expected: Any) -> None:
        ledger.update(canonical([kind, key, actual, expected]))
        if actual != expected:
            failures.append(dict(kind=kind, key=key, actual=actual, expected=expected))

    for season, table in ref["literal_phase_table"].items():
        for phase, expected_power in table.items():
            counts["literal_cells"] += 1
            actual_power = POWERS[season][phase]
            check("literal_power", [season, phase], actual_power, expected_power)
            for group in source["course_groups"]:
                counts["course_phase_components"] += 1
                check(
                    "course_phase",
                    [group["id"], season, phase],
                    actual_power in group["same_power_category"],
                    phase in group["phases"][season],
                )
    check(
        "declared_month_partition",
        None,
        MONTH_PARTITION,
        ref["declared_month_partition"],
    )
    for month, season in ref["declared_month_partition"].items():
        for phase in ref["literal_phase_table"][season]:
            for group in source["course_groups"]:
                counts["month_components"] += 1
                check(
                    "month_component",
                    [month, group["id"], phase],
                    POWERS[MONTH_PARTITION[month]][phase]
                    in group["same_power_category"],
                    phase in group["phases"][season],
                )
    boards = []
    for month, general, diurnal in itertools.product(BRANCHES, BRANCHES, [True, False]):
        key = [month, general, diurnal]
        board = build_liureng_board(
            seed_for("甲子", month),
            month_general_override=general,
            guiren_profile="tanyuan_xieji_v1",
            is_diurnal_override=diurnal,
        )
        boards.append(dict(key=key, board=board))
        counts["boards"] += 1
        evidence = board["seasonal_evidence"]
        season = ref["declared_month_partition"][month]
        table = ref["literal_phase_table"][season]
        check("season_partition", key, evidence["season_partition"], season)
        check("phase_powers", key, evidence["phase_powers"], table)
        check(
            "row_order",
            key,
            [r["earth_branch"] for r in evidence["rows"]],
            list(BRANCHES),
        )
        for row in evidence["rows"]:
            counts["rows"] += 1
            # The input hour is symbolically 子; month general rotation is explicit.
            expected_sky = BRANCHES[
                (BRANCHES.index(row["earth_branch"]) + BRANCHES.index(general)) % 12
            ]
            check(
                "sky_rotation",
                [key, row["earth_branch"]],
                row["sky_branch"],
                expected_sky,
            )
            for layer, phase_field, power_field, expected_phase in [
                (
                    "sky",
                    "sky_element",
                    "sky_seasonal_power",
                    ref["branch_elements"][expected_sky],
                ),
                (
                    "god",
                    "god_element",
                    "god_seasonal_power",
                    ref["literal_god_elements"][row["god"]],
                ),
                (
                    "earth",
                    "earth_element",
                    "earth_seasonal_power",
                    ref["branch_elements"][row["earth_branch"]],
                ),
            ]:
                counts["objects"] += 1
                subject = [key, row["earth_branch"], layer]
                check("object_phase", subject, row[phase_field], expected_phase)
                check("object_power", subject, row[power_field], table[expected_phase])
                for group in source["course_groups"]:
                    counts["board_course_components"] += 1
                    check(
                        "board_component",
                        [subject, group["id"]],
                        row[power_field] in group["same_power_category"],
                        expected_phase in group["phases"][season],
                    )
    return (
        dict(
            counts=counts,
            failures=failures,
            ledger_sha256=ledger.hexdigest(),
            components_passed=not failures,
            source_variant=source["source_variant"],
            full_named_predicate_adjudicated=False,
            last18days_profile_certified=False,
            independent_expert_review=False,
        ),
        boards,
    )


def audit_sparse() -> dict[str, Any]:
    ref = fidelity_reference()
    from fatebridge.core.output_liuren_seasonal import LiurenSeasonalEvidence

    counts = dict(
        valid=0,
        invalid=0,
        valid_rejected=0,
        invalid_accepted=0,
        metadata_faults=0,
        metadata_faults_accepted=0,
    )
    failures = []
    for day in ref["days"]:
        phase = ref["stem_elements"][day[0]]
        contexts = [
            (dict(month_branch=month), season)
            for month, season in ref["declared_month_partition"].items()
        ]
        contexts += [
            (dict(season_partition=season), season)
            for season in ref["literal_phase_table"]
        ]
        contexts += [
            (dict(phase_powers=table), season)
            for season, table in ref["literal_phase_table"].items()
        ]
        for context, season in contexts:
            expected = ref["literal_phase_table"][season][phase]
            for power in ["旺", "相", "休", "囚", "死"]:
                payload = dict(day_ganzhi=day, day_stem_seasonal_power=power, **context)
                valid = power == expected
                counts["valid" if valid else "invalid"] += 1
                try:
                    LiurenSeasonalEvidence.model_validate(payload)
                except ValueError:
                    accepted = False
                else:
                    accepted = True
                if accepted != valid:
                    counts["valid_rejected" if valid else "invalid_accepted"] += 1
                    failures.append(
                        dict(input=payload, expected_power=expected, accepted=accepted)
                    )
    for field, wrong in ref["invalid_metadata_values"].items():
        counts["metadata_faults"] += 1
        try:
            LiurenSeasonalEvidence.model_validate({field: wrong})
        except ValueError:
            accepted = False
        else:
            accepted = True
        if accepted:
            counts["metadata_faults_accepted"] += 1
            failures.append(dict(input={field: wrong}, accepted=True))
    return dict(
        counts=counts,
        failures=failures,
        sparse_checks_passed=not failures,
        reference_kind=ref["metadata_reference_kind"],
    )


def audit() -> dict[str, Any]:
    outline, _ = audit_outline()
    sparse = audit_sparse()
    return dict(
        outline=outline,
        sparse=sparse,
        audit_passed=outline["components_passed"] and sparse["sparse_checks_passed"],
        complete_classical_conformance=False,
        calendar_accuracy_certified=False,
        new_model_processes=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-full-conformance", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing audit evidence")
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "audit_passed",
                    "complete_classical_conformance",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if result["audit_passed"] and not args.require_full_conformance else 1


if __name__ == "__main__":
    raise SystemExit(main())
