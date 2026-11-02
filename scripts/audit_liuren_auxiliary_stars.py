"""Keep literal 德禄马 labels separate from synthetic board expansions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_auxiliary_stars_v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
GODS = "贵人 螣蛇 朱雀 六合 勾陈 青龙 天空 白虎 太常 玄武 太阴 天后".split()
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/liureng_auxiliary_stars.py",
    "src/fatebridge/core/metaphysics/liureng_life_stages.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_liuren_auxiliary.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/data/agent_examples.json",
    "scripts/audit_liuren_auxiliary_stars.py",
)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen auxiliary-star inventory changed")
    for name, value in manifest["files"].items():
        if sha(corpus / name) != value:
            raise ValueError(f"Frozen auxiliary-star source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    for folder, key in (
        ("liuren_life_stages_v1", "reused_life_stage_freeze_sha256"),
        ("ren_calendar_pmo_v1", "pmo_freeze_sha256"),
    ):
        if sha(ROOT / "tests/fixtures" / folder / "freeze.json") != result[key]:
            raise ValueError(f"Reused frozen reference changed: {folder}")
    return result


def expected_token(ref: dict[str, Any], star_id: str, day: str, month: str) -> str:
    key = (
        day[0]
        if star_id in {"day_de", "day_lu"}
        else day[1] if star_id in {"branch_de", "day_horse"} else month
    )
    return str(ref["tables"][star_id][key])


def audit() -> dict[str, Any]:
    ref = reference()
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.liureng_auxiliary_stars import (
        build_auxiliary_stars,
    )
    from fatebridge.services.metaphysics import calculate_liureng_gods

    cycle = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]
    god_map = dict(zip(BRANCHES, GODS))
    literal: dict[tuple[str, str], dict[str, Any]] = {}
    failures = []
    contexts = positions = matches = 0
    # These are synthetic rotations, not new classical examples. Expectations
    # use frozen literal tokens and the inverse of the declared rotation.
    for day_index, day in enumerate(cycle):
        head = day_index // 10 * 10
        dun = {cycle[i][1]: cycle[i][0] for i in range(head, head + 10)}
        for offset in range(12):
            plate = {b: BRANCHES[(i + offset) % 12] for i, b in enumerate(BRANCHES)}
            uppers = [BRANCHES[(offset + i * 3) % 12] for i in range(4)]
            lessons = [dict(index=i + 1, upper_branch=b) for i, b in enumerate(uppers)]
            transmissions = [BRANCHES[(offset + i * 4) % 12] for i in range(3)]
            for month in "寅卯辰巳午未申酉戌亥子丑":
                actual = build_auxiliary_stars(
                    day_ganzhi=day,
                    month_branch=month,
                    sky_by_earth=plate,
                    god_by_sky=god_map,
                    lessons=lessons,
                    transmissions=transmissions,
                )
                contexts += 1
                expected_ids = set(ref["tables"])
                if (
                    len(actual["stars"]) != len(expected_ids)
                    or {s["id"] for s in actual["stars"]} != expected_ids
                ):
                    failures.append(
                        dict(
                            day=day,
                            month=month,
                            offset=offset,
                            reason="seven-rule inventory changed",
                        )
                    )
                for star in actual["stars"]:
                    star_id = star["id"]
                    token = expected_token(ref, star_id, day, month)
                    branch = token[-1]
                    earth = BRANCHES[(BRANCHES.index(branch) - offset) % 12]
                    expected = dict(
                        source_token=token,
                        branch=branch,
                        earth_branch=earth,
                        god=god_map[branch],
                        dun_stem=dun.get(branch),
                        ganzhi=dun[branch] + branch if branch in dun else None,
                        xun_kong=branch not in dun,
                        seated_kong=earth not in dun,
                        lesson_indices=[
                            i + 1 for i, b in enumerate(uppers) if b == branch
                        ],
                        transmission_positions=[
                            p
                            for p, b in zip(
                                ("initial", "middle", "final"), transmissions
                            )
                            if b == branch
                        ],
                        on_day_stem=uppers[0] == branch,
                        on_day_branch=uppers[2] == branch,
                        original_pdf_pages=ref["source_pages"][star_id],
                    )
                    matched = all(star[k] == v for k, v in expected.items())
                    positions += 1
                    matches += matched
                    if not matched:
                        failures.append(
                            dict(
                                day=day,
                                month=month,
                                offset=offset,
                                id=star_id,
                                expected=expected,
                                actual=star,
                            )
                        )
                    key = (
                        day[0]
                        if star_id in {"day_de", "day_lu"}
                        else day[1] if star_id in {"branch_de", "day_horse"} else month
                    )
                    literal_key = (star_id, key)
                    if literal_key not in literal:
                        literal[literal_key] = dict(
                            id=star_id,
                            key=key,
                            expected=token,
                            actual=star["source_token"],
                            matched=star["source_token"] == token,
                        )
                if actual["complete_classical_conformance"] is not False:
                    failures.append(
                        dict(day=day, month=month, reason="overclaimed conformance")
                    )
    civil = []
    for probe in ref["civil_probes"]:
        result = calculate_liureng_gods(
            **{f"analysis_{k}": probe[k] for k in ("year", "month", "day", "hour")},
            analysis_timezone="Asia/Shanghai",
            use_true_solar_time=False,
        )
        aux = result["liureng"]["auxiliary_stars"]
        lunar = result["calendar_context"]["lunar_calendar"]
        matched = (
            aux["month_building_branch"] == probe["expected_month_branch"]
            and aux["nominal_month"] == probe["expected_month_number"]
            and lunar["year"] == probe["expected_lunar_year"]
            and lunar["month"] == probe["expected_lunar_month"]
        )
        civil.append(
            dict(
                probe=probe,
                month_building_branch=aux["month_building_branch"],
                nominal_month=aux["nominal_month"],
                lunar_year=lunar["year"],
                lunar_month=lunar["month"],
                matched=matched,
            )
        )
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    literal_rows = list(literal.values())
    return dict(
        audit_id="liuren_auxiliary_stars_v1",
        literal_table_entries=len(literal_rows),
        reused_lu_entries=10,
        literal_anchor_checks=literal_rows,
        literal_anchor_match_count=sum(r["matched"] for r in literal_rows),
        synthetic_contexts=contexts,
        derived_position_checks=positions,
        derived_position_match_count=matches,
        civil_probes=civil,
        failures=failures,
        source_sha256=ref["source_sha256"],
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=before,
        implementation_unchanged_during_audit=unchanged,
        selected_excerpt_checks_passed=unchanged
        and not failures
        and len(literal_rows) == 80
        and contexts == 8640
        and positions == 60480
        and all(r["matched"] for r in literal_rows + civil),
        classical_acceptance_passed=False,
        goal_complete=False,
        new_real_world_outcomes=0,
        new_historical_examples=0,
        model_invocations=0,
        limits=ref["limitations"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "literal_anchor_match_count",
                    "synthetic_contexts",
                    "derived_position_match_count",
                    "selected_excerpt_checks_passed",
                )
            }
        )
    )
    return 0 if result["selected_excerpt_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
