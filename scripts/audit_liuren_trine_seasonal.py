"""Audit nominal trine seasonal facts against frozen literal anchors."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_trine_seasonal_v1"
PIN = "80a5f4f9c7ef881a08dae8b7434b995ec760c8421f4fe34e6ccbb3abc845d14a"
BOARD_PIN = "82a7d7e7f76cf8a64da2f7080904a4c9308f5e502d8382015a16b7ba8dd315c1"
BUSINESS_PIN = "37a3b2d074fe0ba35cb6ffdb7f19640e9955f74cc69a606957f986817c493669"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
FIELD = "nominal_seasonal_evidence"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen nominal trine manifest identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest) != {
        "reference.json",
        "protocol.json",
        "gugong-158.png",
        "gugong-159.png",
        "tanyuan-113.jpg",
    } or {p.name for p in folder.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen nominal trine inventory changed")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Frozen nominal trine source changed")
    value: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/liuren_seasonal_v1/freeze.json")
        != value["old_seasonal_freeze_sha256"]
    ):
        raise ValueError("Original seasonal table identity changed")
    return value


def context(branches: list[str]) -> dict[str, Any]:
    return dict(
        day_ganzhi="甲子",
        lessons=[dict(index=i + 1, upper_branch=branches[i % 3]) for i in range(4)],
        transmissions={
            p: dict(branch=b, god="贵人", earth_branch="子")
            for p, b in zip(["initial", "middle", "final"], branches, strict=True)
        },
    )


def audit() -> dict[str, Any]:
    ref = reference()
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.liureng_transmission_relations import (
        transmission_relations,
    )
    from scripts.audit_liuren_seasonal import seed_for

    failures: list[dict[str, Any]] = []
    triples = 0
    slots = 0
    complete = 0
    for symbols in itertools.product(BRANCHES, repeat=3):
        branches = list(symbols)
        ctx = context(branches)
        legacy = transmission_relations(**ctx)
        if any(FIELD in t for t in legacy["trines"]):
            failures.append(dict(kind="missing_month_old_shape", branches=branches))
        for month, season in ref["month_partition"].items():
            got = transmission_relations(**ctx, month_branch=month)
            restored = copy.deepcopy(got)
            for row in restored["trines"]:
                row.pop(FIELD)
            if restored != legacy:
                failures.append(
                    dict(kind="old_direct_values", branches=branches, month=month)
                )
            triples += 1
            for row, anchor in zip(got["trines"], ref["trines"], strict=True):
                slots += 1
                expected_complete = set(branches) == set(anchor["branches"])
                e = row[FIELD]
                if not expected_complete:
                    if e is not None:
                        failures.append(
                            dict(
                                kind="incomplete_has_evidence",
                                branches=branches,
                                month=month,
                            )
                        )
                    continue
                complete += 1
                power = ref["phase_powers"][season][anchor["element"]]
                expected = dict(
                    month_branch=month,
                    season_partition=season,
                    nominal_element=anchor["element"],
                    nominal_power=power,
                    course_component=ref["power_to_component"][power],
                    full_named_course_adjudicated=False,
                    transformation_confirmed=None,
                )
                if not isinstance(e, dict) or any(
                    type(e.get(k)) is not type(v) or e.get(k) != v
                    for k, v in expected.items()
                ):
                    failures.append(
                        dict(
                            kind="nominal_power",
                            branches=branches,
                            month=month,
                            actual=e,
                            expected=expected,
                        )
                    )
    case = ref["primary_example"]
    board = build_liureng_board(
        seed_for(case["source_day"], case["engine_representative_month_branch"]),
        month_general_override="辰",
        guiren_profile="tanyuan_xieji_v1",
        is_diurnal_override=True,
    )
    actual_branches = [
        board["three_transmissions"][p]["branch"]
        for p in ["initial", "middle", "final"]
    ]
    nominal = next(
        t for t in board["transmission_relations"]["trines"] if t["branches_complete"]
    )[FIELD]
    raw_by_branch = {r["sky_branch"]: r for r in board["seasonal_evidence"]["rows"]}
    raw = [raw_by_branch[b] for b in actual_branches]
    source_match = (
        actual_branches == case["transmissions"]
        and nominal["nominal_element"] == case["nominal_element"]
        and nominal["nominal_power"] == case["nominal_power"]
        and nominal["course_component"] == case["nominal_course_component"]
        and [r["sky_element"] for r in raw] == case["raw_branch_elements"]
        and [r["sky_seasonal_power"] for r in raw] == case["raw_branch_powers"]
    )
    if not source_match:
        failures.append(dict(kind="literal_primary_component"))
    return dict(
        reference_pin=PIN,
        counts=dict(
            ordered_triples_per_month=triples,
            trine_slots=slots,
            complete_nominal_evidence=complete,
            source_example_components=1,
        ),
        source_example=dict(
            id=case["id"],
            branches=actual_branches,
            raw_powers=[r["sky_seasonal_power"] for r in raw],
            nominal_power=nominal["nominal_power"],
            course_component=nominal["course_component"],
            matched=source_match,
            representative_month_not_original_date=True,
        ),
        failures=failures,
        selected_component_checks_passed=not failures,
        full_named_course_adjudicated=False,
        full_classical_conformance=False,
        new_independent_events=0,
        new_model_processes=0,
        goal_complete=False,
    )


def strip_additions(value: Any, path: tuple[str, ...] = ()) -> tuple[Any, list[str]]:
    if isinstance(value, dict):
        out = {}
        paths = []
        for key, item in value.items():
            if key == FIELD:
                if len(path) < 2 or path[-2] != "trines" or not path[-1].isdigit():
                    raise ValueError("Unexpected field outside declared trine path")
                paths.append(".".join(path + (key,)))
                continue
            cleaned, added = strip_additions(item, path + (key,))
            out[key] = cleaned
            paths.extend(added)
        return out, paths
    if isinstance(value, list):
        out_list = []
        paths = []
        for i, item in enumerate(value):
            cleaned, added = strip_additions(item, path + (str(i),))
            out_list.append(cleaned)
            paths.extend(added)
        return out_list, paths
    return value, []


def compare_baselines(run: Path) -> dict[str, Any]:
    reference()
    if (
        sha(run / "before-boards.jsonl.gz") != BOARD_PIN
        or sha(run / "before-business.json.gz") != BUSINESS_PIN
    ):
        raise ValueError("Original numerical baseline changed")
    from fatebridge.application.execution import validate_output
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.services.tool_catalog import CATALOG
    from scripts.audit_liuren_seasonal import seed_for

    compared = 0
    failures = []
    field_count = 0
    with gzip.open(run / "before-boards.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            old = json.loads(line)
            assert not any(
                FIELD in t for t in old["board"]["transmission_relations"]["trines"]
            )
            new = build_liureng_board(
                seed_for(old["day"], "寅"),
                month_general_override=old["general"],
                guiren_profile="tanyuan_xieji_v1",
                is_diurnal_override=True,
            )
            restored, paths = strip_additions(new)
            compared += 1
            field_count += len(paths)
            if restored != old["board"]:
                failures.append(
                    dict(kind="board", day=old["day"], general=old["general"])
                )
    business_rows = []
    for row in json.loads(
        gzip.decompress((run / "before-business.json.gz").read_bytes())
    ):
        spec = next(s for s in CATALOG if s.key == row["key"])
        fn, args, kwargs = spec.bind(spec.request_model.model_validate(row["payload"]))
        new = fn(*args, **kwargs)
        validate_output(spec, new)
        restored, paths = strip_additions(new)
        equal = restored == row["business"]
        business_rows.append(
            dict(
                key=row["key"],
                equal_after_only_declared_additions_removed=equal,
                addition_paths=paths,
            )
        )
        if not equal:
            failures.append(dict(kind="business", key=row["key"]))
    return dict(
        boards_compared=compared,
        declared_board_additions=field_count,
        businesses=business_rows,
        failures=failures,
        legacy_values_restored=not failures,
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--compare-baselines", type=Path)
    args = p.parse_args()
    value = audit()
    if args.compare_baselines:
        value["baseline_comparison"] = compare_baselines(args.compare_baselines)
        value["selected_component_checks_passed"] &= value["baseline_comparison"][
            "legacy_values_restored"
        ]
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in value.items()
                if k not in ["failures", "baseline_comparison"]
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if value["selected_component_checks_passed"] else 1)


if __name__ == "__main__":
    main()
